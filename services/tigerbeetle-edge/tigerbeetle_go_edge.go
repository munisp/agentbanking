package main

import (
	"bytes"
	"os"
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"strconv"
	"sync"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/go-redis/redis/v8"
	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
)

// TigerBeetle data structures
type Account struct {
	ID             uint64    `json:"id" gorm:"primaryKey"`
	UserData       uint64    `json:"user_data"`
	Ledger         uint32    `json:"ledger"`
	Code           uint16    `json:"code"`
	Flags          uint16    `json:"flags"`
	DebitsPending  uint64    `json:"debits_pending"`
	DebitsPosted   uint64    `json:"debits_posted"`
	CreditsPending uint64    `json:"credits_pending"`
	CreditsPosted  uint64    `json:"credits_posted"`
	Timestamp      int64     `json:"timestamp"`
	CreatedAt      time.Time `json:"created_at" gorm:"autoCreateTime"`
	UpdatedAt      time.Time `json:"updated_at" gorm:"autoUpdateTime"`
}

type Transfer struct {
	ID              uint64    `json:"id" gorm:"primaryKey"`
	DebitAccountID  uint64    `json:"debit_account_id"`
	CreditAccountID uint64    `json:"credit_account_id"`
	UserData        uint64    `json:"user_data"`
	PendingID       uint64    `json:"pending_id"`
	Timeout         uint64    `json:"timeout"`
	Ledger          uint32    `json:"ledger"`
	Code            uint16    `json:"code"`
	Flags           uint16    `json:"flags"`
	Amount          uint64    `json:"amount"`
	Timestamp       int64     `json:"timestamp"`
	CreatedAt       time.Time `json:"created_at" gorm:"autoCreateTime"`
	UpdatedAt       time.Time `json:"updated_at" gorm:"autoUpdateTime"`
}

type SyncEvent struct {
	ID        string    `json:"id" gorm:"primaryKey"`
	Type      string    `json:"type"`      // "account", "transfer"
	Operation string    `json:"operation"` // "create", "update"
	Data      string    `json:"data" gorm:"type:text"`
	Source    string    `json:"source"`
	Timestamp int64     `json:"timestamp"`
	Processed bool      `json:"processed" gorm:"default:false"`
	Synced    bool      `json:"synced" gorm:"default:false"`
	CreatedAt time.Time `json:"created_at" gorm:"autoCreateTime"`
}

// API request/response models
type AccountCreate struct {
	ID       uint64 `json:"id" binding:"required"`
	UserData uint64 `json:"user_data"`
	Ledger   uint32 `json:"ledger"`
	Code     uint16 `json:"code"`
	Flags    uint16 `json:"flags"`
}

type TransferCreate struct {
	ID              uint64 `json:"id" binding:"required"`
	DebitAccountID  uint64 `json:"debit_account_id" binding:"required"`
	CreditAccountID uint64 `json:"credit_account_id" binding:"required"`
	UserData        uint64 `json:"user_data"`
	PendingID       uint64 `json:"pending_id"`
	Timeout         uint64 `json:"timeout"`
	Ledger          uint32 `json:"ledger"`
	Code            uint16 `json:"code"`
	Flags           uint16 `json:"flags"`
	Amount          uint64 `json:"amount" binding:"required"`
}

type AccountBalance struct {
	AccountID        uint64 `json:"account_id"`
	DebitsPending    uint64 `json:"debits_pending"`
	DebitsPosted     uint64 `json:"debits_posted"`
	CreditsPending   uint64 `json:"credits_pending"`
	CreditsPosted    uint64 `json:"credits_posted"`
	Balance          int64  `json:"balance"`
	AvailableBalance int64  `json:"available_balance"`
}

// TigerBeetleGoEdge represents the edge service
type TigerBeetleGoEdge struct {
	db                *gorm.DB
	redis             *redis.Client
	zigPrimaryURL     string
	edgeID            string
	syncInterval      time.Duration
	offlineMode       bool
	mutex             sync.RWMutex
	lastSyncTime      time.Time
	syncErrors        []string
	accountsCache     map[uint64]*Account
	transfersCache    map[uint64]*Transfer
	pendingSyncEvents []SyncEvent
}

