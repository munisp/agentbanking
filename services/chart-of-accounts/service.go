package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/google/uuid"
	"github.com/redis/go-redis/v9"
	"github.com/segmentio/kafka-go"
	tigerbeetle "github.com/tigerbeetle/tigerbeetle-go"
	"github.com/tigerbeetle/tigerbeetle-go/pkg/types"
)

type ChartOfAccountsService struct {
	tigerBeetle tigerbeetle.Client
	postgres    *PostgresStore // PostgreSQL persistent storage
	redis       *redis.Client
	kafkaWriter *kafka.Writer

	// Separate mutex for TigerBeetle operations (CGo is not thread-safe)
	tbMu sync.Mutex

	reconciliationStatus map[string]ReconciliationStatus

	// Semaphore to limit concurrent async operations
	eventSem chan struct{} // Limit concurrent event publishing
}

func NewChartOfAccountsService(ctx context.Context) (*ChartOfAccountsService, error) {
	service := &ChartOfAccountsService{
		reconciliationStatus: make(map[string]ReconciliationStatus),
		// Limit concurrent async ops to prevent goroutine explosion
		eventSem: make(chan struct{}, 100),
	}

	// Initialize PostgreSQL first (critical for persistence)
	if err := service.initPostgres(ctx); err != nil {
		log.Printf("WARNING: PostgreSQL connection failed: %v", err)
	}

	if err := service.initTigerBeetle(ctx); err != nil {
		log.Printf("WARNING: TigerBeetle connection failed: %v", err)
	}

	if err := service.initRedis(ctx); err != nil {
		log.Printf("WARNING: Redis connection failed: %v", err)
	}

	if err := service.initKafka(); err != nil {
		log.Printf("WARNING: Kafka connection failed: %v", err)
	}

	return service, nil
}

func (s *ChartOfAccountsService) initPostgres(ctx context.Context) error {
	postgres, err := NewPostgresStore(ctx)
	if err != nil {
		return fmt.Errorf("failed to initialize PostgreSQL: %w", err)
	}
	s.postgres = postgres
	return nil
}

func (s *ChartOfAccountsService) initTigerBeetle(ctx context.Context) error {
	addrsEnv := os.Getenv("TIGERBEETLE_ADDRESSES")
	if addrsEnv == "" {
		addrsEnv = os.Getenv("TIGERBEETLE_ADDRESS")
	}
	if addrsEnv == "" {
		addrsEnv = "tigerbeetle:3000"
	}

	addresses := strings.Split(addrsEnv, ",")
	for i, addr := range addresses {
		addresses[i] = strings.TrimSpace(addr)
	}

	clusterIDStr := os.Getenv("TIGERBEETLE_CLUSTER_ID")
	if clusterIDStr == "" {
		clusterIDStr = "00000000000000000000000000000000"
	}

	clusterID, err := types.HexStringToUint128(clusterIDStr)
	if err != nil {
		return fmt.Errorf("failed to parse cluster ID: %w", err)
	}

	client, err := tigerbeetle.NewClient(clusterID, addresses)
	if err != nil {
		return fmt.Errorf("failed to connect to TigerBeetle: %w", err)
	}

	s.tigerBeetle = client
	log.Printf("Connected to TigerBeetle at %v", addresses)
	return nil
}

func (s *ChartOfAccountsService) initRedis(ctx context.Context) error {
	redisAddr := os.Getenv("REDIS_ADDRESS")
	if redisAddr == "" {
		redisAddr = "redis:6379"
	}

	redisPassword := os.Getenv("REDIS_PASSWORD")
	redisDB := 0
	if dbStr := os.Getenv("REDIS_DB"); dbStr != "" {
		if db, err := strconv.Atoi(dbStr); err == nil {
			redisDB = db
		}
	}

	s.redis = redis.NewClient(&redis.Options{
		Addr:         redisAddr,
		Password:     redisPassword,
		DB:           redisDB,
		DialTimeout:  5 * time.Second,
		ReadTimeout:  3 * time.Second,
		WriteTimeout: 3 * time.Second,
		// Increase pool size to match our semaphore limits (100 cache ops)
		// But keep reasonable to avoid overwhelming Redis
		PoolSize:     50,
		MinIdleConns: 10,
		MaxRetries:   2,
		// Add pool timeout to prevent goroutines waiting forever for connections
		PoolTimeout: 4 * time.Second,
	})

	if err := s.redis.Ping(ctx).Err(); err != nil {
		return fmt.Errorf("failed to connect to Redis: %w", err)
	}

	log.Printf("Connected to Redis at %s", redisAddr)
	return nil
}

func (s *ChartOfAccountsService) initKafka() error {
	kafkaBrokers := os.Getenv("KAFKA_BROKERS")
	if kafkaBrokers == "" {
		kafkaBrokers = "kafka:9092"
	}

	kafkaTopic := os.Getenv("KAFKA_TOPIC")
	if kafkaTopic == "" {
		kafkaTopic = "chart-of-accounts.events"
	}

	// Auto-create topic if it doesn't exist
	conn, err := kafka.Dial("tcp", strings.Split(kafkaBrokers, ",")[0])
	if err == nil {
		defer conn.Close()

		partitions := 3
		replicationFactor := 1

		topicConfigs := []kafka.TopicConfig{
			{
				Topic:             kafkaTopic,
				NumPartitions:     partitions,
				ReplicationFactor: replicationFactor,
			},
		}

		err = conn.CreateTopics(topicConfigs...)
		if err != nil {
			// Ignore error if topic already exists
			log.Printf("Topic creation result (may already exist): %v", err)
		} else {
			log.Printf("Created Kafka topic %s with %d partitions", kafkaTopic, partitions)
		}
	}

	s.kafkaWriter = &kafka.Writer{
		Addr:         kafka.TCP(strings.Split(kafkaBrokers, ",")...),
		Topic:        kafkaTopic,
		Balancer:     &kafka.LeastBytes{},
		BatchTimeout: 10 * time.Millisecond,
		RequiredAcks: kafka.RequireAll,
		WriteTimeout: 5 * time.Second,
		ReadTimeout:  5 * time.Second,
		MaxAttempts:  3,
		Async:        false,
	}

	log.Printf("Kafka writer configured for topic %s at %s", kafkaTopic, kafkaBrokers)
	return nil
}

func (s *ChartOfAccountsService) Close() {
	if s.tigerBeetle != nil {
		s.tbMu.Lock()
		s.tigerBeetle.Close()
		s.tbMu.Unlock()
	}
	if s.redis != nil {
		s.redis.Close()
	}
	if s.kafkaWriter != nil {
		s.kafkaWriter.Close()
	}
}

func (s *ChartOfAccountsService) HealthCheck() ServiceHealth {
	health := ServiceHealth{
		Status:             "healthy",
		TigerBeetleHealthy: false,
		RedisHealthy:       false,
		KafkaHealthy:       true,
		PostgresHealthy:    true,
	}

	if s.tigerBeetle != nil {
		s.tbMu.Lock()
		_, err := s.tigerBeetle.LookupAccounts([]types.Uint128{})
		s.tbMu.Unlock()
		health.TigerBeetleHealthy = err == nil
	}

	if s.redis != nil {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		health.RedisHealthy = s.redis.Ping(ctx).Err() == nil
	}

	if !health.TigerBeetleHealthy || !health.RedisHealthy {
		health.Status = "degraded"
	}

	return health
}

func (s *ChartOfAccountsService) InitializeDefaultCoA(ctx context.Context) error {
	return s.initializeTenantCoA(ctx, "default")
}

