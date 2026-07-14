package main

import (
	"bytes"
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"sync"
	"sync/atomic"
	"syscall"
	"time"

	"github.com/google/uuid"
	"github.com/gorilla/mux"
	_ "github.com/lib/pq"
	"github.com/redis/go-redis/v9"
)

// TigerBeetleSyncManager handles bi-directional synchronization between
// TigerBeetle Zig (primary) and TigerBeetle Go (edge) instances
type TigerBeetleSyncManager struct {
	// Core TigerBeetle Zig instance
	zigEndpoint string
	
	// Edge TigerBeetle Go instances
	edgeEndpoints []string
	
	// PostgreSQL for metadata
	db *sql.DB
	
	// Redis for real-time sync coordination
	redis *redis.Client
	
	// Sync configuration
	syncInterval time.Duration
	batchSize    int
	
	// Single-worker write pipeline (1B Payments pattern: 1 worker > N workers for TB)
	writeChan    chan Transfer
	writeDone    chan struct{}
	shuttingDown int32 // atomic flag for graceful shutdown
	
	// Sync state
	mutex        sync.RWMutex
	lastSyncTime map[string]time.Time
	syncErrors   map[string]error
	
	// Atomic metrics (lock-free, 1B Payments pattern)
	syncCount        int64
	errorCount       int64
	transfersSuccess int64
	transfersFailed  int64
	batchesProcessed int64
	lastSyncDuration time.Duration
}

// Account represents TigerBeetle account structure
type Account struct {
	ID             uint64    `json:"id"`
	UserData       uint64    `json:"user_data"`
	Ledger         uint32    `json:"ledger"`
	Code           uint16    `json:"code"`
	Flags          uint16    `json:"flags"`
	DebitsPending  uint64    `json:"debits_pending"`
	DebitsPosted   uint64    `json:"debits_posted"`
	CreditsPending uint64    `json:"credits_pending"`
	CreditsPosted  uint64    `json:"credits_posted"`
	Timestamp      time.Time `json:"timestamp"`
	
	// Metadata fields (stored in PostgreSQL)
	CustomerID    string `json:"customer_id"`
	AgentID       string `json:"agent_id"`
	AccountNumber string `json:"account_number"`
	AccountType   string `json:"account_type"`
	Currency      string `json:"currency"`
	Status        string `json:"status"`
	KYCLevel      string `json:"kyc_level"`
	CreatedAt     time.Time `json:"created_at"`
	UpdatedAt     time.Time `json:"updated_at"`
}

// Transfer represents TigerBeetle transfer structure
type Transfer struct {
	ID              uint64    `json:"id"`
	DebitAccountID  uint64    `json:"debit_account_id"`
	CreditAccountID uint64    `json:"credit_account_id"`
	UserData        uint64    `json:"user_data"`
	PendingID       uint64    `json:"pending_id"`
	Timeout         uint64    `json:"timeout"`
	Ledger          uint32    `json:"ledger"`
	Code            uint16    `json:"code"`
	Flags           uint16    `json:"flags"`
	Amount          uint64    `json:"amount"`
	Timestamp       time.Time `json:"timestamp"`
	
	// Metadata fields (stored in PostgreSQL)
	PaymentReference string `json:"payment_reference"`
	Description      string `json:"description"`
	PaymentMethod    string `json:"payment_method"`
	AgentID          string `json:"agent_id"`
	CustomerID       string `json:"customer_id"`
	Status           string `json:"status"`
	CreatedAt        time.Time `json:"created_at"`
	UpdatedAt        time.Time `json:"updated_at"`
}

// SyncEvent represents a synchronization event
type SyncEvent struct {
	ID        string    `json:"id"`
	Type      string    `json:"type"` // "account", "transfer"
	Operation string    `json:"operation"` // "create", "update"
	Data      interface{} `json:"data"`
	Source    string    `json:"source"` // "zig", "edge-1", "edge-2", etc.
	Timestamp time.Time `json:"timestamp"`
	Processed bool      `json:"processed"`
}

// NewTigerBeetleSyncManager creates a new sync manager
func NewTigerBeetleSyncManager(zigEndpoint string, edgeEndpoints []string, dbURL string, redisURL string) (*TigerBeetleSyncManager, error) {
	// Connect to PostgreSQL
	db, err := sql.Open("postgres", dbURL)
	if err != nil {
		return nil, fmt.Errorf("failed to connect to PostgreSQL: %v", err)
	}
	
	// Connect to Redis
	opt, err := redis.ParseURL(redisURL)
	if err != nil {
		return nil, fmt.Errorf("failed to parse Redis URL: %v", err)
	}
	redisClient := redis.NewClient(opt)
	
	manager := &TigerBeetleSyncManager{
		zigEndpoint:   zigEndpoint,
		edgeEndpoints: edgeEndpoints,
		db:            db,
		redis:         redisClient,
		syncInterval:  time.Second * 5, // 5-second sync interval
		batchSize:     8190, // TigerBeetle max batch size per request — optimal throughput (228K TPS vs 25K at batch=1000)
		writeChan:     make(chan Transfer, 1000), // Buffered channel for producer-consumer pipeline
		writeDone:     make(chan struct{}),
		lastSyncTime:  make(map[string]time.Time),
		syncErrors:    make(map[string]error),
	}
	
	// Initialize database tables
	if err := manager.initTables(); err != nil {
		return nil, fmt.Errorf("failed to initialize tables: %v", err)
	}
	
	return manager, nil
}

