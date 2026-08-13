// Package main — Africa's Talking SMS Webhook Receiver
//
// Receives inbound SMS and delivery reports from Africa's Talking.
// Parses transaction commands from SMS text, validates format,
// and forwards to the POS API for processing.
//
// Endpoints:
//   POST /sms/incoming     — AT inbound SMS webhook
//   POST /sms/delivery     — AT delivery report webhook
//   GET  /sms/status       — Delivery status dashboard
//   GET  /health           — Health check
//
// SMS Command Format:
//   CI <amount>                    — Cash In
//   CO <amount>                    — Cash Out
//   BAL                            — Check Balance
//   TRF <phone> <amount>           — Transfer
//   HELP                           — Help menu
//   PIN <old> <new>                — Change PIN
//
// Environment:
//   AT_API_KEY, AT_USERNAME, AT_ENVIRONMENT
//   KAFKA_BROKER, POS_API_URL, REDIS_URL
//
// POS_API_URL is REQUIRED for all financial commands. This webhook NEVER
// fabricates balances or transaction references and fails closed when the
// POS API is unreachable.

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
)

// ── Types ────────────────────────────────────────────────────────────────────

// InboundSMS is the payload Africa's Talking sends for incoming SMS.
type InboundSMS struct {
	Date        string `json:"date"`
	From        string `json:"from"`
	ID          string `json:"id"`
	LinkID      string `json:"linkId"`
	Text        string `json:"text"`
	To          string `json:"to"`
	NetworkCode string `json:"networkCode"`
}

// DeliveryReport is the payload for SMS delivery status updates.
type DeliveryReport struct {
	ID          string `json:"id"`
	Status      string `json:"status"` // Success, Sent, Buffered, Rejected, Failed
	PhoneNumber string `json:"phoneNumber"`
	NetworkCode string `json:"networkCode"`
	FailReason  string `json:"failureReason"`
	RetryCount  int    `json:"retryCount"`
}

// SMSCommand represents a parsed transaction command from SMS text.
type SMSCommand struct {
	Type     string  `json:"type"` // CI, CO, BAL, TRF, HELP, PIN
	Amount   float64 `json:"amount"`
	Receiver string  `json:"receiver"`
	OldPIN   string  `json:"oldPin,omitempty"`
	NewPIN   string  `json:"newPin,omitempty"`
	Raw      string  `json:"raw"`
	Valid    bool    `json:"valid"`
	Error    string  `json:"error,omitempty"`
}

// DeliveryLog tracks SMS delivery status.
type DeliveryLog struct {
	MessageID  string    `json:"messageId"`
	Phone      string    `json:"phone"`
	Status     string    `json:"status"`
	FailReason string    `json:"failReason,omitempty"`
	RetryCount int       `json:"retryCount"`
	UpdatedAt  time.Time `json:"updatedAt"`
}

// ── POS API Client ───────────────────────────────────────────────────────────
//
// All financial data (balances, transaction references, PIN changes) comes
// from the POS API. No fabricated values anywhere.

var (
	posAPIURL = strings.TrimRight(getEnv("POS_API_URL", ""), "/")
	posHTTP   = &http.Client{Timeout: 8 * time.Second}
)

// POSBalance is the real balance snapshot returned by the POS API.
type POSBalance struct {
	Balance    float64 `json:"balance"`
	Float      float64 `json:"float"`
	Commission float64 `json:"commission"`
	Currency   string  `json:"currency"`
}

func fetchPOSBalance(phone string) (*POSBalance, error) {
	if posAPIURL == "" {
		return nil, errors.New("POS_API_URL not configured")
	}
	resp, err := posHTTP.Get(fmt.Sprintf("%s/api/v1/agents/balance?phone=%s", posAPIURL, url.QueryEscape(phone)))
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("POS API returned status %d", resp.StatusCode)
	}
	var bal POSBalance
	if err := json.NewDecoder(resp.Body).Decode(&bal); err != nil {
		return nil, err
	}
	return &bal, nil
}

