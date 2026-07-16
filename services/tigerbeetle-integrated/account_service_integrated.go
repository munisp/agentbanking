package main

import (
	"bytes"
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"strconv"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	_ "github.com/lib/pq"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"github.com/redis/go-redis/v9"
)

// TigerBeetleIntegratedAccountService manages accounts using TigerBeetle for balances
type TigerBeetleIntegratedAccountService struct {
	// TigerBeetle endpoints
	zigEndpoint   string
	edgeEndpoint  string
	
	// Traditional databases for metadata
	db    *sql.DB
	redis *redis.Client
	
	// HTTP client for TigerBeetle communication
	httpClient *http.Client
	
	// Metrics
	accountsCreated prometheus.Counter
	balanceQueries  prometheus.Counter
	operationDuration prometheus.Histogram
	operationErrors   prometheus.Counter
}

// Account represents a banking account with TigerBeetle integration
type Account struct {
	// TigerBeetle account data
	ID             uint64 `json:"id"`              // TigerBeetle account ID
	UserData       uint64 `json:"user_data"`       // Custom data field
	Ledger         uint32 `json:"ledger"`          // Ledger classification
	Code           uint16 `json:"code"`            // Account type code
	Flags          uint16 `json:"flags"`           // Account flags
	
	// TigerBeetle balance data (authoritative)
	DebitsPending  uint64 `json:"debits_pending"`
	DebitsPosted   uint64 `json:"debits_posted"`
	CreditsPending uint64 `json:"credits_pending"`
	CreditsPosted  uint64 `json:"credits_posted"`
	Balance        int64  `json:"balance"`         // Calculated balance
	
	// Metadata (stored in PostgreSQL)
	CustomerID       string    `json:"customer_id"`
	AgentID          string    `json:"agent_id"`
	AccountNumber    string    `json:"account_number"`
	AccountType      string    `json:"account_type"`
	Currency         string    `json:"currency"`
	Status           string    `json:"status"`
	KYCLevel         string    `json:"kyc_level"`
	DailyLimit       uint64    `json:"daily_limit"`
	MonthlyLimit     uint64    `json:"monthly_limit"`
	RiskScore        float64   `json:"risk_score"`
	CreatedAt        time.Time `json:"created_at"`
	UpdatedAt        time.Time `json:"updated_at"`
	LastTransaction  time.Time `json:"last_transaction"`
	
	// Additional metadata
	BranchCode       string    `json:"branch_code"`
	ProductCode      string    `json:"product_code"`
	InterestRate     float64   `json:"interest_rate"`
	MinimumBalance   uint64    `json:"minimum_balance"`
	OverdraftLimit   uint64    `json:"overdraft_limit"`
	IsActive         bool      `json:"is_active"`
	IsFrozen         bool      `json:"is_frozen"`
	FreezeReason     string    `json:"freeze_reason"`
	Notes            string    `json:"notes"`
}

// TigerBeetleAccount represents the core TigerBeetle account structure
type TigerBeetleAccount struct {
	ID             uint64 `json:"id"`
	UserData       uint64 `json:"user_data"`
	Ledger         uint32 `json:"ledger"`
	Code           uint16 `json:"code"`
	Flags          uint16 `json:"flags"`
	DebitsPending  uint64 `json:"debits_pending"`
	DebitsPosted   uint64 `json:"debits_posted"`
	CreditsPending uint64 `json:"credits_pending"`
	CreditsPosted  uint64 `json:"credits_posted"`
	Timestamp      int64  `json:"timestamp"`
}
// TigerBeetleTransfer represents a TigerBeetle transfer
type TigerBeetleTransfer struct {
	ID              uint64 `json:"id"`
	DebitAccountID  uint64 `json:"debit_account_id"`
	CreditAccountID uint64 `json:"credit_account_id"`
	Amount          uint64 `json:"amount"`
	Ledger          uint32 `json:"ledger"`
	Code            uint16 `json:"code"`
	Flags           uint16 `json:"flags"`
	PendingID       uint64 `json:"pending_id"`
	UserData        uint64 `json:"user_data"`
	Timeout         uint32 `json:"timeout"`
	Timestamp       int64  `json:"timestamp"`
}


// AccountTransaction represents account transaction history
type AccountTransaction struct {
	ID              string    `json:"id"`
	AccountID       uint64    `json:"account_id"`
	TransferID      uint64    `json:"transfer_id"`      // TigerBeetle transfer ID
	Type            string    `json:"type"`             // debit, credit
	Amount          uint64    `json:"amount"`
	BalanceBefore   int64     `json:"balance_before"`
	BalanceAfter    int64     `json:"balance_after"`
	Description     string    `json:"description"`
	Reference       string    `json:"reference"`
	Status          string    `json:"status"`
	CreatedAt       time.Time `json:"created_at"`
	ProcessedAt     time.Time `json:"processed_at"`
	
	// Additional metadata
	CounterpartyID  uint64    `json:"counterparty_id"`
	PaymentMethod   string    `json:"payment_method"`
	Channel         string    `json:"channel"`
	AgentID         string    `json:"agent_id"`
	Location        string    `json:"location"`
	DeviceID        string    `json:"device_id"`
}

