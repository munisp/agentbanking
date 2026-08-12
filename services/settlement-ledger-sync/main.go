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

	"github.com/jackc/pgx/v5"
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
	KafkaRESTProxyURL  string
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
		TigerBeetleAddr:    getEnv("TB_ADDRESSES", getEnv("TIGERBEETLE_ADDR", "tigerbeetle:3000")),
		TigerBeetleCluster: 0,
		KafkaBrokers:       getEnv("KAFKA_BROKERS", "kafka:9092"),
		KafkaRESTProxyURL:  getEnv("KAFKA_REST_PROXY_URL", ""),
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
	pg          *pgx.Conn
	tbClient    tb.Client
	httpClient  *http.Client
	mu          sync.RWMutex
	batches     []SettlementBatch
	entries     []BillingLedgerEntry
	syncCount   int64
	lastSync    time.Time
	totalSynced int64
}

func NewLedgerSyncEngine(cfg *Config, pg *pgx.Conn, tbClient tb.Client) *LedgerSyncEngine {
	return &LedgerSyncEngine{
		config:     cfg,
		pg:         pg,
		tbClient:   tbClient,
		httpClient: &http.Client{Timeout: 15 * time.Second},
		batches:    make([]SettlementBatch, 0),
		entries:    make([]BillingLedgerEntry, 0),
	}
}

// accountRef maps a logical ledger account identifier to a deterministic
// TigerBeetle Uint128 account ID (same convention as tb-sidecar).
func accountRef(s string) tbtypes.Uint128 {
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
		return fmt.Errorf("failed to fetch pending entries: %w", err)
	}
	if len(entries) == 0 {
		log.Println("[LedgerSync] No pending entries to sync")
		return errNoPending
	}

	// Step 2: Create TigerBeetle transfers for each entry. Entries that fail are
	// marked failed in Postgres and never counted as synced.
	posted := make([]BillingLedgerEntry, 0, len(entries))
	for _, entry := range entries {
		if err := lse.createTigerBeetleTransfer(ctx, entry); err != nil {
			log.Printf("[LedgerSync] TigerBeetle transfer failed for tx %s: %v", entry.TransactionID, err)
			if mErr := lse.markEntryFailed(ctx, entry, err); mErr != nil {
				log.Printf("[LedgerSync] Failed to mark tx %s as failed: %v", entry.TransactionID, mErr)
			}
			continue
		}
		posted = append(posted, entry)
	}
	if len(posted) == 0 {
		return fmt.Errorf("all %d pending entries failed TigerBeetle posting", len(entries))
	}

	// Step 3: Batch entries for settlement — StateCommitted is only set here,
	// after real TigerBeetle postings have been accepted.
	batch := lse.createSettlementBatch(posted)

	// Step 4: Publish to Kafka for downstream consumers. A publish failure fails
	// the cycle loudly; the batch remains committed in TigerBeetle.
	if err := lse.publishSettlementEvent(ctx, batch); err != nil {
		return fmt.Errorf("batch %s committed in TigerBeetle but event publish failed: %w", batch.BatchID, err)
	}

	// Step 5: Mark entries synced in Postgres
	if err := lse.markEntriesSynced(ctx, posted, batch.BatchID); err != nil {
		return fmt.Errorf("batch %s posted and published but Postgres sync-status update failed: %w", batch.BatchID, err)
	}

	// Step 6: Update sync state
	lse.mu.Lock()
	lse.syncCount++
	lse.lastSync = time.Now()
	lse.totalSynced += int64(len(posted))
	lse.batches = append(lse.batches, batch)
	lse.mu.Unlock()

	log.Printf("[LedgerSync] Synced %d entries in batch %s", len(posted), batch.BatchID)
	return nil
}

