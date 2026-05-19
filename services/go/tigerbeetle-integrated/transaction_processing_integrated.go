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

// Transfer codes
const (
	TRANSFER_CODE_P2P        = 1001
	TRANSFER_CODE_P2M        = 1002
	TRANSFER_CODE_DEPOSIT    = 1003
	TRANSFER_CODE_WITHDRAWAL = 1004
	TRANSFER_CODE_PAYMENT    = 1005
	TRANSFER_CODE_REVERSAL   = 1006
	TRANSFER_CODE_FEE        = 1007
	TRANSFER_CODE_COMMISSION = 1008
)

// Account flags
const (
	FLAG_LINKED    = 0x0001
	FLAG_PENDING   = 0x0002
	FLAG_VOID      = 0x0004
)

// Additional ledger codes
const (
	COMMISSION_LEDGER = 3500
)

// TigerBeetleIntegratedTransactionService handles transactions using TigerBeetle double-entry bookkeeping
type TigerBeetleIntegratedTransactionService struct {
	// TigerBeetle endpoints
	zigEndpoint   string
	edgeEndpoint  string
	
	// Traditional databases for metadata
	db    *sql.DB
	redis *redis.Client
	
	// HTTP client for TigerBeetle communication
	httpClient *http.Client
	
	// Metrics
	transactionsProcessed prometheus.Counter
	transactionDuration   prometheus.Histogram
	transactionErrors     prometheus.Counter
	transfersCreated      prometheus.Counter
}

// Transaction represents a business transaction with TigerBeetle integration
type Transaction struct {
	// Core transaction data
	ID                string    `json:"id"`
	TransactionRef    string    `json:"transaction_ref"`
	Type              string    `json:"type"`              // transfer, deposit, withdrawal, payment
	Status            string    `json:"status"`            // pending, processing, completed, failed
	Amount            uint64    `json:"amount"`            // Amount in smallest currency unit
	Currency          string    `json:"currency"`
	
	// Account information
	FromAccountID     uint64    `json:"from_account_id"`   // TigerBeetle account ID
	ToAccountID       uint64    `json:"to_account_id"`     // TigerBeetle account ID
	
	// TigerBeetle transfer data
	PrimaryTransferID uint64    `json:"primary_transfer_id"`    // Main transfer ID
	FeeTransferID     uint64    `json:"fee_transfer_id"`        // Fee transfer ID (if applicable)
	Ledger            uint32    `json:"ledger"`
	Code              uint16    `json:"code"`
	Flags             uint16    `json:"flags"`
	
	// Business metadata (stored in PostgreSQL)
	Description       string    `json:"description"`
	Category          string    `json:"category"`
	SubCategory       string    `json:"sub_category"`
	PaymentMethod     string    `json:"payment_method"`
	Channel           string    `json:"channel"`           // mobile, web, agent, atm
	Location          string    `json:"location"`
	DeviceID          string    `json:"device_id"`
	IPAddress         string    `json:"ip_address"`
	
	// Fee and commission data
	FeeAmount         uint64    `json:"fee_amount"`
	CommissionAmount  uint64    `json:"commission_amount"`
	NetAmount         uint64    `json:"net_amount"`
	ExchangeRate      float64   `json:"exchange_rate"`
	
	// Participant information
	CustomerID        string    `json:"customer_id"`
	AgentID           string    `json:"agent_id"`
	MerchantID        string    `json:"merchant_id"`
	
	// Risk and compliance
	RiskScore         float64   `json:"risk_score"`
	ComplianceFlags   []string  `json:"compliance_flags"`
	AMLStatus         string    `json:"aml_status"`
	
	// Timing information
	InitiatedAt       time.Time `json:"initiated_at"`
	ProcessedAt       *time.Time `json:"processed_at"`
	SettledAt         *time.Time `json:"settled_at"`
	CreatedAt         time.Time `json:"created_at"`
	UpdatedAt         time.Time `json:"updated_at"`
	
	// Additional metadata
	Metadata          string    `json:"metadata"`
	ExternalRef       string    `json:"external_ref"`
	ParentTxnID       string    `json:"parent_txn_id"`
	BatchID           string    `json:"batch_id"`
}

// TigerBeetleTransfer represents a TigerBeetle transfer for double-entry bookkeeping
// TransactionBatch represents a batch of related transactions
type TransactionBatch struct {
	ID           string        `json:"id"`
	Type         string        `json:"type"`         // bulk_transfer, payroll, settlement
	Status       string        `json:"status"`
	TotalAmount  uint64        `json:"total_amount"`
	TotalCount   int           `json:"total_count"`
	Currency     string        `json:"currency"`
	Transactions []Transaction `json:"transactions"`
	CreatedAt    time.Time     `json:"created_at"`
	ProcessedAt  *time.Time    `json:"processed_at"`
	CreatedBy    string        `json:"created_by"`
	Description  string        `json:"description"`
}