// Nigerian banking constants
const (
	// Ledger codes
	CUSTOMER_DEPOSITS_LEDGER = 1000
	AGENT_ACCOUNTS_LEDGER    = 2000
	BANK_RESERVES_LEDGER     = 3000
	FEE_INCOME_LEDGER        = 4000
	
	// Account type codes
	SAVINGS_ACCOUNT_CODE     = 100
	CURRENT_ACCOUNT_CODE     = 200
	AGENT_FLOAT_CODE         = 300
	FIXED_DEPOSIT_CODE       = 400
	LOAN_ACCOUNT_CODE        = 500
	
	// Account flags
	FLAG_DEBITS_MUST_NOT_EXCEED_CREDITS = 1 << 0
	FLAG_CREDITS_MUST_NOT_EXCEED_DEBITS = 1 << 1
	FLAG_HISTORY                        = 1 << 2
)

// NewTigerBeetleIntegratedAccountService creates a new integrated account service
func NewTigerBeetleIntegratedAccountService(zigEndpoint, edgeEndpoint, dbURL, redisURL string) (*TigerBeetleIntegratedAccountService, error) {
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
	
	// Initialize metrics
	accountsCreated := prometheus.NewCounter(prometheus.CounterOpts{
		Name: "accounts_created_total",
		Help: "Total number of accounts created",
	})
	
	balanceQueries := prometheus.NewCounter(prometheus.CounterOpts{
		Name: "balance_queries_total",
		Help: "Total number of balance queries",
	})
	
	operationDuration := prometheus.NewHistogram(prometheus.HistogramOpts{
		Name: "account_operation_duration_seconds",
		Help: "Account operation duration in seconds",
	})
	
	operationErrors := prometheus.NewCounter(prometheus.CounterOpts{
		Name: "account_operation_errors_total",
		Help: "Total number of account operation errors",
	})
	
	prometheus.MustRegister(accountsCreated, balanceQueries, operationDuration, operationErrors)
	
	service := &TigerBeetleIntegratedAccountService{
		zigEndpoint:       zigEndpoint,
		edgeEndpoint:      edgeEndpoint,
		db:                db,
		redis:             redisClient,
		httpClient:        &http.Client{Timeout: 30 * time.Second},
		accountsCreated:   accountsCreated,
		balanceQueries:    balanceQueries,
		operationDuration: operationDuration,
		operationErrors:   operationErrors,
	}
	
	// Initialize database tables
	if err := service.initTables(); err != nil {
		return nil, fmt.Errorf("failed to initialize tables: %v", err)
	}
	
	return service, nil
}