func (s *ChartOfAccountsService) initializeTenantCoA(ctx context.Context, tenantID string) error {
	// Add timeout to prevent indefinite blocking
	ctx, cancel := context.WithTimeout(ctx, 120*time.Second)
	defer cancel()

	defaultAccounts := GetDefaultAccounts()
	accountsByCode := make(map[string]string)

	// OPTIMIZATION: Batch create all TigerBeetle accounts first
	if s.tigerBeetle != nil {
		log.Printf("Creating %d TigerBeetle accounts in batch for tenant %s", len(defaultAccounts), tenantID)
		tbAccounts := make([]types.Account, 0, len(defaultAccounts))

		for _, req := range defaultAccounts {
			tbLedger := uint32(1)
			tbCode := uint16(1)
			tbAccountID := s.generateTigerBeetleID(tenantID, req.Code)

			tbAccounts = append(tbAccounts, types.Account{
				ID:     tbAccountID,
				Ledger: tbLedger,
				Code:   tbCode,
				Flags:  0,
			})
		}

		// Single batch operation instead of 217 individual calls
		if err := s.createTigerBeetleAccountsBatch(ctx, tbAccounts); err != nil {
			log.Printf("WARNING: Batch TigerBeetle account creation failed: %v", err)
		} else {
			log.Printf("Successfully created %d TigerBeetle accounts in batch", len(tbAccounts))
		}
	}

	log.Printf("Creating %d accounts in PostgreSQL for tenant %s", len(defaultAccounts), tenantID)

	// OPTIMIZATION: Batch create all accounts (in-memory + PostgreSQL)
	allAccounts := make([]Account, 0, len(defaultAccounts))

	for _, req := range defaultAccounts {
		select {
		case <-ctx.Done():
			return fmt.Errorf("initialization timeout: %w", ctx.Err())
		default:
		}

		accountID := uuid.New().String()
		now := time.Now()
		normalBalance := GetNormalBalance(req.Type)
		currency := req.Currency
		if currency == "" {
			currency = "NGN"
		}

		account := Account{
			ID:                accountID,
			TenantID:          tenantID,
			Code:              req.Code,
			Name:              req.Name,
			Description:       req.Description,
			Type:              req.Type,
			NormalBalance:     normalBalance,
			ParentID:          req.ParentID,
			Level:             0,
			IsActive:          true,
			IsSystemAccount:   true,
			Currency:          currency,
			TigerBeetleLedger: 1, // All accounts use ledger 1
			TigerBeetleCode:   s.getCodeFromAccountCode(req.Code),
			CBNCode:           req.CBNCode,
			Tags:              req.Tags,
			Metadata:          req.Metadata,
			CreatedAt:         now,
			UpdatedAt:         now,
		}

		// Set TigerBeetle ID (already created in batch)
		if s.tigerBeetle != nil {
			tbAccountID := s.generateTigerBeetleID(tenantID, req.Code)
			account.TigerBeetleID = tbAccountID.String()
		}

		allAccounts = append(allAccounts, account)
		accountsByCode[req.Code] = accountID
	}

	// Bulk insert into PostgreSQL (single transaction)
	if s.postgres != nil {
		if err := s.postgres.BulkSaveAccounts(ctx, allAccounts); err != nil {
			log.Printf("ERROR: Failed to bulk save accounts to PostgreSQL: %v", err)
			return fmt.Errorf("failed to persist accounts: %w", err)
		}
		log.Printf("Successfully saved %d accounts to PostgreSQL", len(allAccounts))
	}

	log.Printf("Initialized %d default accounts for tenant %s", len(accountsByCode), tenantID)
	return nil
}

func (s *ChartOfAccountsService) calculateLevel(tenantID, parentID string) int {
	if parentID == "" {
		return 0
	}

	if s.postgres == nil {
		return 0
	}

	parent, err := s.postgres.GetAccount(context.Background(), tenantID, parentID)
	if err != nil || parent == nil {
		return 0
	}
	return parent.Level
}

func (s *ChartOfAccountsService) ListAccounts(ctx context.Context, tenantID, accountType, parentID string, activeOnly bool) ([]Account, error) {
	log.Printf("ListAccounts called for tenant: %s, type: %s, parent: %s", tenantID, accountType, parentID)

	// Query PostgreSQL directly (no caching)
	if s.postgres == nil {
		return nil, errors.New("PostgreSQL not connected")
	}

	log.Printf("Querying PostgreSQL for accounts...")
	accounts, err := s.postgres.ListAccounts(ctx, tenantID, accountType, parentID, activeOnly)
	if err != nil {
		log.Printf("PostgreSQL query failed: %v", err)
		return nil, err
	}

	// CRITICAL FIX: Ensure TigerBeetleLedger is set to 1 for all accounts
	// This fixes legacy accounts that may have ledger=0
	for i := range accounts {
		if accounts[i].TigerBeetleLedger == 0 {
			accounts[i].TigerBeetleLedger = 1
			log.Printf("Fixed ledger for account %s (%s): ledger=1", accounts[i].Code, accounts[i].Name)
		}
	}

	log.Printf("Found %d accounts", len(accounts))
	return accounts, nil
}

func (s *ChartOfAccountsService) CreateAccount(ctx context.Context, tenantID string, req CreateAccountRequest) (*Account, error) {
	if s.postgres == nil {
		return nil, errors.New("PostgreSQL not connected")
	}

	// Check for existing account in PostgreSQL
	existing, _ := s.postgres.GetAccountByCode(ctx, tenantID, req.Code)
	if existing != nil {
		return existing, nil
	}

	accountID := uuid.New().String()
	now := time.Now()
	normalBalance := GetNormalBalance(req.Type)
	currency := req.Currency
	if currency == "" {
		currency = "NGN"
	}

	account := Account{
		ID:                accountID,
		TenantID:          tenantID,
		Code:              req.Code,
		Name:              req.Name,
		Description:       req.Description,
		Type:              req.Type,
		NormalBalance:     normalBalance,
		ParentID:          req.ParentID,
		Level:             0,
		IsActive:          true,
		IsSystemAccount:   true,
		Currency:          currency,
		TigerBeetleLedger: uint32(1),
		TigerBeetleCode:   s.getCodeFromAccountCode(req.Code),
		CBNCode:           req.CBNCode,
		Tags:              req.Tags,
		Metadata:          req.Metadata,
		CreatedAt:         now,
		UpdatedAt:         now,
	}

	if req.ParentID != "" {
		account.Level = s.calculateLevelUnsafe(tenantID, req.ParentID) + 1
	}

	// Set TigerBeetle ID (account already created in batch during initialization)
	if s.tigerBeetle != nil {
		tbAccountID := s.generateTigerBeetleID(tenantID, req.Code)
		account.TigerBeetleID = tbAccountID.String()
	}

	// PHASE 2: Re-acquire lock to update map (no CGo operations needed)

	// Persist to PostgreSQL (critical - must succeed)
	if s.postgres != nil {
		if err := s.postgres.SaveAccount(ctx, account); err != nil {
			log.Printf("ERROR: Failed to persist account to PostgreSQL: %v", err)
			// Continue anyway - account exists in memory and TigerBeetle
		}
	}

	// Async operations with semaphore control and graceful degradation
	// Try to publish event - drop if system is overloaded
	select {
	case s.eventSem <- struct{}{}:
		go func() {
			defer func() { <-s.eventSem }()
			ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
			defer cancel()

			if err := s.publishEvent(ctx, CoAEvent{
				EventID:     uuid.New().String(),
				EventType:   EventAccountCreated,
				TenantID:    tenantID,
				EntityID:    accountID,
				EntityType:  "account",
				Payload:     map[string]interface{}{"code": req.Code, "name": req.Name, "type": string(req.Type)},
				Timestamp:   now,
				ServiceName: ServiceName,
			}); err != nil {
				// Log but don't fail the request
				log.Printf("Failed to publish event (non-critical): %v", err)
			}
		}()
	default:
		// System overloaded, drop event (account is still created successfully)
		log.Printf("Event queue full, dropping AccountCreated event for %s (account created successfully)", req.Code)
	}

	// Try to cache - drop if system is overloaded

	return &account, nil
}