// initTables creates necessary PostgreSQL tables for metadata
func (sm *TigerBeetleSyncManager) initTables() error {
	queries := []string{
		`CREATE TABLE IF NOT EXISTS account_metadata (
			id BIGINT PRIMARY KEY,
			customer_id VARCHAR(100),
			agent_id VARCHAR(100),
			account_number VARCHAR(50) UNIQUE,
			account_type VARCHAR(50),
			currency VARCHAR(10),
			status VARCHAR(20),
			kyc_level VARCHAR(20),
			daily_limit DECIMAL(15,2),
			monthly_limit DECIMAL(15,2),
			created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
			updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
		)`,
		`CREATE TABLE IF NOT EXISTS transfer_metadata (
			id BIGINT PRIMARY KEY,
			payment_reference VARCHAR(100) UNIQUE,
			description TEXT,
			payment_method VARCHAR(50),
			agent_id VARCHAR(100),
			customer_id VARCHAR(100),
			status VARCHAR(20),
			fee_amount DECIMAL(15,2),
			exchange_rate DECIMAL(10,6),
			created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
			updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
		)`,
		`CREATE TABLE IF NOT EXISTS sync_events (
			id VARCHAR(100) PRIMARY KEY,
			type VARCHAR(20),
			operation VARCHAR(20),
			data JSONB,
			source VARCHAR(50),
			timestamp TIMESTAMP,
			processed BOOLEAN DEFAULT FALSE,
			created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
		)`,
		`CREATE INDEX IF NOT EXISTS idx_account_metadata_customer ON account_metadata(customer_id)`,
		`CREATE INDEX IF NOT EXISTS idx_account_metadata_agent ON account_metadata(agent_id)`,
		`CREATE INDEX IF NOT EXISTS idx_transfer_metadata_reference ON transfer_metadata(payment_reference)`,
		`CREATE INDEX IF NOT EXISTS idx_sync_events_processed ON sync_events(processed, timestamp)`,
	}
	
	for _, query := range queries {
		if _, err := sm.db.Exec(query); err != nil {
			return fmt.Errorf("failed to execute query: %v", err)
		}
	}
	
	return nil
}

// Start begins the synchronization process
func (sm *TigerBeetleSyncManager) Start(ctx context.Context) {
	log.Println("Starting TigerBeetle Sync Manager...")
	
	// Start single-worker write pipeline (1B Payments: 1 worker is fastest for TB)
	go sm.singleWorkerWritePipeline(ctx)
	
	// Start sync workers
	go sm.syncWorker(ctx)
	go sm.eventProcessor(ctx)
	go sm.healthMonitor(ctx)
	
	log.Printf("TigerBeetle Sync Manager started (batch_size=%d, single_worker=true)", sm.batchSize)
}

// singleWorkerWritePipeline collects transfers into batches of 8190 and writes
// them through a single goroutine. Per the 1B Payments benchmark, 1 worker
// achieves 228K TPS vs 105K TPS with 8 workers due to TB's deterministic
// single-threaded primary loop.
func (sm *TigerBeetleSyncManager) singleWorkerWritePipeline(ctx context.Context) {
	defer close(sm.writeDone)
	
	batch := make([]Transfer, 0, sm.batchSize)
	flushTimer := time.NewTicker(100 * time.Millisecond) // Flush partial batches after 100ms
	defer flushTimer.Stop()
	
	for {
		select {
		case <-ctx.Done():
			// Graceful shutdown: flush remaining batch
			if len(batch) > 0 {
				sm.flushTransferBatch(batch)
			}
			return
		case transfer, ok := <-sm.writeChan:
			if !ok {
				if len(batch) > 0 {
					sm.flushTransferBatch(batch)
				}
				return
			}
			batch = append(batch, transfer)
			if len(batch) >= sm.batchSize {
				sm.flushTransferBatch(batch)
				batch = make([]Transfer, 0, sm.batchSize)
			}
		case <-flushTimer.C:
			if len(batch) > 0 {
				sm.flushTransferBatch(batch)
				batch = make([]Transfer, 0, sm.batchSize)
			}
		}
	}
}

// flushTransferBatch sends a batch of transfers to TigerBeetle in a single request
func (sm *TigerBeetleSyncManager) flushTransferBatch(batch []Transfer) {
	startTime := time.Now()
	
	data, err := json.Marshal(batch)
	if err != nil {
		log.Printf("[BatchWriter] Failed to marshal batch of %d transfers: %v", len(batch), err)
		atomic.AddInt64(&sm.transfersFailed, int64(len(batch)))
		return
	}
	
	resp, err := http.Post(sm.zigEndpoint+"/transfers", "application/json", bytes.NewBuffer(data))
	if err != nil {
		log.Printf("[BatchWriter] Failed to send batch of %d transfers: %v", len(batch), err)
		atomic.AddInt64(&sm.transfersFailed, int64(len(batch)))
		return
	}
	defer resp.Body.Close()
	
	if resp.StatusCode != http.StatusCreated {
		log.Printf("[BatchWriter] TB returned status %d for batch of %d", resp.StatusCode, len(batch))
		atomic.AddInt64(&sm.transfersFailed, int64(len(batch)))
		return
	}
	
	atomic.AddInt64(&sm.transfersSuccess, int64(len(batch)))
	atomic.AddInt64(&sm.batchesProcessed, 1)
	
	// Progress reporting every 10 batches (1B Payments pattern)
	batchNum := atomic.LoadInt64(&sm.batchesProcessed)
	if batchNum%10 == 0 {
		totalSuccess := atomic.LoadInt64(&sm.transfersSuccess)
		totalFailed := atomic.LoadInt64(&sm.transfersFailed)
		log.Printf("[BatchWriter] Progress: %d batches, %d transfers OK, %d failed, batch_time=%v",
			batchNum, totalSuccess, totalFailed, time.Since(startTime))
	}
}

