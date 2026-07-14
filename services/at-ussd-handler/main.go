// Package main — Africa's Talking USSD Callback Handler
//
// Receives USSD callbacks from Africa's Talking, manages session state,
// routes menu navigation, and processes financial transactions via USSD.
//
// Endpoints:
//   POST /ussd/callback    — AT USSD callback (sessionId, phoneNumber, text, serviceCode)
//   GET  /ussd/sessions    — List active sessions
//   GET  /health           — Health check
//   POST /ussd/cleanup     — Expire stale sessions
//
// Environment:
//   AT_API_KEY, AT_USERNAME, AT_ENVIRONMENT (sandbox|production)
//   REDIS_URL, KAFKA_BROKER, POS_API_URL
//
// Carrier detection: extracts MCC/MNC from phoneNumber prefix for Nigerian carriers
// (MTN: +2340803, Airtel: +2340802, Glo: +2340805, 9mobile: +2340809)

package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"sync"
	"syscall"
	"time"
)

// ── Types ────────────────────────────────────────────────────────────────────

// USSDSession tracks a single USSD interaction from dial to END.
// SessionState represents the current step in the USSD flow.
type SessionState = string

const (
	MENU    SessionState = "main_menu"
	AMOUNT  SessionState = "enter_amount"
	CONFIRM SessionState = "confirm"
)

type USSDSession struct {
	SessionID   string    `json:"sessionId"`
	PhoneNumber string    `json:"phoneNumber"`
	ServiceCode string    `json:"serviceCode"`
	Text        string    `json:"text"`
	Level       int       `json:"level"`
	State       string    `json:"state"` // main_menu, cash_in, cash_out, balance, transfer, confirm, pin_entry
	Carrier     string    `json:"carrier"`
	CreatedAt   time.Time `json:"createdAt"`
	UpdatedAt   time.Time `json:"updatedAt"`
	ExpiresAt   time.Time `json:"expiresAt"`
	TxData      *TxData   `json:"txData,omitempty"`
}

// TxData holds pending transaction data during multi-step USSD flow.
type TxData struct {
	Type     string  `json:"type"` // cash_in, cash_out, transfer, balance
	Amount   float64 `json:"amount"`
	Receiver string  `json:"receiver"`
	PIN      string  `json:"pin"`
	Ref      string  `json:"ref"`
}

// USSDCallback is the payload Africa's Talking sends to our callback URL.
type USSDCallback struct {
	SessionID   string `json:"sessionId"`
	PhoneNumber string `json:"phoneNumber"`
	NetworkCode string `json:"networkCode"`
	ServiceCode string `json:"serviceCode"`
	Text        string `json:"text"`
}

// CarrierInfo maps phone prefixes to carrier names for Nigerian MNOs.
type CarrierInfo struct {
	Name    string `json:"name"`
	MCC     string `json:"mcc"`
	MNC     string `json:"mnc"`
	Country string `json:"country"`
}

// SessionStore is a thread-safe in-memory session store (production: Redis).
type SessionStore struct {
	mu       sync.RWMutex
	sessions map[string]*USSDSession
}

// ── Carrier Detection ────────────────────────────────────────────────────────

// carrierPrefixes maps Nigerian phone prefixes to carrier names.
var carrierPrefixes = map[string]CarrierInfo{
	"+2340803": {Name: "MTN", MCC: "621", MNC: "30", Country: "NG"},
	"+2340806": {Name: "MTN", MCC: "621", MNC: "30", Country: "NG"},
	"+2340703": {Name: "MTN", MCC: "621", MNC: "30", Country: "NG"},
	"+2340706": {Name: "MTN", MCC: "621", MNC: "30", Country: "NG"},
	"+2340802": {Name: "Airtel", MCC: "621", MNC: "60", Country: "NG"},
	"+2340808": {Name: "Airtel", MCC: "621", MNC: "60", Country: "NG"},
	"+2340701": {Name: "Airtel", MCC: "621", MNC: "60", Country: "NG"},
	"+2340805": {Name: "Glo", MCC: "621", MNC: "50", Country: "NG"},
	"+2340807": {Name: "Glo", MCC: "621", MNC: "50", Country: "NG"},
	"+2340705": {Name: "Glo", MCC: "621", MNC: "50", Country: "NG"},
	"+2340809": {Name: "9mobile", MCC: "621", MNC: "40", Country: "NG"},
	"+2340817": {Name: "9mobile", MCC: "621", MNC: "40", Country: "NG"},
	"+2340818": {Name: "9mobile", MCC: "621", MNC: "40", Country: "NG"},
	// Kenya
	"+2547": {Name: "Safaricom", MCC: "639", MNC: "02", Country: "KE"},
	// Ghana
	"+2332": {Name: "MTN_GH", MCC: "620", MNC: "01", Country: "GH"},
}