// initTables creates necessary PostgreSQL tables for account metadata
func (as *TigerBeetleIntegratedAccountService) initTables() error {
	queries := []string{
		`CREATE TABLE IF NOT EXISTS accounts (
			id BIGINT PRIMARY KEY,
			customer_id VARCHAR(100) NOT NULL,
			agent_id VARCHAR(100),
			account_number VARCHAR(50) UNIQUE NOT NULL,
			account_type VARCHAR(50) NOT NULL,
			currency VARCHAR(10) NOT NULL,
			status VARCHAR(20) DEFAULT 'active',
			kyc_level VARCHAR(20) DEFAULT 'tier1',
			daily_limit BIGINT DEFAULT 1000000,
			monthly_limit BIGINT DEFAULT 30000000,
			risk_score DECIMAL(5,2) DEFAULT 0.0,
			created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
			updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
			last_transaction TIMESTAMP,
			branch_code VARCHAR(20),
			product_code VARCHAR(20),
			interest_rate DECIMAL(8,4) DEFAULT 0.0,
			minimum_balance BIGINT DEFAULT 0,
			overdraft_limit BIGINT DEFAULT 0,
			is_active BOOLEAN DEFAULT TRUE,
			is_frozen BOOLEAN DEFAULT FALSE,
			freeze_reason TEXT,
			notes TEXT
		)`,
		`CREATE TABLE IF NOT EXISTS account_transactions (
			id VARCHAR(100) PRIMARY KEY,
			account_id BIGINT NOT NULL,
			transfer_id BIGINT,
			type VARCHAR(20) NOT NULL,
			amount BIGINT NOT NULL,
			balance_before BIGINT,
			balance_after BIGINT,
			description TEXT,
			reference VARCHAR(100),
			status VARCHAR(20) DEFAULT 'completed',
			created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
			processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
			counterparty_id BIGINT,
			payment_method VARCHAR(50),
			channel VARCHAR(50),
			agent_id VARCHAR(100),
			location VARCHAR(100),
			device_id VARCHAR(100)
		)`,
		`CREATE TABLE IF NOT EXISTS account_limits (
			account_id BIGINT PRIMARY KEY,
			daily_transaction_limit BIGINT,
			daily_transaction_count INTEGER,
			monthly_transaction_limit BIGINT,
			monthly_transaction_count INTEGER,
			last_daily_reset DATE,
			last_monthly_reset DATE,
			created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
			updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
		)`,
		// Indexes
		`CREATE INDEX IF NOT EXISTS idx_accounts_customer ON accounts(customer_id)`,
		`CREATE INDEX IF NOT EXISTS idx_accounts_agent ON accounts(agent_id)`,
		`CREATE INDEX IF NOT EXISTS idx_accounts_number ON accounts(account_number)`,
		`CREATE INDEX IF NOT EXISTS idx_accounts_type ON accounts(account_type)`,
		`CREATE INDEX IF NOT EXISTS idx_accounts_status ON accounts(status)`,
		`CREATE INDEX IF NOT EXISTS idx_transactions_account ON account_transactions(account_id)`,
		`CREATE INDEX IF NOT EXISTS idx_transactions_transfer ON account_transactions(transfer_id)`,
		`CREATE INDEX IF NOT EXISTS idx_transactions_created ON account_transactions(created_at)`,
	}
	
	for _, query := range queries {
		if _, err := as.db.Exec(query); err != nil {
			return fmt.Errorf("failed to execute query: %v", err)
		}
	}
	
	return nil
}

// CreateAccount creates a new account in both TigerBeetle and PostgreSQL
func (as *TigerBeetleIntegratedAccountService) CreateAccount(account Account) (*Account, error) {
	timer := prometheus.NewTimer(as.operationDuration)
	defer timer.ObserveDuration()
	
	// Generate account ID if not provided
	if account.ID == 0 {
		account.ID = as.generateAccountID()
	}
	
	// Set defaults
	account.CreatedAt = time.Now()
	account.UpdatedAt = time.Now()
	account.IsActive = true
	
	// Generate account number if not provided
	if account.AccountNumber == "" {
		account.AccountNumber = as.generateAccountNumber(account.AccountType, account.Currency)
	}
	
	// Set TigerBeetle specific fields based on account type
	as.setTigerBeetleFields(&account)
	
	// Start database transaction
	tx, err := as.db.Begin()
	if err != nil {
		as.operationErrors.Inc()
		return nil, fmt.Errorf("failed to start transaction: %v", err)
	}
	defer tx.Rollback()
	
	// Create account in TigerBeetle
	tbAccount := TigerBeetleAccount{
		ID:        account.ID,
		UserData:  account.UserData,
		Ledger:    account.Ledger,
		Code:      account.Code,
		Flags:     account.Flags,
		Timestamp: time.Now().Unix(),
	}
	
	if err := as.createTigerBeetleAccount(tbAccount); err != nil {
		as.operationErrors.Inc()
		return nil, fmt.Errorf("failed to create TigerBeetle account: %v", err)
	}
	
	// Store account metadata in PostgreSQL
	if err := as.storeAccountMetadata(tx, account); err != nil {
		as.operationErrors.Inc()
		return nil, fmt.Errorf("failed to store account metadata: %v", err)
	}
	
	// Initialize account limits
	if err := as.initializeAccountLimits(tx, account.ID); err != nil {
		as.operationErrors.Inc()
		return nil, fmt.Errorf("failed to initialize account limits: %v", err)
	}
	
	// Commit transaction
	if err := tx.Commit(); err != nil {
		as.operationErrors.Inc()
		return nil, fmt.Errorf("failed to commit transaction: %v", err)
	}
	
	// Publish account creation event
	as.publishAccountEvent(account, "account.created")
	
	// Update metrics
	as.accountsCreated.Inc()
	
	log.Printf("Account created successfully: %s (%d)", account.AccountNumber, account.ID)
	
	return &account, nil
}