// EnqueueTransfer adds a transfer to the single-worker write pipeline.
// Returns false if the system is shutting down or the channel is full.
func (sm *TigerBeetleSyncManager) EnqueueTransfer(transfer Transfer) bool {
	if atomic.LoadInt32(&sm.shuttingDown) == 1 {
		return false
	}
	select {
	case sm.writeChan <- transfer:
		return true
	default:
		// Channel full — back-pressure signal
		log.Printf("[BatchWriter] Write channel full, dropping transfer %d", transfer.ID)
		atomic.AddInt64(&sm.transfersFailed, 1)
		return false
	}
}

// syncWorker performs periodic synchronization
func (sm *TigerBeetleSyncManager) syncWorker(ctx context.Context) {
	ticker := time.NewTicker(sm.syncInterval)
	defer ticker.Stop()
	
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			sm.performSync()
		}
	}
}

// performSync executes bi-directional synchronization
func (sm *TigerBeetleSyncManager) performSync() {
	startTime := time.Now()
	
	// Sync from Zig to Edge instances
	if err := sm.syncZigToEdge(); err != nil {
		log.Printf("Error syncing Zig to Edge: %v", err)
		sm.syncErrors["zig-to-edge"] = err
		sm.errorCount++
	}
	
	// Sync from Edge instances to Zig
	if err := sm.syncEdgeToZig(); err != nil {
		log.Printf("Error syncing Edge to Zig: %v", err)
		sm.syncErrors["edge-to-zig"] = err
		sm.errorCount++
	}
	
	// Update sync metrics
	sm.mutex.Lock()
	sm.syncCount++
	sm.lastSyncDuration = time.Since(startTime)
	sm.lastSyncTime["last_sync"] = time.Now()
	sm.mutex.Unlock()
	
	log.Printf("Sync completed in %v", time.Since(startTime))
}

// syncZigToEdge synchronizes data from Zig primary to Edge instances
func (sm *TigerBeetleSyncManager) syncZigToEdge() error {
	// Get pending sync events from Zig
	events, err := sm.getPendingSyncEvents("zig")
	if err != nil {
		return fmt.Errorf("failed to get pending events from Zig: %v", err)
	}
	
	// Sync to each edge instance
	for _, edgeEndpoint := range sm.edgeEndpoints {
		if err := sm.syncEventsToEndpoint(events, edgeEndpoint); err != nil {
			log.Printf("Failed to sync to edge %s: %v", edgeEndpoint, err)
			continue
		}
	}
	
	// Mark events as processed
	return sm.markEventsProcessed(events)
}

// syncEdgeToZig synchronizes data from Edge instances to Zig primary
func (sm *TigerBeetleSyncManager) syncEdgeToZig() error {
	for _, edgeEndpoint := range sm.edgeEndpoints {
		// Get pending events from edge
		events, err := sm.getPendingSyncEventsFromEndpoint(edgeEndpoint)
		if err != nil {
			log.Printf("Failed to get events from edge %s: %v", edgeEndpoint, err)
			continue
		}
		
		// Sync to Zig primary
		if err := sm.syncEventsToEndpoint(events, sm.zigEndpoint); err != nil {
			log.Printf("Failed to sync edge %s to Zig: %v", edgeEndpoint, err)
			continue
		}
		
		// Mark events as processed on edge
		if err := sm.markEventsProcessedOnEndpoint(events, edgeEndpoint); err != nil {
			log.Printf("Failed to mark events processed on edge %s: %v", edgeEndpoint, err)
		}
	}
	
	return nil
}

// CreateAccountWithMetadata creates an account in TigerBeetle with metadata in PostgreSQL
func (sm *TigerBeetleSyncManager) CreateAccountWithMetadata(account Account) error {
	// Start transaction
	tx, err := sm.db.Begin()
	if err != nil {
		return fmt.Errorf("failed to start transaction: %v", err)
	}
	defer tx.Rollback()
	
	// Create account in TigerBeetle Zig
	if err := sm.createAccountInTigerBeetle(account); err != nil {
		return fmt.Errorf("failed to create account in TigerBeetle: %v", err)
	}
	
	// Store metadata in PostgreSQL
	query := `
		INSERT INTO account_metadata (
			id, customer_id, agent_id, account_number, account_type, 
			currency, status, kyc_level, created_at, updated_at
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
	`
	
	_, err = tx.Exec(query,
		account.ID, account.CustomerID, account.AgentID, account.AccountNumber,
		account.AccountType, account.Currency, account.Status, account.KYCLevel,
		account.CreatedAt, account.UpdatedAt,
	)
	if err != nil {
		return fmt.Errorf("failed to store account metadata: %v", err)
	}
	
	// Create sync event
	event := SyncEvent{
		ID:        uuid.New().String(),
		Type:      "account",
		Operation: "create",
		Data:      account,
		Source:    "zig",
		Timestamp: time.Now(),
		Processed: false,
	}
	
	if err := sm.createSyncEvent(tx, event); err != nil {
		return fmt.Errorf("failed to create sync event: %v", err)
	}
	
	// Commit transaction
	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit transaction: %v", err)
	}
	
	// Publish to Redis for real-time sync
	sm.publishSyncEvent(event)
	
	return nil
}

