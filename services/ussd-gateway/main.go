/*
ussd-gateway — 54agent USSD Transaction Fallback Gateway

Enables POS transactions via USSD (text-only) for 2G/no-data environments.
Agents can process cash-in, cash-out, transfers, and airtime via simple menu codes.

HTTP API (port 8061):

	POST /api/ussd/session     — start or continue a USSD session
	GET  /api/ussd/sessions    — list active sessions
	POST /api/ussd/callback    — carrier callback endpoint (Africa's Talking, Flutterwave)
	GET  /api/ussd/stats       — session stats, completion rates
	GET  /api/health           — liveness check

USSD Flow:

	*347*54# → Main Menu → 1.CashIn 2.CashOut 3.Transfer 4.Airtime 5.Balance 6.MiniStatement
	Each selection → amount → confirm → receipt via SMS

Backend integration (REQUIRED — this gateway never fabricates financial data):

	LEDGER_API_URL       — wallet/ledger API for balances and mini statements
	TRANSACTION_API_URL  — transaction engine for execution (real references)
	AUTH_API_URL         — auth service for PIN verification
*/
package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net/http"
	"net/url"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"

	"github.com/google/uuid"
)

// ── USSD Session State Machine ───────────────────────────────────────────────

type SessionState string

const (
	StateMainMenu       SessionState = "main_menu"
	StateEnterAmount    SessionState = "enter_amount"
	StateEnterRecipient SessionState = "enter_recipient"
	StateEnterPIN       SessionState = "enter_pin"
	StateConfirm        SessionState = "confirm"
	StateComplete       SessionState = "complete"
	StateTimeout        SessionState = "timeout"
	StateCancelled      SessionState = "cancelled"
)

type TransactionType string

const (
	TxCashIn   TransactionType = "cash_in"
	TxCashOut  TransactionType = "cash_out"
	TxTransfer TransactionType = "transfer"
	TxAirtime  TransactionType = "airtime"
	TxBalance  TransactionType = "balance"
	TxMiniStmt TransactionType = "mini_statement"
)

type USSDSession struct {
	ID             string          `json:"id"`
	PhoneNumber    string          `json:"phoneNumber"`
	AgentCode      string          `json:"agentCode"`
	ServiceCode    string          `json:"serviceCode"`
	State          SessionState    `json:"state"`
	TxType         TransactionType `json:"txType,omitempty"`
	Amount         float64         `json:"amount,omitempty"`
	Recipient      string          `json:"recipient,omitempty"`
	PIN            string          `json:"-"`
	TransactionRef string          `json:"transactionRef,omitempty"`
	CreatedAt      time.Time       `json:"createdAt"`
	UpdatedAt      time.Time       `json:"updatedAt"`
	ExpiresAt      time.Time       `json:"expiresAt"`
	StepHistory    []string        `json:"stepHistory"`
	Carrier        string          `json:"carrier,omitempty"`
	NetworkType    string          `json:"networkType,omitempty"` // 2G, 3G, etc.
}

// ── Backend Service Clients ──────────────────────────────────────────────────
//
// All balances, statements, PIN verification and transaction execution are
// delegated to real backend services. This gateway NEVER fabricates financial
// data and only reports success with a real backend-issued reference.

var (
	ledgerAPIURL = strings.TrimRight(os.Getenv("LEDGER_API_URL"), "/")
	txAPIURL     = strings.TrimRight(os.Getenv("TRANSACTION_API_URL"), "/")
	authAPIURL   = strings.TrimRight(os.Getenv("AUTH_API_URL"), "/")
	backendHTTP  = &http.Client{Timeout: 8 * time.Second}
)

// BalanceInfo is the real balance snapshot returned by the ledger/wallet API.
type BalanceInfo struct {
	Balance    float64 `json:"balance"`
	Float      float64 `json:"float"`
	Commission float64 `json:"commission"`
	Currency   string  `json:"currency"`
}

func fetchBalance(phone string) (*BalanceInfo, error) {
	if ledgerAPIURL == "" {
		return nil, errors.New("LEDGER_API_URL not configured")
	}
	resp, err := backendHTTP.Get(fmt.Sprintf("%s/api/v1/agents/balance?phone=%s", ledgerAPIURL, url.QueryEscape(phone)))
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("ledger API returned status %d", resp.StatusCode)
	}
	var info BalanceInfo
	if err := json.NewDecoder(resp.Body).Decode(&info); err != nil {
		return nil, err
	}
	if info.Currency == "" {
		info.Currency = "NGN"
	}
	return &info, nil
}