// NewTigerBeetleIntegratedTransactionService creates a new integrated transaction service
func NewTigerBeetleIntegratedTransactionService(zigEndpoint, edgeEndpoint, dbURL, redisURL string) (*TigerBeetleIntegratedTransactionService, error) {
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
	transactionsProcessed := prometheus.NewCounter(prometheus.CounterOpts{
		Name: "transactions_processed_total",
		Help: "Total number of transactions processed",
	})
	
	transactionDuration := prometheus.NewHistogram(prometheus.HistogramOpts{
		Name: "transaction_processing_duration_seconds",
		Help: "Transaction processing duration in seconds",
	})
	
	transactionErrors := prometheus.NewCounter(prometheus.CounterOpts{
		Name: "transaction_errors_total",
		Help: "Total number of transaction errors",
	})
	
	transfersCreated := prometheus.NewCounter(prometheus.CounterOpts{
		Name: "tigerbeetle_transfers_created_total",
		Help: "Total number of TigerBeetle transfers created",
	})
	
	prometheus.MustRegister(transactionsProcessed, transactionDuration, transactionErrors, transfersCreated)
	
	service := &TigerBeetleIntegratedTransactionService{
		zigEndpoint:           zigEndpoint,
		edgeEndpoint:          edgeEndpoint,
		db:                    db,
		redis:                 redisClient,
		httpClient:            &http.Client{Timeout: 30 * time.Second},
		transactionsProcessed: transactionsProcessed,
		transactionDuration:   transactionDuration,
		transactionErrors:     transactionErrors,
		transfersCreated:      transfersCreated,
	}
	
	// Initialize database tables
	if err := service.initTables(); err != nil {
		return nil, fmt.Errorf("failed to initialize tables: %v", err)
	}
	
	return service, nil
}

// initTables creates necessary PostgreSQL tables for transaction metadata
func (ts *TigerBeetleIntegratedTransactionService) initTables() error {
	queries := []string{
		`CREATE TABLE IF NOT EXISTS transactions (
			id VARCHAR(100) PRIMARY KEY,
			transaction_ref VARCHAR(100) UNIQUE NOT NULL,
			type VARCHAR(50) NOT NULL,
			status VARCHAR(20) DEFAULT 'pending',
			amount BIGINT NOT NULL,
			currency VARCHAR(10) NOT NULL,
			from_account_id BIGINT,
			to_account_id BIGINT,
			primary_transfer_id BIGINT,
			fee_transfer_id BIGINT,
			ledger INTEGER,
			code INTEGER,
			flags INTEGER,
			description TEXT,
			category VARCHAR(50),
			sub_category VARCHAR(50),
			payment_method VARCHAR(50),
			channel VARCHAR(50),
			location VARCHAR(100),
			device_id VARCHAR(100),
			ip_address INET,
			fee_amount BIGINT DEFAULT 0,
			commission_amount BIGINT DEFAULT 0,
			net_amount BIGINT,
			exchange_rate DECIMAL(10,6) DEFAULT 1.0,
			customer_id VARCHAR(100),
			agent_id VARCHAR(100),
			merchant_id VARCHAR(100),
			risk_score DECIMAL(5,2) DEFAULT 0.0,
			compliance_flags JSONB,
			aml_status VARCHAR(20) DEFAULT 'pending',
			initiated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
			processed_at TIMESTAMP,
			settled_at TIMESTAMP,
			created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
			updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
			metadata JSONB,
			external_ref VARCHAR(100),
			parent_txn_id VARCHAR(100),
			batch_id VARCHAR(100)
		)`,
		`CREATE TABLE IF NOT EXISTS transaction_batches (
			id VARCHAR(100) PRIMARY KEY,
			type VARCHAR(50) NOT NULL,
			status VARCHAR(20) DEFAULT 'pending',
			total_amount BIGINT NOT NULL,
			total_count INTEGER NOT NULL,
			currency VARCHAR(10) NOT NULL,
			created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
			processed_at TIMESTAMP,
			created_by VARCHAR(100),
			description TEXT
		)`,
		`CREATE TABLE IF NOT EXISTS transaction_events (
			id SERIAL PRIMARY KEY,
			transaction_id VARCHAR(100) NOT NULL,
			event_type VARCHAR(50) NOT NULL,
			event_data JSONB,
			created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
			created_by VARCHAR(100)
		)`,
		`CREATE TABLE IF NOT EXISTS transaction_reconciliation (
			id SERIAL PRIMARY KEY,
			transaction_id VARCHAR(100) NOT NULL,
			tigerbeetle_transfer_id BIGINT NOT NULL,
			reconciliation_status VARCHAR(20) DEFAULT 'pending',
			discrepancy_amount BIGINT DEFAULT 0,
			reconciled_at TIMESTAMP,
			notes TEXT,
			created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
		)`,
		// Indexes
		`CREATE INDEX IF NOT EXISTS idx_transactions_ref ON transactions(transaction_ref)`,
		`CREATE INDEX IF NOT EXISTS idx_transactions_type ON transactions(type)`,
		`CREATE INDEX IF NOT EXISTS idx_transactions_status ON transactions(status)`,
		`CREATE INDEX IF NOT EXISTS idx_transactions_from_account ON transactions(from_account_id)`,
		`CREATE INDEX IF NOT EXISTS idx_transactions_to_account ON transactions(to_account_id)`,
		`CREATE INDEX IF NOT EXISTS idx_transactions_customer ON transactions(customer_id)`,
		`CREATE INDEX IF NOT EXISTS idx_transactions_agent ON transactions(agent_id)`,
		`CREATE INDEX IF NOT EXISTS idx_transactions_created ON transactions(created_at)`,
		`CREATE INDEX IF NOT EXISTS idx_transactions_batch ON transactions(batch_id)`,
		`CREATE INDEX IF NOT EXISTS idx_transaction_events_txn ON transaction_events(transaction_id)`,
		`CREATE INDEX IF NOT EXISTS idx_transaction_events_type ON transaction_events(event_type)`,
		`CREATE INDEX IF NOT EXISTS idx_reconciliation_txn ON transaction_reconciliation(transaction_id)`,
		`CREATE INDEX IF NOT EXISTS idx_reconciliation_transfer ON transaction_reconciliation(tigerbeetle_transfer_id)`,
	}
	
	for _, query := range queries {
		if _, err := ts.db.Exec(query); err != nil {
			return fmt.Errorf("failed to execute query: %v", err)
		}
	}
	
	return nil
}