// GetAccount retrieves account with current balance from TigerBeetle
func (as *TigerBeetleIntegratedAccountService) GetAccount(accountID uint64) (*Account, error) {
	timer := prometheus.NewTimer(as.operationDuration)
	defer timer.ObserveDuration()
	
	// Get account metadata from PostgreSQL
	account, err := as.getAccountMetadata(accountID)
	if err != nil {
		as.operationErrors.Inc()
		return nil, fmt.Errorf("failed to get account metadata: %v", err)
	}
	
	// Get current balance and details from TigerBeetle
	tbAccount, err := as.getTigerBeetleAccount(accountID)
	if err != nil {
		as.operationErrors.Inc()
		return nil, fmt.Errorf("failed to get TigerBeetle account: %v", err)
	}
	
	// Merge TigerBeetle data with metadata
	account.DebitsPending = tbAccount.DebitsPending
	account.DebitsPosted = tbAccount.DebitsPosted
	account.CreditsPending = tbAccount.CreditsPending
	account.CreditsPosted = tbAccount.CreditsPosted
	account.Balance = int64(tbAccount.CreditsPosted) - int64(tbAccount.DebitsPosted)
	
	return account, nil
}

// GetAccountBalance retrieves current balance from TigerBeetle
func (as *TigerBeetleIntegratedAccountService) GetAccountBalance(accountID uint64) (int64, error) {
	as.balanceQueries.Inc()
	
	// Try edge endpoint first for better performance
	balance, err := as.getBalanceFromEndpoint(accountID, as.edgeEndpoint)
	if err != nil {
		// Fallback to Zig primary
		return as.getBalanceFromEndpoint(accountID, as.zigEndpoint)
	}
	
	return balance, nil
}

// UpdateAccountStatus updates account status and metadata
func (as *TigerBeetleIntegratedAccountService) UpdateAccountStatus(accountID uint64, status string, reason string) error {
	timer := prometheus.NewTimer(as.operationDuration)
	defer timer.ObserveDuration()
	
	// Update in PostgreSQL
	query := `
		UPDATE accounts 
		SET status = $1, updated_at = CURRENT_TIMESTAMP, freeze_reason = $2
		WHERE id = $3
	`
	
	_, err := as.db.Exec(query, status, reason, accountID)
	if err != nil {
		as.operationErrors.Inc()
		return fmt.Errorf("failed to update account status: %v", err)
	}
	
	// Publish status change event
	event := map[string]interface{}{
		"account_id": accountID,
		"status":     status,
		"reason":     reason,
		"timestamp":  time.Now(),
	}
	
	as.publishEvent("account.status_changed", event)
	
	return nil
}

// GetAccountTransactions retrieves transaction history for an account
func (as *TigerBeetleIntegratedAccountService) GetAccountTransactions(accountID uint64, limit int, offset int) ([]AccountTransaction, error) {
	query := `
		SELECT id, account_id, transfer_id, type, amount, balance_before, balance_after,
		       description, reference, status, created_at, processed_at, counterparty_id,
		       payment_method, channel, agent_id, location, device_id
		FROM account_transactions 
		WHERE account_id = $1 
		ORDER BY created_at DESC 
		LIMIT $2 OFFSET $3
	`
	
	rows, err := as.db.Query(query, accountID, limit, offset)
	if err != nil {
		return nil, fmt.Errorf("failed to query transactions: %v", err)
	}
	defer rows.Close()
	
	var transactions []AccountTransaction
	for rows.Next() {
		var tx AccountTransaction
		err := rows.Scan(
			&tx.ID, &tx.AccountID, &tx.TransferID, &tx.Type, &tx.Amount,
			&tx.BalanceBefore, &tx.BalanceAfter, &tx.Description, &tx.Reference,
			&tx.Status, &tx.CreatedAt, &tx.ProcessedAt, &tx.CounterpartyID,
			&tx.PaymentMethod, &tx.Channel, &tx.AgentID, &tx.Location, &tx.DeviceID,
		)
		if err != nil {
			continue
		}
		
		transactions = append(transactions, tx)
	}
	
	return transactions, nil
}

// RecordTransaction records a transaction in the account history
func (as *TigerBeetleIntegratedAccountService) RecordTransaction(tx AccountTransaction) error {
	// Get current balance before recording
	balanceBefore, err := as.GetAccountBalance(tx.AccountID)
	if err != nil {
		balanceBefore = 0 // Default if unable to get balance
	}
	
	tx.BalanceBefore = balanceBefore
	
	// Calculate balance after based on transaction type
	if tx.Type == "credit" {
		tx.BalanceAfter = balanceBefore + int64(tx.Amount)
	} else {
		tx.BalanceAfter = balanceBefore - int64(tx.Amount)
	}
	
	// Generate transaction ID if not provided
	if tx.ID == "" {
		tx.ID = uuid.New().String()
	}
	
	tx.CreatedAt = time.Now()
	tx.ProcessedAt = time.Now()
	
	// Store transaction
	query := `
		INSERT INTO account_transactions (
			id, account_id, transfer_id, type, amount, balance_before, balance_after,
			description, reference, status, created_at, processed_at, counterparty_id,
			payment_method, channel, agent_id, location, device_id
		) VALUES (
			$1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18
		)
	`
	
	_, err = as.db.Exec(query,
		tx.ID, tx.AccountID, tx.TransferID, tx.Type, tx.Amount,
		tx.BalanceBefore, tx.BalanceAfter, tx.Description, tx.Reference,
		tx.Status, tx.CreatedAt, tx.ProcessedAt, tx.CounterpartyID,
		tx.PaymentMethod, tx.Channel, tx.AgentID, tx.Location, tx.DeviceID,
	)
	
	if err != nil {
		return fmt.Errorf("failed to record transaction: %v", err)
	}
	
	// Update last transaction time
	_, err = as.db.Exec(
		"UPDATE accounts SET last_transaction = $1, updated_at = $1 WHERE id = $2",
		time.Now(), tx.AccountID,
	)
	
	return err
}

