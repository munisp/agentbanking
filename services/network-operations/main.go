package main

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"remittance-network/network-operations/migrations"
	"strconv"
	"strings"
	"syscall"
	"time"

	"github.com/gin-contrib/cors"
	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"gorm.io/driver/postgres"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"
)

// =====================================================
// CONFIGURATION
// =====================================================

type Config struct {
	DBHost     string
	DBPort     string
	DBName     string
	DBUser     string
	DBPassword string
	Port       string
}

func loadConfig() *Config {
	return &Config{
		DBHost:     getEnv("DB_HOST", "localhost"),
		DBPort:     getEnv("DB_PORT", "5432"),
		DBName:     getEnv("DB_NAME", "link_core_banking"),
		DBUser:     getEnv("DB_USER", "postgres"),
		DBPassword: getEnv("DB_PASSWORD", "password"),
		Port:       getEnv("PORT", "8080"),
	}
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

func getEnvAsInt(key string, defaultValue int) int {
	if value := os.Getenv(key); value != "" {
		if intValue, err := strconv.Atoi(value); err == nil {
			return intValue
		}
	}
	return defaultValue
}

// =====================================================
// DATABASE MODELS
// =====================================================

// TransactionRecord stores each transaction attempt for statistical analysis
type TransactionRecord struct {
	ID        string    `json:"id" gorm:"type:uuid;primary_key;default:gen_random_uuid()"`
	Type      string    `json:"type" gorm:"type:varchar(50);not null;index:idx_type_channel_medium"`    // transfer, airtime, data, bill_payment, etc
	Channel   string    `json:"channel" gorm:"type:varchar(50);not null;index:idx_type_channel_medium"` // pos, ussd, web, app
	Medium    string    `json:"medium" gorm:"type:varchar(50);not null;index:idx_type_channel_medium"`  // wema, mtn, airtel, etc
	Status    string    `json:"status" gorm:"type:varchar(20);not null"`                                // success, failed
	Amount    float64   `json:"amount" gorm:"type:decimal(15,2)"`                                       // transaction amount in Naira
	AgentID   *string   `json:"agent_id" gorm:"type:uuid;index"`                                        // optional agent tracking
	CreatedAt time.Time `json:"created_at" gorm:"autoCreateTime;index"`
}

// SettlementBatch tracks batch settlement runs
type SettlementBatch struct {
	ID          string    `json:"id" gorm:"type:uuid;primary_key;default:gen_random_uuid()"`
	BatchRef    string    `json:"batch_ref" gorm:"type:varchar(100);uniqueIndex"`
	TenantID    string    `json:"tenant_id" gorm:"type:varchar(100);index"`
	Status      string    `json:"status" gorm:"type:varchar(30);default:'pending'"` // pending, processing, completed, failed
	TotalAmount float64   `json:"total_amount" gorm:"type:decimal(15,2);default:0"`
	TxnCount    int       `json:"txn_count" gorm:"default:0"`
	StartDate   time.Time `json:"start_date"`
	EndDate     time.Time `json:"end_date"`
	ProcessedAt *time.Time `json:"processed_at,omitempty"`
	Notes       string    `json:"notes,omitempty"`
	CreatedAt   time.Time `json:"created_at" gorm:"autoCreateTime"`
	UpdatedAt   time.Time `json:"updated_at" gorm:"autoUpdateTime"`
}

// AgentCashPosition tracks per-agent float balances
type AgentCashPosition struct {
	ID          string    `json:"id" gorm:"type:uuid;primary_key;default:gen_random_uuid()"`
	AgentID     string    `json:"agent_id" gorm:"type:uuid;uniqueIndex:idx_agent_currency"`
	Currency    string    `json:"currency" gorm:"type:varchar(10);uniqueIndex:idx_agent_currency;default:'NGN'"`
	Balance     float64   `json:"balance" gorm:"type:decimal(15,2);default:0"`
	LastTxnAt   *time.Time `json:"last_txn_at,omitempty"`
	CreatedAt   time.Time `json:"created_at" gorm:"autoCreateTime"`
	UpdatedAt   time.Time `json:"updated_at" gorm:"autoUpdateTime"`
}

// ChannelStatistics stores aggregated statistics for predictions (materialized view)
type ChannelStatistics struct {
	ID                string    `json:"id" gorm:"type:uuid;primary_key;default:gen_random_uuid()"`
	Type              string    `json:"type" gorm:"type:varchar(50);not null;uniqueIndex:idx_stats_unique"`
	Channel           string    `json:"channel" gorm:"type:varchar(50);not null;uniqueIndex:idx_stats_unique"`
	Medium            string    `json:"medium" gorm:"type:varchar(50);not null;uniqueIndex:idx_stats_unique"`
	TotalTransactions int       `json:"total_transactions" gorm:"not null;default:0"`
	SuccessCount      int       `json:"success_count" gorm:"not null;default:0"`
	FailureCount      int       `json:"failure_count" gorm:"not null;default:0"`
	SuccessRate       float64   `json:"success_rate" gorm:"type:decimal(5,2);not null;default:0.00"` // 0-100%
	LastUpdated       time.Time `json:"last_updated" gorm:"autoUpdateTime"`
}

// =====================================================
// OPERATIONS MODELS (Canary Releases, A/B Tests, Incidents)
// =====================================================

// CanaryRelease represents a canary deployment
type CanaryRelease struct {
	ID                string                 `json:"id" gorm:"type:uuid;primary_key;default:gen_random_uuid()"`
	Service           string                 `json:"service" gorm:"type:varchar(255);not null;index:idx_canary_service_status"`
	Version           string                 `json:"version" gorm:"type:varchar(50)"`
	Status            string                 `json:"status" gorm:"type:varchar(50);not null;index:idx_canary_service_status"` // "active", "paused", "completed", "rolled_back"
	TrafficPercentage int                    `json:"traffic_percentage" gorm:"default:0"`
	Metrics           map[string]interface{} `json:"metrics" gorm:"type:jsonb;serializer:json"`
	CreatedBy         string                 `json:"created_by"`
	UpdatedBy         string                 `json:"updated_by"`
	CreatedAt         time.Time              `json:"created_at" gorm:"autoCreateTime;index"`
	UpdatedAt         time.Time              `json:"updated_at" gorm:"autoUpdateTime"`
}

// ABTest represents an A/B test
type ABTest struct {
	ID           string                 `json:"id" gorm:"type:uuid;primary_key;default:gen_random_uuid()"`
	Name         string                 `json:"name" gorm:"type:varchar(255);not null;uniqueIndex"`
	Description  string                 `json:"description"`
	Status       string                 `json:"status" gorm:"type:varchar(50);not null;index"` // "running", "completed", "paused"
	VariantA     string                 `json:"variant_a" gorm:"type:varchar(255)"`
	VariantB     string                 `json:"variant_b" gorm:"type:varchar(255)"`
	TrafficSplit int                    `json:"traffic_split" gorm:"default:50"` // Percentage for variant A (0-100)
	ResultsA     map[string]interface{} `json:"results_a" gorm:"type:jsonb;serializer:json"`
	ResultsB     map[string]interface{} `json:"results_b" gorm:"type:jsonb;serializer:json"`
	CreatedBy    string                 `json:"created_by"`
	UpdatedBy    string                 `json:"updated_by"`
	StartedAt    time.Time              `json:"started_at" gorm:"index"`
	EndedAt      *time.Time             `json:"ended_at"`
	CreatedAt    time.Time              `json:"created_at" gorm:"autoCreateTime"`
	UpdatedAt    time.Time              `json:"updated_at" gorm:"autoUpdateTime"`
}

// Incident represents an operational incident
type Incident struct {
	ID          string           `json:"id" gorm:"type:uuid;primary_key;default:gen_random_uuid()"`
	Title       string           `json:"title" gorm:"type:varchar(255);not null"`
	Description string           `json:"description"`
	Severity    string           `json:"severity" gorm:"type:varchar(50);not null;index"` // "critical", "high", "medium", "low"
	Status      string           `json:"status" gorm:"type:varchar(50);not null;index"` // "open", "investigating", "resolved"
	Service     string           `json:"service" gorm:"type:varchar(255);index"`
	AssignedTo  string           `json:"assigned_to"`
	CreatedBy   string           `json:"created_by"`
	UpdatedBy   string           `json:"updated_by"`
	CreatedAt   time.Time        `json:"created_at" gorm:"autoCreateTime;index"`
	ResolvedAt  *time.Time       `json:"resolved_at"`
	Updates     []IncidentUpdate `json:"updates" gorm:"foreignKey:IncidentID;constraint:OnDelete:CASCADE"`
}

// IncidentUpdate represents an update to an incident
type IncidentUpdate struct {
	ID        string    `json:"id" gorm:"type:uuid;primary_key;default:gen_random_uuid()"`
	IncidentID string    `json:"incident_id" gorm:"type:uuid;index"`
	Timestamp time.Time `json:"timestamp" gorm:"autoCreateTime;index"`
	Message   string    `json:"message"`
	Author    string    `json:"author"`
}

// =====================================================
// REQUEST & RESPONSE MODELS
// =====================================================

type RegisterTransactionRequest struct {
	Type    string   `json:"type" binding:"required"`    // transfer, airtime, data, bill_payment, cash_in, cash_out
	Channel string   `json:"channel" binding:"required"` // pos, ussd, web, app
	Medium  string   `json:"medium" binding:"required"`  // wema, mtn, airtel, gtbank, etc
	Status  string   `json:"status" binding:"required"`  // success, failed
	Amount  *float64 `json:"amount"`                     // optional amount in Naira
	AgentID *string  `json:"agent_id"`                   // optional agent ID
}

type RegisterTransactionResponse struct {
	ID                 string    `json:"id"`
	Type               string    `json:"type"`
	Channel            string    `json:"channel"`
	Medium             string    `json:"medium"`
	Status             string    `json:"status"`
	Amount             *float64  `json:"amount,omitempty"`
	RegisteredAt       time.Time `json:"registered_at"`
	Message            string    `json:"message"`
	CurrentSuccessRate float64   `json:"current_success_rate"` // Updated success rate after this transaction
}

type Prediction struct {
	Name       string  `json:"name"`       // Medium name (wema, mtn, airtel, etc)
	Channel    string  `json:"channel"`    // Channel (pos, ussd, web, app)
	Type       string  `json:"type"`       // Transaction type
	Status     string  `json:"status"`     // Success rate as percentage string "90%"
	Rate       float64 `json:"rate"`       // Numeric success rate 0-100
	TotalTxns  int     `json:"total_txns"` // Total transactions recorded
	Confidence string  `json:"confidence"` // low, medium, high based on sample size
}

type GetPredictionsRequest struct {
	Type    *string `form:"type"`    // Optional: filter by transaction type
	Channel *string `form:"channel"` // Optional: filter by channel
	Medium  *string `form:"medium"`  // Optional: filter by specific medium
}

type GetPredictionsResponse struct {
	Predictions []Prediction `json:"predictions"`
	Count       int          `json:"count"`
	FilteredBy  FilterInfo   `json:"filtered_by"`
}

type FilterInfo struct {
	Type    *string `json:"type,omitempty"`
	Channel *string `json:"channel,omitempty"`
	Medium  *string `json:"medium,omitempty"`
}

type ErrorResponse struct {
	Error   string `json:"error"`
	Message string `json:"message"`
}

// =====================================================
// DATABASE SERVICE
// =====================================================

type DatabaseService struct {
	db *gorm.DB
}

func NewDatabaseService(config *Config) (*DatabaseService, error) {
	dsn := fmt.Sprintf("host=%s port=%s user=%s password=%s dbname=%s sslmode=require TimeZone=UTC",
		config.DBHost, config.DBPort, config.DBUser, config.DBPassword, config.DBName)

	db, err := gorm.Open(postgres.Open(dsn), &gorm.Config{
		Logger: logger.Default.LogMode(logger.Info),
	})
	if err != nil {
		return nil, fmt.Errorf("failed to connect to database: %w", err)
	}

	// Auto-migrate tables
	err = db.AutoMigrate(
		&TransactionRecord{},
		&ChannelStatistics{},
		&SettlementBatch{},
		&AgentCashPosition{},
		&CanaryRelease{},
		&ABTest{},
		&Incident{},
		&IncidentUpdate{},
	)
	if err != nil {
		return nil, fmt.Errorf("failed to migrate database: %w", err)
	}

	// Run SQL migrations from embedded files (optional - can be used for advanced migrations)
	if err := migrations.RunMigrations(db); err != nil {
		log.Printf("Warning: Failed to run SQL migrations: %v", err)
	}

	log.Println("Database connected and migrated successfully")
	return &DatabaseService{db: db}, nil
}

// =====================================================
// NETWORK PREDICTION SERVICE
// =====================================================

type NetworkPredictionService struct {
	db *DatabaseService
}

func NewNetworkPredictionService(db *DatabaseService) *NetworkPredictionService {
	return &NetworkPredictionService{db: db}
}

// RegisterTransaction records a new transaction and updates statistics
func (nps *NetworkPredictionService) RegisterTransaction(req *RegisterTransactionRequest) (*RegisterTransactionResponse, error) {
	// Validate status
	if req.Status != "success" && req.Status != "failed" {
		return nil, fmt.Errorf("status must be 'success' or 'failed'")
	}

	// Normalize inputs to lowercase
	req.Type = normalizeString(req.Type)
	req.Channel = normalizeString(req.Channel)
	req.Medium = normalizeString(req.Medium)
	req.Status = normalizeString(req.Status)

	// Create transaction record
	record := &TransactionRecord{
		ID:      uuid.New().String(),
		Type:    req.Type,
		Channel: req.Channel,
		Medium:  req.Medium,
		Status:  req.Status,
		AgentID: req.AgentID,
	}

	if req.Amount != nil {
		record.Amount = *req.Amount
	}

	// Save transaction record
	if err := nps.db.db.Create(record).Error; err != nil {
		return nil, fmt.Errorf("failed to save transaction: %w", err)
	}

	// Update statistics
	if err := nps.updateChannelStatistics(req.Type, req.Channel, req.Medium); err != nil {
		log.Printf("Warning: Failed to update statistics: %v", err)
	}

	// Get updated success rate
	stats, _ := nps.getStatistics(req.Type, req.Channel, req.Medium)
	successRate := 0.0
	if stats != nil {
		successRate = stats.SuccessRate
	}

	return &RegisterTransactionResponse{
		ID:                 record.ID,
		Type:               record.Type,
		Channel:            record.Channel,
		Medium:             record.Medium,
		Status:             record.Status,
		Amount:             req.Amount,
		RegisteredAt:       record.CreatedAt,
		Message:            "Transaction registered successfully",
		CurrentSuccessRate: successRate,
	}, nil
}

// GetPredictions returns success rate predictions for channels
func (nps *NetworkPredictionService) GetPredictions(req *GetPredictionsRequest) (*GetPredictionsResponse, error) {
	query := nps.db.db.Model(&ChannelStatistics{})

	// Apply filters
	if req.Type != nil && *req.Type != "" {
		query = query.Where("type = ?", normalizeString(*req.Type))
	}
	if req.Channel != nil && *req.Channel != "" {
		query = query.Where("channel = ?", normalizeString(*req.Channel))
	}
	if req.Medium != nil && *req.Medium != "" {
		query = query.Where("medium = ?", normalizeString(*req.Medium))
	}

	// Get statistics
	var stats []ChannelStatistics
	if err := query.Order("success_rate DESC").Find(&stats).Error; err != nil {
		return nil, fmt.Errorf("failed to get predictions: %w", err)
	}

	// Convert to predictions
	predictions := make([]Prediction, len(stats))
	for i, stat := range stats {
		predictions[i] = Prediction{
			Name:       stat.Medium,
			Channel:    stat.Channel,
			Type:       stat.Type,
			Status:     fmt.Sprintf("%.0f%%", stat.SuccessRate),
			Rate:       stat.SuccessRate,
			TotalTxns:  stat.TotalTransactions,
			Confidence: calculateConfidence(stat.TotalTransactions),
		}
	}

	return &GetPredictionsResponse{
		Predictions: predictions,
		Count:       len(predictions),
		FilteredBy: FilterInfo{
			Type:    req.Type,
			Channel: req.Channel,
			Medium:  req.Medium,
		},
	}, nil
}

// updateChannelStatistics recalculates statistics for a specific channel combination
func (nps *NetworkPredictionService) updateChannelStatistics(txType, channel, medium string) error {
	// Count total, success, and failure
	var totalCount, successCount, failureCount int64

	nps.db.db.Model(&TransactionRecord{}).
		Where("type = ? AND channel = ? AND medium = ?", txType, channel, medium).
		Count(&totalCount)

	nps.db.db.Model(&TransactionRecord{}).
		Where("type = ? AND channel = ? AND medium = ? AND status = ?", txType, channel, medium, "success").
		Count(&successCount)

	nps.db.db.Model(&TransactionRecord{}).
		Where("type = ? AND channel = ? AND medium = ? AND status = ?", txType, channel, medium, "failed").
		Count(&failureCount)

	// Calculate success rate
	successRate := 0.0
	if totalCount > 0 {
		successRate = (float64(successCount) / float64(totalCount)) * 100.0
	}

	// Upsert statistics
	stats := ChannelStatistics{
		Type:              txType,
		Channel:           channel,
		Medium:            medium,
		TotalTransactions: int(totalCount),
		SuccessCount:      int(successCount),
		FailureCount:      int(failureCount),
		SuccessRate:       successRate,
	}

	// Try to update existing record, or create new one
	result := nps.db.db.Where("type = ? AND channel = ? AND medium = ?", txType, channel, medium).
		Assign(stats).
		FirstOrCreate(&stats)

	return result.Error
}

// getStatistics retrieves statistics for a specific combination
func (nps *NetworkPredictionService) getStatistics(txType, channel, medium string) (*ChannelStatistics, error) {
	var stats ChannelStatistics
	err := nps.db.db.Where("type = ? AND channel = ? AND medium = ?", txType, channel, medium).
		First(&stats).Error
	if err != nil {
		return nil, err
	}
	return &stats, nil
}

// =====================================================
// HELPER FUNCTIONS
// =====================================================

func normalizeString(s string) string {
	return strings.ToLower(strings.TrimSpace(s))
}

func calculateConfidence(totalTransactions int) string {
	if totalTransactions < 10 {
		return "low"
	} else if totalTransactions < 50 {
		return "medium"
	}
	return "high"
}

func parseIntOrDefault(value string, defaultValue int) int {
	if val, err := strconv.Atoi(value); err == nil {
		return val
	}
	return defaultValue
}

// =====================================================
// HTTP HANDLERS
// =====================================================

type NetworkOperationsHandler struct {
	service *NetworkPredictionService
}

func NewNetworkOperationsHandler(service *NetworkPredictionService) *NetworkOperationsHandler {
	return &NetworkOperationsHandler{service: service}
}

// RegisterTransaction handles POST /api/v1/transactions
func (h *NetworkOperationsHandler) RegisterTransaction(c *gin.Context) {
	var req RegisterTransactionRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, ErrorResponse{
			Error:   "validation_error",
			Message: err.Error(),
		})
		return
	}

	response, err := h.service.RegisterTransaction(&req)
	if err != nil {
		c.JSON(http.StatusInternalServerError, ErrorResponse{
			Error:   "registration_failed",
			Message: err.Error(),
		})
		return
	}

	c.JSON(http.StatusCreated, response)
}