func (s *ChartOfAccountsService) calculateLevelUnsafe(tenantID, parentID string) int {
	if parentID == "" || s.postgres == nil {
		return 0
	}
	parent, err := s.postgres.GetAccount(context.Background(), tenantID, parentID)
	if err != nil || parent == nil {
		return 0
	}
	return parent.Level
}

func (s *ChartOfAccountsService) GetAccount(ctx context.Context, tenantID, accountID string) (*Account, error) {
	if s.postgres == nil {
		return nil, errors.New("PostgreSQL not connected")
	}

	account, err := s.postgres.GetAccount(ctx, tenantID, accountID)
	if err != nil {
		return nil, fmt.Errorf("account not found: %w", err)
	}

	// Auto-fix legacy accounts with ledger=0
	if account.TigerBeetleLedger == 0 {
		account.TigerBeetleLedger = 1
		if updateErr := s.postgres.SaveAccount(ctx, *account); updateErr != nil {
			log.Printf("WARNING: Failed to update account ledger: %v", updateErr)
		}
	}

	return account, nil
}

// Fast account creation for initialization - skips event publishing and caching
func (s *ChartOfAccountsService) createAccountFast(ctx context.Context, tenantID string, req CreateAccountRequest) (*Account, error) {
	if s.postgres == nil {
		return nil, errors.New("PostgreSQL not connected")
	}

	// Check for existing in PostgreSQL
	existing, _ := s.postgres.GetAccountByCode(ctx, tenantID, req.Code)
	if existing != nil {
		return existing, nil
	}

	accountID := uuid.New().String()
	now := time.Now()
	normalBalance := GetNormalBalance(req.Type)
	currency := req.Currency
	if currency == "" {
		currency = "NGN"
	}

	account := Account{
		ID:                accountID,
		TenantID:          tenantID,
		Code:              req.Code,
		Name:              req.Name,
		Description:       req.Description,
		Type:              req.Type,
		NormalBalance:     normalBalance,
		ParentID:          req.ParentID,
		Level:             0,
		IsActive:          true,
		IsSystemAccount:   true,
		Currency:          currency,
		TigerBeetleLedger: uint32(1),
		TigerBeetleCode:   s.getCodeFromAccountCode(req.Code),
		CBNCode:           req.CBNCode,
		Tags:              req.Tags,
		Metadata:          req.Metadata,
		CreatedAt:         now,
		UpdatedAt:         now,
	}

	if req.ParentID != "" {
		account.Level = s.calculateLevelUnsafe(tenantID, req.ParentID) + 1
	}

	// Set TigerBeetle ID (already created in batch)
	if s.tigerBeetle != nil {
		tbAccountID := s.generateTigerBeetleID(tenantID, req.Code)
		account.TigerBeetleID = tbAccountID.String()
	}

	// Persist to PostgreSQL only (no events, no cache during initialization)
	if err := s.postgres.SaveAccount(ctx, account); err != nil {
		return nil, fmt.Errorf("failed to persist account: %w", err)
	}

	return &account, nil
}

func (s *ChartOfAccountsService) UpdateAccount(ctx context.Context, tenantID, accountID string, req UpdateAccountRequest) (*Account, error) {
	if s.postgres == nil {
		return nil, errors.New("PostgreSQL not connected")
	}

	account, err := s.postgres.GetAccount(ctx, tenantID, accountID)
	if err != nil {
		return nil, errors.New("account not found")
	}

	if req.Name != "" {
		account.Name = req.Name
	}
	if req.Description != "" {
		account.Description = req.Description
	}
	if req.IsActive != nil {
		account.IsActive = *req.IsActive
	}
	if req.CBNCode != "" {
		account.CBNCode = req.CBNCode
	}
	if req.Tags != nil {
		account.Tags = req.Tags
	}
	if req.Metadata != nil {
		account.Metadata = req.Metadata
	}
	account.UpdatedAt = time.Now()

	// Persist to PostgreSQL
	if err := s.postgres.SaveAccount(ctx, *account); err != nil {
		log.Printf("ERROR: Failed to update account in PostgreSQL: %v", err)
		return nil, err
	}

	go s.publishEvent(context.Background(), CoAEvent{
		EventID:     uuid.New().String(),
		EventType:   EventAccountUpdated,
		TenantID:    tenantID,
		EntityID:    accountID,
		EntityType:  "account",
		Payload:     map[string]interface{}{"code": account.Code, "name": account.Name},
		Timestamp:   time.Now(),
		ServiceName: ServiceName,
	})

	return account, nil
}

func (s *ChartOfAccountsService) DeleteAccount(ctx context.Context, tenantID, accountID string) error {
	if s.postgres == nil {
		return errors.New("PostgreSQL not connected")
	}

	account, err := s.postgres.GetAccount(ctx, tenantID, accountID)
	if err != nil {
		return errors.New("account not found")
	}

	if account.IsSystemAccount {
		return errors.New("cannot delete system account")
	}

	account.IsActive = false
	account.UpdatedAt = time.Now()

	// Persist to PostgreSQL (soft delete)
	if err := s.postgres.SaveAccount(ctx, *account); err != nil {
		log.Printf("ERROR: Failed to delete account in PostgreSQL: %v", err)
		return err
	}

	go s.publishEvent(context.Background(), CoAEvent{
		EventID:     uuid.New().String(),
		EventType:   EventAccountDeleted,
		TenantID:    tenantID,
		EntityID:    accountID,
		EntityType:  "account",
		Payload:     map[string]interface{}{"code": account.Code},
		Timestamp:   time.Now(),
		ServiceName: ServiceName,
	})

	if s.redis != nil {
		cacheKey := fmt.Sprintf("coa:%s:account:%s", tenantID, accountID)
		s.redis.Del(ctx, cacheKey)
	}

	return nil
}

func (s *ChartOfAccountsService) GetAccountBalance(ctx context.Context, tenantID, accountID string) (*AccountBalance, error) {
	// Get account from PostgreSQL
	account, err := s.GetAccount(ctx, tenantID, accountID)
	if err != nil {
		return nil, err
	}

	balance := &AccountBalance{
		AccountID:   accountID,
		AccountCode: account.Code,
		AccountName: account.Name,
		Currency:    account.Currency,
		AsOfDate:    time.Now(),
	}

	// PHASE 2: TigerBeetle lookup (CGo) - NO main lock held
	if s.tigerBeetle != nil && account.TigerBeetleID != "" {
		tbID, err := types.HexStringToUint128(account.TigerBeetleID)
		if err == nil {
			s.tbMu.Lock()
			accounts, err := s.tigerBeetle.LookupAccounts([]types.Uint128{tbID})
			s.tbMu.Unlock()

			if err == nil && len(accounts) > 0 {
				tbAccount := accounts[0]
				bal := tbAccount.DebitsPosted.BigInt()
				balance.DebitBalance = bal.Int64()
				bal = tbAccount.CreditsPosted.BigInt()
				balance.CreditBalance = bal.Int64()
				bal = tbAccount.DebitsPending.BigInt()
				balance.PendingDebits = bal.Int64()
				bal = tbAccount.CreditsPending.BigInt()
				balance.PendingCredits = bal.Int64()
			}
		}
	}

	// Calculate net balance
	if account.NormalBalance == NormalBalanceDebit {
		balance.NetBalance = balance.DebitBalance - balance.CreditBalance
		balance.BalanceType = "debit"
	} else {
		balance.NetBalance = balance.CreditBalance - balance.DebitBalance
		balance.BalanceType = "credit"
	}

	return balance, nil
}