// Helper methods

func (as *TigerBeetleIntegratedAccountService) generateAccountID() uint64 {
	// Generate unique account ID (timestamp + random)
	return uint64(time.Now().UnixNano())
}

func (as *TigerBeetleIntegratedAccountService) generateAccountNumber(accountType, currency string) string {
	// Generate account number based on type and currency
	prefix := "0001" // Bank code
	typeCode := "00"
	
	switch accountType {
	case "savings":
		typeCode = "01"
	case "current":
		typeCode = "02"
	case "agent_float":
		typeCode = "03"
	case "fixed_deposit":
		typeCode = "04"
	}
	
	// Generate unique suffix
	suffix := fmt.Sprintf("%08d", time.Now().Unix()%100000000)
	
	return fmt.Sprintf("%s%s%s", prefix, typeCode, suffix)
}

func (as *TigerBeetleIntegratedAccountService) setTigerBeetleFields(account *Account) {
	// Set ledger based on account type
	switch account.AccountType {
	case "savings", "current":
		account.Ledger = CUSTOMER_DEPOSITS_LEDGER
	case "agent_float":
		account.Ledger = AGENT_ACCOUNTS_LEDGER
	default:
		account.Ledger = CUSTOMER_DEPOSITS_LEDGER
	}
	
	// Set code based on account type
	switch account.AccountType {
	case "savings":
		account.Code = SAVINGS_ACCOUNT_CODE
	case "current":
		account.Code = CURRENT_ACCOUNT_CODE
	case "agent_float":
		account.Code = AGENT_FLOAT_CODE
	case "fixed_deposit":
		account.Code = FIXED_DEPOSIT_CODE
	case "loan":
		account.Code = LOAN_ACCOUNT_CODE
	default:
		account.Code = SAVINGS_ACCOUNT_CODE
	}
	
	// Set flags based on account type
	account.Flags = FLAG_HISTORY // Always enable history
	
	if account.AccountType == "loan" {
		account.Flags |= FLAG_CREDITS_MUST_NOT_EXCEED_DEBITS
	}
	
	// Set user data (can be used for custom business logic)
	account.UserData = account.ID
}

func (as *TigerBeetleIntegratedAccountService) storeAccountMetadata(tx *sql.Tx, account Account) error {
	query := `
		INSERT INTO accounts (
			id, customer_id, agent_id, account_number, account_type, currency,
			status, kyc_level, daily_limit, monthly_limit, risk_score,
			created_at, updated_at, branch_code, product_code, interest_rate,
			minimum_balance, overdraft_limit, is_active, is_frozen, notes
		) VALUES (
			$1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21
		)
	`
	
	_, err := tx.Exec(query,
		account.ID, account.CustomerID, account.AgentID, account.AccountNumber,
		account.AccountType, account.Currency, account.Status, account.KYCLevel,
		account.DailyLimit, account.MonthlyLimit, account.RiskScore,
		account.CreatedAt, account.UpdatedAt, account.BranchCode, account.ProductCode,
		account.InterestRate, account.MinimumBalance, account.OverdraftLimit,
		account.IsActive, account.IsFrozen, account.Notes,
	)
	
	return err
}

func (as *TigerBeetleIntegratedAccountService) initializeAccountLimits(tx *sql.Tx, accountID uint64) error {
	query := `
		INSERT INTO account_limits (
			account_id, daily_transaction_limit, daily_transaction_count,
			monthly_transaction_limit, monthly_transaction_count,
			last_daily_reset, last_monthly_reset
		) VALUES ($1, $2, 0, $3, 0, CURRENT_DATE, CURRENT_DATE)
	`
	
	_, err := tx.Exec(query, accountID, 1000000, 30000000) // Default limits
	return err
}