// StatementEntry is a single real transaction line from the ledger API.
type StatementEntry struct {
	Date        string  `json:"date"`
	Type        string  `json:"type"`
	Amount      float64 `json:"amount"`
	Currency    string  `json:"currency"`
	Description string  `json:"description"`
}

func fetchMiniStatement(phone string) ([]StatementEntry, error) {
	if ledgerAPIURL == "" {
		return nil, errors.New("LEDGER_API_URL not configured")
	}
	resp, err := backendHTTP.Get(fmt.Sprintf("%s/api/v1/agents/mini-statement?phone=%s&limit=5", ledgerAPIURL, url.QueryEscape(phone)))
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("ledger API returned status %d", resp.StatusCode)
	}
	var body struct {
		Transactions []StatementEntry `json:"transactions"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&body); err != nil {
		return nil, err
	}
	return body.Transactions, nil
}

// verifyAgentPIN verifies the collected PIN against the auth service.
func verifyAgentPIN(phone, pin string) error {
	if authAPIURL == "" {
		return errors.New("AUTH_API_URL not configured")
	}
	payload, _ := json.Marshal(map[string]string{"phone": phone, "pin": pin})
	resp, err := backendHTTP.Post(authAPIURL+"/api/v1/auth/verify-pin", "application/json", bytes.NewReader(payload))
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("auth service returned status %d", resp.StatusCode)
	}
	var result struct {
		Valid bool `json:"valid"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return err
	}
	if !result.Valid {
		return errors.New("invalid PIN")
	}
	return nil
}

// ExecutionResult is the real outcome returned by the transaction engine.
type ExecutionResult struct {
	Reference  string  `json:"reference"`
	Status     string  `json:"status"`
	Fee        float64 `json:"fee"`
	Commission float64 `json:"commission"`
	Error      string  `json:"error"`
}

// executeTransaction posts the confirmed transaction to the transaction engine.
// The USSD session ID is used as the idempotency key so carrier retries can
// never double-execute a money movement.
func executeTransaction(s *USSDSession) (*ExecutionResult, error) {
	if txAPIURL == "" {
		return nil, errors.New("TRANSACTION_API_URL not configured")
	}
	payload, _ := json.Marshal(map[string]interface{}{
		"type":       string(s.TxType),
		"amount":     s.Amount,
		"agentPhone": s.PhoneNumber,
		"recipient":  s.Recipient,
		"channel":    "ussd",
	})
	req, err := http.NewRequest(http.MethodPost, txAPIURL+"/api/v1/transactions", bytes.NewReader(payload))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Idempotency-Key", s.ID)
	resp, err := backendHTTP.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	var result ExecutionResult
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("transaction engine returned unreadable response (status %d)", resp.StatusCode)
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 || result.Reference == "" {
		if result.Error != "" {
			return nil, errors.New(result.Error)
		}
		return nil, fmt.Errorf("transaction engine returned status %d without a reference", resp.StatusCode)
	}
	return &result, nil
}

// ── Session Store ────────────────────────────────────────────────────────────

type SessionStore struct {
	mu       sync.RWMutex
	sessions map[string]*USSDSession
	stats    USSDStats
}

type USSDStats struct {
	TotalSessions        int64            `json:"totalSessions"`
	ActiveSessions       int64            `json:"activeSessions"`
	CompletedSessions    int64            `json:"completedSessions"`
	TimedOutSessions     int64            `json:"timedOutSessions"`
	CancelledSessions    int64            `json:"cancelledSessions"`
	TxByType             map[string]int64 `json:"txByType"`
	AvgSessionDurationMs int64            `json:"avgSessionDurationMs"`
	TotalAmountProcessed float64          `json:"totalAmountProcessed"`
}

func NewSessionStore() *SessionStore {
	return &SessionStore{
		sessions: make(map[string]*USSDSession),
		stats: USSDStats{
			TxByType: make(map[string]int64),
		},
	}
}

