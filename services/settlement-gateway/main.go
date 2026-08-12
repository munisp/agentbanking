package main

import (
	"bytes"
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"

	tb "github.com/tigerbeetle/tigerbeetle-go"
	tbtypes "github.com/tigerbeetle/tigerbeetle-go/pkg/types"
)

// SettlementGateway handles settlement routing between TigerBeetle, Mojaloop, and bank rails
// Middleware: Kafka, Dapr, Redis, TigerBeetle, Mojaloop, Temporal, APISIX, Permify

type Config struct {
	Port              string
	KafkaBrokers      string
	KafkaRESTProxyURL string
	RedisURL          string
	TigerBeetleAddr   string
	TigerBeetleCluster string
	MojaLoopURL       string
	DaprHTTPPort      string
	TemporalAddr      string
	PermifyAddr       string
	FeeRatePct        float64
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
	httpClient  *http.Client
	mu          sync.RWMutex
	settlements map[string]*SettlementResult
	metrics     Metrics
}

func NewGateway(cfg Config, tbClient tb.Client) *Gateway {
	return &Gateway{
		config:      cfg,
		tbClient:    tbClient,
		httpClient:  &http.Client{Timeout: 15 * time.Second},
		settlements: make(map[string]*SettlementResult),
	}
}

// newUUID generates a random RFC-4122 v4 UUID using crypto/rand.
func newUUID() string {
	var b [16]byte
	if _, err := rand.Read(b[:]); err != nil {
		panic(err)
	}
	b[6] = (b[6] & 0x0f) | 0x40
	b[8] = (b[8] & 0x3f) | 0x80
	return fmt.Sprintf("%x-%x-%x-%x-%x", b[0:4], b[4:6], b[6:8], b[8:10], b[10:16])
}

// accountIDToUint128 maps an external account identifier to a deterministic
// TigerBeetle Uint128 account ID (same convention as tb-sidecar).
func accountIDToUint128(s string) tbtypes.Uint128 {
	var result tbtypes.Uint128
	b := []byte(s)
	if len(b) > 16 {
		b = b[:16]
	}
	copy(result[:], b)
	return result
}

func (g *Gateway) recordSuccess(amount float64) {
	g.metrics.Lock()
	g.metrics.Total++
	g.metrics.Success++
	g.metrics.Volume += amount
	g.metrics.Unlock()
}

func (g *Gateway) recordFailure(amount float64) {
	g.metrics.Lock()
	g.metrics.Total++
	g.metrics.Failed++
	g.metrics.Unlock()
}