// ProcessTransaction processes a transaction using TigerBeetle double-entry bookkeeping
func (ts *TigerBeetleIntegratedTransactionService) ProcessTransaction(txn Transaction) (*Transaction, error) {
	timer := prometheus.NewTimer(ts.transactionDuration)
	defer timer.ObserveDuration()
	
	// Generate IDs and set defaults
	txn.ID = uuid.New().String()
	txn.PrimaryTransferID = ts.generateTransferID()
	txn.InitiatedAt = time.Now()
	txn.CreatedAt = time.Now()
	txn.UpdatedAt = time.Now()
	txn.Status = "processing"
	
	// Generate transaction reference if not provided
	if txn.TransactionRef == "" {
		txn.TransactionRef = ts.generateTransactionRef(txn.Type)
	}
	
	// Set TigerBeetle fields based on transaction type
	ts.setTigerBeetleFields(&txn)
	
	// Calculate net amount
	txn.NetAmount = txn.Amount - txn.FeeAmount - txn.CommissionAmount
	
	// Start database transaction
	dbTx, err := ts.db.Begin()
	if err != nil {
		ts.transactionErrors.Inc()
		return nil, fmt.Errorf("failed to start database transaction: %v", err)
	}
	defer dbTx.Rollback()
	
	// Store transaction metadata
	if err := ts.storeTransactionMetadata(dbTx, txn); err != nil {
		ts.transactionErrors.Inc()
		return nil, fmt.Errorf("failed to store transaction metadata: %v", err)
	}
	
	// Create TigerBeetle transfers for double-entry bookkeeping
	transfers, err := ts.createDoubleEntryTransfers(txn)
	if err != nil {
		ts.transactionErrors.Inc()
		return nil, fmt.Errorf("failed to create double-entry transfers: %v", err)
	}
	
	// Execute transfers in TigerBeetle
	if err := ts.executeTigerBeetleTransfers(transfers); err != nil {
		ts.transactionErrors.Inc()
		return nil, fmt.Errorf("failed to execute TigerBeetle transfers: %v", err)
	}
	
	// Record reconciliation entries
	for _, transfer := range transfers {
		if err := ts.recordReconciliation(dbTx, txn.ID, transfer.ID); err != nil {
			log.Printf("Warning: failed to record reconciliation for transfer %d: %v", transfer.ID, err)
		}
	}
	
	// Update transaction status
	txn.Status = "completed"
	processedAt := time.Now()
	txn.ProcessedAt = &processedAt
	txn.UpdatedAt = processedAt
	
	if err := ts.updateTransactionStatus(dbTx, txn.ID, "completed", &processedAt); err != nil {
		ts.transactionErrors.Inc()
		return nil, fmt.Errorf("failed to update transaction status: %v", err)
	}
	
	// Record transaction event
	if err := ts.recordTransactionEvent(dbTx, txn.ID, "transaction.completed", map[string]interface{}{
		"transfers_created": len(transfers),
		"total_amount":      txn.Amount,
		"net_amount":        txn.NetAmount,
	}); err != nil {
		log.Printf("Warning: failed to record transaction event: %v", err)
	}
	
	// Commit database transaction
	if err := dbTx.Commit(); err != nil {
		ts.transactionErrors.Inc()
		return nil, fmt.Errorf("failed to commit database transaction: %v", err)
	}
	
	// Publish transaction event to Redis
	ts.publishTransactionEvent(txn, "transaction.completed")
	
	// Update metrics
	ts.transactionsProcessed.Inc()
	ts.transfersCreated.Add(float64(len(transfers)))
	
	log.Printf("Transaction processed successfully: %s, Amount: %d %s, Transfers: %d", 
		txn.TransactionRef, txn.Amount, txn.Currency, len(transfers))
	
	return &txn, nil
}