// GetAccountBalancesBatch fetches balances for multiple accounts in a single TigerBeetle call.
// Returns a map of account ID → AccountBalance. Accounts with no TB ID or failed lookups are omitted.
func (s *ChartOfAccountsService) GetAccountBalancesBatch(ctx context.Context, accounts []Account) map[string]*AccountBalance {
	result := make(map[string]*AccountBalance, len(accounts))
	if s.tigerBeetle == nil {
		return result
	}

	tbIDs := make([]types.Uint128, 0, len(accounts))
	tbIDToAccount := make(map[string]*Account, len(accounts))

	for i := range accounts {
		if accounts[i].TigerBeetleID == "" {
			continue
		}
		tbID, err := types.HexStringToUint128(accounts[i].TigerBeetleID)
		if err != nil {
			continue
		}
		tbIDs = append(tbIDs, tbID)
		tbIDToAccount[accounts[i].TigerBeetleID] = &accounts[i]
	}

	if len(tbIDs) == 0 {
		return result
	}

	s.tbMu.Lock()
	tbAccounts, err := s.tigerBeetle.LookupAccounts(tbIDs)
	s.tbMu.Unlock()

	if err != nil {
		return result
	}

	for _, tbAcc := range tbAccounts {
		acc := tbIDToAccount[tbAcc.ID.String()]
		if acc == nil {
			continue
		}
		debits := tbAcc.DebitsPosted.BigInt()
		credits := tbAcc.CreditsPosted.BigInt()
		pendingD := tbAcc.DebitsPending.BigInt()
		pendingC := tbAcc.CreditsPending.BigInt()
		bal := &AccountBalance{
			AccountID:     acc.ID,
			AccountCode:   acc.Code,
			AccountName:   acc.Name,
			Currency:      acc.Currency,
			DebitBalance:  debits.Int64(),
			CreditBalance: credits.Int64(),
			PendingDebits: pendingD.Int64(),
			PendingCredits: pendingC.Int64(),
			AsOfDate:      time.Now(),
		}
		if acc.NormalBalance == NormalBalanceDebit {
			bal.NetBalance = bal.DebitBalance - bal.CreditBalance
			bal.BalanceType = "debit"
		} else {
			bal.NetBalance = bal.CreditBalance - bal.DebitBalance
			bal.BalanceType = "credit"
		}
		result[acc.ID] = bal
	}

	return result
}

func (s *ChartOfAccountsService) GetAccountHistory(ctx context.Context, tenantID, accountID string) (*AccountHistory, error) {
	account, err := s.GetAccount(ctx, tenantID, accountID)
	if err != nil {
		return nil, err
	}

	history := &AccountHistory{
		AccountID:    accountID,
		Transactions: []TransactionRecord{},
	}

	if s.tigerBeetle != nil && account.TigerBeetleID != "" {
		tbID, err := types.HexStringToUint128(account.TigerBeetleID)
		if err == nil {
			filter := types.AccountFilter{
				AccountID:    tbID,
				TimestampMin: 0,
				TimestampMax: 0,
				Limit:        100,
				Flags:        0, // Get all transfers
			}

			s.tbMu.Lock()
			transfers, err := s.tigerBeetle.GetAccountTransfers(filter)
			s.tbMu.Unlock()
			if err == nil {
				var runningBalance int64
				for _, transfer := range transfers {
					var debitAmount, creditAmount int64
					if transfer.DebitAccountID == tbID {
						amt := transfer.Amount.BigInt()
						debitAmount = amt.Int64()
						runningBalance -= debitAmount
					} else {
						amt := transfer.Amount.BigInt()
						creditAmount = amt.Int64()
						runningBalance += creditAmount
					}

					record := TransactionRecord{
						TransactionID:  transfer.ID.String(),
						Date:           time.Unix(0, int64(transfer.Timestamp)),
						DebitAmount:    debitAmount,
						CreditAmount:   creditAmount,
						RunningBalance: runningBalance,
					}
					history.Transactions = append(history.Transactions, record)
				}
			}
		}
	}

	history.TotalCount = len(history.Transactions)
	return history, nil
}

func (s *ChartOfAccountsService) GetAccountHierarchy(ctx context.Context, tenantID string) (*AccountHierarchy, error) {
	// Get all accounts from PostgreSQL
	accounts, err := s.ListAccounts(ctx, tenantID, "", "", true)
	if err != nil {
		return nil, err
	}

	// Build account map for hierarchy construction
	accountMap := make(map[string]Account)
	for _, acc := range accounts {
		accountMap[acc.ID] = acc
	}

	hierarchy := &AccountHierarchy{
		TenantID: tenantID,
		Roots:    []AccountNode{},
	}

	for _, account := range accounts {
		if account.ParentID == "" && account.IsActive {
			node := s.buildAccountNodeFromMap(accountMap, account)
			hierarchy.Roots = append(hierarchy.Roots, node)
		}
	}

	return hierarchy, nil
}

func (s *ChartOfAccountsService) buildAccountNode(tenantID string, account Account) AccountNode {
	node := AccountNode{
		Account:  account,
		Children: []AccountNode{},
	}

	// Get children from PostgreSQL
	if s.postgres != nil {
		children, err := s.postgres.ListAccounts(context.Background(), tenantID, "", account.ID, true)
		if err == nil {
			for _, child := range children {
				childNode := s.buildAccountNode(tenantID, child)
				node.Children = append(node.Children, childNode)
			}
		}
	}

	return node
}

func (s *ChartOfAccountsService) buildAccountNodeFromMap(accountMap map[string]Account, account Account) AccountNode {
	node := AccountNode{
		Account:  account,
		Children: []AccountNode{},
	}

	for _, child := range accountMap {
		if child.ParentID == account.ID && child.IsActive {
			childNode := s.buildAccountNodeFromMap(accountMap, child)
			node.Children = append(node.Children, childNode)
		}
	}

	return node
}

func (s *ChartOfAccountsService) GetChildAccounts(ctx context.Context, tenantID, parentID string) ([]Account, error) {
	// Get all accounts from PostgreSQL and filter by parent
	return s.ListAccounts(ctx, tenantID, "", parentID, true)
}

func (s *ChartOfAccountsService) getChildAccountsLegacy(ctx context.Context, tenantID, parentID string) ([]Account, error) {
	// Use the main ListAccounts function which queries PostgreSQL
	return s.ListAccounts(ctx, tenantID, "", parentID, true)
}

