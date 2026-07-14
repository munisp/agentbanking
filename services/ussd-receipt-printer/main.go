// USSD Receipt Printer Service — Sprint 76
// Auto-generates thermal receipts for completed *384# USSD transactions
// Connects to Kafka for transaction events, Redis for template cache
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

const (
	ServiceName    = "ussd-receipt-printer"
	ServiceVersion = "1.0.0"
	DefaultPort    = "9100"
	ReceiptWidth   = 32 // characters for thermal printer
)

type ReceiptTemplate struct {
	ID       string `json:"id"`
	Name     string `json:"name"`
	Header   string `json:"header"`
	Footer   string `json:"footer"`
	Locale   string `json:"locale"`
	Currency string `json:"currency"`
}

type USSDTransaction struct {
	ID            string  `json:"id"`
	Type          string  `json:"type"` // cash_in, cash_out, balance, transfer, airtime, bills
	Amount        float64 `json:"amount"`
	Currency      string  `json:"currency"`
	AgentID       string  `json:"agentId"`
	AgentName     string  `json:"agentName"`
	CustomerPhone string  `json:"customerPhone"`
	Carrier       string  `json:"carrier"`
	ShortCode     string  `json:"shortCode"`
	SessionID     string  `json:"sessionId"`
	Reference     string  `json:"reference"`
	Status        string  `json:"status"`
	Timestamp     int64   `json:"timestamp"`
	Region        string  `json:"region"`
	Country       string  `json:"country"`
}

type Receipt struct {
	ID          string `json:"id"`
	TxID        string `json:"txId"`
	Content     string `json:"content"`
	PrintStatus string `json:"printStatus"`
	CreatedAt   int64  `json:"createdAt"`
	PrintedAt   int64  `json:"printedAt,omitempty"`
}

type ReceiptService struct {
	mu        sync.RWMutex
	receipts  map[string]*Receipt
	templates map[string]*ReceiptTemplate
	kafkaAddr string
	redisAddr string
}

func NewReceiptService() *ReceiptService {
	svc := &ReceiptService{
		receipts:  make(map[string]*Receipt),
		templates: make(map[string]*ReceiptTemplate),
		kafkaAddr: getEnv("KAFKA_BROKER", "localhost:9092"),
		redisAddr: getEnv("REDIS_URL", "localhost:6379"),
	}
	svc.loadDefaultTemplates()
	return svc
}

func (s *ReceiptService) loadDefaultTemplates() {
	templates := []ReceiptTemplate{
		{ID: "default_en", Name: "English Default", Header: "54agent POS SERVICES", Footer: "Thank you for banking with 54agent", Locale: "en", Currency: "NGN"},
		{ID: "default_fr", Name: "French Default", Header: "SERVICES POS 54agent", Footer: "Merci d'utiliser 54agent", Locale: "fr", Currency: "XOF"},
		{ID: "default_sw", Name: "Swahili Default", Header: "HUDUMA ZA POS 54agent", Footer: "Asante kwa kutumia 54agent", Locale: "sw", Currency: "KES"},
		{ID: "default_ha", Name: "Hausa Default", Header: "SABIS NA POS 54agent", Footer: "Na gode da amfani da 54agent", Locale: "ha", Currency: "NGN"},
		{ID: "default_yo", Name: "Yoruba Default", Header: "ISE POS 54agent", Footer: "E se fun lilo 54agent", Locale: "yo", Currency: "NGN"},
	}
	for _, t := range templates {
		tc := t
		s.templates[t.ID] = &tc
	}
}

func (s *ReceiptService) GenerateReceipt(tx USSDTransaction) *Receipt {
	template := s.getTemplate(tx.Country)
	content := s.formatReceipt(tx, template)
	receipt := &Receipt{
		ID:          fmt.Sprintf("RCP-%d-%s", time.Now().UnixMilli(), tx.ID[:8]),
		TxID:        tx.ID,
		Content:     content,
		PrintStatus: "queued",
		CreatedAt:   time.Now().UnixMilli(),
	}
	s.mu.Lock()
	s.receipts[receipt.ID] = receipt
	s.mu.Unlock()
	return receipt
}

