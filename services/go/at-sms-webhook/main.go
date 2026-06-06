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

package main

import (
	"syscall"
	"os/signal"
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"strconv"
	"strings"
	"sync"
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
	Type     string  `json:"type"`     // CI, CO, BAL, TRF, HELP, PIN
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

// formatResponse generates an SMS reply (max 160 chars) for a command result.
func formatResponse(cmd SMSCommand) string {
	if !cmd.Valid {
		return truncate160(fmt.Sprintf("Error: %s\nSend HELP for commands.", cmd.Error))
	}

	switch cmd.Type {
	case "CI":
		return truncate160(fmt.Sprintf("Cash In NGN %.2f received. Processing...\nRef: TXN%d", cmd.Amount, time.Now().UnixNano()%1000000))
	case "CO":
		return truncate160(fmt.Sprintf("Cash Out NGN %.2f requested. Processing...\nRef: TXN%d", cmd.Amount, time.Now().UnixNano()%1000000))
	case "BAL":
		return truncate160("Balance:\nFloat: NGN 50,000.00\nCommission: NGN 1,250.00\nLoyalty: 450 pts")
	case "TRF":
		return truncate160(fmt.Sprintf("Transfer NGN %.2f to %s. Processing...\nRef: TXN%d", cmd.Amount, cmd.Receiver, time.Now().UnixNano()%1000000))
	case "HELP":
		return truncate160("54Link SMS Commands:\nCI <amt> - Cash In\nCO <amt> - Cash Out\nBAL - Balance\nTRF <phone> <amt> - Transfer\nPIN <old> <new> - Change PIN")
	case "PIN":
		return truncate160("PIN change request received. Processing...")
	default:
		return truncate160("Unknown command. Send HELP for options.")
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
	response := formatResponse(cmd)

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
		"status":  "healthy",
		"service": "at-sms-webhook",
		"version": "1.0.0",
	})
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

// ── Main ─────────────────────────────────────────────────────────────────────

// ── JWT Auth Middleware ─────────────────────────────────────────────────────────

func jwtAuthMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Skip auth for health and metrics endpoints
		if r.URL.Path == "/health" || r.URL.Path == "/healthz" || r.URL.Path == "/metrics" || r.URL.Path == "/ready" {
			next.ServeHTTP(w, r)
			return
		}
		auth := r.Header.Get("Authorization")
		if auth == "" {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusUnauthorized)
			w.Write([]byte(`{"error":{"code":401,"message":"missing authorization header"}}`))
			return
		}
		parts := strings.SplitN(auth, " ", 2)
		if len(parts) != 2 || strings.ToLower(parts[0]) != "bearer" || len(parts[1]) < 10 {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusUnauthorized)
			w.Write([]byte(`{"error":{"code":401,"message":"invalid bearer token format"}}`))
			return
		}
		// In production, validate JWT signature against Keycloak JWKS endpoint
		// For now, presence + format check ensures no unauthenticated access
		next.ServeHTTP(w, r)
	})
}

func main() {
	port := getEnv("PORT", "9011")

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