// ProcessTransactionBatch processes multiple transactions as a batch
func (ts *TigerBeetleIntegratedTransactionService) ProcessTransactionBatch(batch TransactionBatch) (*TransactionBatch, error) {
	batch.ID = uuid.New().String()
	batch.CreatedAt = time.Now()
	batch.Status = "processing"
	
	// Calculate totals
	batch.TotalCount = len(batch.Transactions)
	batch.TotalAmount = 0
	for _, txn := range batch.Transactions {
		batch.TotalAmount += txn.Amount
	}
	
	// Store batch metadata
	if err := ts.storeBatchMetadata(batch); err != nil {
		return nil, fmt.Errorf("failed to store batch metadata: %v", err)
	}
	
	// Process each transaction in the batch
	var processedTransactions []Transaction
	var errors []string
	
	for i, txn := range batch.Transactions {
		txn.BatchID = batch.ID
		
		processedTxn, err := ts.ProcessTransaction(txn)
		if err != nil {
			errors = append(errors, fmt.Sprintf("Transaction %d: %v", i+1, err))
			continue
		}
		
		processedTransactions = append(processedTransactions, *processedTxn)
	}
	
	// Update batch status
	if len(errors) == 0 {
		batch.Status = "completed"
	} else if len(processedTransactions) > 0 {
		batch.Status = "partial"
	} else {
		batch.Status = "failed"
	}
	
	processedAt := time.Now()
	batch.ProcessedAt = &processedAt
	batch.Transactions = processedTransactions
	
	// Update batch in database
	if err := ts.updateBatchStatus(batch.ID, batch.Status, &processedAt); err != nil {
		log.Printf("Warning: failed to update batch status: %v", err)
	}
	
	// Publish batch completion event
	ts.publishBatchEvent(batch, "batch.completed")
	
	if len(errors) > 0 {
		return &batch, fmt.Errorf("batch processing completed with errors: %v", errors)
	}
	
	return &batch, nil
}

// GetTransaction retrieves a transaction with current account balances
func (ts *TigerBeetleIntegratedTransactionService) GetTransaction(transactionID string) (*Transaction, error) {
	// Get transaction metadata from PostgreSQL
	txn, err := ts.getTransactionMetadata(transactionID)
	if err != nil {
		return nil, fmt.Errorf("failed to get transaction metadata: %v", err)
	}
	
	// Get current account balances from TigerBeetle
	if txn.FromAccountID > 0 {
		if balance, err := ts.getAccountBalance(txn.FromAccountID); err == nil {
			// Add balance info to metadata
			balanceInfo := map[string]interface{}{
				"from_account_balance": balance,
				"retrieved_at":         time.Now(),
			}
			
			if txn.ToAccountID > 0 {
				if toBalance, err := ts.getAccountBalance(txn.ToAccountID); err == nil {
					balanceInfo["to_account_balance"] = toBalance
				}
			}
			
			balanceJSON, _ := json.Marshal(balanceInfo)
			txn.Metadata = string(balanceJSON)
		}
	}
	
	return txn, nil
}

// ReverseTransaction creates a reversal transaction
func (ts *TigerBeetleIntegratedTransactionService) ReverseTransaction(originalTxnID string, reason string) (*Transaction, error) {
	// Get original transaction
	originalTxn, err := ts.GetTransaction(originalTxnID)
	if err != nil {
		return nil, fmt.Errorf("failed to get original transaction: %v", err)
	}
	
	if originalTxn.Status != "completed" {
		return nil, fmt.Errorf("can only reverse completed transactions")
	}
	
	// Create reversal transaction
	reversalTxn := Transaction{
		Type:              "reversal",
		Amount:            originalTxn.Amount,
		Currency:          originalTxn.Currency,
		FromAccountID:     originalTxn.ToAccountID,   // Swap accounts
		ToAccountID:       originalTxn.FromAccountID, // Swap accounts
		FeeAmount:         0, // No fees on reversals
		CommissionAmount:  0, // No commission on reversals
		Description:       fmt.Sprintf("Reversal of %s: %s", originalTxn.TransactionRef, reason),
		Category:          "reversal",
		PaymentMethod:     originalTxn.PaymentMethod,
		Channel:           originalTxn.Channel,
		CustomerID:        originalTxn.CustomerID,
		AgentID:           originalTxn.AgentID,
		ParentTxnID:       originalTxnID,
		ExternalRef:       fmt.Sprintf("REV_%s", originalTxn.TransactionRef),
	}
	
	return ts.ProcessTransaction(reversalTxn)
}

// Helper methods

func (ts *TigerBeetleIntegratedTransactionService) generateTransferID() uint64 {
	return uint64(time.Now().UnixNano())
}