func (as *TigerBeetleIntegratedAccountService) getAccountMetadata(accountID uint64) (*Account, error) {
	query := `
		SELECT id, customer_id, agent_id, account_number, account_type, currency,
		       status, kyc_level, daily_limit, monthly_limit, risk_score,
		       created_at, updated_at, last_transaction, branch_code, product_code,
		       interest_rate, minimum_balance, overdraft_limit, is_active, is_frozen,
		       freeze_reason, notes
		FROM accounts WHERE id = $1
	`
	
	row := as.db.QueryRow(query, accountID)
	
	var account Account
	var lastTransaction sql.NullTime
	var freezeReason sql.NullString
	
	err := row.Scan(
		&account.ID, &account.CustomerID, &account.AgentID, &account.AccountNumber,
		&account.AccountType, &account.Currency, &account.Status, &account.KYCLevel,
		&account.DailyLimit, &account.MonthlyLimit, &account.RiskScore,
		&account.CreatedAt, &account.UpdatedAt, &lastTransaction, &account.BranchCode,
		&account.ProductCode, &account.InterestRate, &account.MinimumBalance,
		&account.OverdraftLimit, &account.IsActive, &account.IsFrozen,
		&freezeReason, &account.Notes,
	)
	
	if err != nil {
		return nil, err
	}
	
	if lastTransaction.Valid {
		account.LastTransaction = lastTransaction.Time
	}
	
	if freezeReason.Valid {
		account.FreezeReason = freezeReason.String
	}
	
	return &account, nil
}

func (as *TigerBeetleIntegratedAccountService) createTigerBeetleAccount(account TigerBeetleAccount) error {
	// Try edge endpoint first
	if err := as.sendAccountToEndpoint(account, as.edgeEndpoint); err != nil {
		log.Printf("Edge endpoint failed, trying Zig primary: %v", err)
		// Fallback to Zig primary
		return as.sendAccountToEndpoint(account, as.zigEndpoint)
	}
	
	return nil
}

func (as *TigerBeetleIntegratedAccountService) sendAccountToEndpoint(account TigerBeetleAccount, endpoint string) error {
	data, err := json.Marshal([]TigerBeetleAccount{account})
	if err != nil {
		return fmt.Errorf("failed to marshal account: %v", err)
	}
	
	resp, err := as.httpClient.Post(endpoint+"/accounts", "application/json", bytes.NewBuffer(data))
	if err != nil {
		return fmt.Errorf("failed to send account: %v", err)
	}
	defer resp.Body.Close()
	
	if resp.StatusCode != http.StatusCreated && resp.StatusCode != http.StatusOK {
		return fmt.Errorf("TigerBeetle returned status %d", resp.StatusCode)
	}
	
	return nil
}

func (as *TigerBeetleIntegratedAccountService) getTigerBeetleAccount(accountID uint64) (*TigerBeetleAccount, error) {
	// Try edge endpoint first
	account, err := as.getAccountFromEndpoint(accountID, as.edgeEndpoint)
	if err != nil {
		// Fallback to Zig primary
		return as.getAccountFromEndpoint(accountID, as.zigEndpoint)
	}
	
	return account, nil
}

func (as *TigerBeetleIntegratedAccountService) getAccountFromEndpoint(accountID uint64, endpoint string) (*TigerBeetleAccount, error) {
	resp, err := as.httpClient.Get(fmt.Sprintf("%s/accounts/%d", endpoint, accountID))
	if err != nil {
		return nil, fmt.Errorf("failed to get account: %v", err)
	}
	defer resp.Body.Close()
	
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("endpoint returned status %d", resp.StatusCode)
	}
	
	var account TigerBeetleAccount
	if err := json.NewDecoder(resp.Body).Decode(&account); err != nil {
		return nil, fmt.Errorf("failed to decode account response: %v", err)
	}
	
	return &account, nil
}

func (as *TigerBeetleIntegratedAccountService) getBalanceFromEndpoint(accountID uint64, endpoint string) (int64, error) {
	resp, err := as.httpClient.Get(fmt.Sprintf("%s/accounts/%d/balance", endpoint, accountID))
	if err != nil {
		return 0, fmt.Errorf("failed to get balance: %v", err)
	}
	defer resp.Body.Close()
	
	if resp.StatusCode != http.StatusOK {
		return 0, fmt.Errorf("endpoint returned status %d", resp.StatusCode)
	}
	
	var result struct {
		Balance int64 `json:"balance"`
	}
	
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return 0, fmt.Errorf("failed to decode balance response: %v", err)
	}
	
	return result.Balance, nil
}

func (as *TigerBeetleIntegratedAccountService) publishAccountEvent(account Account, eventType string) {
	event := map[string]interface{}{
		"type":      eventType,
		"account":   account,
		"timestamp": time.Now(),
	}
	
	as.publishEvent(eventType, event)
}