func (ss *SessionStore) GetOrCreate(sessionID, phoneNumber, serviceCode string) *USSDSession {
	ss.mu.Lock()
	defer ss.mu.Unlock()

	if s, ok := ss.sessions[sessionID]; ok {
		return s
	}

	s := &USSDSession{
		ID:          sessionID,
		PhoneNumber: phoneNumber,
		ServiceCode: serviceCode,
		State:       StateMainMenu,
		CreatedAt:   time.Now(),
		UpdatedAt:   time.Now(),
		ExpiresAt:   time.Now().Add(3 * time.Minute), // USSD sessions timeout after 3 min
		StepHistory: []string{},
	}
	ss.sessions[sessionID] = s
	ss.stats.TotalSessions++
	ss.stats.ActiveSessions++
	return s
}

func (ss *SessionStore) Complete(sessionID string, txRef string, amount float64, txType TransactionType) {
	ss.mu.Lock()
	defer ss.mu.Unlock()
	if s, ok := ss.sessions[sessionID]; ok {
		s.State = StateComplete
		s.TransactionRef = txRef
		s.UpdatedAt = time.Now()
		ss.stats.CompletedSessions++
		ss.stats.ActiveSessions--
		ss.stats.TxByType[string(txType)]++
		ss.stats.TotalAmountProcessed += amount
		duration := time.Since(s.CreatedAt).Milliseconds()
		if ss.stats.CompletedSessions > 0 {
			ss.stats.AvgSessionDurationMs = (ss.stats.AvgSessionDurationMs*(ss.stats.CompletedSessions-1) + duration) / ss.stats.CompletedSessions
		}
	}
}

func (ss *SessionStore) GetStats() USSDStats {
	ss.mu.RLock()
	defer ss.mu.RUnlock()
	return ss.stats
}

func (ss *SessionStore) GetActiveSessions() []*USSDSession {
	ss.mu.RLock()
	defer ss.mu.RUnlock()
	active := make([]*USSDSession, 0)
	for _, s := range ss.sessions {
		if s.State != StateComplete && s.State != StateTimeout && s.State != StateCancelled {
			active = append(active, s)
		}
	}
	return active
}

// cleanup removes expired sessions (alias for CleanExpired)
func (ss *SessionStore) CleanExpired() int {
	ss.mu.Lock()
	defer ss.mu.Unlock()
	cleaned := 0
	for id, s := range ss.sessions {
		if time.Now().After(s.ExpiresAt) && s.State != StateComplete {
			s.State = StateTimeout
			ss.stats.TimedOutSessions++
			ss.stats.ActiveSessions--
			delete(ss.sessions, id)
			cleaned++
		}
	}
	return cleaned
}

// ── USSD Response Builder ────────────────────────────────────────────────────

type USSDResponse struct {
	Text      string `json:"text"`
	Action    string `json:"action"` // "CON" (continue) or "END" (terminate)
	SessionID string `json:"sessionId"`
}

func continueResponse(sessionID, text string) USSDResponse {
	return USSDResponse{Text: text, Action: "CON", SessionID: sessionID}
}

func endResponse(sessionID, text string) USSDResponse {
	return USSDResponse{Text: text, Action: "END", SessionID: sessionID}
}

// ── USSD State Machine ──────────────────────────────────────────────────────

func processUSSD(store *SessionStore, sessionID, phoneNumber, serviceCode, input string) USSDResponse {
	session := store.GetOrCreate(sessionID, phoneNumber, serviceCode)

	// Check timeout
	if time.Now().After(session.ExpiresAt) {
		return endResponse(sessionID, "Session expired. Please dial again.")
	}

	session.UpdatedAt = time.Now()
	session.StepHistory = append(session.StepHistory, input)

	switch session.State {
	case StateMainMenu:
		return handleMainMenu(store, session, input)
	case StateEnterAmount:
		return handleEnterAmount(session, input)
	case StateEnterRecipient:
		return handleEnterRecipient(session, input)
	case StateEnterPIN:
		return handleEnterPIN(store, session, input)
	case StateConfirm:
		return handleConfirm(store, session, input)
	default:
		return endResponse(sessionID, "Invalid session state. Please dial again.")
	}
}