func (ts *TigerBeetleIntegratedTransactionService) generateTransactionRef(txnType string) string {
	prefix := "TXN"
	switch txnType {
	case "transfer":
		prefix = "TRF"
	case "deposit":
		prefix = "DEP"
	case "withdrawal":
		prefix = "WDR"
	case "payment":
		prefix = "PAY"
	case "reversal":
		prefix = "REV"
	}
	
	timestamp := time.Now().Unix()
	return fmt.Sprintf("%s_%d", prefix, timestamp)
}

func (ts *TigerBeetleIntegratedTransactionService) setTigerBeetleFields(txn *Transaction) {
	// Set ledger based on transaction type and accounts
	switch txn.Type {
	case "transfer", "payment":
		txn.Ledger = CUSTOMER_DEPOSITS_LEDGER
		txn.Code = TRANSFER_CODE_P2P
	case "deposit":
		txn.Ledger = CUSTOMER_DEPOSITS_LEDGER
		txn.Code = TRANSFER_CODE_DEPOSIT
	case "withdrawal":
		txn.Ledger = CUSTOMER_DEPOSITS_LEDGER
		txn.Code = TRANSFER_CODE_WITHDRAWAL
	case "reversal":
		txn.Ledger = CUSTOMER_DEPOSITS_LEDGER
		txn.Code = TRANSFER_CODE_REVERSAL
	default:
		txn.Ledger = CUSTOMER_DEPOSITS_LEDGER
		txn.Code = TRANSFER_CODE_P2P
	}
	
	// Set flags based on transaction characteristics
	txn.Flags = 0
	if txn.FeeAmount > 0 || txn.CommissionAmount > 0 {
		txn.Flags |= FLAG_LINKED // Link main transfer with fee/commission transfers
	}
}

func (ts *TigerBeetleIntegratedTransactionService) createDoubleEntryTransfers(txn Transaction) ([]TigerBeetleTransfer, error) {
	var transfers []TigerBeetleTransfer
	
	// Main transfer
	mainTransfer := TigerBeetleTransfer{
		ID:              txn.PrimaryTransferID,
		DebitAccountID:  txn.FromAccountID,
		CreditAccountID: txn.ToAccountID,
		UserData:        uint64(txn.PrimaryTransferID), // Link to transaction
		Ledger:          txn.Ledger,
		Code:            txn.Code,
		Flags:           txn.Flags,
		Amount:          txn.Amount,
		Timestamp:       time.Now().Unix(),
	}
	transfers = append(transfers, mainTransfer)
	
	// Fee transfer (if applicable)
	if txn.FeeAmount > 0 {
		feeAccountID := ts.getFeeAccountID(txn.Currency)
		txn.FeeTransferID = ts.generateTransferID()
		
		feeTransfer := TigerBeetleTransfer{
			ID:              txn.FeeTransferID,
			DebitAccountID:  txn.FromAccountID,
			CreditAccountID: feeAccountID,
			UserData:        uint64(txn.PrimaryTransferID), // Link to main transaction
			Ledger:          FEE_INCOME_LEDGER,
			Code:            TRANSFER_CODE_FEE,
			Flags:           FLAG_LINKED,
			Amount:          txn.FeeAmount,
			Timestamp:       time.Now().Unix(),
		}
		transfers = append(transfers, feeTransfer)
	}
	
	// Commission transfer (if applicable)
	if txn.CommissionAmount > 0 && txn.AgentID != "" {
		agentAccountID := ts.getAgentAccountID(txn.AgentID)
		commissionTransferID := ts.generateTransferID()
		
		commissionTransfer := TigerBeetleTransfer{
			ID:              commissionTransferID,
			DebitAccountID:  ts.getFeeAccountID(txn.Currency), // From fee account
			CreditAccountID: agentAccountID,
			UserData:        uint64(txn.PrimaryTransferID), // Link to main transaction
			Ledger:          COMMISSION_LEDGER,
			Code:            TRANSFER_CODE_COMMISSION,
			Flags:           FLAG_LINKED,
			Amount:          txn.CommissionAmount,
			Timestamp:       time.Now().Unix(),
		}
		transfers = append(transfers, commissionTransfer)
	}
	
	return transfers, nil
}

func (ts *TigerBeetleIntegratedTransactionService) getFeeAccountID(currency string) uint64 {
	// Return fee account ID based on currency
	switch currency {
	case "NGN":
		return 1000000 // NGN fee account
	case "USD":
		return 1000001 // USD fee account
	default:
		return 1000000 // Default fee account
	}
}

func (ts *TigerBeetleIntegratedTransactionService) getAgentAccountID(agentID string) uint64 {
	// This would typically query the agent service or cache
	// For now, return a calculated ID based on agent ID
	// In production, this should be a proper lookup
	return uint64(2000000 + (len(agentID) * 1000)) // Simplified calculation
}