func (s *ChartOfAccountsService) CreateJournalEntry(ctx context.Context, tenantID string, req CreateJournalEntryRequest) (*JournalEntry, error) {
	// Validate balance
	var totalDebits, totalCredits int64
	for _, line := range req.Lines {
		totalDebits += line.DebitAmount
		totalCredits += line.CreditAmount
	}

	if totalDebits != totalCredits {
		return nil, fmt.Errorf("journal entry not balanced: debits=%d, credits=%d", totalDebits, totalCredits)
	}

	if len(req.Lines) < 2 {
		return nil, errors.New("journal entry must have at least 2 lines")
	}

	// PHASE 1: Prepare entry with main lock

	entryID := uuid.New().String()
	// Use first 8 chars of tenantID or full string if shorter
	tenantPrefix := tenantID
	if len(tenantID) > 8 {
		tenantPrefix = tenantID
	}
	entryNumber := fmt.Sprintf("JE-%s-%d", tenantPrefix, time.Now().UnixNano())
	now := time.Now()

	var lines []JournalLine
	var accountsForTransfer []JournalLine

	for i, lineReq := range req.Lines {
		var account *Account

		account, _ = s.postgres.GetAccount(ctx, tenantID, lineReq.AccountID)
		if account == nil {
			account, _ = s.postgres.GetAccountByCode(ctx, tenantID, lineReq.AccountID)
		}

		if account == nil {
			log.Printf("ERROR: Account not found for line %d: %s", i+1, lineReq.AccountID)
			return nil, fmt.Errorf("account %s not found", lineReq.AccountID)
		}

		line := JournalLine{
			ID:           fmt.Sprintf("%s-L%d", entryID, i+1),
			AccountID:    account.ID, // Use actual account ID from looked up account
			AccountCode:  account.Code,
			AccountName:  account.Name,
			Description:  lineReq.Description,
			DebitAmount:  lineReq.DebitAmount,
			CreditAmount: lineReq.CreditAmount,
		}
		lines = append(lines, line)
	}

	// Copy lines for TigerBeetle processing
	accountsForTransfer = append([]JournalLine{}, lines...)

	// Release main lock before CGo operations

	// PHASE 2: TigerBeetle operations (CGo) - NO main lock held
	var tbTransferIDs []string
	if s.tigerBeetle != nil {
		var debitAccounts, creditAccounts []JournalLine
		for _, line := range accountsForTransfer {
			if line.DebitAmount > 0 {
				debitAccounts = append(debitAccounts, line)
			}
			if line.CreditAmount > 0 {
				creditAccounts = append(creditAccounts, line)
			}
		}

		for _, debit := range debitAccounts {
			for _, credit := range creditAccounts {
				amount := debit.DebitAmount
				if credit.CreditAmount < amount {
					amount = credit.CreditAmount
				}

				if amount > 0 {
					transferID, err := s.createTigerBeetleTransfer(ctx, tenantID, debit.AccountID, credit.AccountID, amount)
					if err != nil {
						log.Printf("WARNING: Failed to create TigerBeetle transfer: %v", err)
					} else {
						tbTransferIDs = append(tbTransferIDs, transferID)
					}
				}
			}
		}
	}

	// PHASE 3: Re-acquire lock to save entry
	tbTransferID := ""
	if len(tbTransferIDs) > 0 {
		tbTransferID = tbTransferIDs[0]
	}
	entry := JournalEntry{
		ID:                    entryID,
		TenantID:              tenantID,
		EntryNumber:           entryNumber,
		Date:                  req.Date,
		EntryDate:             req.Date,
		Description:           req.Description,
		Reference:             req.Reference,
		Lines:                 lines,
		Status:                "posted",
		IsReversed:            false,
		TigerBeetleIDs:        tbTransferIDs,
		TigerBeetleTransferID: tbTransferID,
		TotalDebit:            totalDebits,
		TotalCredit:           totalCredits,
		PostedBy:              req.PostedBy,
		Metadata:              req.Metadata,
		CreatedAt:             now,
		UpdatedAt:             now,
	}

	// Persist to PostgreSQL
	if s.postgres != nil {
		if err := s.postgres.SaveJournalEntry(ctx, entry); err != nil {
			log.Printf("ERROR: Failed to persist journal entry to PostgreSQL: %v", err)
		}
	}

	// Async event publishing
	go s.publishEvent(context.Background(), CoAEvent{
		EventID:     uuid.New().String(),
		EventType:   EventJournalEntryCreated,
		TenantID:    tenantID,
		EntityID:    entryID,
		EntityType:  "journal_entry",
		Payload:     map[string]interface{}{"entry_number": entryNumber, "total_amount": totalDebits},
		Timestamp:   now,
		ServiceName: ServiceName,
	})

	return &entry, nil
}

func (s *ChartOfAccountsService) ListJournalEntries(ctx context.Context, tenantID string) ([]JournalEntry, error) {
	// Query PostgreSQL
	if s.postgres != nil {
		entries, err := s.postgres.ListJournalEntries(ctx, tenantID, "", nil, nil)
		if err == nil {
			return entries, nil
		}
	}

	// If PostgreSQL unavailable, return empty
	return []JournalEntry{}, nil
}

func (s *ChartOfAccountsService) GetJournalEntry(ctx context.Context, tenantID, entryID string) (*JournalEntry, error) {
	if s.postgres == nil {
		return nil, errors.New("PostgreSQL not connected")
	}

	entry, err := s.postgres.GetJournalEntry(ctx, tenantID, entryID)
	if err != nil {
		return nil, errors.New("journal entry not found")
	}

	return entry, nil
}

func (s *ChartOfAccountsService) ReverseJournalEntry(ctx context.Context, tenantID, entryID string) (*JournalEntry, error) {
	original, err := s.GetJournalEntry(ctx, tenantID, entryID)
	if err != nil {
		return nil, err
	}

	if original.IsReversed {
		return nil, errors.New("journal entry already reversed")
	}

	var reversalLines []JournalLineRequest
	for _, line := range original.Lines {
		reversalLines = append(reversalLines, JournalLineRequest{
			AccountID:    line.AccountID,
			Description:  fmt.Sprintf("Reversal: %s", line.Description),
			DebitAmount:  line.CreditAmount,
			CreditAmount: line.DebitAmount,
		})
	}

	reversalReq := CreateJournalEntryRequest{
		Date:        time.Now(),
		Description: fmt.Sprintf("Reversal of %s", original.EntryNumber),
		Reference:   original.EntryNumber,
		Lines:       reversalLines,
		PostedBy:    "system",
	}

	reversal, err := s.CreateJournalEntry(ctx, tenantID, reversalReq)
	if err != nil {
		return nil, fmt.Errorf("failed to create reversal: %w", err)
	}

	reversal.ReversalOf = entryID

	original.IsReversed = true
	original.ReversedBy = reversal.ID
	original.UpdatedAt = time.Now()

	// Save updates to PostgreSQL
	if s.postgres != nil {
		s.postgres.SaveJournalEntry(ctx, *original)
		s.postgres.SaveJournalEntry(ctx, *reversal)
	}

	go s.publishEvent(context.Background(), CoAEvent{
		EventID:     uuid.New().String(),
		EventType:   EventJournalEntryReversed,
		TenantID:    tenantID,
		EntityID:    entryID,
		EntityType:  "journal_entry",
		Payload:     map[string]interface{}{"reversal_id": reversal.ID},
		Timestamp:   time.Now(),
		ServiceName: ServiceName,
	})

	return reversal, nil
}