func handleMainMenu(store *SessionStore, s *USSDSession, input string) USSDResponse {
	if input == "" {
		return continueResponse(s.ID,
			"Welcome to 54agent POS\n"+
				"1. Cash In\n"+
				"2. Cash Out\n"+
				"3. Transfer\n"+
				"4. Buy Airtime\n"+
				"5. Check Balance\n"+
				"6. Mini Statement")
	}

	switch input {
	case "1":
		s.TxType = TxCashIn
		s.State = StateEnterAmount
		return continueResponse(s.ID, "Cash In\nEnter amount (NGN):")
	case "2":
		s.TxType = TxCashOut
		s.State = StateEnterAmount
		return continueResponse(s.ID, "Cash Out\nEnter amount (NGN):")
	case "3":
		s.TxType = TxTransfer
		s.State = StateEnterRecipient
		return continueResponse(s.ID, "Transfer\nEnter recipient phone number:")
	case "4":
		s.TxType = TxAirtime
		s.State = StateEnterRecipient
		return continueResponse(s.ID, "Buy Airtime\nEnter phone number:")
	case "5":
		s.TxType = TxBalance
		info, err := fetchBalance(s.PhoneNumber)
		if err != nil {
			log.Printf("[USSD] balance lookup failed (session=%s): %v", s.ID, err)
			s.State = StateCancelled
			return endResponse(s.ID, "Balance service unavailable. Please try again later.")
		}
		txRef := fmt.Sprintf("BAL-%s", uuid.New().String()[:8])
		store.Complete(s.ID, txRef, 0, TxBalance)
		return endResponse(s.ID, fmt.Sprintf(
			"Balance: %s %s\nFloat: %s %s\nCommission Today: %s %s",
			info.Currency, formatAmount(info.Balance),
			info.Currency, formatAmount(info.Float),
			info.Currency, formatAmount(info.Commission)))
	case "6":
		s.TxType = TxMiniStmt
		entries, err := fetchMiniStatement(s.PhoneNumber)
		if err != nil {
			log.Printf("[USSD] mini statement lookup failed (session=%s): %v", s.ID, err)
			s.State = StateCancelled
			return endResponse(s.ID, "Statement service unavailable. Please try again later.")
		}
		txRef := fmt.Sprintf("STMT-%s", uuid.New().String()[:8])
		store.Complete(s.ID, txRef, 0, TxMiniStmt)
		if len(entries) == 0 {
			return endResponse(s.ID, "No recent transactions.")
		}
		var sb strings.Builder
		sb.WriteString("Last Transactions:\n")
		for i, e := range entries {
			if i >= 5 {
				break
			}
			label := e.Description
			if label == "" {
				label = txTypeLabel(TransactionType(e.Type))
			}
			currency := e.Currency
			if currency == "" {
				currency = "NGN"
			}
			fmt.Fprintf(&sb, "%d. %s %s %s\n", i+1, label, currency, formatAmount(e.Amount))
		}
		return endResponse(s.ID, strings.TrimRight(sb.String(), "\n"))
	default:
		return continueResponse(s.ID, "Invalid option. Please select 1-6:")
	}
}

func handleEnterAmount(s *USSDSession, input string) USSDResponse {
	amount, err := strconv.ParseFloat(input, 64)
	if err != nil || amount <= 0 {
		return continueResponse(s.ID, "Invalid amount. Enter a valid number:")
	}
	if amount < 100 {
		return continueResponse(s.ID, "Minimum amount is NGN 100. Enter amount:")
	}
	if amount > 1000000 {
		return continueResponse(s.ID, "Maximum amount is NGN 1,000,000. Enter amount:")
	}

	s.Amount = amount
	s.State = StateEnterPIN
	return continueResponse(s.ID, fmt.Sprintf(
		"%s NGN %s\nEnter your 4-digit PIN:", txTypeLabel(s.TxType), formatAmount(amount)))
}

func handleEnterRecipient(s *USSDSession, input string) USSDResponse {
	// Validate phone number (Nigerian format)
	cleaned := strings.ReplaceAll(input, " ", "")
	if len(cleaned) < 10 || len(cleaned) > 15 {
		return continueResponse(s.ID, "Invalid phone number. Enter 10-15 digits:")
	}
	s.Recipient = cleaned
	s.State = StateEnterAmount
	return continueResponse(s.ID, fmt.Sprintf("Recipient: %s\nEnter amount (NGN):", cleaned))
}

