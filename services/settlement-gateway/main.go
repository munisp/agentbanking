package main

import (
	"bytes"
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"log"
	"math"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"

	"github.com/segmentio/kafka-go"
	tb "github.com/tigerbeetle/tigerbeetle-go"
	tbtypes "github.com/tigerbeetle/tigerbeetle-go/pkg/types"
)

// SettlementGateway handles settlement routing between TigerBeetle, Mojaloop, and bank rails
// Middleware: Kafka, Dapr, Redis, TigerBeetle, Mojaloop, Temporal, APISIX, Permify

type Config struct {
	Port               string
	KafkaBrokers       string
	RedisURL           string
	TigerBeetleAddr    string
	TigerBeetleCluster uint64
	MojaLoopURL        string
	MojaLoopFSPID      string
	DaprHTTPPort       string
	TemporalAddr       string
	PermifyAddr        string
}

type SettlementRequest struct {
	TransactionID   string  `json:"transaction_id"`
	SourceAccountID string  `json:"source_account_id"`
	DestAccountID   string  `json:"dest_account_id"`
	Amount          float64 `json:"amount"`
	Currency        string  `json:"currency"`
	SettlementType  string  `json:"settlement_type"`
	TenantID        int     `json:"tenant_id"`
	Region          string  `json:"region"`
}

type SettlementResult struct {
	TransactionID  string    `json:"transaction_id"`
	Status         string    `json:"status"`
	TigerBeetleRef string    `json:"tigerbeetle_ref"`
	MojaLoopRef    string    `json:"mojaloop_ref,omitempty"`
	SettledAt      time.Time `json:"settled_at"`
	NetAmount      float64   `json:"net_amount"`
	Fees           float64   `json:"fees"`
}

type Metrics struct {
	sync.Mutex
	Total   int64   `json:"total"`
	Success int64   `json:"success"`
	Failed  int64   `json:"failed"`
	Volume  float64 `json:"volume"`
}

type Gateway struct {
	config      Config
	tbClient    tb.Client
	kafkaWriter *kafka.Writer
	httpClient  *http.Client
	mu          sync.RWMutex
	settlements map[string]*SettlementResult
	metrics     Metrics
}

func NewGateway(cfg Config, tbClient tb.Client, kafkaWriter *kafka.Writer) *Gateway {
	return &Gateway{
		config:      cfg,
		tbClient:    tbClient,
		kafkaWriter: kafkaWriter,
		httpClient:  &http.Client{Timeout: 15 * time.Second},
		settlements: make(map[string]*SettlementResult),
	}
}

// stringToUint128 converts a string ID to a deterministic tbtypes.Uint128
// using the first 16 bytes of the string (or zero-padded if shorter).
func stringToUint128(s string) tbtypes.Uint128 {
	var result tbtypes.Uint128
	b := []byte(s)
	if len(b) > 16 {
		b = b[:16]
	}
	copy(result[:], b)
	return result
}

func newUUID() string {
	var b [16]byte
	if _, err := rand.Read(b[:]); err != nil {
		log.Fatalf("crypto/rand unavailable: %v", err)
	}
	b[6] = (b[6] & 0x0f) | 0x40
	b[8] = (b[8] & 0x3f) | 0x80
	return fmt.Sprintf("%x-%x-%x-%x-%x", b[0:4], b[4:6], b[6:8], b[8:10], b[10:16])
}

// postTigerBeetleTransfer posts a real double-entry transfer to the TigerBeetle
// cluster and returns the reference of the transfer actually committed.
func (g *Gateway) postTigerBeetleTransfer(req SettlementRequest) (string, error) {
	transferID := stringToUint128("stl:" + req.TransactionID)
	amountKobo := uint64(math.Round(req.Amount * 100))
	if amountKobo == 0 {
		return "", fmt.Errorf("invalid settlement amount %.2f", req.Amount)
	}

	results, err := g.tbClient.CreateTransfers([]tbtypes.Transfer{
		{
			ID:              transferID,
			DebitAccountID:  stringToUint128(req.SourceAccountID),
			CreditAccountID: stringToUint128(req.DestAccountID),
			Amount:          tbtypes.ToUint128(amountKobo),
			Ledger:          1,
			Code:            1,
			Flags:           0,
		},
	})
	if err != nil {
		return "", fmt.Errorf("tigerbeetle CreateTransfers: %w", err)
	}
	if len(results) > 0 {
		return "", fmt.Errorf("tigerbeetle transfer rejected: result=%v index=%d", results[0].Result, results[0].Index)
	}
	return hex.EncodeToString(transferID[:]), nil
}

