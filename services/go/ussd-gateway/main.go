/*
ussd-gateway — 54Link USSD Transaction Fallback Gateway

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
*/
package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"strconv"
	"strings"
	"sync"
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
	TxCashIn       TransactionType = "cash_in"
	TxCashOut      TransactionType = "cash_out"
	TxTransfer     TransactionType = "transfer"
	TxAirtime      TransactionType = "airtime"
	TxBalance      TransactionType = "balance"
	TxMiniStmt     TransactionType = "mini_statement"
)

type USSDSession struct {
	ID            string          `json:"id"`
	PhoneNumber   string          `json:"phoneNumber"`
	AgentCode     string          `json:"agentCode"`
	ServiceCode   string          `json:"serviceCode"`
	State         SessionState    `json:"state"`
	TxType        TransactionType `json:"txType,omitempty"`
	Amount        float64         `json:"amount,omitempty"`
	Recipient     string          `json:"recipient,omitempty"`
	PIN           string          `json:"-"`
	TransactionRef string         `json:"transactionRef,omitempty"`
	CreatedAt     time.Time       `json:"createdAt"`
	UpdatedAt     time.Time       `json:"updatedAt"`
	ExpiresAt     time.Time       `json:"expiresAt"`
	StepHistory   []string        `json:"stepHistory"`
	Carrier       string          `json:"carrier,omitempty"`
	NetworkType   string          `json:"networkType,omitempty"` // 2G, 3G, etc.
}

// ── Session Store ────────────────────────────────────────────────────────────

type SessionStore struct {
	mu       sync.RWMutex
	sessions map[string]*USSDSession
	stats    USSDStats
}

type USSDStats struct {
	TotalSessions    int64            `json:"totalSessions"`
	ActiveSessions   int64            `json:"activeSessions"`
	CompletedSessions int64           `json:"completedSessions"`
	TimedOutSessions int64            `json:"timedOutSessions"`
	CancelledSessions int64           `json:"cancelledSessions"`
	TxByType         map[string]int64 `json:"txByType"`
	AvgSessionDurationMs int64        `json:"avgSessionDurationMs"`
	TotalAmountProcessed float64      `json:"totalAmountProcessed"`
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
			"Welcome to 54Link POS\n"+
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
		// Simulate balance check
		txRef := fmt.Sprintf("BAL-%s", uuid.New().String()[:8])
		store.Complete(s.ID, txRef, 0, TxBalance)
		return endResponse(s.ID, fmt.Sprintf(
			"Balance: NGN 125,000.00\nFloat: NGN 500,000.00\nCommission Today: NGN 3,450.00\nRef: %s", txRef))
	case "6":
		s.TxType = TxMiniStmt
		txRef := fmt.Sprintf("STMT-%s", uuid.New().String()[:8])
		store.Complete(s.ID, txRef, 0, TxMiniStmt)
		return endResponse(s.ID,
			"Last 5 Transactions:\n"+
				"1. CashIn NGN5,000 ✓\n"+
				"2. CashOut NGN2,000 ✓\n"+
				"3. Transfer NGN10,000 ✓\n"+
				"4. Airtime NGN500 ✓\n"+
				"5. CashIn NGN8,000 ✓\n"+
				fmt.Sprintf("Ref: %s", txRef))
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
		// Process transaction
		txRef := fmt.Sprintf("USSD-%s-%s", strings.ToUpper(string(s.TxType)[:3]), uuid.New().String()[:8])
		fee := calculateFee(s.TxType, s.Amount)
		commission := calculateCommission(s.TxType, s.Amount)
		store.Complete(s.ID, txRef, s.Amount, s.TxType)

		receipt := fmt.Sprintf(
			"%s Successful!\nAmount: NGN %s\nFee: NGN %s\nCommission: NGN %s\nRef: %s\nTime: %s",
			txTypeLabel(s.TxType),
			formatAmount(s.Amount),
			formatAmount(fee),
			formatAmount(commission),
			txRef,
			time.Now().Format("15:04 02/01/2006"))
		if s.Recipient != "" {
			receipt = fmt.Sprintf("%s Successful!\nTo: %s\nAmount: NGN %s\nFee: NGN %s\nRef: %s\nTime: %s",
				txTypeLabel(s.TxType), s.Recipient,
				formatAmount(s.Amount), formatAmount(fee), txRef,
				time.Now().Format("15:04 02/01/2006"))
		}
		return endResponse(s.ID, receipt)
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
