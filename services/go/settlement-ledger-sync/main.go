// Package main implements the Settlement Ledger Sync service.
// Synchronizes billing ledger entries with TigerBeetle double-entry accounting,
// publishes settlement events to Kafka, and interfaces with Mojaloop for
// interbank settlement finality. Uses Dapr for service-to-service communication.
// Persistence: PostgreSQL (all state — NO in-memory slices)
// Integrates with: TigerBeetle, Kafka, Mojaloop, Dapr, PostgreSQL, Redis, APISIX, OpenSearch
package main

import (
	"bytes"
	"database/sql"
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"sync/atomic"
	"syscall"
	"time"

	_ "github.com/lib/pq"
)

type Config struct {
	Port               string
	PostgresURL        string
	TigerBeetleAddr    string
	TigerBeetleCluster uint32
	KafkaBrokers       string
	MojaloopHubURL     string
	MojaloopFSPID      string
	DaprHTTPPort       string
	RedisAddr          string
	APISIXAdminURL     string
	OpenSearchURL      string
	SyncInterval       time.Duration
}

func loadConfig() *Config {
	return &Config{
		Port:               getEnv("PORT", "9102"),
		PostgresURL:        getEnv("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/settlement_ledger_sync?sslmode=disable"),
		TigerBeetleAddr:    getEnv("TIGERBEETLE_ADDR", "tigerbeetle:3000"),
		TigerBeetleCluster: 0,
		KafkaBrokers:       getEnv("KAFKA_BROKERS", "kafka:9092"),
		MojaloopHubURL:     getEnv("MOJALOOP_HUB_URL", "http://mojaloop-hub:4003"),
		MojaloopFSPID:      getEnv("MOJALOOP_FSP_ID", "54link"),
		DaprHTTPPort:       getEnv("DAPR_HTTP_PORT", "3500"),
		RedisAddr:          getEnv("REDIS_ADDR", "redis:6379"),
		APISIXAdminURL:     getEnv("APISIX_ADMIN_URL", "http://apisix:9180"),
		OpenSearchURL:      getEnv("OPENSEARCH_URL", "http://localhost:9200"),
		SyncInterval:       30 * time.Second,
	}
}

// ═══════════════════════════════════════════════════════════════════════════════
// Domain Models
// ═══════════════════════════════════════════════════════════════════════════════

type LedgerEntryType string

const (
	EntryDebit  LedgerEntryType = "debit"
	EntryCredit LedgerEntryType = "credit"
)

type SettlementState string

const (
	StatePending   SettlementState = "pending"
	StateCommitted SettlementState = "committed"
	StateSettled   SettlementState = "settled"
	StateFailed    SettlementState = "failed"
)

type BillingLedgerEntry struct {
	ID              int64   `json:"id"`
	TransactionID   string  `json:"transactionId"`
	AgentID         string  `json:"agentId"`
	ClientID        string  `json:"clientId"`
	TransactionType string  `json:"transactionType"`
	GrossAmount     int64   `json:"grossAmount"`
	GrossFee        int64   `json:"grossFee"`
	PlatformShare   int64   `json:"platformShare"`
	ClientShare     int64   `json:"clientShare"`
	AgentCommission int64   `json:"agentCommission"`
	Currency        string  `json:"currency"`
	BillingModel    string  `json:"billingModel"`
	SyncStatus      string  `json:"syncStatus"`
	ProcessedAt     time.Time `json:"processedAt"`
}

type MojaloopTransfer struct {
	TransferID string `json:"transferId"`
	PayerFSP   string `json:"payerFsp"`
	PayeeFSP   string `json:"payeeFsp"`
	Amount     string `json:"amount"`
	Currency   string `json:"currency"`
	Condition  string `json:"condition"`
	Expiration string `json:"expiration"`
	ILPPacket  string `json:"ilpPacket"`
}

type SettlementBatch struct {
	BatchID       string          `json:"batchId"`
	Period        string          `json:"period"`
	State         SettlementState `json:"state"`
	EntryCount    int             `json:"entryCount"`
	TotalAmount   int64           `json:"totalAmount"`
	PlatformTotal int64           `json:"platformTotal"`
	ClientTotal   int64           `json:"clientTotal"`
	CreatedAt     time.Time       `json:"createdAt"`
	CommittedAt   *time.Time      `json:"committedAt,omitempty"`
	SettledAt     *time.Time      `json:"settledAt,omitempty"`
}