// NewTigerBeetleGoEdge creates a new edge service instance
func NewTigerBeetleGoEdge(dbPath, redisURL, zigPrimaryURL, edgeID string) (*TigerBeetleGoEdge, error) {
	// Initialize SQLite database
	db, err := gorm.Open(sqlite.Open(dbPath), &gorm.Config{})
	if err != nil {
		return nil, fmt.Errorf("failed to connect to SQLite: %v", err)
	}

	// Auto-migrate tables
	err = db.AutoMigrate(&Account{}, &Transfer{}, &SyncEvent{})
	if err != nil {
		return nil, fmt.Errorf("failed to migrate database: %v", err)
	}

	// Initialize Redis client
	opt, err := redis.ParseURL(redisURL)
	if err != nil {
		log.Printf("Failed to parse Redis URL, running in offline mode: %v", err)
		opt = nil
	}

	var redisClient *redis.Client
	if opt != nil {
		redisClient = redis.NewClient(opt)
		// Test Redis connection
		ctx := context.Background()
		_, err = redisClient.Ping(ctx).Result()
		if err != nil {
			log.Printf("Redis connection failed, running in offline mode: %v", err)
			redisClient = nil
		}
	}

	service := &TigerBeetleGoEdge{
		db:             db,
		redis:          redisClient,
		zigPrimaryURL:  zigPrimaryURL,
		edgeID:         edgeID,
		syncInterval:   time.Second * 10, // 10-second sync interval
		offlineMode:    redisClient == nil,
		accountsCache:  make(map[uint64]*Account),
		transfersCache: make(map[uint64]*Transfer),
	}

	// Load existing data into cache
	service.loadCacheFromDB()

	return service, nil
}

// loadCacheFromDB loads existing accounts and transfers into memory cache
func (tbe *TigerBeetleGoEdge) loadCacheFromDB() {
	// Load accounts
	var accounts []Account
	tbe.db.Find(&accounts)
	for _, account := range accounts {
		tbe.accountsCache[account.ID] = &account
	}

	// Load transfers
	var transfers []Transfer
	tbe.db.Find(&transfers)
	for _, transfer := range transfers {
		tbe.transfersCache[transfer.ID] = &transfer
	}

	log.Printf("Loaded %d accounts and %d transfers into cache", len(accounts), len(transfers))
}

// StartSyncWorker starts the background sync worker
func (tbe *TigerBeetleGoEdge) StartSyncWorker(ctx context.Context) {
	if tbe.offlineMode {
		log.Println("Running in offline mode - sync worker disabled")
		return
	}

	go func() {
		ticker := time.NewTicker(tbe.syncInterval)
		defer ticker.Stop()

		for {
			select {
			case <-ctx.Done():
				return
			case <-ticker.C:
				tbe.performSync()
			}
		}
	}()

	// Subscribe to Redis sync events
	go tbe.subscribeToSyncEvents(ctx)

	log.Println("Sync worker started")
}

// performSync performs bidirectional synchronization with Zig primary
func (tbe *TigerBeetleGoEdge) performSync() {
	tbe.mutex.Lock()
	defer tbe.mutex.Unlock()

	log.Println("Starting sync with Zig primary...")

	// Sync from Zig primary to edge
	if err := tbe.syncFromZigPrimary(); err != nil {
		tbe.syncErrors = append(tbe.syncErrors, fmt.Sprintf("sync from zig: %v", err))
		log.Printf("Error syncing from Zig primary: %v", err)
	}

	// Sync from edge to Zig primary
	if err := tbe.syncToZigPrimary(); err != nil {
		tbe.syncErrors = append(tbe.syncErrors, fmt.Sprintf("sync to zig: %v", err))
		log.Printf("Error syncing to Zig primary: %v", err)
	}

	tbe.lastSyncTime = time.Now()
	log.Println("Sync completed")
}

