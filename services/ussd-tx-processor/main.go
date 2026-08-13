// USSD Transaction Processor — Go microservice
// Processes cash-in, cash-out, balance inquiry, and transfer via USSD menu codes
// Bridges Africa's Talking USSD callbacks to the 54agent transaction engine
//
// Endpoints:
//   POST /process       — Process a USSD transaction step
//   POST /complete      — Complete a multi-step USSD transaction
//   GET  /session/:id   — Get session state
//   GET  /health        — Health check
//   GET  /stats         — Transaction statistics
//   POST /validate      — Validate USSD input for a given step
//
// Backend integration (REQUIRED — this processor never fabricates financial data):
//   TRANSACTION_API_URL  — transaction engine for execution (real references)
//   LEDGER_API_URL       — wallet/ledger API for real balances
//   AUTH_API_URL         — auth service for PIN verification

package main

import (
	"bytes"
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net/http"
	"net/url"
	"os"
	"os/signal"
	"regexp"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"
)

// ── Types ────────────────────────────────────────────────────────────────────

type TxType string

const (
	TxCashIn   TxType = "cash_in"
	TxCashOut  TxType = "cash_out"
	TxBalance  TxType = "balance"
	TxTransfer TxType = "transfer"
	TxAirtime  TxType = "airtime"
	TxBills    TxType = "bills"
)

type SessionStep string

const (
	StepSelectTxType SessionStep = "select_type"
	StepEnterAmount  SessionStep = "enter_amount"
	StepEnterPhone   SessionStep = "enter_phone"
	StepEnterPin     SessionStep = "enter_pin"
	StepConfirm      SessionStep = "confirm"
	StepComplete     SessionStep = "complete"
	StepError        SessionStep = "error"
)

type UssdSession struct {
	ID          string      `json:"id"`
	PhoneNumber string      `json:"phoneNumber"`
	AgentCode   string      `json:"agentCode"`
	TxType      TxType      `json:"txType"`
	Step        SessionStep `json:"step"`
	Amount      float64     `json:"amount"`
	TargetPhone string      `json:"targetPhone"`
	Pin         string      `json:"pin"`
	Carrier     string      `json:"carrier"`
	MenuCode    string      `json:"menuCode"`
	CreatedAt   time.Time   `json:"createdAt"`
	UpdatedAt   time.Time   `json:"updatedAt"`
	ExpiresAt   time.Time   `json:"expiresAt"`
	TxRef       string      `json:"txRef,omitempty"`
	Status      string      `json:"status"`
	ErrorMsg    string      `json:"errorMsg,omitempty"`
}

type ProcessRequest struct {
	SessionID   string `json:"sessionId"`
	PhoneNumber string `json:"phoneNumber"`
	AgentCode   string `json:"agentCode"`
	Input       string `json:"input"`
	MenuCode    string `json:"menuCode"`
	Carrier     string `json:"carrier"`
}

type ProcessResponse struct {
	SessionID string `json:"sessionId"`
	Response  string `json:"response"`
	Continue  bool   `json:"continue"`
	Step      string `json:"step"`
	TxRef     string `json:"txRef,omitempty"`
}

type TxStats struct {
	TotalSessions   int            `json:"totalSessions"`
	ActiveSessions  int            `json:"activeSessions"`
	CompletedTx     int            `json:"completedTx"`
	FailedTx        int            `json:"failedTx"`
	ByType          map[string]int `json:"byType"`
	AvgDurationSecs float64        `json:"avgDurationSecs"`
}

// ── Backend Service Clients ──────────────────────────────────────────────────
//
// All balances, PIN verification and transaction execution are delegated to
// real backend services. This processor NEVER fabricates financial data and
// only reports success with a real backend-issued reference.

var (
	transactionAPIURL = strings.TrimRight(os.Getenv("TRANSACTION_API_URL"), "/")
	ledgerAPIURL      = strings.TrimRight(os.Getenv("LEDGER_API_URL"), "/")
	authAPIURL        = strings.TrimRight(os.Getenv("AUTH_API_URL"), "/")
	backendHTTP       = &http.Client{Timeout: 8 * time.Second}
)

// BalanceInfo is the real balance snapshot returned by the ledger/wallet API.
type BalanceInfo struct {
	Balance   float64 `json:"balance"`
	Available float64 `json:"available_balance"`
	Currency  string  `json:"currency"`
}