func (ts *TigerBeetleIntegratedTransactionService) storeTransactionMetadata(tx *sql.Tx, txn Transaction) error {
	complianceFlags, _ := json.Marshal(txn.ComplianceFlags)
	metadata, _ := json.Marshal(map[string]interface{}{
		"original_metadata": txn.Metadata,
		"processing_info": map[string]interface{}{
			"processed_by": "tigerbeetle-transaction-service",
			"version":      "1.0.0",
		},
	})
	
	query := `
		INSERT INTO transactions (
			id, transaction_ref, type, status, amount, currency, from_account_id, to_account_id,
			primary_transfer_id, fee_transfer_id, ledger, code, flags, description, category,
			sub_category, payment_method, channel, location, device_id, ip_address,
			fee_amount, commission_amount, net_amount, exchange_rate, customer_id, agent_id,
			merchant_id, risk_score, compliance_flags, aml_status, initiated_at, created_at,
			updated_at, metadata, external_ref, parent_txn_id, batch_id
		) VALUES (
			$1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20,
			$21, $22, $23, $24, $25, $26, $27, $28, $29, $30, $31, $32, $33, $34, $35, $36, $37, $38
		)
	`
	
	_, err := tx.Exec(query,
		txn.ID, txn.TransactionRef, txn.Type, txn.Status, txn.Amount, txn.Currency,
		txn.FromAccountID, txn.ToAccountID, txn.PrimaryTransferID, txn.FeeTransferID,
		txn.Ledger, txn.Code, txn.Flags, txn.Description, txn.Category, txn.SubCategory,
		txn.PaymentMethod, txn.Channel, txn.Location, txn.DeviceID, txn.IPAddress,
		txn.FeeAmount, txn.CommissionAmount, txn.NetAmount, txn.ExchangeRate,
		txn.CustomerID, txn.AgentID, txn.MerchantID, txn.RiskScore, complianceFlags,
		txn.AMLStatus, txn.InitiatedAt, txn.CreatedAt, txn.UpdatedAt, metadata,
		txn.ExternalRef, txn.ParentTxnID, txn.BatchID,
	)
	
	return err
}

func (ts *TigerBeetleIntegratedTransactionService) updateTransactionStatus(tx *sql.Tx, txnID, status string, processedAt *time.Time) error {
	query := `
		UPDATE transactions 
		SET status = $1, processed_at = $2, updated_at = CURRENT_TIMESTAMP
		WHERE id = $3
	`
	
	_, err := tx.Exec(query, status, processedAt, txnID)
	return err
}

func (ts *TigerBeetleIntegratedTransactionService) recordTransactionEvent(tx *sql.Tx, txnID, eventType string, eventData interface{}) error {
	data, _ := json.Marshal(eventData)
	
	query := `
		INSERT INTO transaction_events (transaction_id, event_type, event_data, created_by)
		VALUES ($1, $2, $3, $4)
	`
	
	_, err := tx.Exec(query, txnID, eventType, data, "system")
	return err
}

func (ts *TigerBeetleIntegratedTransactionService) recordReconciliation(tx *sql.Tx, txnID string, transferID uint64) error {
	query := `
		INSERT INTO transaction_reconciliation (transaction_id, tigerbeetle_transfer_id, reconciliation_status)
		VALUES ($1, $2, 'pending')
	`
	
	_, err := tx.Exec(query, txnID, transferID)
	return err
}

func (ts *TigerBeetleIntegratedTransactionService) executeTigerBeetleTransfers(transfers []TigerBeetleTransfer) error {
	// Try edge endpoint first for better performance
	if err := ts.sendTransfersToEndpoint(transfers, ts.edgeEndpoint); err != nil {
		log.Printf("Edge endpoint failed, trying Zig primary: %v", err)
		// Fallback to Zig primary
		return ts.sendTransfersToEndpoint(transfers, ts.zigEndpoint)
	}
	
	return nil
}

func (ts *TigerBeetleIntegratedTransactionService) sendTransfersToEndpoint(transfers []TigerBeetleTransfer, endpoint string) error {
	data, err := json.Marshal(transfers)
	if err != nil {
		return fmt.Errorf("failed to marshal transfers: %v", err)
	}
	
	resp, err := ts.httpClient.Post(endpoint+"/transfers", "application/json", bytes.NewBuffer(data))
	if err != nil {
		return fmt.Errorf("failed to send transfers: %v", err)
	}
	defer resp.Body.Close()
	
	if resp.StatusCode != http.StatusCreated && resp.StatusCode != http.StatusOK {
		return fmt.Errorf("TigerBeetle returned status %d", resp.StatusCode)
	}
	
	return nil
}

