// Package main implements the Settlement Ledger Sync service.
// Synchronizes billing ledger entries with TigerBeetle double-entry accounting,
// publishes settlement events to Kafka, and interfaces with Mojaloop for
// interbank settlement finality. Uses Dapr for service-to-service communication.
// Integrates with: TigerBeetle, Kafka, Mojaloop, Dapr, PostgreSQL, Redis, APISIX
package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
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

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/segmentio/kafka-go"
	tb "github.com/tigerbeetle/tigerbeetle-go"
	tbtypes "github.com/tigerbeetle/tigerbeetle-go/pkg/types"
)

var errNoPending = errors.New("no pending ledger entries to sync")

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
	SyncInterval       time.Duration
}

func loadConfig() *Config {
	return &Config{
		Port:               getEnv("PORT", "9102"),
		PostgresURL:        getEnv("POSTGRES_URL", ""),
		TigerBeetleAddr:    getEnv("TIGERBEETLE_ADDR", "tigerbeetle:3000"),
		TigerBeetleCluster: 0,
		KafkaBrokers:       getEnv("KAFKA_BROKERS", "kafka:9092"),
		MojaloopHubURL:     getEnv("MOJALOOP_HUB_URL", "http://mojaloop-hub:4003"),
		MojaloopFSPID:      getEnv("MOJALOOP_FSP_ID", "54agent"),
		DaprHTTPPort:       getEnv("DAPR_HTTP_PORT", "3500"),
		RedisAddr:          getEnv("REDIS_ADDR", "redis:6379"),
		APISIXAdminURL:     getEnv("APISIX_ADMIN_URL", "http://apisix:9180"),
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
	ID              int64     `json:"id"`
	TransactionID   string    `json:"transactionId"`
	AgentID         string    `json:"agentId"`
	ClientID        string    `json:"clientId"`
	TransactionType string    `json:"transactionType"`
	GrossAmount     int64     `json:"grossAmount"` // Amount in minor units (kobo)
	GrossFee        int64     `json:"grossFee"`
	PlatformShare   int64     `json:"platformShare"`
	ClientShare     int64     `json:"clientShare"`
	AgentCommission int64     `json:"agentCommission"`
	Currency        string    `json:"currency"`
	BillingModel    string    `json:"billingModel"`
	ProcessedAt     time.Time `json:"processedAt"`
}

type TigerBeetleTransfer struct {
	ID              [16]byte `json:"id"`
	DebitAccountID  [16]byte `json:"debitAccountId"`
	CreditAccountID [16]byte `json:"creditAccountId"`
	Amount          uint64   `json:"amount"`
	Ledger          uint32   `json:"ledger"`
	Code            uint16   `json:"code"`
	Timestamp       uint64   `json:"timestamp"`
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
// Settlement Ledger Sync Engine
// ═══════════════════════════════════════════════════════════════════════════════

type LedgerSyncEngine struct {
	config      *Config
	pgPool      *pgxpool.Pool
	tbClient    tb.Client
	kafkaWriter *kafka.Writer
	httpClient  *http.Client
	mu          sync.RWMutex
	batches     []SettlementBatch
	syncCount   int64
	lastSync    time.Time
	totalSynced int64
}

func NewLedgerSyncEngine(cfg *Config, pgPool *pgxpool.Pool, tbClient tb.Client, kafkaWriter *kafka.Writer) *LedgerSyncEngine {
	return &LedgerSyncEngine{
		config:      cfg,
		pgPool:      pgPool,
		tbClient:    tbClient,
		kafkaWriter: kafkaWriter,
		httpClient:  &http.Client{Timeout: 20 * time.Second},
		batches:     make([]SettlementBatch, 0),
	}
}

// stringToUint128 converts a string ID to a deterministic tbtypes.Uint128.
func stringToUint128(s string) tbtypes.Uint128 {
	var result tbtypes.Uint128
	b := []byte(s)
	if len(b) > 16 {
		b = b[:16]
	}
	copy(result[:], b)
	return result
}

// SyncPendingEntries fetches unsynced billing ledger entries from Postgres,
// creates double-entry transfers in TigerBeetle, and publishes settlement events to Kafka
func (lse *LedgerSyncEngine) SyncPendingEntries(ctx context.Context) error {
	log.Println("[LedgerSync] Starting sync cycle")

	// Step 1: Fetch pending entries from billing ledger (PostgreSQL)
	entries, err := lse.fetchPendingEntries(ctx)
	if err != nil {
		return fmt.Errorf("fetch pending entries: %w", err)
	}
	if len(entries) == 0 {
		return errNoPending
	}

	// Step 2: Create TigerBeetle transfers for each entry. Only entries whose
	// transfers were actually committed count towards the batch.
	synced := make([]BillingLedgerEntry, 0, len(entries))
	failed := 0
	for _, entry := range entries {
		if err := lse.createTigerBeetleTransfer(ctx, entry); err != nil {
			log.Printf("[LedgerSync] TigerBeetle transfer failed for tx %s: %v", entry.TransactionID, err)
			failed++
			continue
		}
		synced = append(synced, entry)
	}

	if len(synced) == 0 {
		return fmt.Errorf("all %d pending entries failed to post to TigerBeetle", len(entries))
	}

	// Step 3: Batch the successfully synced entries for settlement
	batch := lse.createSettlementBatch(synced)

	// Step 4: Publish to Kafka for downstream consumers. A committed state is
	// only recorded once the event is durably published.
	if err := lse.publishSettlementEvent(ctx, batch); err != nil {
		batch.State = StateFailed
		batch.CommittedAt = nil
		lse.mu.Lock()
		lse.batches = append(lse.batches, batch)
		lse.mu.Unlock()
		return fmt.Errorf("publish settlement event for batch %s: %w", batch.BatchID, err)
	}

	// Step 5: Update sync state
	lse.mu.Lock()
	lse.syncCount++
	lse.lastSync = time.Now()
	lse.totalSynced += int64(len(synced))
	lse.batches = append(lse.batches, batch)
	lse.mu.Unlock()

	log.Printf("[LedgerSync] Synced %d entries in batch %s (%d failed)", len(synced), batch.BatchID, failed)
	return nil
}

// fetchPendingEntries queries the real pending billing ledger entries from Postgres.
func (lse *LedgerSyncEngine) fetchPendingEntries(ctx context.Context) ([]BillingLedgerEntry, error) {
	rows, err := lse.pgPool.Query(ctx, `
		SELECT id, transaction_id, agent_id, client_id, transaction_type,
		       gross_amount, gross_fee, platform_share, client_share, agent_commission,
		       currency, billing_model, processed_at
		FROM platform_billing_ledger
		WHERE sync_status = 'pending'
		ORDER BY id
		LIMIT 1000`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	entries := make([]BillingLedgerEntry, 0)
	for rows.Next() {
		var e BillingLedgerEntry
		if err := rows.Scan(&e.ID, &e.TransactionID, &e.AgentID, &e.ClientID, &e.TransactionType,
			&e.GrossAmount, &e.GrossFee, &e.PlatformShare, &e.ClientShare, &e.AgentCommission,
			&e.Currency, &e.BillingModel, &e.ProcessedAt); err != nil {
			return nil, err
		}
		entries = append(entries, e)
	}
	return entries, rows.Err()
}

// ensureTBAccount creates a ledger account in TigerBeetle, tolerating EXISTS.
func (lse *LedgerSyncEngine) ensureTBAccount(id tbtypes.Uint128, code uint16) error {
	results, err := lse.tbClient.CreateAccounts([]tbtypes.Account{
		{ID: id, Ledger: 1, Code: code, Flags: 0},
	})
	if err != nil {
		return fmt.Errorf("tigerbeetle CreateAccounts: %w", err)
	}
	for _, res := range results {
		if !strings.Contains(fmt.Sprintf("%v", res.Result), "EXISTS") {
			return fmt.Errorf("tigerbeetle account creation rejected: result=%v index=%d", res.Result, res.Index)
		}
	}
	return nil
}

// createTigerBeetleTransfer posts the real double-entry transfers for a billing
// entry and marks the Postgres row synced only after the cluster accepts them.
func (lse *LedgerSyncEngine) createTigerBeetleTransfer(ctx context.Context, entry BillingLedgerEntry) error {
	customerAcct := stringToUint128("cust:" + entry.ClientID)
	platformAcct := stringToUint128("platform:revenue")
	clientAcct := stringToUint128("client:" + entry.ClientID)
	agentAcct := stringToUint128("agent:" + entry.AgentID)

	for _, acct := range []struct {
		id   tbtypes.Uint128
		code uint16
	}{
		{customerAcct, 1001},
		{platformAcct, 1002},
		{clientAcct, 1003},
		{agentAcct, 1004},
	} {
		if err := lse.ensureTBAccount(acct.id, acct.code); err != nil {
			return err
		}
	}

	transfers := make([]tbtypes.Transfer, 0, 3)
	addTransfer := func(leg string, debit, credit tbtypes.Uint128, amount int64, code uint16) {
		if amount <= 0 {
			return
		}
		transfers = append(transfers, tbtypes.Transfer{
			ID:              stringToUint128("sync:" + entry.TransactionID + ":" + leg),
			DebitAccountID:  debit,
			CreditAccountID: credit,
			Amount:          tbtypes.ToUint128(uint64(amount)),
			Ledger:          1,
			Code:            code,
			Flags:           0,
		})
	}
	// 1. Customer → Platform (platformShare)
	addTransfer("platform", customerAcct, platformAcct, entry.PlatformShare, 10)
	// 2. Customer → Client (clientShare)
	addTransfer("client", customerAcct, clientAcct, entry.ClientShare, 11)
	// 3. Client → Agent (agentCommission)
	addTransfer("agent", clientAcct, agentAcct, entry.AgentCommission, 12)

	if len(transfers) == 0 {
		return fmt.Errorf("entry %s has no positive shares to transfer", entry.TransactionID)
	}

	results, err := lse.tbClient.CreateTransfers(transfers)
	if err != nil {
		return fmt.Errorf("tigerbeetle CreateTransfers: %w", err)
	}
	if len(results) > 0 {
		return fmt.Errorf("tigerbeetle transfer rejected: result=%v index=%d", results[0].Result, results[0].Index)
	}

	// Mark the row synced only after the cluster accepted the transfers.
	if _, err := lse.pgPool.Exec(ctx,
		`UPDATE platform_billing_ledger SET sync_status = 'synced', synced_at = NOW() WHERE id = $1 AND sync_status = 'pending'`,
		entry.ID); err != nil {
		return fmt.Errorf("mark ledger entry %d synced: %w", entry.ID, err)
	}

	log.Printf("[TigerBeetle] Posted %d transfers for tx %s: platform=%d, client=%d, agent=%d",
		len(transfers), entry.TransactionID, entry.PlatformShare, entry.ClientShare, entry.AgentCommission)
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

// publishSettlementEvent publishes the committed batch to Kafka topic
// "billing.settlement.committed" and returns an error on failure.
func (lse *LedgerSyncEngine) publishSettlementEvent(ctx context.Context, batch SettlementBatch) error {
	raw, err := json.Marshal(batch)
	if err != nil {
		return err
	}
	if err := lse.kafkaWriter.WriteMessages(ctx, kafka.Message{
		Key:   []byte(batch.BatchID),
		Value: raw,
	}); err != nil {
		return fmt.Errorf("kafka write billing.settlement.committed: %w", err)
	}
	log.Printf("[Kafka] Published settlement batch %s: %d entries, total=%d",
		batch.BatchID, batch.EntryCount, batch.TotalAmount)
	return nil
}

// InitiateMojaloopSettlement triggers interbank settlement via Mojaloop
func (lse *LedgerSyncEngine) InitiateMojaloopSettlement(ctx context.Context, batchID string) error {
	lse.mu.RLock()
	var batch *SettlementBatch
	for i := range lse.batches {
		if lse.batches[i].BatchID == batchID {
			b := lse.batches[i]
			batch = &b
			break
		}
	}
	lse.mu.RUnlock()
	if batch == nil {
		return fmt.Errorf("settlement batch %s not found", batchID)
	}
	if batch.State != StateCommitted {
		return fmt.Errorf("settlement batch %s is not committed (state=%s)", batchID, batch.State)
	}

	transfer := MojaloopTransfer{
		TransferID: stringToUUID(batchID),
		PayerFSP:   lse.config.MojaloopFSPID,
		PayeeFSP:   lse.config.MojaloopFSPID,
		Amount:     strconv.FormatFloat(float64(batch.TotalAmount)/100.0, 'f', 2, 64),
		Currency:   "NGN",
		Expiration: time.Now().Add(10 * time.Minute).UTC().Format(time.RFC3339),
	}
	raw, _ := json.Marshal(transfer)
	req, err := http.NewRequestWithContext(ctx, http.MethodPost,
		strings.TrimRight(lse.config.MojaloopHubURL, "/")+"/transfers", bytes.NewReader(raw))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/vnd.interoperability.transfers+json;version=1.0")
	req.Header.Set("Accept", "application/vnd.interoperability.transfers+json;version=1.0")
	req.Header.Set("FSPIOP-Source", lse.config.MojaloopFSPID)
	req.Header.Set("Date", time.Now().UTC().Format(http.TimeFormat))

	resp, err := lse.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("mojaloop hub unreachable: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 400 {
		return fmt.Errorf("mojaloop hub rejected settlement: HTTP %d", resp.StatusCode)
	}

	now := time.Now()
	lse.mu.Lock()
	for i := range lse.batches {
		if lse.batches[i].BatchID == batchID {
			lse.batches[i].State = StateSettled
			lse.batches[i].SettledAt = &now
			break
		}
	}
	lse.mu.Unlock()

	log.Printf("[Mojaloop] Interbank settlement initiated for batch %s (transferId=%s)", batchID, transfer.TransferID)
	return nil
}

// stringToUUID deterministically renders a batch ID as a UUID-shaped string.
func stringToUUID(s string) string {
	id := stringToUint128(s)
	return fmt.Sprintf("%x-%x-%x-%x-%x", id[0:4], id[4:6], id[6:8], id[8:10], id[10:16])
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
				if errors.Is(err, errNoPending) {
					log.Println("[Scheduler] No pending entries to sync")
				} else {
					log.Printf("[Scheduler] Sync error: %v", err)
				}
			}
		}
	}
}

// ═══════════════════════════════════════════════════════════════════════════════
// HTTP API
// ═══════════════════════════════════════════════════════════════════════════════

func (lse *LedgerSyncEngine) handleHealth(w http.ResponseWriter, r *http.Request) {
	lse.mu.RLock()
	defer lse.mu.RUnlock()
	json.NewEncoder(w).Encode(map[string]interface{}{
		"status":      "healthy",
		"service":     "settlement-ledger-sync",
		"lastSync":    lse.lastSync,
		"syncCount":   lse.syncCount,
		"totalSynced": lse.totalSynced,
		"batches":     len(lse.batches),
	})
}

func (lse *LedgerSyncEngine) handleTriggerSync(w http.ResponseWriter, r *http.Request) {
	if err := lse.SyncPendingEntries(r.Context()); err != nil {
		if errors.Is(err, errNoPending) {
			http.Error(w, errNoPending.Error(), http.StatusNotFound)
			return
		}
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	json.NewEncoder(w).Encode(map[string]string{"status": "synced"})
}

func (lse *LedgerSyncEngine) handleGetBatches(w http.ResponseWriter, r *http.Request) {
	lse.mu.RLock()
	defer lse.mu.RUnlock()
	json.NewEncoder(w).Encode(lse.batches)
}

func (lse *LedgerSyncEngine) handleSettleBatch(w http.ResponseWriter, r *http.Request) {
	batchID := r.URL.Query().Get("batchId")
	if batchID == "" {
		http.Error(w, "batchId required", http.StatusBadRequest)
		return
	}
	if err := lse.InitiateMojaloopSettlement(r.Context(), batchID); err != nil {
		http.Error(w, err.Error(), http.StatusBadGateway)
		return
	}
	json.NewEncoder(w).Encode(map[string]string{"status": "settlement_initiated", "batchId": batchID})
}

func main() {
	cfg := loadConfig()
	log.Printf("Starting Settlement Ledger Sync on port %s", cfg.Port)

	// Postgres is the source of pending entries — refuse to start without it.
	if cfg.PostgresURL == "" {
		log.Fatal("[LedgerSync] POSTGRES_URL not set — refusing to start")
	}
	pgPool, err := pgxpool.New(context.Background(), cfg.PostgresURL)
	if err != nil {
		log.Fatalf("[LedgerSync] postgres connect failed: %v", err)
	}
	if err := pgPool.Ping(context.Background()); err != nil {
		log.Fatalf("[LedgerSync] postgres unreachable: %v", err)
	}
	defer pgPool.Close()

	// TigerBeetle is the double-entry ledger — refuse to start without it.
	tbClient, err := tb.NewClient(tbtypes.ToUint128(uint64(cfg.TigerBeetleCluster)), []string{cfg.TigerBeetleAddr})
	if err != nil {
		log.Fatalf("[LedgerSync] tigerbeetle client init failed (%s): %v", cfg.TigerBeetleAddr, err)
	}
	defer tbClient.Close()

	kafkaWriter := &kafka.Writer{
		Addr:         kafka.TCP(strings.Split(cfg.KafkaBrokers, ",")...),
		Topic:        "billing.settlement.committed",
		RequiredAcks: kafka.RequireOne,
	}
	defer kafkaWriter.Close()

	engine := NewLedgerSyncEngine(cfg, pgPool, tbClient, kafkaWriter)

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	go engine.StartScheduler(ctx)

	mux := http.NewServeMux()
	mux.HandleFunc("/health", engine.handleHealth)
	mux.HandleFunc("/api/v1/ledger/sync", engine.handleTriggerSync)
	mux.HandleFunc("/api/v1/ledger/batches", engine.handleGetBatches)
	mux.HandleFunc("/api/v1/ledger/settle", engine.handleSettleBatch)

	server := &http.Server{Addr: ":" + cfg.Port, Handler: mux}

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
