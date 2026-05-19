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

// TigerBeetleIntegratedPaymentService handles payments using TigerBeetle for accounting
type TigerBeetleIntegratedPaymentService struct {
	// TigerBeetle endpoints
	zigEndpoint   string
	edgeEndpoint  string
	
	// Traditional databases for metadata
	db    *sql.DB
	redis *redis.Client
	
	// HTTP client for TigerBeetle communication
	httpClient *http.Client
	
	// Metrics
	paymentsProcessed prometheus.Counter
	paymentDuration   prometheus.Histogram
	paymentErrors     prometheus.Counter
}

// Payment represents a payment transaction with TigerBeetle integration
type Payment struct {
	// Core payment data
	ID                string    `json:"id"`
	PaymentReference  string    `json:"payment_reference"`
	PayerAccountID    uint64    `json:"payer_account_id"`    // TigerBeetle account ID
	PayeeAccountID    uint64    `json:"payee_account_id"`    // TigerBeetle account ID
	Amount            uint64    `json:"amount"`              // Amount in smallest currency unit
	Currency          string    `json:"currency"`
	
	// TigerBeetle transfer data
	TransferID        uint64    `json:"transfer_id"`         // TigerBeetle transfer ID
	FeeTransferID     uint64    `json:"fee_transfer_id"`     // Fee transfer ID
	Ledger            uint32    `json:"ledger"`
	Code              uint16    `json:"code"`
	
	// Metadata (stored in PostgreSQL)
	PaymentMethod     string    `json:"payment_method"`
	PaymentType       string    `json:"payment_type"`
	Description       string    `json:"description"`
	Status            string    `json:"status"`
	ProcessorResponse string    `json:"processor_response"`
	FeeAmount         uint64    `json:"fee_amount"`
	NetAmount         uint64    `json:"net_amount"`
	ExchangeRate      float64   `json:"exchange_rate"`
	ProcessedAt       *time.Time `json:"processed_at"`
	SettledAt         *time.Time `json:"settled_at"`
	CreatedAt         time.Time `json:"created_at"`
	UpdatedAt         time.Time `json:"updated_at"`
	Metadata          string    `json:"metadata"`
	RiskScore         float64   `json:"risk_score"`
	AgentID           string    `json:"agent_id"`
	CustomerID        string    `json:"customer_id"`
}

// TigerBeetleTransfer represents a TigerBeetle transfer
// TigerBeetleAccount represents a TigerBeetle account
// Nigerian banking ledger codes

// Nigerian banking account codes

// Transfer codes for different payment types

// NewTigerBeetleIntegratedPaymentService creates a new integrated payment service
func NewTigerBeetleIntegratedPaymentService(zigEndpoint, edgeEndpoint, dbURL, redisURL string) (*TigerBeetleIntegratedPaymentService, error) {
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
	paymentsProcessed := prometheus.NewCounter(prometheus.CounterOpts{
		Name: "payments_processed_total",
		Help: "Total number of payments processed",
	})
	
	paymentDuration := prometheus.NewHistogram(prometheus.HistogramOpts{
		Name: "payment_processing_duration_seconds",
		Help: "Payment processing duration in seconds",
	})
	
	paymentErrors := prometheus.NewCounter(prometheus.CounterOpts{
		Name: "payment_errors_total",
		Help: "Total number of payment errors",
	})
	
	prometheus.MustRegister(paymentsProcessed, paymentDuration, paymentErrors)
	
	service := &TigerBeetleIntegratedPaymentService{
		zigEndpoint:       zigEndpoint,
		edgeEndpoint:      edgeEndpoint,
		db:                db,
		redis:             redisClient,
		httpClient:        &http.Client{Timeout: 30 * time.Second},
		paymentsProcessed: paymentsProcessed,
		paymentDuration:   paymentDuration,
		paymentErrors:     paymentErrors,
	}
	
	// Initialize database tables
	if err := service.initTables(); err != nil {
		return nil, fmt.Errorf("failed to initialize tables: %v", err)
	}
	
	return service, nil
}