func handleEnterPIN(store *SessionStore, s *USSDSession, input string) USSDResponse {
	if len(input) != 4 {
		return continueResponse(s.ID, "PIN must be 4 digits. Try again:")
	}
	s.PIN = input
	s.State = StateConfirm

	confirmText := fmt.Sprintf(
		"Confirm %s\nAmount: NGN %s",
		txTypeLabel(s.TxType), formatAmount(s.Amount))
	if s.Recipient != "" {
		confirmText += fmt.Sprintf("\nTo: %s", s.Recipient)
	}
	fee := calculateFee(s.TxType, s.Amount)
	if fee > 0 {
		confirmText += fmt.Sprintf("\nFee: NGN %s", formatAmount(fee))
		confirmText += fmt.Sprintf("\nTotal: NGN %s", formatAmount(s.Amount+fee))
	}
	confirmText += "\n\n1. Confirm\n2. Cancel"
	return continueResponse(s.ID, confirmText)
}

func handleConfirm(store *SessionStore, s *USSDSession, input string) USSDResponse {
	switch input {
	case "1":
		// Verify PIN against the auth service before any money movement.
		if err := verifyAgentPIN(s.PhoneNumber, s.PIN); err != nil {
			log.Printf("[USSD] PIN verification failed (session=%s): %v", s.ID, err)
			s.State = StateCancelled
			return endResponse(s.ID, "Transaction rejected: PIN verification failed.")
		}

		// Execute against the transaction engine — only a real backend
		// reference may be shown to the customer as a confirmation.
		result, err := executeTransaction(s)
		if err != nil {
			log.Printf("[USSD] transaction execution failed (session=%s, type=%s, amount=%.2f): %v",
				s.ID, s.TxType, s.Amount, err)
			s.State = StateCancelled
			return endResponse(s.ID, fmt.Sprintf(
				"%s could not be completed. No funds were moved. Please try again later.",
				txTypeLabel(s.TxType)))
		}

		store.Complete(s.ID, result.Reference, s.Amount, s.TxType)

		if s.Recipient != "" {
			return endResponse(s.ID, fmt.Sprintf(
				"%s Successful!\nTo: %s\nAmount: NGN %s\nFee: NGN %s\nRef: %s\nTime: %s",
				txTypeLabel(s.TxType), s.Recipient,
				formatAmount(s.Amount), formatAmount(result.Fee), result.Reference,
				time.Now().Format("15:04 02/01/2006")))
		}
		return endResponse(s.ID, fmt.Sprintf(
			"%s Successful!\nAmount: NGN %s\nFee: NGN %s\nCommission: NGN %s\nRef: %s\nTime: %s",
			txTypeLabel(s.TxType),
			formatAmount(s.Amount),
			formatAmount(result.Fee),
			formatAmount(result.Commission),
			result.Reference,
			time.Now().Format("15:04 02/01/2006")))
	case "2":
		s.State = StateCancelled
		return endResponse(s.ID, "Transaction cancelled.")
	default:
		return continueResponse(s.ID, "Press 1 to Confirm or 2 to Cancel:")
	}
}

// ── Helpers ──────────────────────────────────────────────────────────────────

func txTypeLabel(t TransactionType) string {
	switch t {
	case TxCashIn:
		return "Cash In"
	case TxCashOut:
		return "Cash Out"
	case TxTransfer:
		return "Transfer"
	case TxAirtime:
		return "Airtime"
	case TxBalance:
		return "Balance"
	case TxMiniStmt:
		return "Mini Statement"
	default:
		return string(t)
	}
}

func formatAmount(amount float64) string {
	return fmt.Sprintf("%.2f", amount)
}

func calculateFee(txType TransactionType, amount float64) float64 {
	switch txType {
	case TxCashOut:
		if amount <= 5000 {
			return 25
		}
		return amount * 0.005 // 0.5%
	case TxTransfer:
		if amount <= 5000 {
			return 10
		}
		return amount * 0.003 // 0.3%
	default:
		return 0
	}
}

func calculateCommission(txType TransactionType, amount float64) float64 {
	switch txType {
	case TxCashIn:
		return amount * 0.003 // 0.3%
	case TxCashOut:
		return amount * 0.005 // 0.5%
	case TxTransfer:
		return amount * 0.002 // 0.2%
	case TxAirtime:
		return amount * 0.025 // 2.5%
	default:
		return 0
	}
}

// ── HTTP Server ──────────────────────────────────────────────────────────────