// syncFromZigPrimary syncs data from Zig primary to edge
func (tbe *TigerBeetleGoEdge) syncFromZigPrimary() error {
	// Get pending sync events from Zig primary
	resp, err := http.Get(fmt.Sprintf("%s/sync/events?limit=100", tbe.zigPrimaryURL))
	if err != nil {
		return fmt.Errorf("failed to get sync events: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("Zig primary returned status %d", resp.StatusCode)
	}

	var syncResponse struct {
		Events []SyncEvent `json:"events"`
		Count  int         `json:"count"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&syncResponse); err != nil {
		return fmt.Errorf("failed to decode sync response: %v", err)
	}

	// Process sync events
	processedEventIDs := []string{}
	for _, event := range syncResponse.Events {
		if err := tbe.processSyncEvent(event); err != nil {
			log.Printf("Failed to process sync event %s: %v", event.ID, err)
			continue
		}
		processedEventIDs = append(processedEventIDs, event.ID)
	}

	// Mark events as processed on Zig primary
	if len(processedEventIDs) > 0 {
		if err := tbe.markEventsProcessedOnZig(processedEventIDs); err != nil {
			log.Printf("Failed to mark events processed on Zig: %v", err)
		}
	}

	log.Printf("Processed %d sync events from Zig primary", len(processedEventIDs))
	return nil
}

// syncToZigPrimary syncs data from edge to Zig primary
func (tbe *TigerBeetleGoEdge) syncToZigPrimary() error {
	// Get unsynced events from local database
	var unsyncedEvents []SyncEvent
	if err := tbe.db.Where("synced = ?", false).Limit(100).Find(&unsyncedEvents).Error; err != nil {
		return fmt.Errorf("failed to get unsynced events: %v", err)
	}

	if len(unsyncedEvents) == 0 {
		return nil // Nothing to sync
	}

	// Send events to Zig primary
	eventData, err := json.Marshal(unsyncedEvents)
	if err != nil {
		return fmt.Errorf("failed to marshal sync events: %v", err)
	}

	resp, err := http.Post(
		fmt.Sprintf("%s/sync/from-edge", tbe.zigPrimaryURL),
		"application/json",
		bytes.NewBuffer(eventData),
	)
	if err != nil {
		return fmt.Errorf("failed to send sync events: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("Zig primary returned status %d", resp.StatusCode)
	}

	// Mark events as synced
	eventIDs := make([]string, len(unsyncedEvents))
	for i, event := range unsyncedEvents {
		eventIDs[i] = event.ID
	}

	if err := tbe.db.Model(&SyncEvent{}).Where("id IN ?", eventIDs).Update("synced", true).Error; err != nil {
		return fmt.Errorf("failed to mark events as synced: %v", err)
	}

	log.Printf("Synced %d events to Zig primary", len(unsyncedEvents))
	return nil
}

// processSyncEvent processes a sync event from Zig primary
func (tbe *TigerBeetleGoEdge) processSyncEvent(event SyncEvent) error {
	switch event.Type {
	case "account":
		return tbe.processAccountSyncEvent(event)
	case "transfer":
		return tbe.processTransferSyncEvent(event)
	default:
		return fmt.Errorf("unknown sync event type: %s", event.Type)
	}
}

// processAccountSyncEvent processes account sync event
func (tbe *TigerBeetleGoEdge) processAccountSyncEvent(event SyncEvent) error {
	var accounts []Account
	if err := json.Unmarshal([]byte(event.Data), &accounts); err != nil {
		return fmt.Errorf("failed to unmarshal account data: %v", err)
	}

	for _, account := range accounts {
		// Check if account exists
		var existingAccount Account
		result := tbe.db.First(&existingAccount, account.ID)

		if result.Error == gorm.ErrRecordNotFound {
			// Create new account
			if err := tbe.db.Create(&account).Error; err != nil {
				return fmt.Errorf("failed to create account: %v", err)
			}
			tbe.accountsCache[account.ID] = &account
		} else if result.Error == nil {
			// Update existing account
			if err := tbe.db.Save(&account).Error; err != nil {
				return fmt.Errorf("failed to update account: %v", err)
			}
			tbe.accountsCache[account.ID] = &account
		} else {
			return fmt.Errorf("database error: %v", result.Error)
		}
	}

	return nil
}

// processTransferSyncEvent processes transfer sync event
func (tbe *TigerBeetleGoEdge) processTransferSyncEvent(event SyncEvent) error {
	var transfers []Transfer
	if err := json.Unmarshal([]byte(event.Data), &transfers); err != nil {
		return fmt.Errorf("failed to unmarshal transfer data: %v", err)
	}

	for _, transfer := range transfers {
		// Check if transfer exists
		var existingTransfer Transfer
		result := tbe.db.First(&existingTransfer, transfer.ID)

		if result.Error == gorm.ErrRecordNotFound {
			// Create new transfer
			if err := tbe.db.Create(&transfer).Error; err != nil {
				return fmt.Errorf("failed to create transfer: %v", err)
			}
			tbe.transfersCache[transfer.ID] = &transfer

			// Update account balances in cache
			tbe.updateAccountBalances(transfer)
		} else if result.Error != nil {
			return fmt.Errorf("database error: %v", result.Error)
		}
		// If transfer exists, skip (transfers are immutable)
	}

	return nil
}

// updateAccountBalances updates account balances after a transfer
func (tbe *TigerBeetleGoEdge) updateAccountBalances(transfer Transfer) {
	// Update debit account
	if debitAccount, exists := tbe.accountsCache[transfer.DebitAccountID]; exists {
		debitAccount.DebitsPosted += transfer.Amount
		tbe.db.Save(debitAccount)
	}

	// Update credit account
	if creditAccount, exists := tbe.accountsCache[transfer.CreditAccountID]; exists {
		creditAccount.CreditsPosted += transfer.Amount
		tbe.db.Save(creditAccount)
	}
}

// markEventsProcessedOnZig marks events as processed on Zig primary
func (tbe *TigerBeetleGoEdge) markEventsProcessedOnZig(eventIDs []string) error {
	data, err := json.Marshal(eventIDs)
	if err != nil {
		return err
	}

	resp, err := http.Post(
		fmt.Sprintf("%s/sync/events/mark-processed", tbe.zigPrimaryURL),
		"application/json",
		bytes.NewBuffer(data),
	)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("Zig primary returned status %d", resp.StatusCode)
	}

	return nil
}

// subscribeToSyncEvents subscribes to Redis sync events
func (tbe *TigerBeetleGoEdge) subscribeToSyncEvents(ctx context.Context) {
	if tbe.redis == nil {
		return
	}

	pubsub := tbe.redis.Subscribe(ctx, "tigerbeetle_sync")
	defer pubsub.Close()

	for {
		select {
		case <-ctx.Done():
			return
		case msg := <-pubsub.Channel():
			var event SyncEvent
			if err := json.Unmarshal([]byte(msg.Payload), &event); err != nil {
				log.Printf("Failed to unmarshal sync event: %v", err)
				continue
			}

			// Process real-time sync event
			if err := tbe.processSyncEvent(event); err != nil {
				log.Printf("Failed to process real-time sync event: %v", err)
			}
		}
	}
}

// createSyncEvent creates a sync event for edge-originated changes
func (tbe *TigerBeetleGoEdge) createSyncEvent(eventType, operation string, data interface{}) error {
	dataJSON, err := json.Marshal(data)
	if err != nil {
		return err
	}

	event := SyncEvent{
		ID:        fmt.Sprintf("%s-%d", tbe.edgeID, time.Now().UnixNano()),
		Type:      eventType,
		Operation: operation,
		Data:      string(dataJSON),
		Source:    tbe.edgeID,
		Timestamp: time.Now().UnixNano(),
		Processed: false,
		Synced:    false,
	}

	return tbe.db.Create(&event).Error
}

// SetupRoutes sets up HTTP routes
func (tbe *TigerBeetleGoEdge) SetupRoutes() *gin.Engine {
	gin.SetMode(gin.ReleaseMode)
	r := gin.Default()

	// CORS middleware
	r.Use(func(c *gin.Context) {
		c.Header("Access-Control-Allow-Origin", "*")
		c.Header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
		c.Header("Access-Control-Allow-Headers", "Content-Type, Authorization")

		if c.Request.Method == "OPTIONS" {
			c.AbortWithStatus(204)
			return
		}

		c.Next()
	})

	// Health check
	r.GET("/health", func(c *gin.Context) {
		c.JSON(200, gin.H{
			"status":            "healthy",
			"service":           "tigerbeetle-go-edge",
			"edge_id":           tbe.edgeID,
			"offline_mode":      tbe.offlineMode,
			"last_sync":         tbe.lastSyncTime,
			"accounts_cached":   len(tbe.accountsCache),
			"transfers_cached":  len(tbe.transfersCache),
			"sync_errors":       len(tbe.syncErrors),
		})
	})

	// Account endpoints
	r.POST("/accounts", tbe.createAccounts)
	r.GET("/accounts/:id", tbe.getAccount)
	r.GET("/accounts/:id/balance", tbe.getAccountBalance)

	// Transfer endpoints
	r.POST("/transfers", tbe.createTransfers)
	r.GET("/transfers/:id", tbe.getTransfer)

	// Sync endpoints
	r.GET("/sync/status", tbe.getSyncStatus)
	r.POST("/sync/force", tbe.forceSync)

	// Metrics endpoint
	r.GET("/metrics", tbe.getMetrics)

	return r
}

// createAccounts creates accounts on the edge
func (tbe *TigerBeetleGoEdge) createAccounts(c *gin.Context) {
	var accountsCreate []AccountCreate
	if err := c.ShouldBindJSON(&accountsCreate); err != nil {
		c.JSON(400, gin.H{"error": err.Error()})
		return
	}

	tbe.mutex.Lock()
	defer tbe.mutex.Unlock()

	accounts := make([]Account, len(accountsCreate))
	for i, ac := range accountsCreate {
		accounts[i] = Account{
			ID:        ac.ID,
			UserData:  ac.UserData,
			Ledger:    ac.Ledger,
			Code:      ac.Code,
			Flags:     ac.Flags,
			Timestamp: time.Now().UnixNano(),
		}
	}

	// Save to database
	if err := tbe.db.Create(&accounts).Error; err != nil {
		c.JSON(500, gin.H{"error": fmt.Sprintf("failed to create accounts: %v", err)})
		return
	}

	// Update cache
	for _, account := range accounts {
		tbe.accountsCache[account.ID] = &account
	}

	// Create sync event
	if err := tbe.createSyncEvent("account", "create", accounts); err != nil {
		log.Printf("Failed to create sync event: %v", err)
	}

	c.JSON(201, gin.H{
		"success":          true,
		"accounts_created": len(accounts),
		"offline_mode":     tbe.offlineMode,
	})
}

// getAccount gets an account by ID
func (tbe *TigerBeetleGoEdge) getAccount(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.ParseUint(idStr, 10, 64)
	if err != nil {
		c.JSON(400, gin.H{"error": "invalid account ID"})
		return
	}

	tbe.mutex.RLock()
	account, exists := tbe.accountsCache[id]
	tbe.mutex.RUnlock()

	if !exists {
		c.JSON(404, gin.H{"error": "account not found"})
		return
	}

	c.JSON(200, account)
}

// getAccountBalance gets account balance
func (tbe *TigerBeetleGoEdge) getAccountBalance(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.ParseUint(idStr, 10, 64)
	if err != nil {
		c.JSON(400, gin.H{"error": "invalid account ID"})
		return
	}

	tbe.mutex.RLock()
	account, exists := tbe.accountsCache[id]
	tbe.mutex.RUnlock()

	if !exists {
		c.JSON(404, gin.H{"error": "account not found"})
		return
	}

	balance := int64(account.CreditsPosted) - int64(account.DebitsPosted)
	availableBalance := balance - int64(account.CreditsPending) + int64(account.DebitsPending)

	c.JSON(200, AccountBalance{
		AccountID:        account.ID,
		DebitsPending:    account.DebitsPending,
		DebitsPosted:     account.DebitsPosted,
		CreditsPending:   account.CreditsPending,
		CreditsPosted:    account.CreditsPosted,
		Balance:          balance,
		AvailableBalance: availableBalance,
	})
}

// createTransfers creates transfers on the edge
func (tbe *TigerBeetleGoEdge) createTransfers(c *gin.Context) {
	var transfersCreate []TransferCreate
	if err := c.ShouldBindJSON(&transfersCreate); err != nil {
		c.JSON(400, gin.H{"error": err.Error()})
		return
	}

	tbe.mutex.Lock()
	defer tbe.mutex.Unlock()

	transfers := make([]Transfer, len(transfersCreate))
	for i, tc := range transfersCreate {
		// Validate accounts exist
		if _, exists := tbe.accountsCache[tc.DebitAccountID]; !exists {
			c.JSON(400, gin.H{"error": fmt.Sprintf("debit account %d not found", tc.DebitAccountID)})
			return
		}
		if _, exists := tbe.accountsCache[tc.CreditAccountID]; !exists {
			c.JSON(400, gin.H{"error": fmt.Sprintf("credit account %d not found", tc.CreditAccountID)})
			return
		}

		transfers[i] = Transfer{
			ID:              tc.ID,
			DebitAccountID:  tc.DebitAccountID,
			CreditAccountID: tc.CreditAccountID,
			UserData:        tc.UserData,
			PendingID:       tc.PendingID,
			Timeout:         tc.Timeout,
			Ledger:          tc.Ledger,
			Code:            tc.Code,
			Flags:           tc.Flags,
			Amount:          tc.Amount,
			Timestamp:       time.Now().UnixNano(),
		}
	}

	// Save to database
	if err := tbe.db.Create(&transfers).Error; err != nil {
		c.JSON(500, gin.H{"error": fmt.Sprintf("failed to create transfers: %v", err)})
		return
	}

	// Update cache and account balances
	for _, transfer := range transfers {
		tbe.transfersCache[transfer.ID] = &transfer
		tbe.updateAccountBalances(transfer)
	}

	// Create sync event
	if err := tbe.createSyncEvent("transfer", "create", transfers); err != nil {
		log.Printf("Failed to create sync event: %v", err)
	}

	c.JSON(201, gin.H{
		"success":           true,
		"transfers_created": len(transfers),
		"offline_mode":      tbe.offlineMode,
	})
}

// getTransfer gets a transfer by ID
func (tbe *TigerBeetleGoEdge) getTransfer(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.ParseUint(idStr, 10, 64)
	if err != nil {
		c.JSON(400, gin.H{"error": "invalid transfer ID"})
		return
	}

	tbe.mutex.RLock()
	transfer, exists := tbe.transfersCache[id]
	tbe.mutex.RUnlock()

	if !exists {
		c.JSON(404, gin.H{"error": "transfer not found"})
		return
	}

	c.JSON(200, transfer)
}

// getSyncStatus gets synchronization status
func (tbe *TigerBeetleGoEdge) getSyncStatus(c *gin.Context) {
	tbe.mutex.RLock()
	defer tbe.mutex.RUnlock()

	var pendingEvents int64
	tbe.db.Model(&SyncEvent{}).Where("synced = ?", false).Count(&pendingEvents)

	c.JSON(200, gin.H{
		"edge_id":           tbe.edgeID,
		"offline_mode":      tbe.offlineMode,
		"last_sync":         tbe.lastSyncTime,
		"pending_events":    pendingEvents,
		"sync_errors":       tbe.syncErrors,
		"accounts_cached":   len(tbe.accountsCache),
		"transfers_cached":  len(tbe.transfersCache),
	})
}

// forceSync forces immediate synchronization
func (tbe *TigerBeetleGoEdge) forceSync(c *gin.Context) {
	if tbe.offlineMode {
		c.JSON(400, gin.H{"error": "cannot sync in offline mode"})
		return
	}

	go tbe.performSync()

	c.JSON(200, gin.H{
		"success": true,
		"message": "sync initiated",
	})
}

// getMetrics gets service metrics
func (tbe *TigerBeetleGoEdge) getMetrics(c *gin.Context) {
	tbe.mutex.RLock()
	defer tbe.mutex.RUnlock()

	var pendingEvents int64
	tbe.db.Model(&SyncEvent{}).Where("synced = ?", false).Count(&pendingEvents)

	c.JSON(200, gin.H{
		"edge_id":           tbe.edgeID,
		"accounts_total":    len(tbe.accountsCache),
		"transfers_total":   len(tbe.transfersCache),
		"pending_events":    pendingEvents,
		"offline_mode":      tbe.offlineMode,
		"last_sync":         tbe.lastSyncTime,
		"sync_errors_count": len(tbe.syncErrors),
	})
}

func tigerbeetle_go_edgeMain() {
	// Configuration from environment variables
	dbPath := getEnv("SQLITE_DB_PATH", "/data/tigerbeetle_edge.db")
	redisURL := getEnv("REDIS_URL", "redis://:redis_secure_password@redis:6379")
	zigPrimaryURL := getEnv("ZIG_PRIMARY_URL", "http://tigerbeetle-zig-primary:8030")
	edgeID := getEnv("EDGE_ID", "edge-1")
	port := getEnv("PORT", "8031")

	// Create TigerBeetle Go Edge service
	service, err := NewTigerBeetleGoEdge(dbPath, redisURL, zigPrimaryURL, edgeID)
	if err != nil {
		log.Fatalf("Failed to create TigerBeetle Go Edge service: %v", err)
	}

	// Start sync worker
	ctx := context.Background()
	service.StartSyncWorker(ctx)

	// Setup routes and start server
	r := service.SetupRoutes()

	log.Printf("Starting TigerBeetle Go Edge service on port %s", port)
	log.Printf("Edge ID: %s", edgeID)
	log.Printf("Zig Primary URL: %s", zigPrimaryURL)
	log.Printf("Offline Mode: %v", service.offlineMode)

	if err := r.Run(":" + port); err != nil {
		log.Fatalf("Failed to start server: %v", err)
	}
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}