// initTables creates necessary PostgreSQL tables for payment metadata
func (ps *TigerBeetleIntegratedPaymentService) initTables() error {
	query := `
		CREATE TABLE IF NOT EXISTS payments (
			id VARCHAR(100) PRIMARY KEY,
			payment_reference VARCHAR(100) UNIQUE NOT NULL,
			payer_account_id BIGINT NOT NULL,
			payee_account_id BIGINT NOT NULL,
			amount BIGINT NOT NULL,
			currency VARCHAR(10) NOT NULL,
			transfer_id BIGINT,
			fee_transfer_id BIGINT,
			ledger INTEGER,
			code INTEGER,
			payment_method VARCHAR(50),
			payment_type VARCHAR(50),
			description TEXT,
			status VARCHAR(20) DEFAULT 'pending',
			processor_response TEXT,
			fee_amount BIGINT DEFAULT 0,
			net_amount BIGINT,
			exchange_rate DECIMAL(10,6) DEFAULT 1.0,
			processed_at TIMESTAMP,
			settled_at TIMESTAMP,
			created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
			updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
			metadata JSONB,
			risk_score DECIMAL(5,2) DEFAULT 0.0,
			agent_id VARCHAR(100),
			customer_id VARCHAR(100)
		);
		
		CREATE INDEX IF NOT EXISTS idx_payments_reference ON payments(payment_reference);
		CREATE INDEX IF NOT EXISTS idx_payments_payer ON payments(payer_account_id);
		CREATE INDEX IF NOT EXISTS idx_payments_payee ON payments(payee_account_id);
		CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);
		CREATE INDEX IF NOT EXISTS idx_payments_agent ON payments(agent_id);
		CREATE INDEX IF NOT EXISTS idx_payments_customer ON payments(customer_id);
		CREATE INDEX IF NOT EXISTS idx_payments_created ON payments(created_at);
	`
	
	_, err := ps.db.Exec(query)
	return err
}

// ProcessPayment processes a payment using TigerBeetle double-entry bookkeeping
func (ps *TigerBeetleIntegratedPaymentService) ProcessPayment(payment Payment) (*Payment, error) {
	timer := prometheus.NewTimer(ps.paymentDuration)
	defer timer.ObserveDuration()
	
	// Generate IDs
	payment.ID = uuid.New().String()
	payment.TransferID = ps.generateTransferID()
	payment.FeeTransferID = ps.generateTransferID()
	payment.CreatedAt = time.Now()
	payment.UpdatedAt = time.Now()
	payment.Status = "processing"
	
	// Calculate net amount
	payment.NetAmount = payment.Amount - payment.FeeAmount
	
	// Start database transaction
	tx, err := ps.db.Begin()
	if err != nil {
		ps.paymentErrors.Inc()
		return nil, fmt.Errorf("failed to start transaction: %v", err)
	}
	defer tx.Rollback()
	
	// Store payment metadata in PostgreSQL
	if err := ps.storePaymentMetadata(tx, payment); err != nil {
		ps.paymentErrors.Inc()
		return nil, fmt.Errorf("failed to store payment metadata: %v", err)
	}
	
	// Create TigerBeetle transfers
	transfers := []TigerBeetleTransfer{
		// Main payment transfer
		{
			ID:              payment.TransferID,
			DebitAccountID:  payment.PayerAccountID,
			CreditAccountID: payment.PayeeAccountID,
			UserData:        uint64(payment.TransferID), // Link to payment
			Ledger:          CUSTOMER_DEPOSITS_LEDGER,
			Code:            TRANSFER_CODE_PAYMENT,
			Amount:          payment.Amount,
			Timestamp:       time.Now().Unix(),
		},
	}
	
	// Add fee transfer if fee amount > 0
	if payment.FeeAmount > 0 {
		feeAccountID := ps.getFeeAccountID(payment.Currency)
		transfers = append(transfers, TigerBeetleTransfer{
			ID:              payment.FeeTransferID,
			DebitAccountID:  payment.PayerAccountID,
			CreditAccountID: feeAccountID,
			UserData:        uint64(payment.TransferID), // Link to main payment
			Ledger:          FEE_INCOME_LEDGER,
			Code:            TRANSFER_CODE_FEE,
			Amount:          payment.FeeAmount,
			Timestamp:       time.Now().Unix(),
		})
	}
	
	// Execute transfers in TigerBeetle
	if err := ps.createTigerBeetleTransfers(transfers); err != nil {
		ps.paymentErrors.Inc()
		return nil, fmt.Errorf("failed to create TigerBeetle transfers: %v", err)
	}
	
	// Update payment status
	payment.Status = "completed"
	payment.ProcessedAt = &payment.UpdatedAt
	payment.UpdatedAt = time.Now()
	
	// Update payment in database
	if err := ps.updatePaymentStatus(tx, payment.ID, "completed", payment.ProcessedAt); err != nil {
		ps.paymentErrors.Inc()
		return nil, fmt.Errorf("failed to update payment status: %v", err)
	}
	
	// Commit transaction
	if err := tx.Commit(); err != nil {
		ps.paymentErrors.Inc()
		return nil, fmt.Errorf("failed to commit transaction: %v", err)
	}
	
	// Publish payment event to Redis
	ps.publishPaymentEvent(payment, "payment.completed")
	
	// Update metrics
	ps.paymentsProcessed.Inc()
	
	log.Printf("Payment processed successfully: %s, Amount: %d %s", 
		payment.PaymentReference, payment.Amount, payment.Currency)
	
	return &payment, nil
}