func main() {
	store := NewSessionStore()

	if ledgerAPIURL == "" || txAPIURL == "" || authAPIURL == "" {
		log.Printf("[ussd-gateway] WARNING: backend URLs incomplete (LEDGER_API_URL=%t TRANSACTION_API_URL=%t AUTH_API_URL=%t) — affected operations will fail closed",
			ledgerAPIURL != "", txAPIURL != "", authAPIURL != "")
	}

	// Cleanup expired sessions every 30s
	go func() {
		for range time.NewTicker(30 * time.Second).C {
			cleaned := store.CleanExpired()
			if cleaned > 0 {
				log.Printf("[USSD] Cleaned %d expired sessions", cleaned)
			}
		}
	}()

	mux := http.NewServeMux()
	handler := corsMiddleware(mux)

	// ── USSD Session Endpoint ────────────────────────────────────────────
	mux.HandleFunc("/api/ussd/session", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
			return
		}
		var req struct {
			SessionID   string `json:"sessionId"`
			PhoneNumber string `json:"phoneNumber"`
			ServiceCode string `json:"serviceCode"`
			Text        string `json:"text"`
			NetworkType string `json:"networkType"`
			Carrier     string `json:"carrier"`
		}
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			http.Error(w, "Invalid request", http.StatusBadRequest)
			return
		}
		if req.SessionID == "" {
			req.SessionID = uuid.New().String()
		}
		if req.ServiceCode == "" {
			req.ServiceCode = "*347*54#"
		}

		resp := processUSSD(store, req.SessionID, req.PhoneNumber, req.ServiceCode, req.Text)
		jsonResponse(w, resp, http.StatusOK)
	})

	// ── Africa's Talking Callback ────────────────────────────────────────
	mux.HandleFunc("/api/ussd/callback", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
			return
		}
		r.ParseForm()
		sessionID := r.FormValue("sessionId")
		phoneNumber := r.FormValue("phoneNumber")
		serviceCode := r.FormValue("serviceCode")
		text := r.FormValue("text")
		networkType := r.FormValue("networkCode")

		if sessionID == "" {
			sessionID = uuid.New().String()
		}

		// Parse multi-step input (Africa's Talking sends "1*5000*1234")
		inputs := strings.Split(text, "*")
		lastInput := ""
		if len(inputs) > 0 {
			lastInput = inputs[len(inputs)-1]
		}

		resp := processUSSD(store, sessionID, phoneNumber, serviceCode, lastInput)

		// Africa's Talking expects plain text with CON/END prefix
		w.Header().Set("Content-Type", "text/plain")
		fmt.Fprintf(w, "%s %s", resp.Action, resp.Text)
		_ = networkType
	})

	// ── Active Sessions ──────────────────────────────────────────────────
	mux.HandleFunc("/api/ussd/sessions", func(w http.ResponseWriter, r *http.Request) {
		jsonResponse(w, store.GetActiveSessions(), http.StatusOK)
	})

	// ── Stats ────────────────────────────────────────────────────────────
	mux.HandleFunc("/api/ussd/stats", func(w http.ResponseWriter, r *http.Request) {
		jsonResponse(w, store.GetStats(), http.StatusOK)
	})

	// ── Health ───────────────────────────────────────────────────────────
	mux.HandleFunc("/api/health", func(w http.ResponseWriter, r *http.Request) {
		jsonResponse(w, map[string]interface{}{
			"status":  "healthy",
			"service": "ussd-gateway",
			"version": "1.0.0",
			"uptime":  time.Since(startTime).String(),
		}, http.StatusOK)
	})

	port := os.Getenv("PORT")
	if port == "" {
		port = "8061"
	}
	log.Printf("[ussd-gateway] Starting on :%s", port)
	log.Fatal(http.ListenAndServe(":"+port, handler))
}

var startTime = time.Now()

func corsMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type")
		if r.Method == "OPTIONS" {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		next.ServeHTTP(w, r)
	})
}

func jsonResponse(w http.ResponseWriter, data interface{}, status int) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(data)
}

// --- Production: Graceful Shutdown ---
func setupGracefulShutdown(srv *http.Server) {
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		sig := <-quit
		log.Printf("[shutdown] Received signal %s, shutting down gracefully...", sig)
		ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
		defer cancel()
		if err := srv.Shutdown(ctx); err != nil {
			log.Printf("[shutdown] Server forced to shutdown: %v", err)
		}
		log.Println("[shutdown] Server exited")
	}()
}