// GetPredictions handles GET /api/v1/predictions
func (h *NetworkOperationsHandler) GetPredictions(c *gin.Context) {
	var req GetPredictionsRequest
	if err := c.ShouldBindQuery(&req); err != nil {
		c.JSON(http.StatusBadRequest, ErrorResponse{
			Error:   "validation_error",
			Message: err.Error(),
		})
		return
	}

	response, err := h.service.GetPredictions(&req)
	if err != nil {
		c.JSON(http.StatusInternalServerError, ErrorResponse{
			Error:   "prediction_failed",
			Message: err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, response)
}

// GetNetworkStatus handles GET /status  (deprecated wrapper)
func (h *NetworkOperationsHandler) GetNetworkStatus(c *gin.Context) {
	timeWindow := 60
	if tw := c.Query("time_window"); tw != "" {
		if v, err := strconv.Atoi(tw); err == nil {
			timeWindow = v
		}
	}

	since := time.Now().UTC().Add(-time.Duration(timeWindow) * time.Minute)

	var records []TransactionRecord
	h.service.db.db.Where("created_at >= ?", since).Find(&records)

	// Aggregate per medium
	type stats struct{ total, ok int }
	byNetwork := map[string]*stats{}
	for _, r := range records {
		if byNetwork[r.Medium] == nil {
			byNetwork[r.Medium] = &stats{}
		}
		byNetwork[r.Medium].total++
		if r.Status == "success" {
			byNetwork[r.Medium].ok++
		}
	}

	var networks []gin.H
	overall := "healthy"
	for network, s := range byNetwork {
		rate := 0.0
		if s.total > 0 {
			rate = float64(s.ok) / float64(s.total) * 100
		}
		status := "healthy"
		if rate < 50 {
			status = "degraded"
			overall = "degraded"
		} else if rate < 80 {
			status = "warning"
		}
		networks = append(networks, gin.H{
			"network_type":            network,
			"status":                  status,
			"success_rate":            rate,
			"total_transactions":      s.total,
			"successful_transactions": s.ok,
			"failed_transactions":     s.total - s.ok,
			"last_updated":            time.Now().UTC(),
		})
	}

	c.JSON(http.StatusOK, gin.H{
		"networks":       networks,
		"overall_health": overall,
		"timestamp":      time.Now().UTC(),
	})
}

// GetNetworkTypeStatus handles GET /status/:networkType (deprecated wrapper)
func (h *NetworkOperationsHandler) GetNetworkTypeStatus(c *gin.Context) {
	networkType := c.Param("networkType")
	timeWindow := 60
	if tw := c.Query("time_window"); tw != "" {
		if v, err := strconv.Atoi(tw); err == nil {
			timeWindow = v
		}
	}

	since := time.Now().UTC().Add(-time.Duration(timeWindow) * time.Minute)

	var records []TransactionRecord
	h.service.db.db.Where("medium = ? AND created_at >= ?", strings.ToLower(networkType), since).Find(&records)

	total := len(records)
	ok := 0
	for _, r := range records {
		if r.Status == "success" {
			ok++
		}
	}
	rate := 0.0
	if total > 0 {
		rate = float64(ok) / float64(total) * 100
	}
	status := "healthy"
	if rate < 50 {
		status = "degraded"
	} else if rate < 80 {
		status = "warning"
	}
	c.JSON(http.StatusOK, gin.H{
		"network_type":            networkType,
		"status":                  status,
		"success_rate":            rate,
		"total_transactions":      total,
		"successful_transactions": ok,
		"failed_transactions":     total - ok,
		"last_updated":            time.Now().UTC(),
	})
}

// RecordTransactionResult handles POST /transaction/result (deprecated wrapper → delegates to RegisterTransaction)
func (h *NetworkOperationsHandler) RecordTransactionResult(c *gin.Context) {
	var body struct {
		NetworkType string  `json:"network_type"`
		Success     bool    `json:"success"`
		Amount      float64 `json:"amount"`
		AgentID     string  `json:"agent_id"`
	}
	if err := c.ShouldBindJSON(&body); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	status := "failed"
	if body.Success {
		status = "success"
	}
	req := &RegisterTransactionRequest{
		Type:    "transfer",
		Channel: "pos",
		Medium:  body.NetworkType,
		Status:  status,
	}
	if body.Amount > 0 {
		req.Amount = &body.Amount
	}
	if body.AgentID != "" {
		req.AgentID = &body.AgentID
	}
	resp, err := h.service.RegisterTransaction(req)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, resp)
}

// GetTransaction handles GET /api/v1/transactions/:id
func (h *NetworkOperationsHandler) GetTransaction(c *gin.Context) {
	id := c.Param("id")
	var record TransactionRecord
	if err := h.service.db.db.Where("id = ?", id).First(&record).Error; err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "transaction not found"})
		return
	}
	c.JSON(http.StatusOK, record)
}