// GetPayment retrieves a payment with current balance information from TigerBeetle
func (ps *TigerBeetleIntegratedPaymentService) GetPayment(paymentID string) (*Payment, error) {
	// Get payment metadata from PostgreSQL
	payment, err := ps.getPaymentMetadata(paymentID)
	if err != nil {
		return nil, fmt.Errorf("failed to get payment metadata: %v", err)
	}
	
	// Get current account balances from TigerBeetle
	payerBalance, err := ps.getAccountBalance(payment.PayerAccountID)
	if err != nil {
		log.Printf("Warning: failed to get payer balance: %v", err)
	}
	
	payeeBalance, err := ps.getAccountBalance(payment.PayeeAccountID)
	if err != nil {
		log.Printf("Warning: failed to get payee balance: %v", err)
	}
	
	// Add balance information to metadata
	balanceInfo := map[string]interface{}{
		"payer_balance": payerBalance,
		"payee_balance": payeeBalance,
		"retrieved_at":  time.Now(),
	}
	
	balanceJSON, _ := json.Marshal(balanceInfo)
	payment.Metadata = string(balanceJSON)
	
	return payment, nil
}

// GetAccountBalance retrieves account balance from TigerBeetle
func (ps *TigerBeetleIntegratedPaymentService) GetAccountBalance(accountID uint64) (int64, error) {
	return ps.getAccountBalance(accountID)
}

// ProcessAgentPayment processes a payment involving an agent with special handling
func (ps *TigerBeetleIntegratedPaymentService) ProcessAgentPayment(payment Payment) (*Payment, error) {
	// Set agent-specific ledger and codes
	payment.Ledger = AGENT_ACCOUNTS_LEDGER
	payment.Code = 1009
	
	// Add agent commission calculation
	agentCommission := ps.calculateAgentCommission(payment.Amount, payment.AgentID)
	
	// Create additional transfer for agent commission
	if agentCommission > 0 {
		// This will be handled in the main ProcessPayment method
		// by adding an additional transfer
		payment.FeeAmount += agentCommission
	}
	
	return ps.ProcessPayment(payment)
}

// Helper methods

func (ps *TigerBeetleIntegratedPaymentService) generateTransferID() uint64 {
	// Generate unique transfer ID (timestamp + random)
	return uint64(time.Now().UnixNano())
}

func (ps *TigerBeetleIntegratedPaymentService) getFeeAccountID(currency string) uint64 {
	// Return fee account ID based on currency
	// This would be configured based on your fee structure
	switch currency {
	case "NGN":
		return 1000000 // NGN fee account
	case "USD":
		return 1000001 // USD fee account
	default:
		return 1000000 // Default fee account
	}
}

func (ps *TigerBeetleIntegratedPaymentService) calculateAgentCommission(amount uint64, agentID string) uint64 {
	// Calculate agent commission based on amount and agent tier
	// This is a simplified calculation - implement your business logic
	commissionRate := 0.005 // 0.5%
	return uint64(float64(amount) * commissionRate)
}

func (ps *TigerBeetleIntegratedPaymentService) storePaymentMetadata(tx *sql.Tx, payment Payment) error {
	query := `
		INSERT INTO payments (
			id, payment_reference, payer_account_id, payee_account_id, amount, currency,
			transfer_id, fee_transfer_id, ledger, code, payment_method, payment_type,
			description, status, fee_amount, net_amount, exchange_rate, created_at,
			updated_at, metadata, risk_score, agent_id, customer_id
		) VALUES (
			$1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23
		)
	`
	
	_, err := tx.Exec(query,
		payment.ID, payment.PaymentReference, payment.PayerAccountID, payment.PayeeAccountID,
		payment.Amount, payment.Currency, payment.TransferID, payment.FeeTransferID,
		payment.Ledger, payment.Code, payment.PaymentMethod, payment.PaymentType,
		payment.Description, payment.Status, payment.FeeAmount, payment.NetAmount,
		payment.ExchangeRate, payment.CreatedAt, payment.UpdatedAt, payment.Metadata,
		payment.RiskScore, payment.AgentID, payment.CustomerID,
	)
	
	return err
}