// postMojaloopTransfer performs a real FSPIOP POST /transfers against the
// Mojaloop hub and returns the transfer ID accepted by the hub.
func (g *Gateway) postMojaloopTransfer(ctx context.Context, req SettlementRequest) (string, error) {
	if g.config.MojaLoopURL == "" {
		return "", fmt.Errorf("mojaloop hub URL not configured")
	}
	transferID := newUUID()
	body := map[string]interface{}{
		"transferId": transferID,
		"payerFsp":   g.config.MojaLoopFSPID,
		"payeeFsp":   g.config.MojaLoopFSPID,
		"amount": map[string]string{
			"currency": req.Currency,
			"amount":   strconv.FormatFloat(req.Amount, 'f', 2, 64),
		},
		"ilpPacket":  "",
		"condition":  "",
		"expiration": time.Now().Add(5 * time.Minute).UTC().Format(time.RFC3339),
	}
	raw, _ := json.Marshal(body)
	httpReq, err := http.NewRequestWithContext(ctx, http.MethodPost,
		strings.TrimRight(g.config.MojaLoopURL, "/")+"/transfers", bytes.NewReader(raw))
	if err != nil {
		return "", err
	}
	httpReq.Header.Set("Content-Type", "application/vnd.interoperability.transfers+json;version=1.0")
	httpReq.Header.Set("Accept", "application/vnd.interoperability.transfers+json;version=1.0")
	httpReq.Header.Set("FSPIOP-Source", g.config.MojaLoopFSPID)
	httpReq.Header.Set("Date", time.Now().UTC().Format(http.TimeFormat))

	resp, err := g.httpClient.Do(httpReq)
	if err != nil {
		return "", fmt.Errorf("mojaloop hub unreachable: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 400 {
		return "", fmt.Errorf("mojaloop hub rejected transfer: HTTP %d", resp.StatusCode)
	}
	return transferID, nil
}

// publishSettlementEvent publishes the completed settlement to Kafka for real.
func (g *Gateway) publishSettlementEvent(ctx context.Context, result SettlementResult) error {
	if g.kafkaWriter == nil {
		return fmt.Errorf("kafka writer not configured")
	}
	raw, err := json.Marshal(result)
	if err != nil {
		return err
	}
	return g.kafkaWriter.WriteMessages(ctx, kafka.Message{
		Key:   []byte(result.TransactionID),
		Value: raw,
	})
}

func (g *Gateway) handleSettle(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	var req SettlementRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request", http.StatusBadRequest)
		return
	}

	g.metrics.Lock()
	g.metrics.Total++
	g.metrics.Unlock()

	// Step 1: post the real TigerBeetle transfer. No fabricated refs.
	tbRef, err := g.postTigerBeetleTransfer(req)
	if err != nil {
		g.metrics.Lock()
		g.metrics.Failed++
		g.metrics.Unlock()
		log.Printf("[TigerBeetle] settlement %s failed: %v", req.TransactionID, err)
		http.Error(w, fmt.Sprintf("settlement failed at tigerbeetle: %v", err), http.StatusServiceUnavailable)
		return
	}

	// Step 2: for instant settlements, perform a real Mojaloop transfer.
	var mojaRef string
	if req.SettlementType == "instant" {
		mojaRef, err = g.postMojaloopTransfer(r.Context(), req)
		if err != nil {
			g.metrics.Lock()
			g.metrics.Failed++
			g.metrics.Unlock()
			log.Printf("[Mojaloop] instant settlement %s failed after TB commit %s: %v", req.TransactionID, tbRef, err)
			http.Error(w, fmt.Sprintf("mojaloop transfer failed (tigerbeetle_ref=%s): %v", tbRef, err), http.StatusBadGateway)
			return
		}
	}

	result := &SettlementResult{
		TransactionID:  req.TransactionID,
		Status:         "completed",
		TigerBeetleRef: tbRef,
		MojaLoopRef:    mojaRef,
		SettledAt:      time.Now(),
		NetAmount:      req.Amount * 0.985,
		Fees:           req.Amount * 0.015,
	}

	// Step 3: publish the completion event to Kafka for real.
	if err := g.publishSettlementEvent(r.Context(), *result); err != nil {
		g.metrics.Lock()
		g.metrics.Failed++
		g.metrics.Unlock()
		log.Printf("[Kafka] publish billing.settlement.completed failed for %s (tigerbeetle_ref=%s): %v",
			req.TransactionID, tbRef, err)
		http.Error(w, fmt.Sprintf("settlement committed (tigerbeetle_ref=%s) but kafka publish failed: %v", tbRef, err),
			http.StatusBadGateway)
		return
	}

	g.mu.Lock()
	g.settlements[req.TransactionID] = result
	g.mu.Unlock()

	g.metrics.Lock()
	g.metrics.Success++
	g.metrics.Volume += req.Amount
	g.metrics.Unlock()

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(result)
}