func (s *ChartOfAccountsService) GetTrialBalance(ctx context.Context, tenantID, asOfDate string) (*TrialBalance, error) {
	log.Printf("GetTrialBalance called for tenant: %s", tenantID)
	accounts, err := s.ListAccounts(ctx, tenantID, "", "", true)
	if err != nil {
		return nil, err
	}
	log.Printf("Retrieved %d accounts for trial balance", len(accounts))

	trialBalance := &TrialBalance{
		TenantID:    tenantID,
		AsOfDate:    asOfDate,
		Accounts:    []TrialBalanceLine{},
		GeneratedAt: time.Now(),
	}

	// OPTIMIZATION: Batch lookup all TigerBeetle balances at once
	tbBalances := make(map[string]*AccountBalance)
	if s.tigerBeetle != nil {
		log.Printf("Batch looking up %d TigerBeetle accounts", len(accounts))
		var tbIDs []types.Uint128
		idToAccountID := make(map[string]string)

		for _, account := range accounts {
			if account.TigerBeetleID != "" {
				tbID, err := types.HexStringToUint128(account.TigerBeetleID)
				if err == nil {
					tbIDs = append(tbIDs, tbID)
					idToAccountID[account.TigerBeetleID] = account.ID
				}
			}
		}

		if len(tbIDs) > 0 {
			s.tbMu.Lock()
			tbAccounts, err := s.tigerBeetle.LookupAccounts(tbIDs)
			s.tbMu.Unlock()

			if err == nil {
				for _, tbAcc := range tbAccounts {
					accountID := idToAccountID[tbAcc.ID.String()]
					bal := &AccountBalance{AccountID: accountID}
					debitsPosted := tbAcc.DebitsPosted.BigInt()
					creditsPosted := tbAcc.CreditsPosted.BigInt()
					debitsPending := tbAcc.DebitsPending.BigInt()
					creditsPending := tbAcc.CreditsPending.BigInt()
					bal.DebitBalance = (&debitsPosted).Int64()
					bal.CreditBalance = (&creditsPosted).Int64()
					bal.PendingDebits = (&debitsPending).Int64()
					bal.PendingCredits = (&creditsPending).Int64()
					tbBalances[accountID] = bal
				}
			}
			log.Printf("Retrieved balances for %d TigerBeetle accounts", len(tbBalances))
		}
	}

	var totalDebits, totalCredits int64

	for _, account := range accounts {
		var debitBalance, creditBalance int64

		// Use pre-fetched balance if available
		if balance, exists := tbBalances[account.ID]; exists {
			// Net balance = debits - credits from TigerBeetle
			netBalance := balance.DebitBalance - balance.CreditBalance

			// Classify based on account normal balance and net position
			if account.NormalBalance == NormalBalanceDebit {
				// Debit normal accounts (Assets, Expenses)
				if netBalance >= 0 {
					debitBalance = netBalance
				} else {
					creditBalance = -netBalance // Show as credit if negative
				}
			} else {
				// Credit normal accounts (Liabilities, Equity, Revenue)
				if netBalance <= 0 {
					creditBalance = -netBalance
				} else {
					debitBalance = netBalance // Show as debit if positive
				}
			}
		}

		if debitBalance != 0 || creditBalance != 0 {
			line := TrialBalanceLine{
				AccountCode:   account.Code,
				AccountName:   account.Name,
				AccountType:   string(account.Type),
				DebitBalance:  debitBalance,
				CreditBalance: creditBalance,
			}
			trialBalance.Accounts = append(trialBalance.Accounts, line)
			totalDebits += debitBalance
			totalCredits += creditBalance
		}
	}

	trialBalance.TotalDebits = totalDebits
	trialBalance.TotalCredits = totalCredits
	trialBalance.IsBalanced = totalDebits == totalCredits

	log.Printf("Trial balance complete: %d lines, debits=%d, credits=%d", len(trialBalance.Accounts), totalDebits, totalCredits)
	return trialBalance, nil
}

func (s *ChartOfAccountsService) GetBalanceSheet(ctx context.Context, tenantID, asOfDate string) (*BalanceSheet, error) {
	accounts, err := s.ListAccounts(ctx, tenantID, "", "", true)
	if err != nil {
		return nil, err
	}

	balanceSheet := &BalanceSheet{
		TenantID:    tenantID,
		AsOfDate:    asOfDate,
		Assets:      BalanceSheetSection{Name: "Assets", Items: []BalanceSheetItem{}},
		Liabilities: BalanceSheetSection{Name: "Liabilities", Items: []BalanceSheetItem{}},
		Equity:      BalanceSheetSection{Name: "Equity", Items: []BalanceSheetItem{}},
		GeneratedAt: time.Now(),
	}

	// Batch fetch all TigerBeetle balances
	tbBalances := make(map[string]*AccountBalance)
	if s.tigerBeetle != nil {
		tbIDs := []types.Uint128{}
		idToAccountID := make(map[string]string)

		for _, account := range accounts {
			if account.TigerBeetleID != "" {
				if tbID, err := types.HexStringToUint128(account.TigerBeetleID); err == nil {
					tbIDs = append(tbIDs, tbID)
					idToAccountID[tbID.String()] = account.ID
				}
			}
		}

		if len(tbIDs) > 0 {
			s.tbMu.Lock()
			tbAccounts, err := s.tigerBeetle.LookupAccounts(tbIDs)
			s.tbMu.Unlock()

			if err == nil {
				for _, tbAcc := range tbAccounts {
					accountID := idToAccountID[tbAcc.ID.String()]
					bal := &AccountBalance{AccountID: accountID}
					debitsPosted := tbAcc.DebitsPosted.BigInt()
					creditsPosted := tbAcc.CreditsPosted.BigInt()
					debitsPending := tbAcc.DebitsPending.BigInt()
					creditsPending := tbAcc.CreditsPending.BigInt()
					bal.DebitBalance = (&debitsPosted).Int64()
					bal.CreditBalance = (&creditsPosted).Int64()
					bal.PendingDebits = (&debitsPending).Int64()
					bal.PendingCredits = (&creditsPending).Int64()
					bal.NetBalance = bal.DebitBalance - bal.CreditBalance
					tbBalances[accountID] = bal
				}
			}
		}
	}

	for _, account := range accounts {
		var netBalance int64

		if balance, exists := tbBalances[account.ID]; exists {
			netBalance = balance.NetBalance
		}

		if netBalance == 0 {
			continue
		}

		item := BalanceSheetItem{
			AccountCode: account.Code,
			AccountName: account.Name,
			Balance:     netBalance,
			Level:       account.Level,
		}

		switch account.Type {
		case AccountTypeAsset:
			balanceSheet.Assets.Items = append(balanceSheet.Assets.Items, item)
			balanceSheet.Assets.Subtotal += netBalance
		case AccountTypeLiability:
			balanceSheet.Liabilities.Items = append(balanceSheet.Liabilities.Items, item)
			balanceSheet.Liabilities.Subtotal += netBalance
		case AccountTypeEquity:
			balanceSheet.Equity.Items = append(balanceSheet.Equity.Items, item)
			balanceSheet.Equity.Subtotal += netBalance
		}
	}

	balanceSheet.TotalAssets = balanceSheet.Assets.Subtotal
	balanceSheet.TotalLiabilities = balanceSheet.Liabilities.Subtotal
	balanceSheet.TotalEquity = balanceSheet.Equity.Subtotal
	balanceSheet.IsBalanced = balanceSheet.TotalAssets == (balanceSheet.TotalLiabilities + balanceSheet.TotalEquity)

	return balanceSheet, nil
}