func (s *ReceiptService) getTemplate(country string) *ReceiptTemplate {
	localeMap := map[string]string{"NG": "default_en", "KE": "default_sw", "SN": "default_fr", "GH": "default_en", "ZA": "default_en"}
	if id, ok := localeMap[country]; ok {
		if t, exists := s.templates[id]; exists {
			return t
		}
	}
	return s.templates["default_en"]
}

func (s *ReceiptService) formatReceipt(tx USSDTransaction, tmpl *ReceiptTemplate) string {
	sep := strings.Repeat("=", ReceiptWidth)
	dash := strings.Repeat("-", ReceiptWidth)
	txTypeNames := map[string]string{
		"cash_in": "CASH IN", "cash_out": "CASH OUT", "balance": "BALANCE INQUIRY",
		"transfer": "TRANSFER", "airtime": "AIRTIME", "bills": "BILL PAYMENT",
	}
	txName := txTypeNames[tx.Type]
	if txName == "" {
		txName = strings.ToUpper(tx.Type)
	}
	ts := time.UnixMilli(tx.Timestamp).Format("2006-01-02 15:04:05")
	lines := []string{
		sep, center(tmpl.Header, ReceiptWidth), center(txName, ReceiptWidth), sep,
		fmt.Sprintf("Ref:    %s", tx.Reference), fmt.Sprintf("Date:   %s", ts),
		fmt.Sprintf("Agent:  %s", tx.AgentName), fmt.Sprintf("Phone:  %s", maskPhone(tx.CustomerPhone)),
		dash, fmt.Sprintf("Amount: %s %.2f", tx.Currency, tx.Amount),
		fmt.Sprintf("Status: %s", strings.ToUpper(tx.Status)),
		fmt.Sprintf("Via:    USSD %s", tx.ShortCode), fmt.Sprintf("Net:    %s", tx.Carrier),
		dash, center(tmpl.Footer, ReceiptWidth), sep,
	}
	return strings.Join(lines, "\n")
}

func center(s string, w int) string {
	if len(s) >= w {
		return s[:w]
	}
	pad := (w - len(s)) / 2
	return strings.Repeat(" ", pad) + s + strings.Repeat(" ", w-pad-len(s))
}

func maskPhone(phone string) string {
	if len(phone) < 6 {
		return phone
	}
	return phone[:3] + strings.Repeat("*", len(phone)-6) + phone[len(phone)-3:]
}

func getEnv(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}

func main() {
	svc := NewReceiptService()
	mux := http.NewServeMux()

	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(map[string]interface{}{
			"service": ServiceName, "version": ServiceVersion, "status": "healthy",
			"templates": len(svc.templates), "receipts": len(svc.receipts),
		})
	})

	mux.HandleFunc("/api/receipt/generate", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}
		var tx USSDTransaction
		if err := json.NewDecoder(r.Body).Decode(&tx); err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}
		receipt := svc.GenerateReceipt(tx)
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(receipt)
	})

	mux.HandleFunc("/api/receipt/print", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}
		var req struct {
			ReceiptID string `json:"receiptId"`
		}
		json.NewDecoder(r.Body).Decode(&req)
		svc.mu.Lock()
		if rcp, ok := svc.receipts[req.ReceiptID]; ok {
			rcp.PrintStatus = "printed"
			rcp.PrintedAt = time.Now().UnixMilli()
		}
		svc.mu.Unlock()
		json.NewEncoder(w).Encode(map[string]string{"status": "printed"})
	})

	mux.HandleFunc("/api/templates", func(w http.ResponseWriter, r *http.Request) {
		svc.mu.RLock()
		defer svc.mu.RUnlock()
		templates := make([]*ReceiptTemplate, 0, len(svc.templates))
		for _, t := range svc.templates {
			templates = append(templates, t)
		}
		json.NewEncoder(w).Encode(templates)
	})

	port := getEnv("PORT", DefaultPort)
	log.Printf("[%s] v%s listening on :%s (kafka=%s redis=%s)", ServiceName, ServiceVersion, port, svc.kafkaAddr, svc.redisAddr)
	log.Fatal(http.ListenAndServe(":"+port, mux))
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