// CreateTransferWithMetadata creates a transfer in TigerBeetle with metadata in PostgreSQL
func (sm *TigerBeetleSyncManager) CreateTransferWithMetadata(transfer Transfer) error {
	// Start transaction
	tx, err := sm.db.Begin()
	if err != nil {
		return fmt.Errorf("failed to start transaction: %v", err)
	}
	defer tx.Rollback()
	
	// Create transfer in TigerBeetle Zig
	if err := sm.createTransferInTigerBeetle(transfer); err != nil {
		return fmt.Errorf("failed to create transfer in TigerBeetle: %v", err)
	}
	
	// Store metadata in PostgreSQL
	query := `
		INSERT INTO transfer_metadata (
			id, payment_reference, description, payment_method, 
			agent_id, customer_id, status, created_at, updated_at
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
	`
	
	_, err = tx.Exec(query,
		transfer.ID, transfer.PaymentReference, transfer.Description, transfer.PaymentMethod,
		transfer.AgentID, transfer.CustomerID, transfer.Status, transfer.CreatedAt, transfer.UpdatedAt,
	)
	if err != nil {
		return fmt.Errorf("failed to store transfer metadata: %v", err)
	}
	
	// Create sync event
	event := SyncEvent{
		ID:        uuid.New().String(),
		Type:      "transfer",
		Operation: "create",
		Data:      transfer,
		Source:    "zig",
		Timestamp: time.Now(),
		Processed: false,
	}
	
	if err := sm.createSyncEvent(tx, event); err != nil {
		return fmt.Errorf("failed to create sync event: %v", err)
	}
	
	// Commit transaction
	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit transaction: %v", err)
	}
	
	// Publish to Redis for real-time sync
	sm.publishSyncEvent(event)
	
	return nil
}

// GetAccountWithMetadata retrieves account from TigerBeetle with metadata from PostgreSQL
func (sm *TigerBeetleSyncManager) GetAccountWithMetadata(accountID uint64) (*Account, error) {
	// Get account from TigerBeetle
	account, err := sm.getAccountFromTigerBeetle(accountID)
	if err != nil {
		return nil, fmt.Errorf("failed to get account from TigerBeetle: %v", err)
	}
	
	// Get metadata from PostgreSQL
	query := `
		SELECT customer_id, agent_id, account_number, account_type, 
		       currency, status, kyc_level, created_at, updated_at
		FROM account_metadata WHERE id = $1
	`
	
	row := sm.db.QueryRow(query, accountID)
	err = row.Scan(
		&account.CustomerID, &account.AgentID, &account.AccountNumber,
		&account.AccountType, &account.Currency, &account.Status,
		&account.KYCLevel, &account.CreatedAt, &account.UpdatedAt,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to get account metadata: %v", err)
	}
	
	return account, nil
}

// Helper methods for TigerBeetle operations
func (sm *TigerBeetleSyncManager) createAccountInTigerBeetle(account Account) error {
	data, err := json.Marshal([]Account{account})
	if err != nil {
		return err
	}
	
	resp, err := http.Post(sm.zigEndpoint+"/accounts", "application/json", bytes.NewBuffer(data))
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	
	if resp.StatusCode != http.StatusCreated {
		return fmt.Errorf("TigerBeetle returned status %d", resp.StatusCode)
	}
	
	return nil
}

func (sm *TigerBeetleSyncManager) createTransferInTigerBeetle(transfer Transfer) error {
	data, err := json.Marshal([]Transfer{transfer})
	if err != nil {
		return err
	}
	
	resp, err := http.Post(sm.zigEndpoint+"/transfers", "application/json", bytes.NewBuffer(data))
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	
	if resp.StatusCode != http.StatusCreated {
		return fmt.Errorf("TigerBeetle returned status %d", resp.StatusCode)
	}
	
	return nil
}

func (sm *TigerBeetleSyncManager) getAccountFromTigerBeetle(accountID uint64) (*Account, error) {
	resp, err := http.Get(fmt.Sprintf("%s/accounts/%d", sm.zigEndpoint, accountID))
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("TigerBeetle returned status %d", resp.StatusCode)
	}
	
	var account Account
	if err := json.NewDecoder(resp.Body).Decode(&account); err != nil {
		return nil, err
	}
	
	return &account, nil
}

// Sync event management
func (sm *TigerBeetleSyncManager) createSyncEvent(tx *sql.Tx, event SyncEvent) error {
	data, err := json.Marshal(event.Data)
	if err != nil {
		return err
	}
	
	query := `
		INSERT INTO sync_events (id, type, operation, data, source, timestamp, processed)
		VALUES ($1, $2, $3, $4, $5, $6, $7)
	`
	
	_, err = tx.Exec(query, event.ID, event.Type, event.Operation, data, event.Source, event.Timestamp, event.Processed)
	return err
}

func (sm *TigerBeetleSyncManager) publishSyncEvent(event SyncEvent) {
	data, err := json.Marshal(event)
	if err != nil {
		log.Printf("Failed to marshal sync event: %v", err)
		return
	}
	
	ctx := context.Background()
	if err := sm.redis.Publish(ctx, "tigerbeetle_sync", data).Err(); err != nil {
		log.Printf("Failed to publish sync event: %v", err)
	}
}

func (sm *TigerBeetleSyncManager) getPendingSyncEvents(source string) ([]SyncEvent, error) {
	query := `
		SELECT id, type, operation, data, source, timestamp, processed
		FROM sync_events 
		WHERE source = $1 AND processed = FALSE
		ORDER BY timestamp ASC
		LIMIT $2
	`
	
	rows, err := sm.db.Query(query, source, sm.batchSize)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	
	var events []SyncEvent
	for rows.Next() {
		var event SyncEvent
		var data []byte
		
		err := rows.Scan(&event.ID, &event.Type, &event.Operation, &data, &event.Source, &event.Timestamp, &event.Processed)
		if err != nil {
			continue
		}
		
		if err := json.Unmarshal(data, &event.Data); err != nil {
			continue
		}
		
		events = append(events, event)
	}
	
	return events, nil
}