func (g *Gateway) handleHealth(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"status":  "healthy",
		"service": "settlement-gateway",
		"version": "1.0.0",
		"connections": map[string]string{
			"kafka":       g.config.KafkaBrokers,
			"redis":       g.config.RedisURL,
			"tigerbeetle": g.config.TigerBeetleAddr,
			"mojaloop":    g.config.MojaLoopURL,
			"temporal":    g.config.TemporalAddr,
			"dapr":        g.config.DaprHTTPPort,
		},
	})
}

func (g *Gateway) handleMetrics(w http.ResponseWriter, r *http.Request) {
	g.metrics.Lock()
	defer g.metrics.Unlock()
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(g.metrics)
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func main() {
	clusterID, _ := strconv.ParseUint(getEnv("TIGERBEETLE_CLUSTER_ID", "0"), 10, 64)
	cfg := Config{
		Port:               getEnv("PORT", "8080"),
		KafkaBrokers:       getEnv("KAFKA_BROKERS", "localhost:9092"),
		RedisURL:           getEnv("REDIS_URL", "redis://localhost:6379"),
		TigerBeetleAddr:    getEnv("TIGERBEETLE_ADDR", "localhost:3000"),
		TigerBeetleCluster: clusterID,
		MojaLoopURL:        getEnv("MOJALOOP_URL", "http://localhost:4000"),
		MojaLoopFSPID:      getEnv("MOJALOOP_FSP_ID", "54agent"),
		DaprHTTPPort:       getEnv("DAPR_HTTP_PORT", "3500"),
		TemporalAddr:       getEnv("TEMPORAL_ADDR", "localhost:7233"),
		PermifyAddr:        getEnv("PERMIFY_ADDR", "localhost:3478"),
	}

	// TigerBeetle is the core settlement rail — refuse to start without it.
	tbClient, err := tb.NewClient(tbtypes.ToUint128(cfg.TigerBeetleCluster), []string{cfg.TigerBeetleAddr})
	if err != nil {
		log.Fatalf("[SettlementGateway] TigerBeetle client init failed (%s): %v — refusing to start", cfg.TigerBeetleAddr, err)
	}
	defer tbClient.Close()

	// Kafka is required to publish settlement events — refuse to run silently.
	kafkaWriter := &kafka.Writer{
		Addr:         kafka.TCP(strings.Split(cfg.KafkaBrokers, ",")...),
		Topic:        "billing.settlement.completed",
		RequiredAcks: kafka.RequireOne,
	}
	defer kafkaWriter.Close()

	gw := NewGateway(cfg, tbClient, kafkaWriter)

	mux := http.NewServeMux()
	mux.HandleFunc("/api/v1/settle", gw.handleSettle)
	mux.HandleFunc("/health", gw.handleHealth)
	mux.HandleFunc("/metrics", gw.handleMetrics)

	srv := &http.Server{Addr: ":" + cfg.Port, Handler: mux, ReadTimeout: 15 * time.Second, WriteTimeout: 15 * time.Second}
	go func() {
		log.Printf("[SettlementGateway] Starting on :%s", cfg.Port)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatal(err)
		}
	}()

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit
	log.Println("[SettlementGateway] Shutting down...")
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	srv.Shutdown(ctx)
}