// POSTxResult is the real execution outcome returned by the POS API.
type POSTxResult struct {
	Reference string `json:"reference"`
	Status    string `json:"status"`
	Error     string `json:"error"`
}

// forwardTransactionToPOS posts a CI/CO/TRF command to the POS API for real
// execution. The AT message ID is used as the idempotency key so carrier
// retries can never double-execute a money movement.
func forwardTransactionToPOS(sms InboundSMS, cmd SMSCommand) (*POSTxResult, error) {
	if posAPIURL == "" {
		return nil, errors.New("POS_API_URL not configured")
	}
	txType := map[string]string{"CI": "cash_in", "CO": "cash_out", "TRF": "transfer"}[cmd.Type]
	payload, _ := json.Marshal(map[string]interface{}{
		"type":       txType,
		"amount":     cmd.Amount,
		"agentPhone": sms.From,
		"recipient":  cmd.Receiver,
		"channel":    "sms",
	})
	req, err := http.NewRequest(http.MethodPost, posAPIURL+"/api/v1/transactions", bytes.NewReader(payload))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Idempotency-Key", sms.ID)
	resp, err := posHTTP.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	var result POSTxResult
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("POS API returned unreadable response (status %d)", resp.StatusCode)
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 || result.Reference == "" {
		if result.Error != "" {
			return nil, errors.New(result.Error)
		}
		return nil, fmt.Errorf("POS API returned status %d without a reference", resp.StatusCode)
	}
	return &result, nil
}

// forwardPINChangeToPOS submits a PIN change request to the POS/auth backend.
func forwardPINChangeToPOS(sms InboundSMS, cmd SMSCommand) error {
	if posAPIURL == "" {
		return errors.New("POS_API_URL not configured")
	}
	payload, _ := json.Marshal(map[string]string{
		"phone":   sms.From,
		"old_pin": cmd.OldPIN,
		"new_pin": cmd.NewPIN,
	})
	req, err := http.NewRequest(http.MethodPost, posAPIURL+"/api/v1/auth/change-pin", bytes.NewReader(payload))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Idempotency-Key", sms.ID)
	resp, err := posHTTP.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		var body struct {
			Error string `json:"error"`
		}
		json.NewDecoder(resp.Body).Decode(&body)
		if body.Error != "" {
			return errors.New(body.Error)
		}
		return fmt.Errorf("POS API returned status %d", resp.StatusCode)
	}
	return nil
}

// ── SMS Command Parser ───────────────────────────────────────────────────────

// parseSMSCommand parses a raw SMS text into a structured command.
// validate ensures the command format is correct before processing.
func parseSMSCommand(text string) SMSCommand {
	text = strings.TrimSpace(text)
	cmd := SMSCommand{Raw: text}

	parts := strings.Fields(strings.ToUpper(text))
	if len(parts) == 0 {
		cmd.Error = "Empty message"
		return cmd
	}

	cmd.Type = parts[0]

	switch cmd.Type {
	case "CI": // Cash In: CI <amount>
		if len(parts) < 2 {
			cmd.Error = "Usage: CI <amount>"
			return cmd
		}
		amount, err := strconv.ParseFloat(parts[1], 64)
		if err != nil || amount <= 0 {
			cmd.Error = "Invalid amount"
			return cmd
		}
		cmd.Amount = amount
		cmd.Valid = true

	case "CO": // Cash Out: CO <amount>
		if len(parts) < 2 {
			cmd.Error = "Usage: CO <amount>"
			return cmd
		}
		amount, err := strconv.ParseFloat(parts[1], 64)
		if err != nil || amount <= 0 {
			cmd.Error = "Invalid amount"
			return cmd
		}
		cmd.Amount = amount
		cmd.Valid = true

	case "BAL": // Balance check
		cmd.Valid = true

	case "TRF": // Transfer: TRF <phone> <amount>
		if len(parts) < 3 {
			cmd.Error = "Usage: TRF <phone> <amount>"
			return cmd
		}
		cmd.Receiver = parts[1]
		amount, err := strconv.ParseFloat(parts[2], 64)
		if err != nil || amount <= 0 {
			cmd.Error = "Invalid amount"
			return cmd
		}
		cmd.Amount = amount
		cmd.Valid = true

	case "HELP":
		cmd.Valid = true

	case "PIN": // PIN change: PIN <old> <new>
		if len(parts) < 3 {
			cmd.Error = "Usage: PIN <old_pin> <new_pin>"
			return cmd
		}
		cmd.OldPIN = parts[1]
		cmd.NewPIN = parts[2]
		if len(cmd.NewPIN) < 4 || len(cmd.NewPIN) > 6 {
			cmd.Error = "PIN must be 4-6 digits"
			return cmd
		}
		cmd.Valid = true

	default:
		cmd.Error = fmt.Sprintf("Unknown command: %s. Send HELP for options.", cmd.Type)
	}

	return cmd
}