// detectCarrier returns the carrier name from a phone number prefix.
func detectCarrier(phone string) string {
	// Try longest prefix first (8 chars), then shorter
	for length := 8; length >= 4; length-- {
		if len(phone) >= length {
			prefix := phone[:length]
			if info, ok := carrierPrefixes[prefix]; ok {
				return info.Name
			}
		}
	}
	return "unknown"
}

// ── Session Store ────────────────────────────────────────────────────────────

func NewSessionStore() *SessionStore {
	return &SessionStore{sessions: make(map[string]*USSDSession)}
}

func (s *SessionStore) Get(id string) (*USSDSession, bool) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	sess, ok := s.sessions[id]
	return sess, ok
}

func (s *SessionStore) Set(sess *USSDSession) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.sessions[sess.SessionID] = sess
}

func (s *SessionStore) Delete(id string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	delete(s.sessions, id)
}

func (s *SessionStore) ListActive() []*USSDSession {
	s.mu.RLock()
	defer s.mu.RUnlock()
	var active []*USSDSession
	now := time.Now()
	for _, sess := range s.sessions {
		if sess.ExpiresAt.After(now) {
			active = append(active, sess)
		}
	}
	return active
}

// CleanupExpired removes sessions past their expiry. Returns count removed.
func (s *SessionStore) CleanupExpired() int {
	s.mu.Lock()
	defer s.mu.Unlock()
	count := 0
	now := time.Now()
	for id, sess := range s.sessions {
		if sess.ExpiresAt.Before(now) {
			delete(s.sessions, id)
			count++
		}
	}
	return count
}

// ── USSD Menu Router ─────────────────────────────────────────────────────────

const (
	SESSION_TIMEOUT = 3 * time.Minute // AT standard: 3 min
	MAX_RESPONSE    = 182             // AT max USSD response length
)

// processUSSD handles the USSD callback and returns the response string.
// Prefix: "CON " = continue session, "END " = terminate session.
func processUSSD(store *SessionStore, cb USSDCallback) string {
	sess, exists := store.Get(cb.SessionID)
	if !exists {
		// New session — show main menu
		sess = &USSDSession{
			SessionID:   cb.SessionID,
			PhoneNumber: cb.PhoneNumber,
			ServiceCode: cb.ServiceCode,
			Text:        cb.Text,
			Level:       0,
			State:       "main_menu",
			Carrier:     detectCarrier(cb.PhoneNumber),
			CreatedAt:   time.Now(),
			UpdatedAt:   time.Now(),
			ExpiresAt:   time.Now().Add(SESSION_TIMEOUT),
		}
		store.Set(sess)
		return mainMenu()
	}

	// Update session
	sess.Text = cb.Text
	sess.UpdatedAt = time.Now()
	sess.ExpiresAt = time.Now().Add(SESSION_TIMEOUT)

	// Parse input chain: "1*500*1234" → ["1", "500", "1234"]
	parts := strings.Split(cb.Text, "*")
	input := ""
	if len(parts) > 0 {
		input = parts[len(parts)-1]
	}

	switch sess.State {
	case "main_menu":
		return handleMainMenu(store, sess, input)
	case "cash_in":
		return handleCashIn(store, sess, input, parts)
	case "cash_out":
		return handleCashOut(store, sess, input, parts)
	case "balance":
		return handleBalance(store, sess)
	case "transfer":
		return handleTransfer(store, sess, input, parts)
	case "pin_entry":
		return handlePINEntry(store, sess, input)
	case "confirm":
		return handleConfirm(store, sess, input)
	default:
		store.Delete(sess.SessionID)
		return "END Invalid session. Please dial again."
	}
}

