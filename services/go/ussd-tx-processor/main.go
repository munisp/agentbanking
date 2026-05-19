// USSD Transaction Processor — Go microservice
// Processes cash-in, cash-out, balance inquiry, and transfer via USSD menu codes
// Bridges Africa's Talking USSD callbacks to the 54Link transaction engine
//
// Endpoints:
//   POST /process       — Process a USSD transaction step
//   POST /complete      — Complete a multi-step USSD transaction
//   GET  /session/:id   — Get session state
//   GET  /health        — Health check
//   GET  /stats         — Transaction statistics
//   POST /validate      — Validate USSD input for a given step

package main

import (
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"regexp"
	"strconv"
	"strings"
	"sync"
	"time"
)

// ── Types ────────────────────────────────────────────────────────────────────

type TxType string

const (
	TxCashIn  TxType = "cash_in"
	TxCashOut TxType = "cash_out"
	TxBalance TxType = "balance"
	TxTransfer TxType = "transfer"
	TxAirtime TxType = "airtime"
	TxBills   TxType = "bills"
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

// ── Session Store ────────────────────────────────────────────────────────────

var (
	sessions     = make(map[string]*UssdSession)
	sessionsMu   sync.RWMutex
	completedTx  int
	failedTx     int
	totalDuration float64
	phoneRegex   = regexp.MustCompile(`^(\+?[0-9]{10,15})$`)
)

const sessionTTL = 5 * time.Minute

func generateID() string {
	b := make([]byte, 8)
	rand.Read(b)
	return "USSD-TX-" + hex.EncodeToString(b)
}

func generateTxRef() string {
	b := make([]byte, 6)
	rand.Read(b)
	return "54L-" + strings.ToUpper(hex.EncodeToString(b))
}

// ── Menu Trees ───────────────────────────────────────────────────────────────

func getMainMenu() string {
	return "CON Welcome to 54Link POS\n" +
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
	return fmt.Sprintf("END Transaction successful!\nRef: %s\nType: %s\nAmount: NGN %.2f\nThank you for using 54Link.", s.TxRef, s.TxType, s.Amount)
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

		// Balance inquiry completes immediately
		if session.TxType == TxBalance {
			session.TxRef = generateTxRef()
			session.Status = "completed"
			session.Step = StepComplete
			completedTx++
			dur := time.Since(session.CreatedAt).Seconds()
			totalDuration += dur
			return ProcessResponse{SessionID: session.ID, Response: fmt.Sprintf("END Balance Inquiry\nRef: %s\nYour balance will be sent via SMS.\nThank you for using 54Link.", session.TxRef), Continue: false, TxRef: session.TxRef, Step: string(StepComplete)}
		}

		session.Step = StepConfirm
		return ProcessResponse{SessionID: session.ID, Response: getConfirmation(session), Continue: true, Step: string(StepConfirm)}

	case StepConfirm:
		if input == "1" {
			session.TxRef = generateTxRef()
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
	go cleanupExpiredSessions()

	mux := http.NewServeMux()
	mux.HandleFunc("/process", handleProcess)
	mux.HandleFunc("/complete", handleComplete)
	mux.HandleFunc("/session/", handleSession)
	mux.HandleFunc("/validate", handleValidate)
	mux.HandleFunc("/stats", handleStats)
	mux.HandleFunc("/health", handleHealth)

	port := "8111"
	log.Printf("[ussd-tx-processor] Starting on :%s", port)
	if err := http.ListenAndServe(":"+port, mux); err != nil {
		log.Fatalf("Server failed: %v", err)
	}
}