// UpdateTransactionStatus handles PATCH /api/v1/transactions/:id/status
func (h *NetworkOperationsHandler) UpdateTransactionStatus(c *gin.Context) {
	id := c.Param("id")
	var body struct {
		Status string `json:"status" binding:"required"`
	}
	if err := c.ShouldBindJSON(&body); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	var record TransactionRecord
	if err := h.service.db.db.Where("id = ?", id).First(&record).Error; err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "transaction not found"})
		return
	}

	if err := h.service.db.db.Model(&TransactionRecord{}).Where("id = ?", id).Update("status", body.Status).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	if err := h.service.updateChannelStatistics(record.Type, record.Channel, record.Medium); err != nil {
		log.Printf("Warning: Failed to update statistics after status change: %v", err)
	}

	c.JSON(http.StatusOK, gin.H{"id": id, "status": body.Status})
}

// CreateSettlementBatch handles POST /api/v1/settlements/batches
func (h *NetworkOperationsHandler) CreateSettlementBatch(c *gin.Context) {
	var body struct {
		TenantID  string    `json:"tenant_id"`
		StartDate time.Time `json:"start_date"`
		EndDate   time.Time `json:"end_date"`
		Notes     string    `json:"notes"`
	}
	if err := c.ShouldBindJSON(&body); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// Aggregate transactions in the date range for this tenant
	var result struct {
		Total float64
		Count int64
	}
	h.service.db.db.Model(&TransactionRecord{}).
		Where("created_at BETWEEN ? AND ? AND status = 'success'", body.StartDate, body.EndDate).
		Select("COALESCE(SUM(amount), 0) as total, COUNT(*) as count").
		Scan(&result)

	batch := SettlementBatch{
		BatchRef:    fmt.Sprintf("BATCH-%d", time.Now().UnixMilli()),
		TenantID:    body.TenantID,
		Status:      "pending",
		TotalAmount: result.Total,
		TxnCount:    int(result.Count),
		StartDate:   body.StartDate,
		EndDate:     body.EndDate,
		Notes:       body.Notes,
	}
	if err := h.service.db.db.Create(&batch).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusCreated, batch)
}