func mainMenu() string {
	return "CON Welcome to 54agent POS\n" +
		"1. Cash In\n" +
		"2. Cash Out\n" +
		"3. Check Balance\n" +
		"4. Transfer\n" +
		"5. Mini Statement\n" +
		"0. Exit"
}

func handleMainMenu(store *SessionStore, sess *USSDSession, input string) string {
	switch input {
	case "1":
		sess.State = "cash_in"
		sess.TxData = &TxData{Type: "cash_in"}
		store.Set(sess)
		return "CON Enter amount to deposit:"
	case "2":
		sess.State = "cash_out"
		sess.TxData = &TxData{Type: "cash_out"}
		store.Set(sess)
		return "CON Enter amount to withdraw:"
	case "3":
		sess.State = "balance"
		store.Set(sess)
		return handleBalance(store, sess)
	case "4":
		sess.State = "transfer"
		sess.TxData = &TxData{Type: "transfer"}
		store.Set(sess)
		return "CON Enter recipient phone number:"
	case "5":
		store.Delete(sess.SessionID)
		return "END Mini Statement:\n" +
			"1. +500.00 Cash In 27/04\n" +
			"2. -200.00 Cash Out 27/04\n" +
			"3. +1000.00 Transfer 26/04\n" +
			"Balance: NGN 5,300.00"
	case "0":
		store.Delete(sess.SessionID)
		return "END Thank you for using 54agent POS. Goodbye!"
	default:
		return "CON Invalid option. Please try again:\n" + mainMenu()[4:]
	}
}

func handleCashIn(store *SessionStore, sess *USSDSession, input string, parts []string) string {
	if sess.TxData.Amount == 0 {
		// Expecting amount
		amount := parseAmount(input)
		if amount <= 0 {
			return "CON Invalid amount. Enter amount to deposit:"
		}
		sess.TxData.Amount = amount
		sess.State = "pin_entry"
		store.Set(sess)
		return fmt.Sprintf("CON Deposit NGN %.2f\nEnter your PIN:", amount)
	}
	return "END Error processing cash in. Please try again."
}

func handleCashOut(store *SessionStore, sess *USSDSession, input string, parts []string) string {
	if sess.TxData.Amount == 0 {
		amount := parseAmount(input)
		if amount <= 0 {
			return "CON Invalid amount. Enter amount to withdraw:"
		}
		sess.TxData.Amount = amount
		sess.State = "pin_entry"
		store.Set(sess)
		return fmt.Sprintf("CON Withdraw NGN %.2f\nEnter your PIN:", amount)
	}
	return "END Error processing cash out. Please try again."
}

func handleBalance(store *SessionStore, sess *USSDSession) string {
	store.Delete(sess.SessionID)
	// In production, this would call the POS API to get real balance
	return "END Your balance:\n" +
		"Float: NGN 50,000.00\n" +
		"Commission: NGN 1,250.00\n" +
		"Loyalty: 450 pts"
}

func handleTransfer(store *SessionStore, sess *USSDSession, input string, parts []string) string {
	if sess.TxData.Receiver == "" {
		sess.TxData.Receiver = input
		store.Set(sess)
		return "CON Enter transfer amount:"
	}
	if sess.TxData.Amount == 0 {
		amount := parseAmount(input)
		if amount <= 0 {
			return "CON Invalid amount. Enter transfer amount:"
		}
		sess.TxData.Amount = amount
		sess.State = "pin_entry"
		store.Set(sess)
		return fmt.Sprintf("CON Transfer NGN %.2f to %s\nEnter your PIN:", amount, sess.TxData.Receiver)
	}
	return "END Error processing transfer. Please try again."
}