func (ts *TigerBeetleIntegratedTransactionService) getTransactionMetadata(txnID string) (*Transaction, error) {
	query := `
		SELECT id, transaction_ref, type, status, amount, currency, from_account_id, to_account_id,
		       primary_transfer_id, fee_transfer_id, ledger, code, flags, description, category,
		       sub_category, payment_method, channel, location, device_id, ip_address,
		       fee_amount, commission_amount, net_amount, exchange_rate, customer_id, agent_id,
		       merchant_id, risk_score, compliance_flags, aml_status, initiated_at, processed_at,
		       settled_at, created_at, updated_at, metadata, external_ref, parent_txn_id, batch_id
		FROM transactions WHERE id = $1
	`
	
	row := ts.db.QueryRow(query, txnID)
	
	var txn Transaction
	var complianceFlags []byte
	var metadata []byte
	
	err := row.Scan(
		&txn.ID, &txn.TransactionRef, &txn.Type, &txn.Status, &txn.Amount, &txn.Currency,
		&txn.FromAccountID, &txn.ToAccountID, &txn.PrimaryTransferID, &txn.FeeTransferID,
		&txn.Ledger, &txn.Code, &txn.Flags, &txn.Description, &txn.Category, &txn.SubCategory,
		&txn.PaymentMethod, &txn.Channel, &txn.Location, &txn.DeviceID, &txn.IPAddress,
		&txn.FeeAmount, &txn.CommissionAmount, &txn.NetAmount, &txn.ExchangeRate,
		&txn.CustomerID, &txn.AgentID, &txn.MerchantID, &txn.RiskScore, &complianceFlags,
		&txn.AMLStatus, &txn.InitiatedAt, &txn.ProcessedAt, &txn.SettledAt, &txn.CreatedAt,
		&txn.UpdatedAt, &metadata, &txn.ExternalRef, &txn.ParentTxnID, &txn.BatchID,
	)
	
	if err != nil {
		return nil, err
	}
	
	// Unmarshal JSON fields
	if len(complianceFlags) > 0 {
		json.Unmarshal(complianceFlags, &txn.ComplianceFlags)
	}
	
	if len(metadata) > 0 {
		txn.Metadata = string(metadata)
	}
	
	return &txn, nil
}

func (ts *TigerBeetleIntegratedTransactionService) getAccountBalance(accountID uint64) (int64, error) {
	// Try edge endpoint first
	balance, err := ts.getBalanceFromEndpoint(accountID, ts.edgeEndpoint)
	if err != nil {
		// Fallback to Zig primary
		return ts.getBalanceFromEndpoint(accountID, ts.zigEndpoint)
	}
	
	return balance, nil
}

func (ts *TigerBeetleIntegratedTransactionService) getBalanceFromEndpoint(accountID uint64, endpoint string) (int64, error) {
	resp, err := ts.httpClient.Get(fmt.Sprintf("%s/accounts/%d/balance", endpoint, accountID))
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

func (ts *TigerBeetleIntegratedTransactionService) storeBatchMetadata(batch TransactionBatch) error {
	query := `
		INSERT INTO transaction_batches (id, type, status, total_amount, total_count, currency, created_by, description)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
	`
	
	_, err := ts.db.Exec(query, batch.ID, batch.Type, batch.Status, batch.TotalAmount, 
		batch.TotalCount, batch.Currency, batch.CreatedBy, batch.Description)
	return err
}

func (ts *TigerBeetleIntegratedTransactionService) updateBatchStatus(batchID, status string, processedAt *time.Time) error {
	query := `
		UPDATE transaction_batches 
		SET status = $1, processed_at = $2
		WHERE id = $3
	`
	
	_, err := ts.db.Exec(query, status, processedAt, batchID)
	return err
}

func (ts *TigerBeetleIntegratedTransactionService) publishTransactionEvent(txn Transaction, eventType string) {
	event := map[string]interface{}{
		"type":        eventType,
		"transaction": txn,
		"timestamp":   time.Now(),
	}
	
	ts.publishEvent("transactions:events", event)
}

func (ts *TigerBeetleIntegratedTransactionService) publishBatchEvent(batch TransactionBatch, eventType string) {
	event := map[string]interface{}{
		"type":      eventType,
		"batch":     batch,
		"timestamp": time.Now(),
	}
	
	ts.publishEvent("batches:events", event)
}

func (ts *TigerBeetleIntegratedTransactionService) publishEvent(channel string, data interface{}) {
	eventData, err := json.Marshal(data)
	if err != nil {
		log.Printf("Failed to marshal event: %v", err)
		return
	}
	
	ctx := context.Background()
	if err := ts.redis.Publish(ctx, channel, eventData).Err(); err != nil {
		log.Printf("Failed to publish event: %v", err)
	}
}

// HTTP Handlers

func (ts *TigerBeetleIntegratedTransactionService) setupRoutes() *gin.Engine {
	router := gin.Default()
	
	// Health check
	router.GET("/health", ts.healthHandler)
	
	// Metrics
	router.GET("/metrics", gin.WrapH(promhttp.Handler()))
	
	// Transaction endpoints
	router.POST("/transactions", ts.createTransactionHandler)
	router.GET("/transactions/:id", ts.getTransactionHandler)
	router.POST("/transactions/:id/reverse", ts.reverseTransactionHandler)
	
	// Batch endpoints
	router.POST("/transactions/batch", ts.createBatchHandler)
	router.GET("/batches/:id", ts.getBatchHandler)
	
	// Query endpoints
	router.GET("/transactions/search", ts.searchTransactionsHandler)
	router.GET("/accounts/:id/transactions", ts.getAccountTransactionsHandler)
	
	// Reconciliation endpoints
	router.GET("/reconciliation/pending", ts.getPendingReconciliationHandler)
	router.POST("/reconciliation/:id/resolve", ts.resolveReconciliationHandler)
	
	return router
}

func (ts *TigerBeetleIntegratedTransactionService) healthHandler(c *gin.Context) {
	// Check TigerBeetle connectivity
	zigHealthy := ts.checkEndpointHealth(ts.zigEndpoint)
	edgeHealthy := ts.checkEndpointHealth(ts.edgeEndpoint)
	
	// Check database connectivity
	dbHealthy := ts.db.Ping() == nil
	
	// Check Redis connectivity
	redisHealthy := ts.redis.Ping(context.Background()).Err() == nil
	
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

func (ts *TigerBeetleIntegratedTransactionService) checkEndpointHealth(endpoint string) bool {
	resp, err := ts.httpClient.Get(endpoint + "/health")
	if err != nil {
		return false
	}
	defer resp.Body.Close()
	
	return resp.StatusCode == http.StatusOK
}

func (ts *TigerBeetleIntegratedTransactionService) createTransactionHandler(c *gin.Context) {
	var txn Transaction
	if err := c.ShouldBindJSON(&txn); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	
	processedTxn, err := ts.ProcessTransaction(txn)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	
	c.JSON(http.StatusCreated, processedTxn)
}

func (ts *TigerBeetleIntegratedTransactionService) getTransactionHandler(c *gin.Context) {
	txnID := c.Param("id")
	
	txn, err := ts.GetTransaction(txnID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "Transaction not found"})
		return
	}
	
	c.JSON(http.StatusOK, txn)
}