func (s *ChartOfAccountsService) GetIncomeStatement(ctx context.Context, tenantID, startDate, endDate string) (*IncomeStatement, error) {
	accounts, err := s.ListAccounts(ctx, tenantID, "", "", true)
	if err != nil {
		return nil, err
	}

	incomeStatement := &IncomeStatement{
		TenantID:    tenantID,
		StartDate:   startDate,
		EndDate:     endDate,
		Revenue:     IncomeStatementSection{Name: "Revenue", Items: []IncomeStatementItem{}},
		Expenses:    IncomeStatementSection{Name: "Expenses", Items: []IncomeStatementItem{}},
		GeneratedAt: time.Now(),
	}

	// Batch fetch all TigerBeetle balances
	tbBalances := make(map[string]*AccountBalance)
	if s.tigerBeetle != nil {
		tbIDs := []types.Uint128{}
		idToAccountID := make(map[string]string)

		for _, account := range accounts {
			if account.TigerBeetleID != "" {
				if tbID, err := types.HexStringToUint128(account.TigerBeetleID); err == nil {
					tbIDs = append(tbIDs, tbID)
					idToAccountID[tbID.String()] = account.ID
				}
			}
		}

		if len(tbIDs) > 0 {
			s.tbMu.Lock()
			tbAccounts, err := s.tigerBeetle.LookupAccounts(tbIDs)
			s.tbMu.Unlock()

			if err == nil {
				for _, tbAcc := range tbAccounts {
					accountID := idToAccountID[tbAcc.ID.String()]
					bal := &AccountBalance{AccountID: accountID}
					debitsPosted := tbAcc.DebitsPosted.BigInt()
					creditsPosted := tbAcc.CreditsPosted.BigInt()
					debitsPending := tbAcc.DebitsPending.BigInt()
					creditsPending := tbAcc.CreditsPending.BigInt()
					bal.DebitBalance = (&debitsPosted).Int64()
					bal.CreditBalance = (&creditsPosted).Int64()
					bal.PendingDebits = (&debitsPending).Int64()
					bal.PendingCredits = (&creditsPending).Int64()
					bal.NetBalance = bal.DebitBalance - bal.CreditBalance
					tbBalances[accountID] = bal
				}
			}
		}
	}

	for _, account := range accounts {
		var netBalance int64

		if balance, exists := tbBalances[account.ID]; exists {
			netBalance = balance.NetBalance
		}

		if netBalance == 0 {
			continue
		}

		item := IncomeStatementItem{
			AccountCode: account.Code,
			AccountName: account.Name,
			Amount:      netBalance,
		}

		switch account.Type {
		case AccountTypeRevenue:
			incomeStatement.Revenue.Items = append(incomeStatement.Revenue.Items, item)
			incomeStatement.Revenue.Subtotal += netBalance
		case AccountTypeExpense:
			incomeStatement.Expenses.Items = append(incomeStatement.Expenses.Items, item)
			incomeStatement.Expenses.Subtotal += netBalance
		}
	}

	incomeStatement.TotalRevenue = incomeStatement.Revenue.Subtotal
	incomeStatement.TotalExpenses = incomeStatement.Expenses.Subtotal
	incomeStatement.NetIncome = incomeStatement.TotalRevenue - incomeStatement.TotalExpenses

	return incomeStatement, nil
}

func (s *ChartOfAccountsService) GenerateCBNReturn(ctx context.Context, tenantID, returnType, reportingDate string) (*CBNReturn, error) {
	mappings := GetCBNMappingByReturnType(returnType)
	if len(mappings) == 0 {
		return nil, fmt.Errorf("unknown return type: %s", returnType)
	}

	cbnReturn := &CBNReturn{
		TenantID:      tenantID,
		ReturnType:    returnType,
		ReportingDate: reportingDate,
		Data:          make(map[string]interface{}),
		GeneratedAt:   time.Now(),
	}

	accounts, err := s.ListAccounts(ctx, tenantID, "", "", true)
	if err != nil {
		return nil, err
	}

	accountBalances := make(map[string]int64)
	for _, account := range accounts {
		balance, err := s.GetAccountBalance(ctx, tenantID, account.ID)
		if err == nil {
			accountBalances[account.Code] = balance.NetBalance
		}
	}

	for _, mapping := range mappings {
		var totalBalance int64
		codes := strings.Split(mapping.CoACode, ",")
		for _, code := range codes {
			code = strings.TrimSpace(code)
			if balance, exists := accountBalances[code]; exists {
				totalBalance += balance
			}
			for accCode, balance := range accountBalances {
				if strings.HasPrefix(accCode, code) && accCode != code {
					totalBalance += balance
				}
			}
		}

		cbnReturn.Data[mapping.CBNCode] = map[string]interface{}{
			"name":        mapping.CBNName,
			"line_number": mapping.LineNumber,
			"amount":      totalBalance,
		}
	}

	go s.publishEvent(context.Background(), CoAEvent{
		EventID:     uuid.New().String(),
		EventType:   EventCBNReturnGenerated,
		TenantID:    tenantID,
		EntityID:    fmt.Sprintf("%s-%s", returnType, reportingDate),
		EntityType:  "cbn_return",
		Payload:     map[string]interface{}{"return_type": returnType, "reporting_date": reportingDate},
		Timestamp:   time.Now(),
		ServiceName: ServiceName,
	})

	return cbnReturn, nil
}

func (s *ChartOfAccountsService) ReconcileWithTigerBeetle(ctx context.Context, tenantID string) (*ReconciliationResult, error) {
	result := &ReconciliationResult{
		TenantID:      tenantID,
		StartedAt:     time.Now(),
		Discrepancies: []Discrepancy{},
		Status:        "running",
	}

	accounts, err := s.ListAccounts(ctx, tenantID, "", "", true)
	if err != nil {
		result.Status = "failed"
		return result, err
	}

	result.AccountsChecked = len(accounts)

	for _, account := range accounts {
		if account.TigerBeetleID == "" {
			continue
		}

		coaBalance, err := s.GetAccountBalance(ctx, tenantID, account.ID)
		if err != nil {
			continue
		}

		tbID, err := types.HexStringToUint128(account.TigerBeetleID)
		if err != nil {
			continue
		}

		if s.tigerBeetle != nil {
			s.tbMu.Lock()
			tbAccounts, err := s.tigerBeetle.LookupAccounts([]types.Uint128{tbID})
			s.tbMu.Unlock()
			if err != nil || len(tbAccounts) == 0 {
				result.Discrepancies = append(result.Discrepancies, Discrepancy{
					AccountID:   account.ID,
					AccountCode: account.Code,
					Type:        "missing_in_tigerbeetle",
					CoABalance:  coaBalance.NetBalance,
					Severity:    "high",
				})
				continue
			}

			tbAccount := tbAccounts[0]
			var tbBalance int64
			if account.NormalBalance == NormalBalanceDebit {
				debits := tbAccount.DebitsPosted.BigInt()
				credits := tbAccount.CreditsPosted.BigInt()
				tbBalance = debits.Int64() - credits.Int64()
			} else {
				credits := tbAccount.CreditsPosted.BigInt()
				debits := tbAccount.DebitsPosted.BigInt()
				tbBalance = credits.Int64() - debits.Int64()
			}

			if coaBalance.NetBalance != tbBalance {
				diff := coaBalance.NetBalance - tbBalance
				severity := "low"
				if diff > 100000 || diff < -100000 {
					severity = "critical"
				} else if diff > 10000 || diff < -10000 {
					severity = "high"
				} else if diff > 1000 || diff < -1000 {
					severity = "medium"
				}

				result.Discrepancies = append(result.Discrepancies, Discrepancy{
					AccountID:          account.ID,
					AccountCode:        account.Code,
					Type:               "balance_mismatch",
					CoABalance:         coaBalance.NetBalance,
					TigerBeetleBalance: tbBalance,
					Difference:         diff,
					Severity:           severity,
				})
			}
		}
	}

	result.CompletedAt = time.Now()
	if len(result.Discrepancies) == 0 {
		result.Status = "success"
	} else {
		result.Status = "completed_with_discrepancies"
	}

	s.reconciliationStatus[tenantID] = ReconciliationStatus{
		TenantID:           tenantID,
		LastReconciliation: result.CompletedAt,
		Status:             result.Status,
		DiscrepancyCount:   len(result.Discrepancies),
	}

	go s.publishEvent(context.Background(), CoAEvent{
		EventID:     uuid.New().String(),
		EventType:   EventReconciliationRun,
		TenantID:    tenantID,
		EntityID:    tenantID,
		EntityType:  "reconciliation",
		Payload:     map[string]interface{}{"accounts_checked": result.AccountsChecked, "discrepancies": len(result.Discrepancies)},
		Timestamp:   time.Now(),
		ServiceName: ServiceName,
	})

	return result, nil
}

func (s *ChartOfAccountsService) GetReconciliationStatus(ctx context.Context, tenantID string) (*ReconciliationStatus, error) {

	status, exists := s.reconciliationStatus[tenantID]
	if !exists {
		return &ReconciliationStatus{
			TenantID: tenantID,
			Status:   "never_run",
		}, nil
	}

	return &status, nil
}

// All Chart of Accounts use ledger 1 to allow transfers between any accounts