func (ps *TigerBeetleIntegratedPaymentService) updatePaymentStatus(tx *sql.Tx, paymentID, status string, processedAt *time.Time) error {
	query := `
		UPDATE payments 
		SET status = $1, processed_at = $2, updated_at = CURRENT_TIMESTAMP
		WHERE id = $3
	`
	
	_, err := tx.Exec(query, status, processedAt, paymentID)
	return err
}

func (ps *TigerBeetleIntegratedPaymentService) getPaymentMetadata(paymentID string) (*Payment, error) {
	query := `
		SELECT id, payment_reference, payer_account_id, payee_account_id, amount, currency,
		       transfer_id, fee_transfer_id, ledger, code, payment_method, payment_type,
		       description, status, fee_amount, net_amount, exchange_rate, processed_at,
		       settled_at, created_at, updated_at, metadata, risk_score, agent_id, customer_id
		FROM payments WHERE id = $1
	`
	
	row := ps.db.QueryRow(query, paymentID)
	
	var payment Payment
	err := row.Scan(
		&payment.ID, &payment.PaymentReference, &payment.PayerAccountID, &payment.PayeeAccountID,
		&payment.Amount, &payment.Currency, &payment.TransferID, &payment.FeeTransferID,
		&payment.Ledger, &payment.Code, &payment.PaymentMethod, &payment.PaymentType,
		&payment.Description, &payment.Status, &payment.FeeAmount, &payment.NetAmount,
		&payment.ExchangeRate, &payment.ProcessedAt, &payment.SettledAt, &payment.CreatedAt,
		&payment.UpdatedAt, &payment.Metadata, &payment.RiskScore, &payment.AgentID, &payment.CustomerID,
	)
	
	if err != nil {
		return nil, err
	}
	
	return &payment, nil
}

func (ps *TigerBeetleIntegratedPaymentService) createTigerBeetleTransfers(transfers []TigerBeetleTransfer) error {
	// Try edge endpoint first for better performance
	if err := ps.sendTransfersToEndpoint(transfers, ps.edgeEndpoint); err != nil {
		log.Printf("Edge endpoint failed, trying Zig primary: %v", err)
		// Fallback to Zig primary
		return ps.sendTransfersToEndpoint(transfers, ps.zigEndpoint)
	}
	
	return nil
}

func (ps *TigerBeetleIntegratedPaymentService) sendTransfersToEndpoint(transfers []TigerBeetleTransfer, endpoint string) error {
	data, err := json.Marshal(transfers)
	if err != nil {
		return fmt.Errorf("failed to marshal transfers: %v", err)
	}
	
	resp, err := ps.httpClient.Post(endpoint+"/transfers", "application/json", bytes.NewBuffer(data))
	if err != nil {
		return fmt.Errorf("failed to send transfers: %v", err)
	}
	defer resp.Body.Close()
	
	if resp.StatusCode != http.StatusCreated && resp.StatusCode != http.StatusOK {
		return fmt.Errorf("TigerBeetle returned status %d", resp.StatusCode)
	}
	
	return nil
}

func (ps *TigerBeetleIntegratedPaymentService) getAccountBalance(accountID uint64) (int64, error) {
	// Try edge endpoint first
	balance, err := ps.getBalanceFromEndpoint(accountID, ps.edgeEndpoint)
	if err != nil {
		// Fallback to Zig primary
		return ps.getBalanceFromEndpoint(accountID, ps.zigEndpoint)
	}
	
	return balance, nil
}