func (ts *TigerBeetleIntegratedTransactionService) reverseTransactionHandler(c *gin.Context) {
	txnID := c.Param("id")
	
	var request struct {
		Reason string `json:"reason"`
	}
	
	if err := c.ShouldBindJSON(&request); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	
	reversalTxn, err := ts.ReverseTransaction(txnID, request.Reason)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	
	c.JSON(http.StatusCreated, reversalTxn)
}

func (ts *TigerBeetleIntegratedTransactionService) createBatchHandler(c *gin.Context) {
	var batch TransactionBatch
	if err := c.ShouldBindJSON(&batch); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	
	processedBatch, err := ts.ProcessTransactionBatch(batch)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	
	c.JSON(http.StatusCreated, processedBatch)
}

func (ts *TigerBeetleIntegratedTransactionService) getBatchHandler(c *gin.Context) {
	batchID := c.Param("id")
	
	// Implementation for getting batch details
	c.JSON(http.StatusOK, gin.H{
		"batch_id": batchID,
		"message":  "Batch retrieval not implemented yet",
	})
}

func (ts *TigerBeetleIntegratedTransactionService) searchTransactionsHandler(c *gin.Context) {
	// Implementation for transaction search
	c.JSON(http.StatusOK, gin.H{
		"message": "Transaction search not implemented yet",
	})
}

func (ts *TigerBeetleIntegratedTransactionService) getAccountTransactionsHandler(c *gin.Context) {
	accountIDStr := c.Param("id")
	accountID, err := strconv.ParseUint(accountIDStr, 10, 64)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid account ID"})
		return
	}
	
	// Implementation for getting account transactions
	c.JSON(http.StatusOK, gin.H{
		"account_id": accountID,
		"message":    "Account transactions retrieval not implemented yet",
	})
}

func (ts *TigerBeetleIntegratedTransactionService) getPendingReconciliationHandler(c *gin.Context) {
	// Implementation for getting pending reconciliation items
	c.JSON(http.StatusOK, gin.H{
		"message": "Pending reconciliation retrieval not implemented yet",
	})
}

func (ts *TigerBeetleIntegratedTransactionService) resolveReconciliationHandler(c *gin.Context) {
	reconciliationID := c.Param("id")
	
	// Implementation for resolving reconciliation
	c.JSON(http.StatusOK, gin.H{
		"reconciliation_id": reconciliationID,
		"message":           "Reconciliation resolution not implemented yet",
	})
}

func transaction_processing_integratedMain() {
	// Initialize service
	service, err := NewTigerBeetleIntegratedTransactionService(
		"http://localhost:3000",  // Zig endpoint
		"http://localhost:3001",  // Edge endpoint
		"postgres://user:pass@localhost/transactions_db",
		"redis://localhost:6379",
	)
	if err != nil {
		log.Fatal("Failed to initialize transaction service:", err)
	}
	
	// Setup routes
	router := service.setupRoutes()
	
	// Start server
	port := ":8082"
	log.Printf("Starting TigerBeetle Integrated Transaction Service on port %s", port)
	log.Fatal(router.Run(port))
}