// handleCommand executes a parsed command against the POS API and generates
// an SMS reply (max 160 chars). Success replies are only produced with real
// backend references; failures say so explicitly.
func handleCommand(sms InboundSMS, cmd SMSCommand) string {
	if !cmd.Valid {
		return truncate160(fmt.Sprintf("Error: %s\nSend HELP for commands.", cmd.Error))
	}

	switch cmd.Type {
	case "CI", "CO", "TRF":
		result, err := forwardTransactionToPOS(sms, cmd)
		if err != nil {
			log.Printf("[SMS] %s execution failed (from=%s): %v", cmd.Type, sms.From, err)
			return truncate160(fmt.Sprintf("%s could not be processed. No funds were moved. Please try again later.", cmdLabel(cmd.Type)))
		}
		if cmd.Type == "TRF" {
			return truncate160(fmt.Sprintf("Transfer NGN %.2f to %s successful.\nRef: %s", cmd.Amount, cmd.Receiver, result.Reference))
		}
		return truncate160(fmt.Sprintf("%s NGN %.2f successful.\nRef: %s", cmdLabel(cmd.Type), cmd.Amount, result.Reference))
	case "BAL":
		bal, err := fetchPOSBalance(sms.From)
		if err != nil {
			log.Printf("[SMS] balance lookup failed (from=%s): %v", sms.From, err)
			return truncate160("Balance service unavailable. Please try again later.")
		}
		currency := bal.Currency
		if currency == "" {
			currency = "NGN"
		}
		return truncate160(fmt.Sprintf("Balance: %s %.2f\nFloat: %s %.2f\nCommission: %s %.2f",
			currency, bal.Balance, currency, bal.Float, currency, bal.Commission))
	case "HELP":
		return truncate160("54agent SMS Commands:\nCI <amt> - Cash In\nCO <amt> - Cash Out\nBAL - Balance\nTRF <phone> <amt> - Transfer\nPIN <old> <new> - Change PIN")
	case "PIN":
		if err := forwardPINChangeToPOS(sms, cmd); err != nil {
			log.Printf("[SMS] PIN change failed (from=%s): %v", sms.From, err)
			return truncate160(fmt.Sprintf("PIN change failed: %s", err.Error()))
		}
		return truncate160("PIN changed successfully. Keep your PIN secret.")
	default:
		return truncate160("Unknown command. Send HELP for options.")
	}
}

func cmdLabel(t string) string {
	switch t {
	case "CI":
		return "Cash In"
	case "CO":
		return "Cash Out"
	case "TRF":
		return "Transfer"
	default:
		return t
	}
}

// truncate160 ensures SMS response fits within 160 character limit.
func truncate160(s string) string {
	if len(s) > 160 {
		return s[:157] + "..."
	}
	return s
}