// ═══════════════════════════════════════════════════════════════════════════════
// PostgreSQL Persistence
// ═══════════════════════════════════════════════════════════════════════════════

var pgDB *sql.DB

func initDB(connStr string) {
	var err error
	pgDB, err = sql.Open("postgres", connStr)
	if err != nil {
		log.Printf("[LedgerSync] DB warning: %v", err)
		return
	}
	pgDB.SetMaxOpenConns(15)
	pgDB.SetMaxIdleConns(5)
	pgDB.SetConnMaxLifetime(5 * time.Minute)

	pgDB.Exec(`CREATE TABLE IF NOT EXISTS billing_ledger_entries (
		id SERIAL PRIMARY KEY,
		transaction_id TEXT UNIQUE NOT NULL,
		agent_id TEXT NOT NULL,
		client_id TEXT NOT NULL,
		transaction_type TEXT NOT NULL,
		gross_amount BIGINT NOT NULL,
		gross_fee BIGINT NOT NULL DEFAULT 0,
		platform_share BIGINT NOT NULL DEFAULT 0,
		client_share BIGINT NOT NULL DEFAULT 0,
		agent_commission BIGINT NOT NULL DEFAULT 0,
		currency TEXT NOT NULL DEFAULT 'NGN',
		billing_model TEXT NOT NULL DEFAULT 'revenue_share',
		sync_status TEXT NOT NULL DEFAULT 'pending',
		processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
		synced_at TIMESTAMPTZ
	)`)
	pgDB.Exec(`CREATE INDEX IF NOT EXISTS idx_ble_sync_status ON billing_ledger_entries(sync_status)`)
	pgDB.Exec(`CREATE INDEX IF NOT EXISTS idx_ble_processed ON billing_ledger_entries(processed_at)`)

	pgDB.Exec(`CREATE TABLE IF NOT EXISTS ledger_settlement_batches (
		batch_id TEXT PRIMARY KEY,
		period TEXT NOT NULL,
		state TEXT NOT NULL DEFAULT 'pending',
		entry_count INT NOT NULL DEFAULT 0,
		total_amount BIGINT NOT NULL DEFAULT 0,
		platform_total BIGINT NOT NULL DEFAULT 0,
		client_total BIGINT NOT NULL DEFAULT 0,
		created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
		committed_at TIMESTAMPTZ,
		settled_at TIMESTAMPTZ
	)`)
	pgDB.Exec(`CREATE INDEX IF NOT EXISTS idx_lsb_state ON ledger_settlement_batches(state)`)

	pgDB.Exec(`CREATE TABLE IF NOT EXISTS tb_sync_log (
		id SERIAL PRIMARY KEY,
		batch_id TEXT NOT NULL,
		entry_id INT NOT NULL,
		tb_transfer_status TEXT NOT NULL DEFAULT 'pending',
		mojaloop_status TEXT DEFAULT NULL,
		kafka_status TEXT DEFAULT NULL,
		error_message TEXT,
		created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
	)`)

	pgDB.Exec(`CREATE TABLE IF NOT EXISTS ledger_sync_metrics (
		id SERIAL PRIMARY KEY,
		sync_count BIGINT NOT NULL DEFAULT 0,
		total_synced BIGINT NOT NULL DEFAULT 0,
		last_sync TIMESTAMPTZ,
		updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
	)`)
	pgDB.Exec(`INSERT INTO ledger_sync_metrics (sync_count, total_synced) VALUES (0, 0) ON CONFLICT DO NOTHING`)

	log.Println("[LedgerSync] PostgreSQL tables initialized")
}

// ═══════════════════════════════════════════════════════════════════════════════
// Settlement Ledger Sync Engine (PostgreSQL-backed)
// ═══════════════════════════════════════════════════════════════════════════════

type LedgerSyncEngine struct {
	config    *Config
	syncCount int64
}

func NewLedgerSyncEngine(cfg *Config) *LedgerSyncEngine {
	return &LedgerSyncEngine{config: cfg}
}