// GetSettlementBatch handles GET /api/v1/settlements/batches/:id
func (h *NetworkOperationsHandler) GetSettlementBatch(c *gin.Context) {
	id := c.Param("id")
	var batch SettlementBatch
	if err := h.service.db.db.Where("id = ? OR batch_ref = ?", id, id).First(&batch).Error; err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "settlement batch not found"})
		return
	}
	c.JSON(http.StatusOK, batch)
}

// ProcessSettlementBatch handles POST /api/v1/settlements/batches/:id/process
func (h *NetworkOperationsHandler) ProcessSettlementBatch(c *gin.Context) {
	id := c.Param("id")
	var batch SettlementBatch
	if err := h.service.db.db.Where("id = ? OR batch_ref = ?", id, id).First(&batch).Error; err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "settlement batch not found"})
		return
	}
	if batch.Status != "pending" {
		c.JSON(http.StatusBadRequest, gin.H{"error": fmt.Sprintf("batch is already %s", batch.Status)})
		return
	}

	now := time.Now().UTC()
	h.service.db.db.Model(&batch).Updates(map[string]interface{}{
		"status":       "completed",
		"processed_at": now,
	})

	c.JSON(http.StatusOK, gin.H{
		"id":           batch.ID,
		"batch_ref":    batch.BatchRef,
		"status":       "completed",
		"total_amount": batch.TotalAmount,
		"txn_count":    batch.TxnCount,
		"processed_at": now,
	})
}