func (as *TigerBeetleIntegratedAccountService) publishEvent(eventType string, data interface{}) {
	eventData, err := json.Marshal(data)
	if err != nil {
		log.Printf("Failed to marshal event: %v", err)
		return
	}
	
	ctx := context.Background()
	if err := as.redis.Publish(ctx, "accounts:events", eventData).Err(); err != nil {
		log.Printf("Failed to publish event: %v", err)
	}
}

// HTTP Handlers

func (as *TigerBeetleIntegratedAccountService) setupRoutes() *gin.Engine {
	router := gin.Default()
	
	// Health check
	router.GET("/health", as.healthHandler)
	
	// Metrics
	router.GET("/metrics", gin.WrapH(promhttp.Handler()))
	
	// Account endpoints
	router.POST("/accounts", as.createAccountHandler)
	router.GET("/accounts/:id", as.getAccountHandler)
	router.GET("/accounts/:id/balance", as.getAccountBalanceHandler)
	router.PUT("/accounts/:id/status", as.updateAccountStatusHandler)
	
	// Transaction endpoints
	router.GET("/accounts/:id/transactions", as.getAccountTransactionsHandler)
	router.POST("/accounts/:id/transactions", as.recordTransactionHandler)
	
	// Bulk operations
	router.POST("/accounts/bulk", as.createAccountsBulkHandler)
	router.GET("/accounts/search", as.searchAccountsHandler)
	
	return router
}

func (as *TigerBeetleIntegratedAccountService) healthHandler(c *gin.Context) {
	// Check TigerBeetle connectivity
	zigHealthy := as.checkEndpointHealth(as.zigEndpoint)
	edgeHealthy := as.checkEndpointHealth(as.edgeEndpoint)
	
	// Check database connectivity
	dbHealthy := as.db.Ping() == nil
	
	// Check Redis connectivity
	redisHealthy := as.redis.Ping(context.Background()).Err() == nil
	
	status := "healthy"
	if !zigHealthy || !edgeHealthy || !dbHealthy || !redisHealthy {
		status = "unhealthy"
		c.Status(http.StatusServiceUnavailable)
	}
	
	c.JSON(http.StatusOK, gin.H{
		"status": status,
		"checks": gin.H{
			"tigerbeetle_zig":  zigHealthy,
			"tigerbeetle_edge": edgeHealthy,
			"database":         dbHealthy,
			"redis":           redisHealthy,
		},
		"timestamp": time.Now(),
	})
}

func (as *TigerBeetleIntegratedAccountService) checkEndpointHealth(endpoint string) bool {
	resp, err := as.httpClient.Get(endpoint + "/health")
	if err != nil {
		return false
	}
	defer resp.Body.Close()
	
	return resp.StatusCode == http.StatusOK
}

func (as *TigerBeetleIntegratedAccountService) createAccountHandler(c *gin.Context) {
	var account Account
	if err := c.ShouldBindJSON(&account); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	
	createdAccount, err := as.CreateAccount(account)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	
	c.JSON(http.StatusCreated, createdAccount)
}

func (as *TigerBeetleIntegratedAccountService) getAccountHandler(c *gin.Context) {
	accountIDStr := c.Param("id")
	accountID, err := strconv.ParseUint(accountIDStr, 10, 64)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid account ID"})
		return
	}
	
	account, err := as.GetAccount(accountID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "Account not found"})
		return
	}
	
	c.JSON(http.StatusOK, account)
}

func (as *TigerBeetleIntegratedAccountService) getAccountBalanceHandler(c *gin.Context) {
	accountIDStr := c.Param("id")
	accountID, err := strconv.ParseUint(accountIDStr, 10, 64)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid account ID"})
		return
	}
	
	balance, err := as.GetAccountBalance(accountID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	
	c.JSON(http.StatusOK, gin.H{
		"account_id": accountID,
		"balance":    balance,
		"timestamp":  time.Now(),
	})
}

func (as *TigerBeetleIntegratedAccountService) updateAccountStatusHandler(c *gin.Context) {
	accountIDStr := c.Param("id")
	accountID, err := strconv.ParseUint(accountIDStr, 10, 64)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid account ID"})
		return
	}
	
	var request struct {
		Status string `json:"status"`
		Reason string `json:"reason"`
	}
	
	if err := c.ShouldBindJSON(&request); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	
	if err := as.UpdateAccountStatus(accountID, request.Status, request.Reason); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	
	c.JSON(http.StatusOK, gin.H{
		"account_id": accountID,
		"status":     request.Status,
		"updated_at": time.Now(),
	})
}