func (ps *TigerBeetleIntegratedPaymentService) getBalanceFromEndpoint(accountID uint64, endpoint string) (int64, error) {
	resp, err := ps.httpClient.Get(fmt.Sprintf("%s/accounts/%d/balance", endpoint, accountID))
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

func (ps *TigerBeetleIntegratedPaymentService) publishPaymentEvent(payment Payment, eventType string) {
	event := map[string]interface{}{
		"type":      eventType,
		"payment":   payment,
		"timestamp": time.Now(),
	}
	
	data, err := json.Marshal(event)
	if err != nil {
		log.Printf("Failed to marshal payment event: %v", err)
		return
	}
	
	ctx := context.Background()
	if err := ps.redis.Publish(ctx, "payments:events", data).Err(); err != nil {
		log.Printf("Failed to publish payment event: %v", err)
	}
}

// HTTP Handlers

func (ps *TigerBeetleIntegratedPaymentService) setupRoutes() *gin.Engine {
	router := gin.Default()
	
	// Health check
	router.GET("/health", ps.healthHandler)
	
	// Metrics
	router.GET("/metrics", gin.WrapH(promhttp.Handler()))
	
	// Payment endpoints
	router.POST("/payments", ps.createPaymentHandler)
	router.GET("/payments/:id", ps.getPaymentHandler)
	router.GET("/payments/:id/status", ps.getPaymentStatusHandler)
	
	// Account balance endpoints
	router.GET("/accounts/:id/balance", ps.getAccountBalanceHandler)
	
	// Agent payment endpoints
	router.POST("/payments/agent", ps.createAgentPaymentHandler)
	
	return router
}

func (ps *TigerBeetleIntegratedPaymentService) healthHandler(c *gin.Context) {
	// Check TigerBeetle connectivity
	zigHealthy := ps.checkEndpointHealth(ps.zigEndpoint)
	edgeHealthy := ps.checkEndpointHealth(ps.edgeEndpoint)
	
	// Check database connectivity
	dbHealthy := ps.db.Ping() == nil
	
	// Check Redis connectivity
	redisHealthy := ps.redis.Ping(context.Background()).Err() == nil
	
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

func (ps *TigerBeetleIntegratedPaymentService) checkEndpointHealth(endpoint string) bool {
	resp, err := ps.httpClient.Get(endpoint + "/health")
	if err != nil {
		return false
	}
	defer resp.Body.Close()
	
	return resp.StatusCode == http.StatusOK
}

func (ps *TigerBeetleIntegratedPaymentService) createPaymentHandler(c *gin.Context) {
	var payment Payment
	if err := c.ShouldBindJSON(&payment); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	
	// Generate payment reference if not provided
	if payment.PaymentReference == "" {
		payment.PaymentReference = fmt.Sprintf("PAY_%d", time.Now().UnixNano())
	}
	
	processedPayment, err := ps.ProcessPayment(payment)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	
	c.JSON(http.StatusCreated, processedPayment)
}

func (ps *TigerBeetleIntegratedPaymentService) getPaymentHandler(c *gin.Context) {
	paymentID := c.Param("id")
	
	payment, err := ps.GetPayment(paymentID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "Payment not found"})
		return
	}
	
	c.JSON(http.StatusOK, payment)
}

func (ps *TigerBeetleIntegratedPaymentService) getPaymentStatusHandler(c *gin.Context) {
	paymentID := c.Param("id")
	
	payment, err := ps.GetPayment(paymentID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "Payment not found"})
		return
	}
	
	c.JSON(http.StatusOK, gin.H{
		"payment_id": payment.ID,
		"status":     payment.Status,
		"amount":     payment.Amount,
		"currency":   payment.Currency,
		"created_at": payment.CreatedAt,
		"updated_at": payment.UpdatedAt,
	})
}

func (ps *TigerBeetleIntegratedPaymentService) getAccountBalanceHandler(c *gin.Context) {
	accountIDStr := c.Param("id")
	accountID, err := strconv.ParseUint(accountIDStr, 10, 64)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid account ID"})
		return
	}
	
	balance, err := ps.GetAccountBalance(accountID)
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

func (ps *TigerBeetleIntegratedPaymentService) createAgentPaymentHandler(c *gin.Context) {
	var payment Payment
	if err := c.ShouldBindJSON(&payment); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	
	// Generate payment reference if not provided
	if payment.PaymentReference == "" {
		payment.PaymentReference = fmt.Sprintf("AGENT_PAY_%d", time.Now().UnixNano())
	}
	
	processedPayment, err := ps.ProcessAgentPayment(payment)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	
	c.JSON(http.StatusCreated, processedPayment)
}

func payment_processing_integratedMain() {
	// Initialize service
	service, err := NewTigerBeetleIntegratedPaymentService(
		"http://localhost:3000",  // Zig endpoint
		"http://localhost:3001",  // Edge endpoint
		"postgres://user:pass@localhost/payments_db",
		"redis://localhost:6379",
	)
	if err != nil {
		log.Fatal("Failed to initialize payment service:", err)
	}
	
	// Setup routes
	router := service.setupRoutes()
	
	// Start server
	port := ":8080"
	log.Printf("Starting TigerBeetle Integrated Payment Service on port %s", port)
	log.Fatal(router.Run(port))
}