// GetAgentCashPosition handles GET /api/v1/cash-positions/agents/:agentId
func (h *NetworkOperationsHandler) GetAgentCashPosition(c *gin.Context) {
	agentID := c.Param("agentId")
	currency := c.Query("currency")
	if currency == "" {
		currency = "NGN"
	}
	var pos AgentCashPosition
	if err := h.service.db.db.Where("agent_id = ? AND currency = ?", agentID, currency).First(&pos).Error; err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "cash position not found for agent"})
		return
	}
	c.JSON(http.StatusOK, pos)
}

// InitializeAgentCashPosition handles POST /api/v1/cash-positions/agents/:agentId/initialize
func (h *NetworkOperationsHandler) InitializeAgentCashPosition(c *gin.Context) {
	agentID := c.Param("agentId")
	var body struct {
		Currency       string  `json:"currency"`
		InitialBalance float64 `json:"initial_balance"`
	}
	if err := c.ShouldBindJSON(&body); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	if body.Currency == "" {
		body.Currency = "NGN"
	}

	pos := AgentCashPosition{
		AgentID:  agentID,
		Currency: body.Currency,
		Balance:  body.InitialBalance,
	}
	result := h.service.db.db.Where(AgentCashPosition{AgentID: agentID, Currency: body.Currency}).
		FirstOrCreate(&pos)
	if result.Error != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": result.Error.Error()})
		return
	}
	c.JSON(http.StatusCreated, pos)
}