func (as *TigerBeetleIntegratedAccountService) getAccountTransactionsHandler(c *gin.Context) {
	accountIDStr := c.Param("id")
	accountID, err := strconv.ParseUint(accountIDStr, 10, 64)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid account ID"})
		return
	}
	
	limit := 50
	offset := 0
	
	if limitStr := c.Query("limit"); limitStr != "" {
		if l, err := strconv.Atoi(limitStr); err == nil && l > 0 && l <= 1000 {
			limit = l
		}
	}
	
	if offsetStr := c.Query("offset"); offsetStr != "" {
		if o, err := strconv.Atoi(offsetStr); err == nil && o >= 0 {
			offset = o
		}
	}
	
	transactions, err := as.GetAccountTransactions(accountID, limit, offset)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	
	c.JSON(http.StatusOK, gin.H{
		"account_id":   accountID,
		"transactions": transactions,
		"limit":        limit,
		"offset":       offset,
		"count":        len(transactions),
	})
}

func (as *TigerBeetleIntegratedAccountService) recordTransactionHandler(c *gin.Context) {
	accountIDStr := c.Param("id")
	accountID, err := strconv.ParseUint(accountIDStr, 10, 64)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid account ID"})
		return
	}
	
	var transaction AccountTransaction
	if err := c.ShouldBindJSON(&transaction); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	
	transaction.AccountID = accountID
	
	if err := as.RecordTransaction(transaction); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	
	c.JSON(http.StatusCreated, gin.H{
		"transaction_id": transaction.ID,
		"account_id":     accountID,
		"status":         "recorded",
	})
}

func (as *TigerBeetleIntegratedAccountService) createAccountsBulkHandler(c *gin.Context) {
	var accounts []Account
	if err := c.ShouldBindJSON(&accounts); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	
	var results []interface{}
	var errors []string
	
	for _, account := range accounts {
		if createdAccount, err := as.CreateAccount(account); err != nil {
			errors = append(errors, fmt.Sprintf("Account %s: %v", account.AccountNumber, err))
		} else {
			results = append(results, createdAccount)
		}
	}
	
	response := gin.H{
		"created": results,
		"count":   len(results),
	}
	
	if len(errors) > 0 {
		response["errors"] = errors
	}
	
	c.JSON(http.StatusCreated, response)
}

func (as *TigerBeetleIntegratedAccountService) searchAccountsHandler(c *gin.Context) {
	// Implement account search functionality
	customerID := c.Query("customer_id")
	agentID := c.Query("agent_id")
	accountType := c.Query("account_type")
	status := c.Query("status")
	
	query := "SELECT id, account_number, account_type, currency, status, created_at FROM accounts WHERE 1=1"
	args := []interface{}{}
	argCount := 0
	
	if customerID != "" {
		argCount++
		query += fmt.Sprintf(" AND customer_id = $%d", argCount)
		args = append(args, customerID)
	}
	
	if agentID != "" {
		argCount++
		query += fmt.Sprintf(" AND agent_id = $%d", argCount)
		args = append(args, agentID)
	}
	
	if accountType != "" {
		argCount++
		query += fmt.Sprintf(" AND account_type = $%d", argCount)
		args = append(args, accountType)
	}
	
	if status != "" {
		argCount++
		query += fmt.Sprintf(" AND status = $%d", argCount)
		args = append(args, status)
	}
	
	query += " ORDER BY created_at DESC LIMIT 100"
	
	rows, err := as.db.Query(query, args...)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	defer rows.Close()
	
	var accounts []map[string]interface{}
	for rows.Next() {
		var id uint64
		var accountNumber, accountType, currency, status string
		var createdAt time.Time
		
		if err := rows.Scan(&id, &accountNumber, &accountType, &currency, &status, &createdAt); err != nil {
			continue
		}
		
		accounts = append(accounts, map[string]interface{}{
			"id":             id,
			"account_number": accountNumber,
			"account_type":   accountType,
			"currency":       currency,
			"status":         status,
			"created_at":     createdAt,
		})
	}
	
	c.JSON(http.StatusOK, gin.H{
		"accounts": accounts,
		"count":    len(accounts),
	})
}

func account_service_integratedMain() {
	// Initialize service
	service, err := NewTigerBeetleIntegratedAccountService(
		"http://localhost:3000",  // Zig endpoint
		"http://localhost:3001",  // Edge endpoint
		"postgres://user:pass@localhost/accounts_db",
		"redis://localhost:6379",
	)
	if err != nil {
		log.Fatal("Failed to initialize account service:", err)
	}
	
	// Setup routes
	router := service.setupRoutes()
	
	// Start server
	port := ":8081"
	log.Printf("Starting TigerBeetle Integrated Account Service on port %s", port)
	log.Fatal(router.Run(port))
}