// fetchPendingEntries queries the billing ledger for entries awaiting sync.
func (lse *LedgerSyncEngine) fetchPendingEntries(ctx context.Context) ([]BillingLedgerEntry, error) {
	rows, err := lse.pg.Query(ctx, `
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

// createTigerBeetleTransfer posts the double-entry distribution for a billing
// entry to the TigerBeetle cluster:
//  1. Customer → Platform (platformShare)
//  2. Customer → Client (clientShare)
//  3. Client → Agent (agentCommission)
func (lse *LedgerSyncEngine) createTigerBeetleTransfer(ctx context.Context, entry BillingLedgerEntry) error {
	customerAcct := accountRef("customer:" + entry.ClientID)
	platformAcct := accountRef("platform-revenue")
	clientAcct := accountRef("client:" + entry.ClientID)
	agentAcct := accountRef("agent:" + entry.AgentID)

	transfers := make([]tbtypes.Transfer, 0, 3)
	if entry.PlatformShare > 0 {
		transfers = append(transfers, tbtypes.Transfer{
			ID:              tbtypes.ID(),
			DebitAccountID:  customerAcct,
			CreditAccountID: platformAcct,
			Amount:          tbtypes.ToUint128(uint64(entry.PlatformShare)),
			Ledger:          1,
			Code:            1,
		})
	}
	if entry.ClientShare > 0 {
		transfers = append(transfers, tbtypes.Transfer{
			ID:              tbtypes.ID(),
			DebitAccountID:  customerAcct,
			CreditAccountID: clientAcct,
			Amount:          tbtypes.ToUint128(uint64(entry.ClientShare)),
			Ledger:          1,
			Code:            1,
		})
	}
	if entry.AgentCommission > 0 {
		transfers = append(transfers, tbtypes.Transfer{
			ID:              tbtypes.ID(),
			DebitAccountID:  clientAcct,
			CreditAccountID: agentAcct,
			Amount:          tbtypes.ToUint128(uint64(entry.AgentCommission)),
			Ledger:          1,
			Code:            1,
		})
	}
	if len(transfers) == 0 {
		return fmt.Errorf("entry %s has no non-zero shares to post", entry.TransactionID)
	}

	results, err := lse.tbClient.CreateTransfers(transfers)
	if err != nil {
		return fmt.Errorf("tigerbeetle cluster unreachable: %w", err)
	}
	if len(results) > 0 {
		return fmt.Errorf("tigerbeetle rejected transfer at index %d: %v", results[0].Index, results[0].Result)
	}

	log.Printf("[TigerBeetle] Posted %d double-entry transfers for tx %s: platform=%d, client=%d, agent=%d",
		len(transfers), entry.TransactionID, entry.PlatformShare, entry.ClientShare, entry.AgentCommission)
	return nil
}

func (lse *LedgerSyncEngine) markEntryFailed(ctx context.Context, entry BillingLedgerEntry, cause error) error {
	_, err := lse.pg.Exec(ctx, `
		UPDATE platform_billing_ledger
		SET sync_status = 'failed', sync_error = $2
		WHERE id = $1`, entry.ID, cause.Error())
	return err
}

func (lse *LedgerSyncEngine) markEntriesSynced(ctx context.Context, entries []BillingLedgerEntry, batchID string) error {
	ids := make([]int64, 0, len(entries))
	for _, e := range entries {
		ids = append(ids, e.ID)
	}
	_, err := lse.pg.Exec(ctx, `
		UPDATE platform_billing_ledger
		SET sync_status = 'synced', settlement_batch_id = $2, synced_at = NOW()
		WHERE id = ANY($1)`, ids, batchID)
	return err
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

// publishSettlementEvent publishes the committed batch to the
// "billing.settlement.committed" Kafka topic via the Kafka REST proxy.
func (lse *LedgerSyncEngine) publishSettlementEvent(ctx context.Context, batch SettlementBatch) error {
	if lse.config.KafkaRESTProxyURL == "" {
		return errors.New("KAFKA_REST_PROXY_URL not configured — cannot publish settlement event")
	}
	payload := map[string]interface{}{
		"records": []map[string]interface{}{{"key": batch.BatchID, "value": batch}},
	}
	body, _ := json.Marshal(payload)
	req, err := http.NewRequestWithContext(ctx, http.MethodPost,
		strings.TrimRight(lse.config.KafkaRESTProxyURL, "/")+"/topics/billing.settlement.committed",
		bytes.NewReader(body))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/vnd.kafka.json.v2+json")
	resp, err := lse.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("kafka rest proxy unreachable: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 300 {
		return fmt.Errorf("kafka rest proxy returned status %d", resp.StatusCode)
	}
	log.Printf("[Kafka] Published settlement batch %s: %d entries, total=%d",
		batch.BatchID, batch.EntryCount, batch.TotalAmount)
	return nil
}

// InitiateMojaloopSettlement triggers interbank settlement via Mojaloop by
// POSTing a real /transfers request to the Mojaloop hub. The batch must already
// be committed in TigerBeetle.
func (lse *LedgerSyncEngine) InitiateMojaloopSettlement(batchID string) error {
	lse.mu.RLock()
	var batch *SettlementBatch
	for i := range lse.batches {
		if lse.batches[i].BatchID == batchID {
			batch = &lse.batches[i]
			break
		}
	}
	lse.mu.RUnlock()
	if batch == nil {
		return fmt.Errorf("settlement batch %s not found", batchID)
	}
	if batch.State != StateCommitted {
		return fmt.Errorf("settlement batch %s is not committed (state: %s)", batchID, batch.State)
	}

	transfer := MojaloopTransfer{
		TransferID: batchID,
		PayerFSP:   lse.config.MojaloopFSPID,
		PayeeFSP:   lse.config.MojaloopFSPID,
		Amount:     strconv.FormatInt(batch.TotalAmount, 10),
		Currency:   "NGN",
		Expiration: time.Now().Add(10 * time.Minute).UTC().Format(time.RFC3339),
	}
	body, _ := json.Marshal(transfer)
	req, err := http.NewRequest(http.MethodPost,
		strings.TrimRight(lse.config.MojaloopHubURL, "/")+"/transfers", bytes.NewReader(body))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/vnd.interoperability.transfers+json;version=1.1")
	req.Header.Set("FSPIOP-Source", lse.config.MojaloopFSPID)
	req.Header.Set("Date", time.Now().UTC().Format(http.TimeFormat))

	resp, err := lse.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("mojaloop hub unreachable: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 300 {
		return fmt.Errorf("mojaloop hub returned status %d", resp.StatusCode)
	}

	now := time.Now()
	lse.mu.Lock()
	batch.State = StateSettled
	batch.SettledAt = &now
	lse.mu.Unlock()

	log.Printf("[Mojaloop] Interbank settlement initiated for batch %s via FSP %s",
		batchID, lse.config.MojaloopFSPID)
	return nil
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
					continue
				}
				log.Printf("[Scheduler] Sync error: %v", err)
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
			http.Error(w, `{"error":"no_pending_entries"}`, http.StatusNotFound)
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
	if err := lse.InitiateMojaloopSettlement(batchID); err != nil {
		http.Error(w, err.Error(), http.StatusBadGateway)
		return
	}
	json.NewEncoder(w).Encode(map[string]string{"status": "settlement_initiated", "batchId": batchID})
}

func main() {
	cfg := loadConfig()
	log.Printf("Starting Settlement Ledger Sync on port %s", cfg.Port)

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Refuse to start without Postgres — it is the source of pending ledger entries.
	if cfg.PostgresURL == "" {
		log.Fatal("POSTGRES_URL is required; refusing to start without the billing ledger source")
	}
	pgConn, err := pgx.Connect(ctx, cfg.PostgresURL)
	if err != nil {
		log.Fatalf("Cannot connect to PostgreSQL (%v); refusing to start", err)
	}
	defer pgConn.Close(ctx)

	// Refuse to start without a live TigerBeetle cluster connection.
	addresses := strings.Split(cfg.TigerBeetleAddr, ",")
	tbClient, err := tb.NewClient(tbtypes.ToUint128(uint64(cfg.TigerBeetleCluster)), addresses)
	if err != nil {
		log.Fatalf("Cannot connect to TigerBeetle cluster at %v (%v); refusing to start", addresses, err)
	}
	defer tbClient.Close()

	engine := NewLedgerSyncEngine(cfg, pgConn, tbClient)

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