// GetCashPositionForecast handles GET /api/v1/cash-positions/forecast?days=N
func (h *NetworkOperationsHandler) GetCashPositionForecast(c *gin.Context) {
	days := 7
	if d, err := strconv.Atoi(c.Query("days")); err == nil && d > 0 {
		days = d
	}

	var positions []AgentCashPosition
	if err := h.service.db.db.Find(&positions).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	type AgentForecast struct {
		ID             string  `json:"id"`
		Name           string  `json:"name"`
		Location       string  `json:"location"`
		CurrentFloat   float64 `json:"currentFloat"`
		PredictedNeed  float64 `json:"predictedNeed"`
		Shortfall      float64 `json:"shortfall"`
		Risk           string  `json:"risk"`
		AvgDailyVolume float64 `json:"avgDailyVolume"`
		LastReplenished string `json:"lastReplenished"`
	}

	since := time.Now().AddDate(0, 0, -30)
	forecasts := make([]AgentForecast, 0, len(positions))

	for _, pos := range positions {
		// Calculate average daily volume from the last 30 days of transactions
		var result struct {
			TotalAmount float64
			TxnDays     int
		}
		h.service.db.db.Raw(`
			SELECT COALESCE(SUM(amount), 0) AS total_amount,
			       COUNT(DISTINCT DATE(created_at)) AS txn_days
			FROM transaction_records
			WHERE agent_id = ? AND status = 'success' AND created_at >= ?`,
			pos.AgentID, since,
		).Scan(&result)

		txnDays := result.TxnDays
		if txnDays == 0 {
			txnDays = 30
		}
		avgDaily := result.TotalAmount / float64(txnDays)
		predictedNeed := avgDaily * float64(days)

		shortfall := predictedNeed - pos.Balance
		if shortfall < 0 {
			shortfall = 0
		}

		var risk string
		ratio := pos.Balance / (predictedNeed + 1)
		switch {
		case ratio < 0.25:
			risk = "critical"
		case ratio < 0.5:
			risk = "high"
		case ratio < 0.75:
			risk = "medium"
		default:
			risk = "low"
		}

		lastReplenished := "N/A"
		if pos.LastTxnAt != nil {
			lastReplenished = pos.LastTxnAt.Format("Jan 2, 2006")
		}

		forecasts = append(forecasts, AgentForecast{
			ID:              pos.AgentID,
			Name:            "Agent " + pos.AgentID[:8],
			Location:        "",
			CurrentFloat:    pos.Balance,
			PredictedNeed:   predictedNeed,
			Shortfall:       shortfall,
			Risk:            risk,
			AvgDailyVolume:  avgDaily,
			LastReplenished: lastReplenished,
		})
	}

	c.JSON(http.StatusOK, gin.H{
		"agents": forecasts,
		"days":   days,
		"total":  len(forecasts),
	})
}