func fetchBalance(phone string) (*BalanceInfo, error) {
	if ledgerAPIURL == "" {
		return nil, errors.New("LEDGER_API_URL not configured")
	}
	resp, err := backendHTTP.Get(fmt.Sprintf("%s/api/v1/accounts/balance?phone=%s", ledgerAPIURL, url.QueryEscape(phone)))
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

// verifyPIN verifies the collected PIN against the auth service.
func verifyPIN(phone, pin string) error {
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
	Reference string `json:"reference"`
	Status    string `json:"status"`
	Error     string `json:"error"`
}

// executeTransaction posts the confirmed transaction to the transaction
// engine. The USSD session ID is used as the idempotency key so carrier
// retries can never double-execute a money movement.
func executeTransaction(s *UssdSession) (*ExecutionResult, error) {
	if transactionAPIURL == "" {
		return nil, errors.New("TRANSACTION_API_URL not configured")
	}
	payload, _ := json.Marshal(map[string]interface{}{
		"type":        string(s.TxType),
		"amount":      s.Amount,
		"agentPhone":  s.PhoneNumber,
		"agentCode":   s.AgentCode,
		"targetPhone": s.TargetPhone,
		"channel":     "ussd",
	})
	req, err := http.NewRequest(http.MethodPost, transactionAPIURL+"/api/v1/transactions", bytes.NewReader(payload))
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

var (
	sessions      = make(map[string]*UssdSession)
	sessionsMu    sync.RWMutex
	completedTx   int
	failedTx      int
	totalDuration float64
	phoneRegex    = regexp.MustCompile(`^(\+?[0-9]{10,15})$`)
)

const sessionTTL = 5 * time.Minute

func generateID() string {
	b := make([]byte, 8)
	rand.Read(b)
	return "USSD-TX-" + hex.EncodeToString(b)
}

// ── Menu Trees ───────────────────────────────────────────────────────────────

func getMainMenu() string {
	return "CON Welcome to 54agent POS\n" +
		"1. Cash In\n" +
		"2. Cash Out\n" +
		"3. Balance Inquiry\n" +
		"4. Transfer\n" +
		"5. Airtime Purchase\n" +
		"6. Bill Payment"
}

func getAmountPrompt(txType TxType) string {
	switch txType {
	case TxCashIn:
		return "CON Enter cash-in amount (NGN):"
	case TxCashOut:
		return "CON Enter cash-out amount (NGN):"
	case TxTransfer:
		return "CON Enter transfer amount (NGN):"
	case TxAirtime:
		return "CON Enter airtime amount (NGN):"
	case TxBills:
		return "CON Enter bill amount (NGN):"
	default:
		return "CON Enter amount (NGN):"
	}
}

func getPhonePrompt(txType TxType) string {
	switch txType {
	case TxTransfer:
		return "CON Enter recipient phone number:"
	case TxAirtime:
		return "CON Enter phone number for airtime:"
	default:
		return "CON Enter customer phone number:"
	}
}

func getConfirmation(s *UssdSession) string {
	msg := fmt.Sprintf("CON Confirm %s\nAmount: NGN %.2f\n", s.TxType, s.Amount)
	if s.TargetPhone != "" {
		msg += fmt.Sprintf("Phone: %s\n", s.TargetPhone)
	}
	msg += "1. Confirm\n2. Cancel"
	return msg
}

func getSuccessMessage(s *UssdSession) string {
	return fmt.Sprintf("END Transaction successful!\nRef: %s\nType: %s\nAmount: NGN %.2f\nThank you for using 54agent.", s.TxRef, s.TxType, s.Amount)
}

// ── Process Logic ────────────────────────────────────────────────────────────

func processStep(req ProcessRequest) ProcessResponse {
	sessionsMu.Lock()
	defer sessionsMu.Unlock()

	session, exists := sessions[req.SessionID]
	if !exists {
		// New session
		session = &UssdSession{
			ID:          req.SessionID,
			PhoneNumber: req.PhoneNumber,
			AgentCode:   req.AgentCode,
			Step:        StepSelectTxType,
			Carrier:     req.Carrier,
			MenuCode:    req.MenuCode,
			CreatedAt:   time.Now(),
			UpdatedAt:   time.Now(),
			ExpiresAt:   time.Now().Add(sessionTTL),
			Status:      "active",
		}
		if req.SessionID == "" {
			session.ID = generateID()
		}
		sessions[session.ID] = session

		// Check if menu code implies a specific transaction type
		if strings.HasPrefix(req.MenuCode, "*384*1") {
			session.TxType = TxCashIn
			session.Step = StepEnterAmount
			return ProcessResponse{SessionID: session.ID, Response: getAmountPrompt(TxCashIn), Continue: true, Step: string(StepEnterAmount)}
		}
		if strings.HasPrefix(req.MenuCode, "*384*2") {
			session.TxType = TxCashOut
			session.Step = StepEnterAmount
			return ProcessResponse{SessionID: session.ID, Response: getAmountPrompt(TxCashOut), Continue: true, Step: string(StepEnterAmount)}
		}
		if strings.HasPrefix(req.MenuCode, "*384*3") {
			session.TxType = TxBalance
			session.Step = StepEnterPin
			return ProcessResponse{SessionID: session.ID, Response: "CON Enter your PIN:", Continue: true, Step: string(StepEnterPin)}
		}

		return ProcessResponse{SessionID: session.ID, Response: getMainMenu(), Continue: true, Step: string(StepSelectTxType)}
	}

	// Check expiry
	if time.Now().After(session.ExpiresAt) {
		session.Status = "expired"
		failedTx++
		delete(sessions, session.ID)
		return ProcessResponse{SessionID: session.ID, Response: "END Session expired. Please dial again.", Continue: false, Step: "expired"}
	}

	session.UpdatedAt = time.Now()
	input := strings.TrimSpace(req.Input)

	switch session.Step {
	case StepSelectTxType:
		switch input {
		case "1":
			session.TxType = TxCashIn
			session.Step = StepEnterAmount
			return ProcessResponse{SessionID: session.ID, Response: getAmountPrompt(TxCashIn), Continue: true, Step: string(StepEnterAmount)}
		case "2":
			session.TxType = TxCashOut
			session.Step = StepEnterAmount
			return ProcessResponse{SessionID: session.ID, Response: getAmountPrompt(TxCashOut), Continue: true, Step: string(StepEnterAmount)}
		case "3":
			session.TxType = TxBalance
			session.Step = StepEnterPin
			return ProcessResponse{SessionID: session.ID, Response: "CON Enter your PIN:", Continue: true, Step: string(StepEnterPin)}
		case "4":
			session.TxType = TxTransfer
			session.Step = StepEnterAmount
			return ProcessResponse{SessionID: session.ID, Response: getAmountPrompt(TxTransfer), Continue: true, Step: string(StepEnterAmount)}
		case "5":
			session.TxType = TxAirtime
			session.Step = StepEnterAmount
			return ProcessResponse{SessionID: session.ID, Response: getAmountPrompt(TxAirtime), Continue: true, Step: string(StepEnterAmount)}
		case "6":
			session.TxType = TxBills
			session.Step = StepEnterAmount
			return ProcessResponse{SessionID: session.ID, Response: getAmountPrompt(TxBills), Continue: true, Step: string(StepEnterAmount)}
		default:
			return ProcessResponse{SessionID: session.ID, Response: "CON Invalid option.\n" + getMainMenu(), Continue: true, Step: string(StepSelectTxType)}
		}

	case StepEnterAmount:
		amount, err := strconv.ParseFloat(input, 64)
		if err != nil || amount <= 0 || amount > 5000000 {
			return ProcessResponse{SessionID: session.ID, Response: "CON Invalid amount. Enter a valid amount (1 - 5,000,000):", Continue: true, Step: string(StepEnterAmount)}
		}
		session.Amount = amount
		if session.TxType == TxTransfer || session.TxType == TxAirtime {
			session.Step = StepEnterPhone
			return ProcessResponse{SessionID: session.ID, Response: getPhonePrompt(session.TxType), Continue: true, Step: string(StepEnterPhone)}
		}
		session.Step = StepEnterPin
		return ProcessResponse{SessionID: session.ID, Response: "CON Enter your PIN:", Continue: true, Step: string(StepEnterPin)}

	case StepEnterPhone:
		cleaned := strings.ReplaceAll(input, " ", "")
		if !phoneRegex.MatchString(cleaned) {
			return ProcessResponse{SessionID: session.ID, Response: "CON Invalid phone number. Try again:", Continue: true, Step: string(StepEnterPhone)}
		}
		session.TargetPhone = cleaned
		session.Step = StepEnterPin
		return ProcessResponse{SessionID: session.ID, Response: "CON Enter your PIN:", Continue: true, Step: string(StepEnterPin)}

	case StepEnterPin:
		if len(input) < 4 || len(input) > 6 {
			return ProcessResponse{SessionID: session.ID, Response: "CON Invalid PIN. Enter 4-6 digit PIN:", Continue: true, Step: string(StepEnterPin)}
		}
		session.Pin = input

		// Verify PIN against the auth service before any balance disclosure
		// or money movement.
		if err := verifyPIN(session.PhoneNumber, session.Pin); err != nil {
			log.Printf("[ussd-tx] PIN verification failed (session=%s): %v", session.ID, err)
			session.Status = "failed"
			failedTx++
			delete(sessions, session.ID)
			return ProcessResponse{SessionID: session.ID, Response: "END PIN verification failed. Transaction cancelled.", Continue: false, Step: "failed"}
		}

		// Balance inquiry completes immediately with the REAL ledger balance
		if session.TxType == TxBalance {
			bal, err := fetchBalance(session.PhoneNumber)
			if err != nil {
				log.Printf("[ussd-tx] balance lookup failed (session=%s): %v", session.ID, err)
				session.Status = "failed"
				session.ErrorMsg = "balance service unavailable"
				failedTx++
				return ProcessResponse{SessionID: session.ID, Response: "END Balance service unavailable. Please try again later.", Continue: false, Step: "failed"}
			}
			session.Status = "completed"
			session.Step = StepComplete
			completedTx++
			dur := time.Since(session.CreatedAt).Seconds()
			totalDuration += dur
			return ProcessResponse{SessionID: session.ID, Response: fmt.Sprintf("END Balance Inquiry\nBalance: %s %.2f\nAvailable: %s %.2f\nThank you for using 54agent.", bal.Currency, bal.Balance, bal.Currency, bal.Available), Continue: false, Step: string(StepComplete)}
		}

		session.Step = StepConfirm
		return ProcessResponse{SessionID: session.ID, Response: getConfirmation(session), Continue: true, Step: string(StepConfirm)}

	case StepConfirm:
		if input == "1" {
			// Execute against the transaction engine — only a real backend
			// reference may be shown to the customer as a confirmation.
			result, err := executeTransaction(session)
			if err != nil {
				log.Printf("[ussd-tx] transaction execution failed (session=%s, type=%s, amount=%.2f): %v",
					session.ID, session.TxType, session.Amount, err)
				session.Status = "failed"
				session.ErrorMsg = err.Error()
				session.Step = StepError
				failedTx++
				return ProcessResponse{SessionID: session.ID, Response: fmt.Sprintf("END Transaction could not be completed. No funds were moved.\nReason: %s", session.ErrorMsg), Continue: false, Step: string(StepError)}
			}
			session.TxRef = result.Reference
			session.Status = "completed"
			session.Step = StepComplete
			completedTx++
			dur := time.Since(session.CreatedAt).Seconds()
			totalDuration += dur
			return ProcessResponse{SessionID: session.ID, Response: getSuccessMessage(session), Continue: false, TxRef: session.TxRef, Step: string(StepComplete)}
		}
		if input == "2" {
			session.Status = "cancelled"
			failedTx++
			delete(sessions, session.ID)
			return ProcessResponse{SessionID: session.ID, Response: "END Transaction cancelled.", Continue: false, Step: "cancelled"}
		}
		return ProcessResponse{SessionID: session.ID, Response: getConfirmation(session), Continue: true, Step: string(StepConfirm)}

	default:
		return ProcessResponse{SessionID: session.ID, Response: "END Session error. Please try again.", Continue: false, Step: "error"}
	}
}

// ── Validation ───────────────────────────────────────────────────────────────

type ValidateRequest struct {
	Step  string `json:"step"`
	Input string `json:"input"`
}

type ValidateResponse struct {
	Valid   bool   `json:"valid"`
	Message string `json:"message,omitempty"`
}

func validateInput(step, input string) ValidateResponse {
	switch SessionStep(step) {
	case StepSelectTxType:
		if input >= "1" && input <= "6" {
			return ValidateResponse{Valid: true}
		}
		return ValidateResponse{Valid: false, Message: "Select 1-6"}
	case StepEnterAmount:
		amount, err := strconv.ParseFloat(input, 64)
		if err != nil || amount <= 0 || amount > 5000000 {
			return ValidateResponse{Valid: false, Message: "Amount must be 1 - 5,000,000"}
		}
		return ValidateResponse{Valid: true}
	case StepEnterPhone:
		if phoneRegex.MatchString(strings.ReplaceAll(input, " ", "")) {
			return ValidateResponse{Valid: true}
		}
		return ValidateResponse{Valid: false, Message: "Invalid phone number"}
	case StepEnterPin:
		if len(input) >= 4 && len(input) <= 6 {
			return ValidateResponse{Valid: true}
		}
		return ValidateResponse{Valid: false, Message: "PIN must be 4-6 digits"}
	case StepConfirm:
		if input == "1" || input == "2" {
			return ValidateResponse{Valid: true}
		}
		return ValidateResponse{Valid: false, Message: "Enter 1 to confirm or 2 to cancel"}
	default:
		return ValidateResponse{Valid: false, Message: "Unknown step"}
	}
}

// ── HTTP Handlers ────────────────────────────────────────────────────────────

func handleProcess(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	var req ProcessRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid JSON", http.StatusBadRequest)
		return
	}
	resp := processStep(req)
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(resp)
}

func handleComplete(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	var req struct {
		SessionID string `json:"sessionId"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid JSON", http.StatusBadRequest)
		return
	}

	sessionsMu.RLock()
	session, exists := sessions[req.SessionID]
	sessionsMu.RUnlock()

	if !exists {
		http.Error(w, "Session not found", http.StatusNotFound)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(session)
}

func handleSession(w http.ResponseWriter, r *http.Request) {
	id := strings.TrimPrefix(r.URL.Path, "/session/")
	if id == "" {
		http.Error(w, "Session ID required", http.StatusBadRequest)
		return
	}

	sessionsMu.RLock()
	session, exists := sessions[id]
	sessionsMu.RUnlock()

	if !exists {
		http.Error(w, "Session not found", http.StatusNotFound)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(session)
}

func handleValidate(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	var req ValidateRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid JSON", http.StatusBadRequest)
		return
	}
	resp := validateInput(req.Step, req.Input)
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(resp)
}

func handleStats(w http.ResponseWriter, r *http.Request) {
	sessionsMu.RLock()
	defer sessionsMu.RUnlock()

	active := 0
	byType := make(map[string]int)
	for _, s := range sessions {
		if s.Status == "active" {
			active++
		}
		byType[string(s.TxType)]++
	}

	avgDur := 0.0
	if completedTx > 0 {
		avgDur = totalDuration / float64(completedTx)
	}

	stats := TxStats{
		TotalSessions:   len(sessions),
		ActiveSessions:  active,
		CompletedTx:     completedTx,
		FailedTx:        failedTx,
		ByType:          byType,
		AvgDurationSecs: avgDur,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(stats)
}

func handleHealth(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"status":  "healthy",
		"service": "ussd-tx-processor",
		"version": "1.0.0",
		"uptime":  time.Since(startTime).String(),
		"backendsConfigured": transactionAPIURL != "" && ledgerAPIURL != "" && authAPIURL != "",
	})
}

var startTime = time.Now()

// ── Session Cleanup ──────────────────────────────────────────────────────────

func cleanupExpiredSessions() {
	for {
		time.Sleep(30 * time.Second)
		sessionsMu.Lock()
		now := time.Now()
		for id, s := range sessions {
			if now.After(s.ExpiresAt) {
				delete(sessions, id)
			}
		}
		sessionsMu.Unlock()
	}
}

func main() {
	if transactionAPIURL == "" || ledgerAPIURL == "" || authAPIURL == "" {
		log.Printf("[ussd-tx-processor] WARNING: backend URLs incomplete (TRANSACTION_API_URL=%t LEDGER_API_URL=%t AUTH_API_URL=%t) — affected operations will fail closed",
			transactionAPIURL != "", ledgerAPIURL != "", authAPIURL != "")
	}

	go cleanupExpiredSessions()

	mux := http.NewServeMux()
	mux.HandleFunc("/process", handleProcess)
	mux.HandleFunc("/complete", handleComplete)
	mux.HandleFunc("/session/", handleSession)
	mux.HandleFunc("/validate", handleValidate)
	mux.HandleFunc("/stats", handleStats)
	mux.HandleFunc("/health", handleHealth)

	port := os.Getenv("PORT")
	if port == "" {
		port = "8111"
	}
	log.Printf("[ussd-tx-processor] Starting on :%s", port)
	if err := http.ListenAndServe(":"+port, mux); err != nil {
		log.Fatalf("Server failed: %v", err)
	}
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