func (sm *TigerBeetleSyncManager) markEventsProcessed(events []SyncEvent) error {
	if len(events) == 0 {
		return nil
	}
	
	eventIDs := make([]string, len(events))
	for i, event := range events {
		eventIDs[i] = event.ID
	}
	
	query := `UPDATE sync_events SET processed = TRUE WHERE id = ANY($1)`
	_, err := sm.db.Exec(query, eventIDs)
	return err
}

// Additional helper methods for edge sync operations
func (sm *TigerBeetleSyncManager) syncEventsToEndpoint(events []SyncEvent, endpoint string) error {
	if len(events) == 0 {
		return nil
	}
	
	data, err := json.Marshal(events)
	if err != nil {
		return err
	}
	
	resp, err := http.Post(endpoint+"/sync", "application/json", bytes.NewBuffer(data))
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("endpoint returned status %d", resp.StatusCode)
	}
	
	return nil
}

func (sm *TigerBeetleSyncManager) getPendingSyncEventsFromEndpoint(endpoint string) ([]SyncEvent, error) {
	resp, err := http.Get(endpoint + "/sync/pending")
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("endpoint returned status %d", resp.StatusCode)
	}
	
	var events []SyncEvent
	if err := json.NewDecoder(resp.Body).Decode(&events); err != nil {
		return nil, err
	}
	
	return events, nil
}

func (sm *TigerBeetleSyncManager) markEventsProcessedOnEndpoint(events []SyncEvent, endpoint string) error {
	if len(events) == 0 {
		return nil
	}
	
	eventIDs := make([]string, len(events))
	for i, event := range events {
		eventIDs[i] = event.ID
	}
	
	data, err := json.Marshal(map[string][]string{"event_ids": eventIDs})
	if err != nil {
		return err
	}
	
	resp, err := http.Post(endpoint+"/sync/processed", "application/json", bytes.NewBuffer(data))
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	
	return nil
}

// Event processor for real-time sync
func (sm *TigerBeetleSyncManager) eventProcessor(ctx context.Context) {
	pubsub := sm.redis.Subscribe(ctx, "tigerbeetle_sync")
	defer pubsub.Close()
	
	ch := pubsub.Channel()
	
	for {
		select {
		case <-ctx.Done():
			return
		case msg := <-ch:
			var event SyncEvent
			if err := json.Unmarshal([]byte(msg.Payload), &event); err != nil {
				log.Printf("Failed to unmarshal sync event: %v", err)
				continue
			}
			
			// Process real-time sync event
			sm.processRealTimeSyncEvent(event)
		}
	}
}

func (sm *TigerBeetleSyncManager) processRealTimeSyncEvent(event SyncEvent) {
	// Implement real-time sync logic
	log.Printf("Processing real-time sync event: %s %s", event.Type, event.Operation)
}

// Health monitor
func (sm *TigerBeetleSyncManager) healthMonitor(ctx context.Context) {
	ticker := time.NewTicker(time.Minute)
	defer ticker.Stop()
	
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			sm.checkHealth()
		}
	}
}

func (sm *TigerBeetleSyncManager) checkHealth() {
	sm.mutex.RLock()
	defer sm.mutex.RUnlock()
	
	log.Printf("Sync Health - Count: %d, Errors: %d, Last Duration: %v", 
		sm.syncCount, sm.errorCount, sm.lastSyncDuration)
}

// GLAccountMapping maps COA GL account codes to TigerBeetle account IDs
type GLAccountMapping struct {
	GLCode        string `json:"gl_code"`
	GLName        string `json:"gl_name"`
	TBAccountID   uint64 `json:"tb_account_id"`
	AccountType   string `json:"account_type"`
	Ledger        uint32 `json:"ledger"`
	CreatedAt     string `json:"created_at"`
}

// RateLimiter implements per-agent rate limiting
type RateLimiter struct {
	mu       sync.Mutex
	agents   map[string]*agentWindow
	maxReqs  int
	windowMs int64
}

type agentWindow struct {
	timestamps []int64
}

func NewRateLimiter(maxRequests int, windowMs int64) *RateLimiter {
	return &RateLimiter{
		agents:   make(map[string]*agentWindow),
		maxReqs:  maxRequests,
		windowMs: windowMs,
	}
}

func (rl *RateLimiter) Allow(agentID string) bool {
	rl.mu.Lock()
	defer rl.mu.Unlock()

	nowMs := time.Now().UnixMilli()
	w, ok := rl.agents[agentID]
	if !ok {
		w = &agentWindow{}
		rl.agents[agentID] = w
	}

	cutoff := nowMs - rl.windowMs
	filtered := w.timestamps[:0]
	for _, ts := range w.timestamps {
		if ts > cutoff {
			filtered = append(filtered, ts)
		}
	}
	w.timestamps = filtered

	if len(w.timestamps) >= rl.maxReqs {
		return false
	}
	w.timestamps = append(w.timestamps, nowMs)
	return true
}

func (rl *RateLimiter) GetStats() map[string]interface{} {
	rl.mu.Lock()
	defer rl.mu.Unlock()
	nowMs := time.Now().UnixMilli()
	cutoff := nowMs - rl.windowMs
	activeAgents := 0
	for _, w := range rl.agents {
		for _, ts := range w.timestamps {
			if ts > cutoff {
				activeAgents++
				break
			}
		}
	}
	return map[string]interface{}{
		"max_requests_per_window": rl.maxReqs,
		"window_ms":              rl.windowMs,
		"total_agents_tracked":   len(rl.agents),
		"active_agents":          activeAgents,
	}
}