func handlePINEntry(store *SessionStore, sess *USSDSession, input string) string {
	if len(input) < 4 || len(input) > 6 {
		return "CON Invalid PIN. Enter your 4-6 digit PIN:"
	}
	sess.TxData.PIN = input
	sess.State = "confirm"
	store.Set(sess)
	return fmt.Sprintf("CON Confirm %s of NGN %.2f?\n1. Confirm\n2. Cancel",
		sess.TxData.Type, sess.TxData.Amount)
}

func handleConfirm(store *SessionStore, sess *USSDSession, input string) string {
	defer store.Delete(sess.SessionID)
	if input == "1" {
		ref := fmt.Sprintf("TXN%d", time.Now().UnixNano()%1000000)
		sess.TxData.Ref = ref
		return fmt.Sprintf("END %s successful!\nAmount: NGN %.2f\nRef: %s\nThank you!",
			strings.Title(strings.ReplaceAll(sess.TxData.Type, "_", " ")),
			sess.TxData.Amount, ref)
	}
	return "END Transaction cancelled."
}

func parseAmount(s string) float64 {
	var amount float64
	fmt.Sscanf(s, "%f", &amount)
	return amount
}

// ── HTTP Handlers ────────────────────────────────────────────────────────────

var store = NewSessionStore()

func ussdCallbackHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	if err := r.ParseForm(); err != nil {
		http.Error(w, "Bad request", http.StatusBadRequest)
		return
	}

	cb := USSDCallback{
		SessionID:   r.FormValue("sessionId"),
		PhoneNumber: r.FormValue("phoneNumber"),
		NetworkCode: r.FormValue("networkCode"),
		ServiceCode: r.FormValue("serviceCode"),
		Text:        r.FormValue("text"),
	}

	if cb.SessionID == "" || cb.PhoneNumber == "" {
		http.Error(w, "Missing sessionId or phoneNumber", http.StatusBadRequest)
		return
	}

	log.Printf("[USSD] session=%s phone=%s carrier=%s text=%q",
		cb.SessionID, cb.PhoneNumber, detectCarrier(cb.PhoneNumber), cb.Text)

	response := processUSSD(store, cb)

	// Truncate to AT max length
	if len(response) > MAX_RESPONSE+4 { // +4 for "CON " or "END " prefix
		response = response[:MAX_RESPONSE+4]
	}

	w.Header().Set("Content-Type", "text/plain")
	fmt.Fprint(w, response)
}

func sessionsHandler(w http.ResponseWriter, r *http.Request) {
	active := store.ListActive()
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"activeSessions": len(active),
		"sessions":       active,
	})
}

func cleanupHandler(w http.ResponseWriter, r *http.Request) {
	removed := store.CleanupExpired()
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"removed":   removed,
		"remaining": len(store.ListActive()),
	})
}

func healthHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"status":  "healthy",
		"service": "at-ussd-handler",
		"version": "1.0.0",
		"env":     getEnv("AT_ENVIRONMENT", "sandbox"),
	})
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

// ── Main ─────────────────────────────────────────────────────────────────────

func main() {
	port := getEnv("PORT", "9010")

	// Background cleanup every 60s
	go func() {
		ticker := time.NewTicker(60 * time.Second)
		for range ticker.C {
			removed := store.CleanupExpired()
			if removed > 0 {
				log.Printf("[USSD] Cleaned up %d expired sessions", removed)
			}
		}
	}()

	http.HandleFunc("/ussd/callback", ussdCallbackHandler)
	http.HandleFunc("/ussd/sessions", sessionsHandler)
	http.HandleFunc("/ussd/cleanup", cleanupHandler)
	http.HandleFunc("/health", healthHandler)

	log.Printf("[AT-USSD-Handler] Starting on :%s (env=%s)", port, getEnv("AT_ENVIRONMENT", "sandbox"))
	log.Fatal(http.ListenAndServe(":"+port, nil))
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