func (lse *LedgerSyncEngine) SyncPendingEntries(ctx context.Context) error {
	log.Println("[LedgerSync] Starting sync cycle")

	if pgDB == nil {
		return fmt.Errorf("database not available")
	}

	// Step 1: Fetch pending entries from billing ledger
	rows, err := pgDB.QueryContext(ctx, `SELECT id, transaction_id, agent_id, client_id, transaction_type,
		gross_amount, gross_fee, platform_share, client_share, agent_commission, currency, billing_model
		FROM billing_ledger_entries WHERE sync_status='pending' ORDER BY processed_at LIMIT 1000 FOR UPDATE SKIP LOCKED`)
	if err != nil {
		return fmt.Errorf("fetch pending entries: %w", err)
	}
	defer rows.Close()

	var entries []BillingLedgerEntry
	for rows.Next() {
		var e BillingLedgerEntry
		err := rows.Scan(&e.ID, &e.TransactionID, &e.AgentID, &e.ClientID,
			&e.TransactionType, &e.GrossAmount, &e.GrossFee,
			&e.PlatformShare, &e.ClientShare, &e.AgentCommission,
			&e.Currency, &e.BillingModel)
		if err != nil {
			continue
		}
		entries = append(entries, e)
	}

	if len(entries) == 0 {
		log.Println("[LedgerSync] No pending entries to sync")
		return nil
	}

	// Step 2: Create TigerBeetle transfers for each entry
	for _, entry := range entries {
		tbErr := lse.createTigerBeetleTransfer(entry)
		status := "synced"
		errMsg := ""
		if tbErr != nil {
			status = "failed"
			errMsg = tbErr.Error()
			log.Printf("[LedgerSync] TigerBeetle transfer failed for tx %s: %v", entry.TransactionID, tbErr)
		}
		pgDB.Exec(`UPDATE billing_ledger_entries SET sync_status=$1, synced_at=NOW() WHERE id=$2`, status, entry.ID)
		pgDB.Exec(`INSERT INTO tb_sync_log (batch_id, entry_id, tb_transfer_status, error_message) VALUES ($1, $2, $3, $4)`,
			fmt.Sprintf("sync_%d", time.Now().Unix()), entry.ID, status, errMsg)
	}

	// Step 3: Batch entries for settlement
	batch := lse.createSettlementBatch(entries)

	// Step 4: Persist batch to PostgreSQL
	now := time.Now()
	pgDB.Exec(`INSERT INTO ledger_settlement_batches (batch_id, period, state, entry_count, total_amount, platform_total, client_total, committed_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
		ON CONFLICT (batch_id) DO UPDATE SET state=$3, entry_count=$4, total_amount=$5, committed_at=$8`,
		batch.BatchID, batch.Period, batch.State, batch.EntryCount,
		batch.TotalAmount, batch.PlatformTotal, batch.ClientTotal, now)

	// Step 5: Publish to Kafka
	lse.publishSettlementEvent(batch)

	// Step 6: Update sync metrics
	atomic.AddInt64(&lse.syncCount, 1)
	pgDB.Exec(`UPDATE ledger_sync_metrics SET sync_count=sync_count+1, total_synced=total_synced+$1, last_sync=NOW(), updated_at=NOW()`, len(entries))

	log.Printf("[LedgerSync] Synced %d entries in batch %s", len(entries), batch.BatchID)
	return nil
}