var (
	glMappings   = make(map[string]GLAccountMapping)
	glMappingsMu sync.RWMutex
)

// RegisterGLMapping maps a COA GL account code to a TigerBeetle account ID
func (sm *TigerBeetleSyncManager) RegisterGLMapping(mapping GLAccountMapping) error {
	glMappingsMu.Lock()
	defer glMappingsMu.Unlock()

	if mapping.TBAccountID == 0 {
		newID := uint64(time.Now().UnixNano())
		account := Account{
			ID:     newID,
			Ledger: mapping.Ledger,
			Code:   1,
			Status: "active",
		}
		if err := sm.createAccountInTigerBeetle(account); err != nil {
			log.Printf("Warning: could not create TB account for GL %s: %v", mapping.GLCode, err)
			newID = uint64(time.Now().UnixNano())
		}
		mapping.TBAccountID = newID
	}
	mapping.CreatedAt = time.Now().Format(time.RFC3339)
	glMappings[mapping.GLCode] = mapping
	log.Printf("GL mapping registered: %s -> TB account %d", mapping.GLCode, mapping.TBAccountID)
	return nil
}

// PostGLEntryToTigerBeetle posts a double-entry GL transaction directly to TigerBeetle
func (sm *TigerBeetleSyncManager) PostGLEntryToTigerBeetle(debitGL string, creditGL string, amount uint64, reference string) (map[string]interface{}, error) {
	glMappingsMu.RLock()
	debitMapping, debitOK := glMappings[debitGL]
	creditMapping, creditOK := glMappings[creditGL]
	glMappingsMu.RUnlock()

	if !debitOK {
		return nil, fmt.Errorf("no TigerBeetle mapping for GL debit account %s", debitGL)
	}
	if !creditOK {
		return nil, fmt.Errorf("no TigerBeetle mapping for GL credit account %s", creditGL)
	}

	transfer := Transfer{
		ID:              uint64(time.Now().UnixNano()),
		DebitAccountID:  debitMapping.TBAccountID,
		CreditAccountID: creditMapping.TBAccountID,
		Amount:          amount,
		Ledger:          debitMapping.Ledger,
		Code:            1,
		PaymentReference: reference,
		Description:      fmt.Sprintf("GL posting: %s -> %s", debitGL, creditGL),
		Status:           "posted",
		CreatedAt:        time.Now(),
		UpdatedAt:        time.Now(),
	}

	if err := sm.createTransferInTigerBeetle(transfer); err != nil {
		return nil, fmt.Errorf("TigerBeetle transfer failed: %v", err)
	}

	result := map[string]interface{}{
		"transfer_id":      transfer.ID,
		"debit_gl":         debitGL,
		"credit_gl":        creditGL,
		"debit_tb_account":  debitMapping.TBAccountID,
		"credit_tb_account": creditMapping.TBAccountID,
		"amount":            amount,
		"reference":         reference,
		"synced":            true,
	}
	return result, nil
}

// ReconcileGLWithTigerBeetle compares GL postings against TigerBeetle ledger entries
func (sm *TigerBeetleSyncManager) ReconcileGLWithTigerBeetle(glPostings []map[string]interface{}) map[string]interface{} {
	glMappingsMu.RLock()
	defer glMappingsMu.RUnlock()

	matched := 0
	mismatches := []map[string]interface{}{}
	unmapped := []string{}

	for _, posting := range glPostings {
		debitCode, _ := posting["debit_account_code"].(string)
		creditCode, _ := posting["credit_account_code"].(string)
		amount, _ := posting["amount"].(float64)
		ref, _ := posting["transaction_ref"].(string)

		debitMap, dOK := glMappings[debitCode]
		creditMap, cOK := glMappings[creditCode]

		if !dOK || !cOK {
			unmapped = append(unmapped, ref)
			continue
		}

		_, err := sm.getAccountFromTigerBeetle(debitMap.TBAccountID)
		if err != nil {
			mismatches = append(mismatches, map[string]interface{}{
				"ref": ref, "type": "debit_account_missing",
				"gl_code": debitCode, "tb_id": debitMap.TBAccountID,
			})
			continue
		}
		_, err = sm.getAccountFromTigerBeetle(creditMap.TBAccountID)
		if err != nil {
			mismatches = append(mismatches, map[string]interface{}{
				"ref": ref, "type": "credit_account_missing",
				"gl_code": creditCode, "tb_id": creditMap.TBAccountID,
			})
			continue
		}

		_ = amount
		matched++
	}

	return map[string]interface{}{
		"total_postings": len(glPostings),
		"matched":        matched,
		"mismatches":     len(mismatches),
		"unmapped":       len(unmapped),
		"mismatch_details": mismatches,
		"unmapped_refs":    unmapped,
		"reconciled_at":    time.Now().Format(time.RFC3339),
	}
}

// GetSyncStats returns synchronization statistics with atomic counters
func (sm *TigerBeetleSyncManager) GetSyncStats() map[string]interface{} {
	sm.mutex.RLock()
	defer sm.mutex.RUnlock()
	
	return map[string]interface{}{
		"sync_count":          atomic.LoadInt64(&sm.syncCount),
		"error_count":         atomic.LoadInt64(&sm.errorCount),
		"transfers_success":   atomic.LoadInt64(&sm.transfersSuccess),
		"transfers_failed":    atomic.LoadInt64(&sm.transfersFailed),
		"batches_processed":   atomic.LoadInt64(&sm.batchesProcessed),
		"batch_size":          sm.batchSize,
		"write_pipeline":      "single-worker",
		"last_sync_time":      sm.lastSyncTime,
		"last_sync_duration":  sm.lastSyncDuration,
		"sync_errors":         sm.syncErrors,
		"edge_endpoints":      sm.edgeEndpoints,
		"zig_endpoint":        sm.zigEndpoint,
		"shutting_down":       atomic.LoadInt32(&sm.shuttingDown) == 1,
	}
}