// initiateMojaloopTransfer POSTs a real transfer to the Mojaloop hub and
// returns the transfer ID actually submitted. It never fabricates a reference.
func (g *Gateway) initiateMojaloopTransfer(req SettlementRequest, amountMinor uint64) (string, error) {
	if g.config.MojaLoopURL == "" {
		return "", fmt.Errorf("MOJALOOP_URL not configured")
	}
	transferID := newUUID()
	payload := map[string]interface{}{
		"transferId": transferID,
		"payerFsp":   getEnv("MOJALOOP_PAYER_FSP", "54agent"),
		"payeeFsp":   getEnv("MOJALOOP_PAYEE_FSP", "54agent"),
		"amount": map[string]string{
			"amount":   fmt.Sprintf("%d", amountMinor),
			"currency": req.Currency,
		},
		"expiration": time.Now().Add(5 * time.Minute).UTC().Format(time.RFC3339),
	}
	body, _ := json.Marshal(payload)
	httpReq, err := http.NewRequest(http.MethodPost,
		strings.TrimRight(g.config.MojaLoopURL, "/")+"/transfers", bytes.NewReader(body))
	if err != nil {
		return "", err
	}
	httpReq.Header.Set("Content-Type", "application/vnd.interoperability.transfers+json;version=1.1")
	httpReq.Header.Set("FSPIOP-Source", getEnv("MOJALOOP_PAYER_FSP", "54agent"))
	httpReq.Header.Set("Date", time.Now().UTC().Format(http.TimeFormat))

	resp, err := g.httpClient.Do(httpReq)
	if err != nil {
		return "", fmt.Errorf("mojaloop hub unreachable: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 300 {
		return "", fmt.Errorf("mojaloop hub returned status %d", resp.StatusCode)
	}
	log.Printf("[Mojaloop] Instant transfer %s submitted for tx %s", transferID, req.TransactionID)
	return transferID, nil
}

// publishSettlementEvent publishes the settlement result to Kafka (REST proxy)
// and Dapr pub/sub. Returns (true, nil) only when every configured channel
// accepted the event.
func (g *Gateway) publishSettlementEvent(result *SettlementResult) (bool, error) {
	published := false

	if g.config.KafkaRESTProxyURL != "" {
		payload := map[string]interface{}{
			"records": []map[string]interface{}{{"key": result.TransactionID, "value": result}},
		}
		body, _ := json.Marshal(payload)
		req, err := http.NewRequest(http.MethodPost,
			strings.TrimRight(g.config.KafkaRESTProxyURL, "/")+"/topics/billing.settlement.completed",
			bytes.NewReader(body))
		if err != nil {
			return false, err
		}
		req.Header.Set("Content-Type", "application/vnd.kafka.json.v2+json")
		resp, err := g.httpClient.Do(req)
		if err != nil {
			return false, fmt.Errorf("kafka rest proxy unreachable: %w", err)
		}
		defer resp.Body.Close()
		if resp.StatusCode >= 300 {
			return false, fmt.Errorf("kafka rest proxy returned status %d", resp.StatusCode)
		}
		published = true
		log.Printf("[Kafka] Published billing.settlement.completed: %s", result.TransactionID)
	} else {
		log.Printf("[Kafka] KAFKA_REST_PROXY_URL not configured — settlement event for %s NOT published", result.TransactionID)
	}

	if g.config.DaprHTTPPort != "" {
		body, _ := json.Marshal(result)
		resp, err := g.httpClient.Post(
			fmt.Sprintf("http://localhost:%s/v1.0/publish/pubsub/settlement-events", g.config.DaprHTTPPort),
			"application/json", bytes.NewReader(body))
		if err != nil {
			return false, fmt.Errorf("dapr pubsub unreachable: %w", err)
		}
		defer resp.Body.Close()
		if resp.StatusCode >= 300 {
			return false, fmt.Errorf("dapr pubsub returned status %d", resp.StatusCode)
		}
		published = true
		log.Printf("[Dapr] Published settlement-events: %s", result.TransactionID)
	}

	return published, nil
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
	if req.TransactionID == "" || req.SourceAccountID == "" || req.DestAccountID == "" {
		http.Error(w, "transaction_id, source_account_id and dest_account_id are required", http.StatusBadRequest)
		return
	}
	if req.Amount <= 0 {
		http.Error(w, "amount must be positive", http.StatusBadRequest)
		return
	}

	// Step 1: post a real double-entry transfer to the TigerBeetle cluster.
	amountMinor := uint64(req.Amount*100 + 0.5)
	tbTransferID := tbtypes.ID()
	results, err := g.tbClient.CreateTransfers([]tbtypes.Transfer{{
		ID:              tbTransferID,
		DebitAccountID:  accountIDToUint128(req.SourceAccountID),
		CreditAccountID: accountIDToUint128(req.DestAccountID),
		Amount:          tbtypes.ToUint128(amountMinor),
		Ledger:          1,
		Code:            1,
	}})
	if err != nil {
		g.recordFailure(req.Amount)
		log.Printf("[TigerBeetle] UNREACHABLE for tx %s: %v", req.TransactionID, err)
		http.Error(w, fmt.Sprintf(`{"error":"tigerbeetle_unreachable","detail":%q}`, err.Error()), http.StatusBadGateway)
		return
	}
	if len(results) > 0 {
		g.recordFailure(req.Amount)
		log.Printf("[TigerBeetle] Transfer REJECTED for tx %s: %v", req.TransactionID, results[0].Result)
		http.Error(w, fmt.Sprintf(`{"error":"tigerbeetle_transfer_rejected","result":%q}`, fmt.Sprint(results[0].Result)), http.StatusBadGateway)
		return
	}
	idBytes := [16]byte(tbTransferID)
	tbRef := hex.EncodeToString(idBytes[:])
	log.Printf("[TigerBeetle] Transfer %s committed: %d minor units %s", tbRef, amountMinor, req.Currency)

	// Step 2: for instant settlement, initiate a real Mojaloop transfer and only
	// report the reference that was actually submitted and accepted.
	var mojaRef string
	if req.SettlementType == "instant" {
		ref, err := g.initiateMojaloopTransfer(req, amountMinor)
		if err != nil {
			g.recordFailure(req.Amount)
			log.Printf("[Mojaloop] Instant transfer FAILED for tx %s: %v", req.TransactionID, err)
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusBadGateway)
			json.NewEncoder(w).Encode(map[string]interface{}{
				"error":            "mojaloop_settlement_failed",
				"detail":           err.Error(),
				"tigerbeetle_ref":  tbRef, // TB leg is committed; surfaced for ops reconciliation
				"transaction_id":   req.TransactionID,
			})
			return
		}
		mojaRef = ref
	}

	fees := req.Amount * (g.config.FeeRatePct / 100.0)
	result := &SettlementResult{
		TransactionID:  req.TransactionID,
		Status:         "completed",
		TigerBeetleRef: tbRef,
		MojaLoopRef:    mojaRef,
		SettledAt:      time.Now(),
		NetAmount:      req.Amount - fees,
		Fees:           fees,
	}
	g.mu.Lock()
	g.settlements[req.TransactionID] = result
	g.mu.Unlock()

	// Step 3: publish the settlement event. A publication failure is surfaced to
	// the caller — never logged as if it happened.
	published, pubErr := g.publishSettlementEvent(result)
	if pubErr != nil {
		g.recordFailure(req.Amount)
		log.Printf("[Kafka] Publish FAILED for %s: %v", req.TransactionID, pubErr)
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusBadGateway)
		json.NewEncoder(w).Encode(map[string]interface{}{
			"error":      "settlement_event_publish_failed",
			"detail":     pubErr.Error(),
			"settlement": result,
		})
		return
	}

	g.recordSuccess(req.Amount)
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"settlement":      result,
		"event_published": published,
	})
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
	feeRate, err := strconv.ParseFloat(getEnv("FEE_RATE_PCT", "1.5"), 64)
	if err != nil {
		log.Fatalf("[SettlementGateway] Invalid FEE_RATE_PCT: %v", err)
	}
	cfg := Config{
		Port:               getEnv("PORT", "8080"),
		KafkaBrokers:       getEnv("KAFKA_BROKERS", "localhost:9092"),
		KafkaRESTProxyURL:  getEnv("KAFKA_REST_PROXY_URL", ""),
		RedisURL:           getEnv("REDIS_URL", "redis://localhost:6379"),
		TigerBeetleAddr:    getEnv("TB_ADDRESSES", getEnv("TIGERBEETLE_ADDR", "localhost:3000")),
		TigerBeetleCluster: getEnv("TB_CLUSTER_ID", "0"),
		MojaLoopURL:        getEnv("MOJALOOP_URL", "http://localhost:4000"),
		DaprHTTPPort:       getEnv("DAPR_HTTP_PORT", ""),
		TemporalAddr:       getEnv("TEMPORAL_ADDR", "localhost:7233"),
		PermifyAddr:        getEnv("PERMIFY_ADDR", "localhost:3478"),
		FeeRatePct:         feeRate,
	}

	// Refuse to start without a live TigerBeetle cluster connection — an in-memory
	// or unreachable ledger would silently fabricate settlements.
	addresses := strings.Split(cfg.TigerBeetleAddr, ",")
	clusterID, err := strconv.ParseUint(cfg.TigerBeetleCluster, 10, 64)
	if err != nil {
		log.Fatalf("[SettlementGateway] Invalid TB_CLUSTER_ID %q: %v", cfg.TigerBeetleCluster, err)
	}
	tbClient, err := tb.NewClient(tbtypes.ToUint128(clusterID), addresses)
	if err != nil {
		log.Fatalf("[SettlementGateway] Refusing to start: cannot connect to TigerBeetle cluster at %v: %v", addresses, err)
	}
	defer tbClient.Close()

	gw := NewGateway(cfg, tbClient)

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