// ── Delivery Tracking ────────────────────────────────────────────────────────

type DeliveryTracker struct {
	mu   sync.RWMutex
	logs map[string]*DeliveryLog
}

func NewDeliveryTracker() *DeliveryTracker {
	return &DeliveryTracker{logs: make(map[string]*DeliveryLog)}
}

func (dt *DeliveryTracker) Update(report DeliveryReport) {
	dt.mu.Lock()
	defer dt.mu.Unlock()
	dt.logs[report.ID] = &DeliveryLog{
		MessageID:  report.ID,
		Phone:      report.PhoneNumber,
		Status:     report.Status,
		FailReason: report.FailReason,
		RetryCount: report.RetryCount,
		UpdatedAt:  time.Now(),
	}
}

func (dt *DeliveryTracker) GetStats() map[string]int {
	dt.mu.RLock()
	defer dt.mu.RUnlock()
	stats := map[string]int{"total": 0, "success": 0, "failed": 0, "pending": 0}
	for _, log := range dt.logs {
		stats["total"]++
		switch log.Status {
		case "Success":
			stats["success"]++
		case "Failed", "Rejected":
			stats["failed"]++
		default:
			stats["pending"]++
		}
	}
	return stats
}

// ── HTTP Handlers ────────────────────────────────────────────────────────────

var tracker = NewDeliveryTracker()

func incomingSMSHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	if err := r.ParseForm(); err != nil {
		http.Error(w, "Bad request", http.StatusBadRequest)
		return
	}

	sms := InboundSMS{
		Date:        r.FormValue("date"),
		From:        r.FormValue("from"),
		ID:          r.FormValue("id"),
		LinkID:      r.FormValue("linkId"),
		Text:        r.FormValue("text"),
		To:          r.FormValue("to"),
		NetworkCode: r.FormValue("networkCode"),
	}

	log.Printf("[SMS-IN] from=%s text=%q network=%s", sms.From, sms.Text, sms.NetworkCode)

	cmd := parseSMSCommand(sms.Text)
	response := handleCommand(sms, cmd)

	log.Printf("[SMS-OUT] to=%s response=%q valid=%v", sms.From, response, cmd.Valid)

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"command":  cmd,
		"response": response,
		"from":     sms.From,
	})
}

func deliveryReportHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	if err := r.ParseForm(); err != nil {
		http.Error(w, "Bad request", http.StatusBadRequest)
		return
	}

	retryCount, _ := strconv.Atoi(r.FormValue("retryCount"))
	report := DeliveryReport{
		ID:          r.FormValue("id"),
		Status:      r.FormValue("status"),
		PhoneNumber: r.FormValue("phoneNumber"),
		NetworkCode: r.FormValue("networkCode"),
		FailReason:  r.FormValue("failureReason"),
		RetryCount:  retryCount,
	}

	log.Printf("[DLR] id=%s status=%s phone=%s reason=%s",
		report.ID, report.Status, report.PhoneNumber, report.FailReason)

	tracker.Update(report)

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"status": "received"})
}

func statusHandler(w http.ResponseWriter, r *http.Request) {
	stats := tracker.GetStats()
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"deliveryStats": stats,
		"service":       "at-sms-webhook",
	})
}

func healthHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"status":           "healthy",
		"service":          "at-sms-webhook",
		"version":          "1.0.0",
		"posApiConfigured": posAPIURL != "",
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
	port := getEnv("PORT", "9011")

	if posAPIURL == "" {
		log.Printf("[AT-SMS-Webhook] WARNING: POS_API_URL not set — all financial commands will fail closed")
	}

	http.HandleFunc("/sms/incoming", incomingSMSHandler)
	http.HandleFunc("/sms/delivery", deliveryReportHandler)
	http.HandleFunc("/sms/status", statusHandler)
	http.HandleFunc("/health", healthHandler)

	log.Printf("[AT-SMS-Webhook] Starting on :%s", port)
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