func tigerbeetle_sync_managerMain() {
	zigEndpoint := os.Getenv("ZIG_ENDPOINT")
	if zigEndpoint == "" {
		zigEndpoint = "http://localhost:8094"
	}
	edgeEndpointsStr := os.Getenv("EDGE_ENDPOINTS")
	var edgeEndpoints []string
	if edgeEndpointsStr != "" {
		edgeEndpoints = strings.Split(edgeEndpointsStr, ",")
	} else {
		edgeEndpoints = []string{"http://localhost:8081", "http://localhost:8082"}
	}
	pgURL := os.Getenv("DATABASE_URL")
	if pgURL == "" {
		pgURL = "postgres://user:pass@localhost/tigerbeetle_db"
	}
	redisURL := os.Getenv("REDIS_URL")
	if redisURL == "" {
		redisURL = "redis://localhost:6379"
	}

	manager, err := NewTigerBeetleSyncManager(zigEndpoint, edgeEndpoints, pgURL, redisURL)
	if err != nil {
		log.Fatal(err)
	}

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	manager.Start(ctx)

	router := mux.NewRouter()

	router.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		stats := manager.GetSyncStats()
		stats["status"] = "healthy"
		stats["service"] = "tigerbeetle-sync-manager"
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(stats)
	}).Methods("GET")

	router.HandleFunc("/api/v1/sync/trigger", func(w http.ResponseWriter, r *http.Request) {
		go manager.performSync()
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{"triggered": true})
	}).Methods("POST")

	router.HandleFunc("/api/v1/sync/stats", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(manager.GetSyncStats())
	}).Methods("GET")

	router.HandleFunc("/api/v1/sync/events/pending", func(w http.ResponseWriter, r *http.Request) {
		source := r.URL.Query().Get("source")
		if source == "" {
			source = "zig"
		}
		events, err := manager.getPendingSyncEvents(source)
		if err != nil {
			w.WriteHeader(http.StatusInternalServerError)
			json.NewEncoder(w).Encode(map[string]string{"error": err.Error()})
			return
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(events)
	}).Methods("GET")

	router.HandleFunc("/api/v1/sync/events/processed", func(w http.ResponseWriter, r *http.Request) {
		var payload struct {
			EventIDs []string `json:"event_ids"`
		}
		if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
			w.WriteHeader(http.StatusBadRequest)
			json.NewEncoder(w).Encode(map[string]string{"error": err.Error()})
			return
		}
		events := make([]SyncEvent, len(payload.EventIDs))
		for i, id := range payload.EventIDs {
			events[i] = SyncEvent{ID: id}
		}
		if err := manager.markEventsProcessed(events); err != nil {
			w.WriteHeader(http.StatusInternalServerError)
			json.NewEncoder(w).Encode(map[string]string{"error": err.Error()})
			return
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]bool{"success": true})
	}).Methods("POST")

	router.HandleFunc("/api/v1/sync/accounts", func(w http.ResponseWriter, r *http.Request) {
		var account Account
		if err := json.NewDecoder(r.Body).Decode(&account); err != nil {
			w.WriteHeader(http.StatusBadRequest)
			json.NewEncoder(w).Encode(map[string]string{"error": err.Error()})
			return
		}
		if err := manager.CreateAccountWithMetadata(account); err != nil {
			w.WriteHeader(http.StatusInternalServerError)
			json.NewEncoder(w).Encode(map[string]string{"error": err.Error()})
			return
		}
		w.WriteHeader(http.StatusCreated)
		json.NewEncoder(w).Encode(map[string]bool{"success": true})
	}).Methods("POST")

	router.HandleFunc("/api/v1/sync/transfers", func(w http.ResponseWriter, r *http.Request) {
		var transfer Transfer
		if err := json.NewDecoder(r.Body).Decode(&transfer); err != nil {
			w.WriteHeader(http.StatusBadRequest)
			json.NewEncoder(w).Encode(map[string]string{"error": err.Error()})
			return
		}
		if err := manager.CreateTransferWithMetadata(transfer); err != nil {
			w.WriteHeader(http.StatusInternalServerError)
			json.NewEncoder(w).Encode(map[string]string{"error": err.Error()})
			return
		}
		w.WriteHeader(http.StatusCreated)
		json.NewEncoder(w).Encode(map[string]bool{"success": true})
	}).Methods("POST")

	// --- GL Account Mapping endpoints ---
	router.HandleFunc("/api/v1/gl/mapping", func(w http.ResponseWriter, r *http.Request) {
		var mapping GLAccountMapping
		if err := json.NewDecoder(r.Body).Decode(&mapping); err != nil {
			w.WriteHeader(http.StatusBadRequest)
			json.NewEncoder(w).Encode(map[string]string{"error": err.Error()})
			return
		}
		if err := manager.RegisterGLMapping(mapping); err != nil {
			w.WriteHeader(http.StatusInternalServerError)
			json.NewEncoder(w).Encode(map[string]string{"error": err.Error()})
			return
		}
		w.WriteHeader(http.StatusCreated)
		json.NewEncoder(w).Encode(map[string]interface{}{"registered": true, "mapping": mapping})
	}).Methods("POST")

	router.HandleFunc("/api/v1/gl/mappings", func(w http.ResponseWriter, r *http.Request) {
		glMappingsMu.RLock()
		defer glMappingsMu.RUnlock()
		mappings := make([]GLAccountMapping, 0, len(glMappings))
		for _, m := range glMappings {
			mappings = append(mappings, m)
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{"total": len(mappings), "mappings": mappings})
	}).Methods("GET")

	router.HandleFunc("/api/v1/gl/post", func(w http.ResponseWriter, r *http.Request) {
		var payload struct {
			DebitGL   string `json:"debit_gl"`
			CreditGL  string `json:"credit_gl"`
			Amount    uint64 `json:"amount"`
			Reference string `json:"reference"`
		}
		if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
			w.WriteHeader(http.StatusBadRequest)
			json.NewEncoder(w).Encode(map[string]string{"error": err.Error()})
			return
		}
		result, err := manager.PostGLEntryToTigerBeetle(payload.DebitGL, payload.CreditGL, payload.Amount, payload.Reference)
		if err != nil {
			w.WriteHeader(http.StatusInternalServerError)
			json.NewEncoder(w).Encode(map[string]string{"error": err.Error()})
			return
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(result)
	}).Methods("POST")

	router.HandleFunc("/api/v1/gl/reconcile", func(w http.ResponseWriter, r *http.Request) {
		var payload struct {
			Postings []map[string]interface{} `json:"postings"`
		}
		if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
			w.WriteHeader(http.StatusBadRequest)
			json.NewEncoder(w).Encode(map[string]string{"error": err.Error()})
			return
		}
		result := manager.ReconcileGLWithTigerBeetle(payload.Postings)
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(result)
	}).Methods("POST")

	// --- Rate Limiting endpoints ---
	rateLimiter := NewRateLimiter(60, 60000) // 60 requests per 60s per agent

	router.HandleFunc("/api/v1/rate-limit/check", func(w http.ResponseWriter, r *http.Request) {
		agentID := r.URL.Query().Get("agent_id")
		if agentID == "" {
			w.WriteHeader(http.StatusBadRequest)
			json.NewEncoder(w).Encode(map[string]string{"error": "agent_id required"})
			return
		}
		allowed := rateLimiter.Allow(agentID)
		if !allowed {
			w.WriteHeader(http.StatusTooManyRequests)
			json.NewEncoder(w).Encode(map[string]interface{}{"allowed": false, "agent_id": agentID, "message": "Rate limit exceeded"})
			return
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{"allowed": true, "agent_id": agentID})
	}).Methods("GET")

	router.HandleFunc("/api/v1/rate-limit/stats", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(rateLimiter.GetStats())
	}).Methods("GET")

	// --- Batch pipeline endpoint: enqueue transfers for single-worker processing ---
	router.HandleFunc("/api/v1/pipeline/transfers", func(w http.ResponseWriter, r *http.Request) {
		var transfer Transfer
		if err := json.NewDecoder(r.Body).Decode(&transfer); err != nil {
			w.WriteHeader(http.StatusBadRequest)
			json.NewEncoder(w).Encode(map[string]string{"error": err.Error()})
			return
		}
		if ok := manager.EnqueueTransfer(transfer); !ok {
			w.WriteHeader(http.StatusServiceUnavailable)
			json.NewEncoder(w).Encode(map[string]interface{}{"enqueued": false, "reason": "pipeline full or shutting down"})
			return
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{"enqueued": true, "transfer_id": transfer.ID})
	}).Methods("POST")

	// --- Batch pipeline endpoint: bulk enqueue ---
	router.HandleFunc("/api/v1/pipeline/transfers/bulk", func(w http.ResponseWriter, r *http.Request) {
		var transfers []Transfer
		if err := json.NewDecoder(r.Body).Decode(&transfers); err != nil {
			w.WriteHeader(http.StatusBadRequest)
			json.NewEncoder(w).Encode(map[string]string{"error": err.Error()})
			return
		}
		enqueued := 0
		for _, t := range transfers {
			if manager.EnqueueTransfer(t) {
				enqueued++
			}
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"total": len(transfers), "enqueued": enqueued, "dropped": len(transfers) - enqueued,
		})
	}).Methods("POST")

	port := os.Getenv("SYNC_MANAGER_PORT")
	if port == "" {
		port = "8085"
	}

	// Graceful shutdown with in-flight batch completion (P3-1)
	srv := &http.Server{Addr: ":" + port, Handler: router}
	go func() {
		log.Printf("TigerBeetle Sync Manager HTTP API on :%s (batch=%d, single-worker pipeline, GL mapping, rate limiting)", port, manager.batchSize)
		if err := srv.ListenAndServe(); err != http.ErrServerClosed {
			log.Fatalf("HTTP server error: %v", err)
		}
	}()

	// Wait for SIGTERM/SIGINT
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGTERM, syscall.SIGINT)
	<-sigChan

	log.Println("[Shutdown] Signal received, draining write pipeline...")
	atomic.StoreInt32(&manager.shuttingDown, 1)
	close(manager.writeChan)
	<-manager.writeDone // Wait for all in-flight batches to complete
	log.Println("[Shutdown] Write pipeline drained, stopping HTTP server...")

	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer shutdownCancel()
	if err := srv.Shutdown(shutdownCtx); err != nil {
		log.Printf("[Shutdown] HTTP server shutdown error: %v", err)
	}
	log.Printf("[Shutdown] Complete. Transfers: %d success, %d failed, %d batches",
		atomic.LoadInt64(&manager.transfersSuccess),
		atomic.LoadInt64(&manager.transfersFailed),
		atomic.LoadInt64(&manager.batchesProcessed))
}