func (s *ChartOfAccountsService) getCodeFromAccountCode(code string) uint16 {
	var result uint16
	for i, c := range code {
		if i >= 4 {
			break
		}
		if c >= '0' && c <= '9' {
			result = result*10 + uint16(c-'0')
		}
	}
	return result
}

func (s *ChartOfAccountsService) generateTigerBeetleID(tenantID, accountCode string) types.Uint128 {
	// Add version suffix for tenants that need recovery from ledger mismatch
	// This allows creating new TigerBeetle accounts with different IDs
	versionSuffix := ""
	if tenantID == "bpmgd" {
		versionSuffix = ":v2" // Forces different hash for recovery
	}

	combined := fmt.Sprintf("%s%s:%s", tenantID, versionSuffix, accountCode)
	hash := uint64(0)
	for _, c := range combined {
		hash = hash*31 + uint64(c)
	}
	return types.ToUint128(hash)
}

// Batch version for initialization - much faster than individual calls
func (s *ChartOfAccountsService) createTigerBeetleAccountsBatch(ctx context.Context, accounts []types.Account) error {
	if s.tigerBeetle == nil {
		return errors.New("TigerBeetle not connected")
	}
	if len(accounts) == 0 {
		return nil
	}

	// Longer timeout for batch operations
	ctx, cancel := context.WithTimeout(ctx, 30*time.Second)
	defer cancel()

	done := make(chan error, 1)
	go func() {
		s.tbMu.Lock()
		defer s.tbMu.Unlock()

		results, err := s.tigerBeetle.CreateAccounts(accounts)
		if err != nil {
			done <- fmt.Errorf("TigerBeetle CreateAccounts batch error: %w", err)
			return
		}

		failCount := 0
		for _, result := range results {
			if result.Result != types.AccountOK && result.Result != types.AccountExistsWithDifferentFlags {
				failCount++
			}
		}
		if failCount > 0 {
			log.Printf("WARNING: %d/%d accounts had non-fatal errors during batch creation", failCount, len(accounts))
		}
		done <- nil
	}()

	select {
	case err := <-done:
		return err
	case <-ctx.Done():
		return fmt.Errorf("TigerBeetle batch operation timeout: %w", ctx.Err())
	}
}

func (s *ChartOfAccountsService) createTigerBeetleAccount(ctx context.Context, account types.Account) error {
	if s.tigerBeetle == nil {
		return errors.New("TigerBeetle not connected")
	}

	// Add timeout for CGo operations
	ctx, cancel := context.WithTimeout(ctx, 15*time.Second)
	defer cancel()

	done := make(chan error, 1)
	go func() {
		s.tbMu.Lock()
		defer s.tbMu.Unlock()

		results, err := s.tigerBeetle.CreateAccounts([]types.Account{account})
		if err != nil {
			done <- fmt.Errorf("TigerBeetle CreateAccounts error: %w", err)
			return
		}

		for _, result := range results {
			if result.Result != types.AccountOK && result.Result != types.AccountExistsWithDifferentFlags {
				done <- fmt.Errorf("failed to create account: %s", result.Result)
				return
			}
		}
		done <- nil
	}()

	select {
	case err := <-done:
		return err
	case <-ctx.Done():
		return fmt.Errorf("TigerBeetle operation timeout: %w", ctx.Err())
	}
}

func (s *ChartOfAccountsService) createTigerBeetleTransfer(ctx context.Context, tenantID, debitAccountID, creditAccountID string, amount int64) (string, error) {
	if s.tigerBeetle == nil {
		return "", errors.New("TigerBeetle not connected")
	}

	debitAccount, err := s.GetAccount(ctx, tenantID, debitAccountID)
	if err != nil {
		return "", err
	}

	creditAccount, err := s.GetAccount(ctx, tenantID, creditAccountID)
	if err != nil {
		return "", err
	}

	if debitAccount.TigerBeetleID == "" || creditAccount.TigerBeetleID == "" {
		return "", errors.New("accounts not linked to TigerBeetle")
	}

	// Validate that both accounts have the same ledger (TigerBeetle requirement)
	if debitAccount.TigerBeetleLedger != creditAccount.TigerBeetleLedger {
		return "", fmt.Errorf("transfer accounts must have the same ledger: debit=%d (account %s: %s), credit=%d (account %s: %s)",
			debitAccount.TigerBeetleLedger, debitAccount.Code, debitAccount.Name,
			creditAccount.TigerBeetleLedger, creditAccount.Code, creditAccount.Name)
	}

	debitTBID, err := types.HexStringToUint128(debitAccount.TigerBeetleID)
	if err != nil {
		return "", fmt.Errorf("invalid debit account TigerBeetle ID: %w", err)
	}

	creditTBID, err := types.HexStringToUint128(creditAccount.TigerBeetleID)
	if err != nil {
		return "", fmt.Errorf("invalid credit account TigerBeetle ID: %w", err)
	}

	transferID := types.ToUint128(uint64(time.Now().UnixNano()))

	// Use the common ledger value (both accounts have the same ledger)
	ledger := debitAccount.TigerBeetleLedger

	transfer := types.Transfer{
		ID:              transferID,
		DebitAccountID:  debitTBID,
		CreditAccountID: creditTBID,
		Amount:          types.ToUint128(uint64(amount)),
		Ledger:          ledger,
		Code:            debitAccount.TigerBeetleCode,
	}

	// Protect TigerBeetle client operations with mutex
	s.tbMu.Lock()
	defer s.tbMu.Unlock()

	results, err := s.tigerBeetle.CreateTransfers([]types.Transfer{transfer})
	if err != nil {
		return "", fmt.Errorf("TigerBeetle CreateTransfers error: %w", err)
	}

	for _, result := range results {
		if result.Result != types.TransferOK {
			return "", fmt.Errorf("failed to create transfer: %s", result.Result)
		}
	}

	return transferID.String(), nil
}

func (s *ChartOfAccountsService) publishEvent(ctx context.Context, event CoAEvent) error {
	if s.kafkaWriter == nil {
		return fmt.Errorf("kafka writer not initialized")
	}

	data, err := json.Marshal(event)
	if err != nil {
		return fmt.Errorf("failed to marshal event: %w", err)
	}

	msg := kafka.Message{
		Key:   []byte(event.EntityID),
		Value: data,
		Headers: []kafka.Header{
			{Key: "event_type", Value: []byte(event.EventType)},
			{Key: "tenant_id", Value: []byte(event.TenantID)},
		},
	}

	// Use provided context (already has timeout from caller)
	if err := s.kafkaWriter.WriteMessages(ctx, msg); err != nil {
		return fmt.Errorf("failed to write kafka message: %w", err)
	}

	return nil
}

func (s *ChartOfAccountsService) cacheAccount(ctx context.Context, tenantID string, account Account) error {
	if s.redis == nil {
		return fmt.Errorf("redis client not initialized")
	}

	// Check if context already cancelled
	select {
	case <-ctx.Done():
		return ctx.Err()
	default:
	}

	// Use provided context (already has timeout from caller)
	cacheKey := fmt.Sprintf("coa:%s:account:%s", tenantID, account.ID)
	data, err := json.Marshal(account)
	if err != nil {
		return fmt.Errorf("failed to marshal account: %w", err)
	}

	if err := s.redis.Set(ctx, cacheKey, data, 1*time.Hour).Err(); err != nil {
		return fmt.Errorf("failed to cache account: %w", err)
	}

	codeKey := fmt.Sprintf("coa:%s:code:%s", tenantID, account.Code)
	if err := s.redis.Set(ctx, codeKey, account.ID, 1*time.Hour).Err(); err != nil {
		return fmt.Errorf("failed to cache code mapping: %w", err)
	}

	return nil
}