// GetCanaryReleases handles GET /api/v1/canary-releases
func (h *NetworkOperationsHandler) GetCanaryReleases(c *gin.Context) {
	service := c.Query("service")
	status := c.Query("status")

	var releases []CanaryRelease
	query := h.service.db.db

	if service != "" {
		query = query.Where("service = ?", service)
	}
	if status != "" {
		query = query.Where("status = ?", status)
	}

	if err := query.Order("created_at DESC").Find(&releases).Error; err != nil {
		c.JSON(http.StatusInternalServerError, ErrorResponse{
			Error:   "fetch_failed",
			Message: err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"releases": releases,
		"total":    len(releases),
	})
}

// CreateCanaryRelease handles POST /api/v1/canary-releases
func (h *NetworkOperationsHandler) CreateCanaryRelease(c *gin.Context) {
	var release CanaryRelease

	if err := c.ShouldBindJSON(&release); err != nil {
		c.JSON(http.StatusBadRequest, ErrorResponse{
			Error:   "validation_error",
			Message: err.Error(),
		})
		return
	}

	release.ID = uuid.New().String()
	release.CreatedAt = time.Now()
	release.UpdatedAt = time.Now()

	if err := h.service.db.db.Create(&release).Error; err != nil {
		c.JSON(http.StatusInternalServerError, ErrorResponse{
			Error:   "creation_failed",
			Message: err.Error(),
		})
		return
	}

	c.JSON(http.StatusCreated, release)
}

// GetABTests handles GET /api/v1/ab-tests
func (h *NetworkOperationsHandler) GetABTests(c *gin.Context) {
	status := c.Query("status")

	var tests []ABTest
	query := h.service.db.db

	if status != "" {
		query = query.Where("status = ?", status)
	}

	if err := query.Order("started_at DESC").Find(&tests).Error; err != nil {
		c.JSON(http.StatusInternalServerError, ErrorResponse{
			Error:   "fetch_failed",
			Message: err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"tests": tests,
		"total": len(tests),
	})
}

// CreateABTest handles POST /api/v1/ab-tests
func (h *NetworkOperationsHandler) CreateABTest(c *gin.Context) {
	var test ABTest

	if err := c.ShouldBindJSON(&test); err != nil {
		c.JSON(http.StatusBadRequest, ErrorResponse{
			Error:   "validation_error",
			Message: err.Error(),
		})
		return
	}

	test.ID = uuid.New().String()
	test.StartedAt = time.Now()

	if err := h.service.db.db.Create(&test).Error; err != nil {
		c.JSON(http.StatusInternalServerError, ErrorResponse{
			Error:   "creation_failed",
			Message: err.Error(),
		})
		return
	}

	c.JSON(http.StatusCreated, test)
}

// GetIncidents handles GET /api/v1/incidents
func (h *NetworkOperationsHandler) GetIncidents(c *gin.Context) {
	status := c.Query("status")
	severity := c.Query("severity")
	service := c.Query("service")
	skip := parseIntOrDefault(c.Query("skip"), 0)
	limit := parseIntOrDefault(c.Query("limit"), 50)

	var incidents []Incident
	query := h.service.db.db.Preload("Updates")

	if status != "" {
		query = query.Where("status = ?", status)
	}
	if severity != "" {
		query = query.Where("severity = ?", severity)
	}
	if service != "" {
		query = query.Where("service = ?", service)
	}

	if err := query.Order("created_at DESC").Offset(skip).Limit(limit).Find(&incidents).Error; err != nil {
		c.JSON(http.StatusInternalServerError, ErrorResponse{
			Error:   "fetch_failed",
			Message: err.Error(),
		})
		return
	}

	var total int64
	h.service.db.db.Model(&Incident{}).Count(&total)

	c.JSON(http.StatusOK, gin.H{
		"incidents": incidents,
		"total":     total,
		"skip":      skip,
		"limit":     limit,
	})
}

// CreateIncident handles POST /api/v1/incidents
func (h *NetworkOperationsHandler) CreateIncident(c *gin.Context) {
	var incident Incident

	if err := c.ShouldBindJSON(&incident); err != nil {
		c.JSON(http.StatusBadRequest, ErrorResponse{
			Error:   "validation_error",
			Message: err.Error(),
		})
		return
	}

	incident.ID = uuid.New().String()
	incident.CreatedAt = time.Now()

	if err := h.service.db.db.Create(&incident).Error; err != nil {
		c.JSON(http.StatusInternalServerError, ErrorResponse{
			Error:   "creation_failed",
			Message: err.Error(),
		})
		return
	}

	c.JSON(http.StatusCreated, incident)
}

// AddIncidentUpdate handles POST /api/v1/incidents/:id/updates
func (h *NetworkOperationsHandler) AddIncidentUpdate(c *gin.Context) {
	incidentID := c.Param("id")
	var update IncidentUpdate

	if err := c.ShouldBindJSON(&update); err != nil {
		c.JSON(http.StatusBadRequest, ErrorResponse{
			Error:   "validation_error",
			Message: err.Error(),
		})
		return
	}

	update.ID = uuid.New().String()
	update.IncidentID = incidentID
	update.Timestamp = time.Now()

	if err := h.service.db.db.Create(&update).Error; err != nil {
		c.JSON(http.StatusInternalServerError, ErrorResponse{
			Error:   "creation_failed",
			Message: err.Error(),
		})
		return
	}

	c.JSON(http.StatusCreated, update)
}

// UpdateIncident handles PATCH /api/v1/incidents/:id
func (h *NetworkOperationsHandler) UpdateIncident(c *gin.Context) {
	incidentID := c.Param("id")
	var updates map[string]interface{}

	if err := c.ShouldBindJSON(&updates); err != nil {
		c.JSON(http.StatusBadRequest, ErrorResponse{
			Error:   "validation_error",
			Message: err.Error(),
		})
		return
	}

	if err := h.service.db.db.Model(&Incident{}).Where("id = ?", incidentID).Updates(updates).Error; err != nil {
		c.JSON(http.StatusInternalServerError, ErrorResponse{
			Error:   "update_failed",
			Message: err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{"message": "incident updated"})
}

// HandleIncidentOptions handles OPTIONS /api/v1/incidents for CORS preflight
func (h *NetworkOperationsHandler) HandleIncidentOptions(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{})
}

// HealthCheck handles GET /health
func (h *NetworkOperationsHandler) HealthCheck(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"status":    "healthy",
		"service":   "network-operations",
		"timestamp": time.Now().UTC(),
	})
}

// =====================================================
// MAIN FUNCTION
// =====================================================

func main() {
	// Load configuration
	config := loadConfig()

	// Initialize database
	db, err := NewDatabaseService(config)
	if err != nil {
		log.Fatalf("Failed to initialize database: %v", err)
	}

	// Initialize service
	predictionService := NewNetworkPredictionService(db)

	// Initialize handler
	handler := NewNetworkOperationsHandler(predictionService)

	// Initialize Gin router
	router := gin.Default()

	// Configure CORS
	corsConfig := cors.DefaultConfig()
	corsConfig.AllowAllOrigins = true
	corsConfig.AllowMethods = []string{"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"}
	corsConfig.AllowHeaders = []string{"Origin", "Content-Type", "Accept", "Authorization", "X-Requested-With"}
	router.Use(cors.New(corsConfig))

	// Health check endpoint
	router.GET("/health", handler.HealthCheck)

	// Deprecated legacy endpoints (still called by some frontend pages)
	router.GET("/status", handler.GetNetworkStatus)
	router.GET("/status/:networkType", handler.GetNetworkTypeStatus)
	router.POST("/transaction/result", handler.RecordTransactionResult)

	// Network telemetry routes
	network := router.Group("/api/network")
	{
		network.GET("/telemetry", handler.GetNetworkTelemetry)
	}

	// API routes
	v1 := router.Group("/api/v1")
	{
		// Transactions
		v1.POST("/transactions", handler.RegisterTransaction)
		v1.GET("/transactions/:id", handler.GetTransaction)
		v1.PATCH("/transactions/:id/status", handler.UpdateTransactionStatus)

		// Predictions
		v1.GET("/predictions", handler.GetPredictions)

		// Settlements
		v1.POST("/settlements/batches", handler.CreateSettlementBatch)
		v1.GET("/settlements/batches/:id", handler.GetSettlementBatch)
		v1.POST("/settlements/batches/:id/process", handler.ProcessSettlementBatch)

		// Agent cash positions
		v1.GET("/cash-positions/forecast", handler.GetCashPositionForecast)
		v1.GET("/cash-positions/agents/:agentId", handler.GetAgentCashPosition)
		v1.POST("/cash-positions/agents/:agentId/initialize", handler.InitializeAgentCashPosition)

		// Canary Releases
		v1.GET("/canary-releases", handler.GetCanaryReleases)
		v1.POST("/canary-releases", handler.CreateCanaryRelease)

		// A/B Tests
		v1.GET("/ab-tests", handler.GetABTests)
		v1.POST("/ab-tests", handler.CreateABTest)

		// Incidents
		v1.GET("/incidents", handler.GetIncidents)
		v1.OPTIONS("/incidents", handler.HandleIncidentOptions)
		v1.POST("/incidents", handler.CreateIncident)
		v1.POST("/incidents/:id/updates", handler.AddIncidentUpdate)
		v1.PATCH("/incidents/:id", handler.UpdateIncident)

		// Chaos Engineering
		v1.GET("/chaos/experiments", handler.GetChaosExperiments)
		v1.POST("/chaos/experiments/:id/run", handler.RunChaosExperiment)

		// Load Tests
		v1.GET("/load-tests", handler.GetLoadTests)
		v1.POST("/load-tests", handler.CreateLoadTest)

		// Cache
		v1.GET("/cache", handler.GetCache)
		v1.GET("/cache/lookup", handler.CacheLookup)
		v1.DELETE("/cache/:ns/flush", handler.FlushCache)

		// Retry Queue
		v1.GET("/retry-queue", handler.GetRetryQueue)
		v1.DELETE("/retry-queue/:id", handler.CancelRetryItem)

		// SIM Orchestrator
		v1.GET("/sims", handler.GetSIMs)
		v1.POST("/sims/:id/:action", handler.SIMAction)

		// Service Mesh
		v1.GET("/mesh/services", handler.GetMeshServices)

		// Database Schema
		v1.GET("/schema", handler.GetSchema)

		// MQTT
		v1.GET("/mqtt/stats", handler.GetMQTTStats)

		// OpenTelemetry
		v1.GET("/otel-config", handler.GetOtelConfig)
		v1.POST("/otel-config/exporters/:name/test", handler.TestOtelExporter)

		// Connection Pools
		v1.GET("/connection-pools", handler.GetConnectionPools)

		// Connection Quality
		v1.GET("/connection-quality", handler.GetConnectionQuality)

		// Carriers
		v1.GET("/carriers", handler.GetCarriers)

		// Archival
		v1.GET("/archival", handler.GetArchival)
		v1.POST("/archival/:entityType/run", handler.RunArchivalJob)

		// Billers
		v1.GET("/billers", handler.GetBillers)
		v1.GET("/billers/:category", handler.GetBillersByCategory)

		// Airtime/Data providers
		v1.GET("/providers", handler.GetProviders)
	}

	// Start server
	srv := &http.Server{
		Addr:    ":" + config.Port,
		Handler: router,
	}

	// Graceful shutdown
	go func() {
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("Failed to start server: %v", err)
		}
	}()

	log.Printf("🚀 Network Operations Service started on port %s", config.Port)
	log.Printf("📊 Endpoints:")
	log.Printf("   POST /api/v1/transactions - Register transaction")
	log.Printf("   GET  /api/v1/predictions - Get channel predictions")
	log.Printf("   GET  /health - Health check")

	// Wait for interrupt signal to gracefully shutdown the server
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit
	log.Println("Shutting down server...")

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	if err := srv.Shutdown(ctx); err != nil {
		log.Fatal("Server forced to shutdown:", err)
	}

	log.Println("Server exited")
}