func (lse *LedgerSyncEngine) createTigerBeetleTransfer(entry BillingLedgerEntry) error {
	tbCoreURL := getEnv("TB_CORE_URL", "http://tigerbeetle-core:8080")

	transfers := []map[string]interface{}{
		{"id": entry.ID*10 + 1, "debit_account_id": 1000, "credit_account_id": 4010, "amount": entry.PlatformShare, "ledger": 1, "code": 1},
		{"id": entry.ID*10 + 2, "debit_account_id": 1000, "credit_account_id": 4011, "amount": entry.ClientShare, "ledger": 1, "code": 2},
		{"id": entry.ID*10 + 3, "debit_account_id": 4011, "credit_account_id": 4012, "amount": entry.AgentCommission, "ledger": 1, "code": 3},
	}

	data, _ := json.Marshal(transfers)
	resp, err := http.Post(fmt.Sprintf("%s/api/v1/transfers", tbCoreURL), "application/json", bytes.NewReader(data))
	if err != nil {
		return fmt.Errorf("TB core request: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 400 {
		return fmt.Errorf("TB core status: %d", resp.StatusCode)
	}

	log.Printf("[TigerBeetle] Double-entry transfers for tx %s: platform=%d, client=%d, agent=%d",
		entry.TransactionID, entry.PlatformShare, entry.ClientShare, entry.AgentCommission)
	return nil
}

func (lse *LedgerSyncEngine) createSettlementBatch(entries []BillingLedgerEntry) SettlementBatch {
	var totalAmount, platformTotal, clientTotal int64
	for _, e := range entries {
		totalAmount += e.GrossAmount
		platformTotal += e.PlatformShare
		clientTotal += e.ClientShare
	}

	now := time.Now()
	return SettlementBatch{
		BatchID:       fmt.Sprintf("BATCH-%d-%02d-%d", now.Year(), now.Month(), now.UnixMilli()),
		Period:        fmt.Sprintf("%d-%02d", now.Year(), now.Month()),
		State:         StateCommitted,
		EntryCount:    len(entries),
		TotalAmount:   totalAmount,
		PlatformTotal: platformTotal,
		ClientTotal:   clientTotal,
		CreatedAt:     now,
		CommittedAt:   &now,
	}
}

func (lse *LedgerSyncEngine) publishSettlementEvent(batch SettlementBatch) {
	data, _ := json.Marshal(batch)

	// Kafka via Dapr
	go func() {
		url := fmt.Sprintf("http://localhost:%s/v1.0/publish/kafka-pubsub/billing.settlement.committed", lse.config.DaprHTTPPort)
		http.Post(url, "application/json", bytes.NewReader(data))
	}()
	// Dapr pub/sub
	go func() {
		url := fmt.Sprintf("http://localhost:%s/v1.0/publish/pubsub/settlement.batch.committed", lse.config.DaprHTTPPort)
		http.Post(url, "application/json", bytes.NewReader(data))
	}()
	// OpenSearch
	go func() {
		idx := fmt.Sprintf("settlement-batches-%s", time.Now().Format("2006.01"))
		url := fmt.Sprintf("%s/%s/_doc/%s", lse.config.OpenSearchURL, idx, batch.BatchID)
		req, _ := http.NewRequest("PUT", url, bytes.NewReader(data))
		req.Header.Set("Content-Type", "application/json")
		http.DefaultClient.Do(req)
	}()

	log.Printf("[Kafka] Published settlement batch %s: %d entries, total=%d", batch.BatchID, batch.EntryCount, batch.TotalAmount)
}

func (lse *LedgerSyncEngine) InitiateMojaloopSettlement(batchID string) error {
	if pgDB == nil {
		return fmt.Errorf("database not available")
	}

	var batch SettlementBatch
	err := pgDB.QueryRow(`SELECT batch_id, period, state, entry_count, total_amount, platform_total, client_total
		FROM ledger_settlement_batches WHERE batch_id=$1`, batchID).Scan(
		&batch.BatchID, &batch.Period, &batch.State, &batch.EntryCount,
		&batch.TotalAmount, &batch.PlatformTotal, &batch.ClientTotal)
	if err != nil {
		return fmt.Errorf("batch not found: %w", err)
	}

	payload := MojaloopTransfer{
		TransferID: batchID,
		PayerFSP:   lse.config.MojaloopFSPID,
		PayeeFSP:   "settlement-bank",
		Amount:     fmt.Sprintf("%.2f", float64(batch.TotalAmount)/100.0),
		Currency:   "NGN",
		Condition:  fmt.Sprintf("cond_%s", batchID),
		Expiration: time.Now().Add(24 * time.Hour).Format(time.RFC3339),
		ILPPacket:  fmt.Sprintf("ilp_%s_%d", batchID, batch.TotalAmount),
	}

	data, _ := json.Marshal(payload)
	resp, err := http.Post(
		fmt.Sprintf("%s/transfers", lse.config.MojaloopHubURL),
		"application/vnd.interoperability.transfers+json;version=1.1",
		bytes.NewReader(data))
	if err != nil {
		pgDB.Exec(`UPDATE ledger_settlement_batches SET state='failed' WHERE batch_id=$1`, batchID)
		return fmt.Errorf("mojaloop request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode == 202 || resp.StatusCode == 200 {
		pgDB.Exec(`UPDATE ledger_settlement_batches SET state='settled', settled_at=NOW() WHERE batch_id=$1`, batchID)
		log.Printf("[Mojaloop] Settlement initiated for batch %s via FSP %s", batchID, lse.config.MojaloopFSPID)
		return nil
	}

	pgDB.Exec(`UPDATE ledger_settlement_batches SET state='failed' WHERE batch_id=$1`, batchID)
	return fmt.Errorf("mojaloop status: %d", resp.StatusCode)
}

// ═══════════════════════════════════════════════════════════════════════════════
// Sync Scheduler
// ═══════════════════════════════════════════════════════════════════════════════

func (lse *LedgerSyncEngine) StartScheduler(ctx context.Context) {
	ticker := time.NewTicker(lse.config.SyncInterval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			log.Println("[Scheduler] Stopping ledger sync scheduler")
			return
		case <-ticker.C:
			if err := lse.SyncPendingEntries(ctx); err != nil {
				log.Printf("[Scheduler] Sync error: %v", err)
			}
		}
	}
}

// ═══════════════════════════════════════════════════════════════════════════════
// HTTP API
// ═══════════════════════════════════════════════════════════════════════════════

func (lse *LedgerSyncEngine) handleHealth(w http.ResponseWriter, r *http.Request) {
	var syncCount, totalSynced int64
	var lastSync *time.Time
	if pgDB != nil {
		pgDB.QueryRow(`SELECT sync_count, total_synced, last_sync FROM ledger_sync_metrics LIMIT 1`).Scan(&syncCount, &totalSynced, &lastSync)
	}
	json.NewEncoder(w).Encode(map[string]interface{}{
		"status":      "healthy",
		"service":     "settlement-ledger-sync",
		"persistence": "postgresql",
		"lastSync":    lastSync,
		"syncCount":   syncCount,
		"totalSynced": totalSynced,
	})
}

func (lse *LedgerSyncEngine) handleTriggerSync(w http.ResponseWriter, r *http.Request) {
	if err := lse.SyncPendingEntries(r.Context()); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	json.NewEncoder(w).Encode(map[string]string{"status": "synced"})
}

func (lse *LedgerSyncEngine) handleGetBatches(w http.ResponseWriter, r *http.Request) {
	if pgDB == nil {
		json.NewEncoder(w).Encode([]SettlementBatch{})
		return
	}
	rows, err := pgDB.Query(`SELECT batch_id, period, state, entry_count, total_amount, platform_total, client_total, created_at
		FROM ledger_settlement_batches ORDER BY created_at DESC LIMIT 100`)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	var batches []SettlementBatch
	for rows.Next() {
		var b SettlementBatch
		rows.Scan(&b.BatchID, &b.Period, &b.State, &b.EntryCount, &b.TotalAmount, &b.PlatformTotal, &b.ClientTotal, &b.CreatedAt)
		batches = append(batches, b)
	}
	if batches == nil {
		batches = []SettlementBatch{}
	}
	json.NewEncoder(w).Encode(batches)
}

func (lse *LedgerSyncEngine) handleSettleBatch(w http.ResponseWriter, r *http.Request) {
	batchID := r.URL.Query().Get("batchId")
	if batchID == "" {
		http.Error(w, "batchId required", http.StatusBadRequest)
		return
	}
	if err := lse.InitiateMojaloopSettlement(batchID); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	json.NewEncoder(w).Encode(map[string]string{"status": "settlement_initiated", "batchId": batchID})
}

func recoverMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		defer func() {
			if err := recover(); err != nil {
				log.Printf("[recovery] panic: %v", err)
				http.Error(w, "internal server error", http.StatusInternalServerError)
			}
		}()
		next.ServeHTTP(w, r)
	})
}

func jwtAuthMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
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
		next.ServeHTTP(w, r)
	})
}

func main() {
	cfg := loadConfig()
	initDB(cfg.PostgresURL)

	log.Printf("Starting Settlement Ledger Sync on port %s (PostgreSQL-backed)", cfg.Port)

	engine := NewLedgerSyncEngine(cfg)

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	go engine.StartScheduler(ctx)

	serveMux := http.NewServeMux()
	serveMux.HandleFunc("/health", engine.handleHealth)
	serveMux.HandleFunc("/api/v1/ledger/sync", engine.handleTriggerSync)
	serveMux.HandleFunc("/api/v1/ledger/batches", engine.handleGetBatches)
	serveMux.HandleFunc("/api/v1/ledger/settle", engine.handleSettleBatch)

	server := &http.Server{Addr: ":" + cfg.Port, Handler: serveMux}

	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)

	go func() {
		<-sigCh
		cancel()
		shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 15*time.Second)
		defer shutdownCancel()
		server.Shutdown(shutdownCtx)
	}()

	log.Printf("Settlement Ledger Sync ready on :%s", cfg.Port)
	if err := server.ListenAndServe(); err != http.ErrServerClosed {
		log.Fatalf("Server error: %v", err)
	}
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
