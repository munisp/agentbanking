package main

import (
	"bytes"
	"context"
	"database/sql/driver"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"syscall"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"gorm.io/driver/postgres"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"
)

// Commission represents a commission record
type Commission struct {
	ID               uuid.UUID        `json:"id" gorm:"type:uuid;primary_key;default:gen_random_uuid()"`
	AgentID          uuid.UUID        `json:"agent_id" gorm:"not null;index;uniqueIndex:idx_commission_agent_ref"`
	TransactionID    uuid.UUID        `json:"transaction_id" gorm:"not null;index"`
	TransactionRef   string           `json:"transaction_ref" gorm:"not null;uniqueIndex:idx_commission_agent_ref"`
	TransactionType  string           `json:"transaction_type" gorm:"not null"`
	Amount           float64          `json:"amount" gorm:"not null"`
	Rate             float64          `json:"rate" gorm:"not null"`
	CommissionAmount float64          `json:"commission_amount" gorm:"not null"`
	Currency         string           `json:"currency" gorm:"default:'USD'"`
	Status           CommissionStatus `json:"status" gorm:"default:'pending'"`
	SettlementID     *uuid.UUID       `json:"settlement_id" gorm:"index"`
	EarnedAt         time.Time        `json:"earned_at" gorm:"not null"`
	SettledAt        *time.Time       `json:"settled_at"`
	Metadata         JSON             `json:"metadata" gorm:"type:jsonb"`
	CreatedAt        time.Time        `json:"created_at"`
	UpdatedAt        time.Time        `json:"updated_at"`
}

// CommissionStatus represents the status of a commission
type CommissionStatus string

const (
	CommissionStatusPending   CommissionStatus = "pending"
	CommissionStatusSettled   CommissionStatus = "settled"
	CommissionStatusCancelled CommissionStatus = "cancelled"
	CommissionStatusDisputed  CommissionStatus = "disputed"
)

// Settlement represents a commission settlement batch
type Settlement struct {
	ID              uuid.UUID        `json:"id" gorm:"type:uuid;primary_key;default:gen_random_uuid()"`
	SettlementRef   string           `json:"settlement_ref" gorm:"uniqueIndex;not null"`
	AgentID         uuid.UUID        `json:"agent_id" gorm:"not null;index"`
	TotalAmount     float64          `json:"total_amount" gorm:"not null"`
	CommissionCount int              `json:"commission_count" gorm:"not null"`
	Currency        string           `json:"currency" gorm:"default:'USD'"`
	Status          SettlementStatus `json:"status" gorm:"default:'pending'"`
	PaymentMethod   string           `json:"payment_method" gorm:"not null"`
	PaymentDetails  JSON             `json:"payment_details" gorm:"type:jsonb"`
	ProcessedAt     *time.Time       `json:"processed_at"`
	FailureReason   string           `json:"failure_reason"`
	StartDate       time.Time        `json:"start_date" gorm:"not null"`
	EndDate         time.Time        `json:"end_date" gorm:"not null"`
	CreatedAt       time.Time        `json:"created_at"`
	UpdatedAt       time.Time        `json:"updated_at"`
	Commissions     []Commission     `json:"commissions" gorm:"foreignKey:SettlementID"`
}

// SettlementStatus represents the status of a settlement
type SettlementStatus string

const (
	SettlementStatusPending    SettlementStatus = "pending"
	SettlementStatusProcessing SettlementStatus = "processing"
	SettlementStatusCompleted  SettlementStatus = "completed"
	SettlementStatusFailed     SettlementStatus = "failed"
	SettlementStatusCancelled  SettlementStatus = "cancelled"
)

// CommissionRule represents commission calculation rules
type CommissionRule struct {
	ID              uuid.UUID  `json:"id" gorm:"type:uuid;primary_key;default:gen_random_uuid()"`
	AgentTier       string     `json:"agent_tier" gorm:"not null"`
	TransactionType string     `json:"transaction_type" gorm:"not null"`
	MinAmount       float64    `json:"min_amount" gorm:"default:0"`
	MaxAmount       float64    `json:"max_amount" gorm:"default:999999999"`
	Rate            float64    `json:"rate" gorm:"not null"`
	FlatFee         float64    `json:"flat_fee" gorm:"default:0"`
	IsActive        bool       `json:"is_active" gorm:"default:true"`
	EffectiveFrom   time.Time  `json:"effective_from" gorm:"not null"`
	EffectiveTo     *time.Time `json:"effective_to"`
	CreatedAt       time.Time  `json:"created_at"`
	UpdatedAt       time.Time  `json:"updated_at"`
}

// AgentBalance represents agent's commission balance
type AgentBalance struct {
	ID               uuid.UUID  `json:"id" gorm:"type:uuid;primary_key;default:gen_random_uuid()"`
	AgentID          uuid.UUID  `json:"agent_id" gorm:"uniqueIndex;not null"`
	PendingBalance   float64    `json:"pending_balance" gorm:"default:0"`
	AvailableBalance float64    `json:"available_balance" gorm:"default:0"`
	SettledBalance   float64    `json:"settled_balance" gorm:"default:0"`
	TotalEarned      float64    `json:"total_earned" gorm:"default:0"`
	Currency         string     `json:"currency" gorm:"default:'USD'"`
	LastSettlementAt *time.Time `json:"last_settlement_at"`
	CreatedAt        time.Time  `json:"created_at"`
	UpdatedAt        time.Time  `json:"updated_at"`
}

// JSON type for JSONB fields
type JSON map[string]interface{}

// Scan implements sql.Scanner interface for GORM to convert JSONB to JSON type
func (j *JSON) Scan(value interface{}) error {
	if value == nil {
		*j = JSON{}
		return nil
	}

	var bytes []byte

	switch v := value.(type) {
	case []byte:
		bytes = v
	case string:
		bytes = []byte(v)
	default:
		return fmt.Errorf("unsupported Scan type for JSON: %T", value)
	}

	result := make(map[string]interface{})
	if len(bytes) == 0 {
		*j = JSON{}
		return nil
	}

	if err := json.Unmarshal(bytes, &result); err != nil {
		return err
	}

	*j = JSON(result)
	return nil
}

// Value implements driver.Valuer interface for GORM to convert JSON type to JSONB
func (j JSON) Value() (driver.Value, error) {
	if j == nil {
		return []byte("{}"), nil
	}
	return json.Marshal(j)
}

// CreateCommissionRequest represents the request to create a new commission
type CreateCommissionRequest struct {
	AgentID         uuid.UUID `json:"agent_id" binding:"required"`
	TransactionID   uuid.UUID `json:"transaction_id" binding:"required"`
	TransactionRef  string    `json:"transaction_ref" binding:"required"`
	TransactionType string    `json:"transaction_type" binding:"required"`
	Amount          float64   `json:"amount" binding:"required,gt=0"`
	Currency        string    `json:"currency"`
	EarnedAt        time.Time `json:"earned_at"`
	Metadata        JSON      `json:"metadata"`
}

// CreateSettlementRequest represents the request to create a settlement
type CreateSettlementRequest struct {
	AgentID        uuid.UUID `json:"agent_id" binding:"required"`
	PaymentMethod  string    `json:"payment_method" binding:"required"`
	PaymentDetails JSON      `json:"payment_details" binding:"required"`
	StartDate      time.Time `json:"start_date" binding:"required"`
	EndDate        time.Time `json:"end_date" binding:"required"`
	AutoProcess    bool      `json:"auto_process"`
}

// UpdateSettlementRequest represents the request to update a settlement
type UpdateSettlementRequest struct {
	Status        SettlementStatus `json:"status"`
	FailureReason string           `json:"failure_reason"`
}

// CreateCommissionRuleRequest represents the request to create a commission rule
type CreateCommissionRuleRequest struct {
	AgentTier       string     `json:"agent_tier" binding:"required"`
	TransactionType string     `json:"transaction_type" binding:"required"`
	MinAmount       float64    `json:"min_amount"`
	MaxAmount       float64    `json:"max_amount"`
	Rate            float64    `json:"rate" binding:"required,gt=0"`
	FlatFee         float64    `json:"flat_fee"`
	IsActive        *bool      `json:"is_active"`
	EffectiveFrom   time.Time  `json:"effective_from" binding:"required"`
	EffectiveTo     *time.Time `json:"effective_to"`
}

// UpdateCommissionRuleRequest represents the request to update a commission rule
type UpdateCommissionRuleRequest struct {
	AgentTier       string     `json:"agent_tier"`
	TransactionType string     `json:"transaction_type"`
	MinAmount       *float64   `json:"min_amount"`
	MaxAmount       *float64   `json:"max_amount"`
	Rate            *float64   `json:"rate"`
	FlatFee         *float64   `json:"flat_fee"`
	IsActive        *bool      `json:"is_active"`
	EffectiveFrom   *time.Time `json:"effective_from"`
	EffectiveTo     *time.Time `json:"effective_to"`
}

// CommissionService handles commission-related operations
type CommissionService struct {
	db *gorm.DB
}

// NewCommissionService creates a new commission service
func NewCommissionService(db *gorm.DB) *CommissionService {
	return &CommissionService{db: db}
}

// CreateCommission creates a new commission record
func (s *CommissionService) CreateCommission(req CreateCommissionRequest) (*Commission, error) {
	// Set default currency
	if req.Currency == "" {
		req.Currency = "USD"
	}

	// Set default earned time
	if req.EarnedAt.IsZero() {
		req.EarnedAt = time.Now()
	}

	// Calculate commission amount based on rules
	rate, err := s.getCommissionRate(req.AgentID, req.TransactionType, req.Amount)
	if err != nil {
		return nil, fmt.Errorf("failed to get commission rate: %w", err)
	}

	commissionAmount := req.Amount * rate

	commission := &Commission{
		AgentID:          req.AgentID,
		TransactionID:    req.TransactionID,
		TransactionRef:   req.TransactionRef,
		TransactionType:  req.TransactionType,
		Amount:           req.Amount,
		Rate:             rate,
		CommissionAmount: commissionAmount,
		Currency:         req.Currency,
		Status:           CommissionStatusPending,
		EarnedAt:         req.EarnedAt,
		Metadata:         req.Metadata,
	}

	if err := s.db.Create(commission).Error; err != nil {
		return nil, fmt.Errorf("failed to create commission: %w", err)
	}

	// Update agent balance
	s.updateAgentBalance(req.AgentID, commissionAmount, "pending")

	return commission, nil
}

// GetCommission retrieves a commission by ID
func (s *CommissionService) GetCommission(id uuid.UUID) (*Commission, error) {
	var commission Commission
	if err := s.db.First(&commission, "id = ?", id).Error; err != nil {
		return nil, fmt.Errorf("failed to get commission: %w", err)
	}
	return &commission, nil
}

// ListCommissions retrieves a list of commissions with pagination and filters
func (s *CommissionService) ListCommissions(page, limit int, agentID *uuid.UUID, status CommissionStatus, startDate, endDate *time.Time) ([]Commission, int64, error) {
	var commissions []Commission
	var total int64

	query := s.db.Model(&Commission{})

	// Apply filters
	if agentID != nil {
		query = query.Where("agent_id = ?", *agentID)
	}
	if status != "" {
		query = query.Where("status = ?", status)
	}
	if startDate != nil {
		query = query.Where("earned_at >= ?", *startDate)
	}
	if endDate != nil {
		query = query.Where("earned_at <= ?", *endDate)
	}

	if err := query.Count(&total).Error; err != nil {
		return nil, 0, fmt.Errorf("failed to count commissions: %w", err)
	}

	offset := (page - 1) * limit
	if err := query.Order("earned_at DESC").Offset(offset).Limit(limit).Find(&commissions).Error; err != nil {
		return nil, 0, fmt.Errorf("failed to list commissions: %w", err)
	}

	return commissions, total, nil
}

// CreateSettlement creates a new settlement for an agent
func (s *CommissionService) CreateSettlement(req CreateSettlementRequest) (*Settlement, error) {
	// Begin the transaction first — FOR UPDATE SKIP LOCKED must execute inside a transaction
	// to prevent concurrent settlement runs from double-settling the same commissions.
	tx := s.db.Begin()
	if tx.Error != nil {
		return nil, fmt.Errorf("failed to begin transaction: %w", tx.Error)
	}

	// FOR UPDATE SKIP LOCKED: rows already locked by another concurrent runner are skipped,
	// eliminating double-settlement races without blocking the caller.
	var commissions []Commission
	if err := tx.Raw(
		`SELECT * FROM commissions
		 WHERE agent_id = ? AND status = ? AND earned_at >= ? AND earned_at <= ?
		 FOR UPDATE SKIP LOCKED`,
		req.AgentID, CommissionStatusPending, req.StartDate, req.EndDate,
	).Scan(&commissions).Error; err != nil {
		tx.Rollback()
		return nil, fmt.Errorf("failed to get pending commissions: %w", err)
	}

	if len(commissions) == 0 {
		tx.Rollback()
		return nil, fmt.Errorf("no pending commissions found for the specified period")
	}

	// Calculate total amount
	var totalAmount float64
	for _, commission := range commissions {
		totalAmount += commission.CommissionAmount
	}

	// Generate settlement reference
	settlementRef := generateSettlementRef()

	settlement := &Settlement{
		SettlementRef:   settlementRef,
		AgentID:         req.AgentID,
		TotalAmount:     totalAmount,
		CommissionCount: len(commissions),
		Currency:        commissions[0].Currency,
		Status:          SettlementStatusPending,
		PaymentMethod:   req.PaymentMethod,
		PaymentDetails:  req.PaymentDetails,
		StartDate:       req.StartDate,
		EndDate:         req.EndDate,
	}

	// Create settlement
	if err := tx.Create(settlement).Error; err != nil {
		tx.Rollback()
		return nil, fmt.Errorf("failed to create settlement: %w", err)
	}

	// Update commissions with settlement ID
	if err := tx.Model(&Commission{}).Where("agent_id = ? AND status = ? AND earned_at >= ? AND earned_at <= ?",
		req.AgentID, CommissionStatusPending, req.StartDate, req.EndDate).
		Updates(map[string]interface{}{
			"settlement_id": settlement.ID,
			"status":        CommissionStatusSettled,
			"settled_at":    time.Now(),
		}).Error; err != nil {
		tx.Rollback()
		return nil, fmt.Errorf("failed to update commissions: %w", err)
	}

	// Update agent balance (pending → available, awaiting final processing)
	s.updateAgentBalanceInTx(tx, req.AgentID, totalAmount, "settled")

	if err := tx.Commit().Error; err != nil {
		return nil, fmt.Errorf("failed to commit settlement transaction: %w", err)
	}

	// Auto-process immediately if requested (e.g. agent-initiated withdrawal)
	if req.AutoProcess {
		if err := s.ProcessSettlement(settlement.ID); err != nil {
			log.Printf("Warning: auto-process failed for settlement %s: %v", settlement.ID, err)
		} else {
			// Re-fetch to return the updated status
			_ = s.db.First(settlement, "id = ?", settlement.ID)
		}
	}

	return settlement, nil
}

// GetSettlement retrieves a settlement by ID
func (s *CommissionService) GetSettlement(id uuid.UUID) (*Settlement, error) {
	var settlement Settlement
	if err := s.db.Preload("Commissions").First(&settlement, "id = ?", id).Error; err != nil {
		return nil, fmt.Errorf("failed to get settlement: %w", err)
	}
	return &settlement, nil
}

// ListSettlements retrieves a list of settlements with pagination and filters
func (s *CommissionService) ListSettlements(page, limit int, agentID *uuid.UUID, status SettlementStatus, startDate, endDate *time.Time) ([]Settlement, int64, error) {
	var settlements []Settlement
	var total int64

	query := s.db.Model(&Settlement{})

	// Apply filters
	if agentID != nil {
		query = query.Where("agent_id = ?", *agentID)
	}
	if status != "" {
		query = query.Where("status = ?", status)
	}
	if startDate != nil {
		query = query.Where("created_at >= ?", *startDate)
	}
	if endDate != nil {
		query = query.Where("created_at <= ?", *endDate)
	}

	if err := query.Count(&total).Error; err != nil {
		return nil, 0, fmt.Errorf("failed to count settlements: %w", err)
	}

	offset := (page - 1) * limit
	if err := query.Order("created_at DESC").Offset(offset).Limit(limit).Find(&settlements).Error; err != nil {
		return nil, 0, fmt.Errorf("failed to list settlements: %w", err)
	}

	return settlements, total, nil
}

// UpdateSettlement updates a settlement
func (s *CommissionService) UpdateSettlement(id uuid.UUID, req UpdateSettlementRequest) (*Settlement, error) {
	var settlement Settlement
	if err := s.db.First(&settlement, "id = ?", id).Error; err != nil {
		return nil, fmt.Errorf("failed to find settlement: %w", err)
	}

	// Update fields if provided
	if req.Status != "" {
		settlement.Status = req.Status
		if req.Status == SettlementStatusCompleted {
			now := time.Now()
			settlement.ProcessedAt = &now
		}
	}
	if req.FailureReason != "" {
		settlement.FailureReason = req.FailureReason
	}

	if err := s.db.Save(&settlement).Error; err != nil {
		return nil, fmt.Errorf("failed to update settlement: %w", err)
	}

	return &settlement, nil
}

// GetAgentBalance retrieves agent's commission balance
func (s *CommissionService) GetAgentBalance(agentID uuid.UUID) (*AgentBalance, error) {
	var balance AgentBalance
	if err := s.db.Where("agent_id = ?", agentID).First(&balance).Error; err != nil {
		if err == gorm.ErrRecordNotFound {
			// Create new balance record
			balance = AgentBalance{
				AgentID:  agentID,
				Currency: "USD",
			}
			if err := s.db.Create(&balance).Error; err != nil {
				return nil, fmt.Errorf("failed to create agent balance: %w", err)
			}
		} else {
			return nil, fmt.Errorf("failed to get agent balance: %w", err)
		}
	}
	return &balance, nil
}

// ListAgentBalances returns all agent balances for the admin overview
func (s *CommissionService) ListAgentBalances(page, limit int) ([]AgentBalance, int64, error) {
	var balances []AgentBalance
	var total int64
	if err := s.db.Model(&AgentBalance{}).Count(&total).Error; err != nil {
		return nil, 0, fmt.Errorf("failed to count balances: %w", err)
	}
	offset := (page - 1) * limit
	if err := s.db.Order("total_earned DESC").Offset(offset).Limit(limit).Find(&balances).Error; err != nil {
		return nil, 0, fmt.Errorf("failed to list balances: %w", err)
	}
	return balances, total, nil
}

// ListCommissionRules returns all commission rules
func (s *CommissionService) ListCommissionRules(activeOnly bool) ([]CommissionRule, error) {
	var rules []CommissionRule
	q := s.db.Order("effective_from DESC")
	if activeOnly {
		q = q.Where("is_active = true")
	}
	if err := q.Find(&rules).Error; err != nil {
		return nil, fmt.Errorf("failed to list rules: %w", err)
	}
	return rules, nil
}

// GetCommissionRule retrieves a single rule by ID
func (s *CommissionService) GetCommissionRule(id uuid.UUID) (*CommissionRule, error) {
	var rule CommissionRule
	if err := s.db.First(&rule, "id = ?", id).Error; err != nil {
		return nil, fmt.Errorf("rule not found: %w", err)
	}
	return &rule, nil
}

// CreateCommissionRule creates a new commission rule
func (s *CommissionService) CreateCommissionRule(req CreateCommissionRuleRequest) (*CommissionRule, error) {
	active := true
	if req.IsActive != nil {
		active = *req.IsActive
	}
	maxAmt := req.MaxAmount
	if maxAmt == 0 {
		maxAmt = 999999999
	}
	rule := &CommissionRule{
		AgentTier:       req.AgentTier,
		TransactionType: req.TransactionType,
		MinAmount:       req.MinAmount,
		MaxAmount:       maxAmt,
		Rate:            req.Rate,
		FlatFee:         req.FlatFee,
		IsActive:        active,
		EffectiveFrom:   req.EffectiveFrom,
		EffectiveTo:     req.EffectiveTo,
	}
	if err := s.db.Create(rule).Error; err != nil {
		return nil, fmt.Errorf("failed to create rule: %w", err)
	}
	return rule, nil
}

// UpdateCommissionRule updates an existing commission rule
func (s *CommissionService) UpdateCommissionRule(id uuid.UUID, req UpdateCommissionRuleRequest) (*CommissionRule, error) {
	var rule CommissionRule
	if err := s.db.First(&rule, "id = ?", id).Error; err != nil {
		return nil, fmt.Errorf("rule not found: %w", err)
	}
	if req.AgentTier != "" {
		rule.AgentTier = req.AgentTier
	}
	if req.TransactionType != "" {
		rule.TransactionType = req.TransactionType
	}
	if req.MinAmount != nil {
		rule.MinAmount = *req.MinAmount
	}
	if req.MaxAmount != nil {
		rule.MaxAmount = *req.MaxAmount
	}
	if req.Rate != nil {
		rule.Rate = *req.Rate
	}
	if req.FlatFee != nil {
		rule.FlatFee = *req.FlatFee
	}
	if req.IsActive != nil {
		rule.IsActive = *req.IsActive
	}
	if req.EffectiveFrom != nil {
		rule.EffectiveFrom = *req.EffectiveFrom
	}
	if req.EffectiveTo != nil {
		rule.EffectiveTo = req.EffectiveTo
	}
	if err := s.db.Save(&rule).Error; err != nil {
		return nil, fmt.Errorf("failed to update rule: %w", err)
	}
	return &rule, nil
}

// DeleteCommissionRule soft-deletes a rule by setting is_active = false
func (s *CommissionService) DeleteCommissionRule(id uuid.UUID) error {
	result := s.db.Model(&CommissionRule{}).Where("id = ?", id).Update("is_active", false)
	if result.Error != nil {
		return fmt.Errorf("failed to deactivate rule: %w", result.Error)
	}
	if result.RowsAffected == 0 {
		return fmt.Errorf("rule not found")
	}
	return nil
}

// ProcessSettlement processes a pending settlement with real payment integration
func (s *CommissionService) ProcessSettlement(id uuid.UUID) error {
	var settlement Settlement
	if err := s.db.First(&settlement, "id = ?", id).Error; err != nil {
		return fmt.Errorf("failed to find settlement: %w", err)
	}

	if settlement.Status != SettlementStatusPending {
		return fmt.Errorf("settlement is not in pending status")
	}

	// Update status to processing
	settlement.Status = SettlementStatusProcessing
	if err := s.db.Save(&settlement).Error; err != nil {
		return fmt.Errorf("failed to update settlement status: %w", err)
	}

	// Process payment synchronously for reliability
	paymentResult, err := s.processPayment(settlement)
	if err != nil {
		settlement.Status = SettlementStatusFailed
		settlement.FailureReason = err.Error()
		s.db.Save(&settlement)
		return fmt.Errorf("payment processing failed: %w", err)
	}

	// Update settlement with payment result
	now := time.Now()
	settlement.Status = SettlementStatusCompleted
	settlement.ProcessedAt = &now
	if settlement.PaymentDetails == nil {
		settlement.PaymentDetails = make(JSON)
	}
	settlement.PaymentDetails["payment_reference"] = paymentResult.Reference
	settlement.PaymentDetails["payment_provider"] = paymentResult.Provider
	settlement.PaymentDetails["processed_at"] = now.Format(time.RFC3339)

	if err := s.db.Save(&settlement).Error; err != nil {
		return fmt.Errorf("failed to update settlement: %w", err)
	}

	// Update agent balance
	s.updateAgentBalance(settlement.AgentID, settlement.TotalAmount, "completed")

	// Publish settlement completed event
	s.publishSettlementEvent(settlement, "settlement.completed")

	return nil
}

// PaymentResult represents the result of a payment processing
type PaymentResult struct {
	Reference string
	Provider  string
	Status    string
}

// processPayment routes to payment-processing-service for actual fund movement
func (s *CommissionService) processPayment(settlement Settlement) (*PaymentResult, error) {
	paymentRef := fmt.Sprintf("STL-%s-%d", settlement.PaymentMethod[:3], time.Now().Unix())

	if err := s.callPaymentServicePayout(settlement); err != nil {
		log.Printf("CRITICAL: payout_service_failed settlement=%s amount=%.2f currency=%s error=%v — settlement will NOT be marked completed",
			settlement.ID, settlement.TotalAmount, settlement.Currency, err)
		return nil, fmt.Errorf("payout to payment service failed: %w", err)
	}

	log.Printf("Settlement payout dispatched: settlement=%s amount=%.2f currency=%s method=%s ref=%s",
		settlement.ID, settlement.TotalAmount, settlement.Currency, settlement.PaymentMethod, paymentRef)

	return &PaymentResult{
		Reference: paymentRef,
		Provider:  settlement.PaymentMethod,
		Status:    "completed",
	}, nil
}

// publishSettlementEvent publishes settlement events for downstream processing
func (s *CommissionService) publishSettlementEvent(settlement Settlement, eventType string) {
	event := map[string]interface{}{
		"event_type":     eventType,
		"settlement_id":  settlement.ID,
		"agent_id":       settlement.AgentID,
		"amount":         settlement.TotalAmount,
		"currency":       settlement.Currency,
		"processed_at":   settlement.ProcessedAt,
		"payment_method": settlement.PaymentMethod,
	}

	eventJSON, _ := json.Marshal(event)
	log.Printf("Settlement event: %s", string(eventJSON))
}

// AgentInfo represents agent information for commission calculation
type AgentInfo struct {
	ID        uuid.UUID `json:"id"`
	Tier      string    `json:"tier"`
	Territory string    `json:"territory_id"`
}

// getAgentInfo retrieves agent information from the agent service
func (s *CommissionService) getAgentInfo(agentID uuid.UUID) (*AgentInfo, error) {
	agentServiceURL := os.Getenv("AGENT_SERVICE_URL")
	if agentServiceURL == "" {
		agentServiceURL = "http://agent-hierarchy-service:8080"
	}

	url := fmt.Sprintf("%s/api/v1/agents/%s", agentServiceURL, agentID)

	client := &http.Client{Timeout: 5 * time.Second}
	resp, err := client.Get(url)
	if err != nil {
		log.Printf("Failed to fetch agent info from service: %v, using fallback", err)
		return s.getAgentInfoFromDB(agentID)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		log.Printf("Agent service returned status %d, using fallback", resp.StatusCode)
		return s.getAgentInfoFromDB(agentID)
	}

	var agentInfo AgentInfo
	if err := json.NewDecoder(resp.Body).Decode(&agentInfo); err != nil {
		log.Printf("Failed to decode agent info: %v, using fallback", err)
		return s.getAgentInfoFromDB(agentID)
	}

	return &agentInfo, nil
}

// getAgentInfoFromDB retrieves agent information directly from database as fallback
func (s *CommissionService) getAgentInfoFromDB(agentID uuid.UUID) (*AgentInfo, error) {
	var result struct {
		ID        uuid.UUID `gorm:"column:id"`
		Tier      string    `gorm:"column:tier"`
		Territory string    `gorm:"column:territory_id"`
	}

	// Try to find agent in different tables based on tier structure
	tables := []string{"agents", "super_agents", "sub_agents", "master_agents"}

	for _, table := range tables {
		query := fmt.Sprintf("SELECT id, tier, territory_id FROM %s WHERE id = ?", table)
		if err := s.db.Raw(query, agentID).Scan(&result).Error; err == nil && result.ID != uuid.Nil {
			return &AgentInfo{
				ID:        result.ID,
				Tier:      result.Tier,
				Territory: result.Territory,
			}, nil
		}
	}

	// Default fallback if agent not found
	log.Printf("Agent %s not found in any table, using default tier", agentID)
	return &AgentInfo{
		ID:   agentID,
		Tier: "agent",
	}, nil
}

// getCommissionRate gets the commission rate for an agent and transaction type
func (s *CommissionService) getCommissionRate(agentID uuid.UUID, transactionType string, amount float64) (float64, error) {
	// Get real agent tier from agent service
	agentInfo, err := s.getAgentInfo(agentID)
	if err != nil {
		log.Printf("Failed to get agent info: %v, using default tier", err)
		agentInfo = &AgentInfo{ID: agentID, Tier: "agent"}
	}

	agentTier := agentInfo.Tier

	var rule CommissionRule
	if err := s.db.Where("agent_tier = ? AND transaction_type = ? AND min_amount <= ? AND max_amount >= ? AND is_active = true AND effective_from <= ? AND (effective_to IS NULL OR effective_to >= ?)",
		agentTier, transactionType, amount, amount, time.Now(), time.Now()).
		Order("effective_from DESC").First(&rule).Error; err != nil {
		if err == gorm.ErrRecordNotFound {
			// Try with wildcard tier
			if err := s.db.Where("(agent_tier IS NULL OR agent_tier = '') AND transaction_type = ? AND min_amount <= ? AND max_amount >= ? AND is_active = true AND effective_from <= ? AND (effective_to IS NULL OR effective_to >= ?)",
				transactionType, amount, amount, time.Now(), time.Now()).
				Order("effective_from DESC").First(&rule).Error; err != nil {
				// Return default rate if no rule found
				return getDefaultCommissionRate(transactionType), nil
			}
		} else {
			return 0, fmt.Errorf("failed to get commission rule: %w", err)
		}
	}

	return rule.Rate, nil
}

// updateAgentBalance updates agent's balance
func (s *CommissionService) updateAgentBalance(agentID uuid.UUID, amount float64, balanceType string) {
	s.updateAgentBalanceInTx(s.db, agentID, amount, balanceType)
}

// updateAgentBalanceInTx updates agent's balance within a transaction
func (s *CommissionService) updateAgentBalanceInTx(tx *gorm.DB, agentID uuid.UUID, amount float64, balanceType string) {
	var balance AgentBalance
	if err := tx.Where("agent_id = ?", agentID).First(&balance).Error; err != nil {
		if err == gorm.ErrRecordNotFound {
			balance = AgentBalance{
				AgentID:  agentID,
				Currency: "USD",
			}
			tx.Create(&balance)
		}
	}

	updates := map[string]interface{}{}

	switch balanceType {
	case "pending":
		updates["pending_balance"] = gorm.Expr("pending_balance + ?", amount)
		updates["total_earned"] = gorm.Expr("total_earned + ?", amount)
	case "settled":
		updates["pending_balance"] = gorm.Expr("pending_balance - ?", amount)
		updates["available_balance"] = gorm.Expr("available_balance + ?", amount)
	case "completed":
		updates["available_balance"] = gorm.Expr("available_balance - ?", amount)
		updates["settled_balance"] = gorm.Expr("settled_balance + ?", amount)
		updates["last_settlement_at"] = time.Now()
	}

	tx.Model(&AgentBalance{}).Where("agent_id = ?", agentID).Updates(updates)
}

// getDefaultCommissionRate returns default commission rate for transaction type
func getDefaultCommissionRate(transactionType string) float64 {
	switch transactionType {
	case "deposit":
		return 0.001 // 0.1%
	case "withdrawal":
		return 0.002 // 0.2%
	case "transfer":
		return 0.0015 // 0.15%
	case "bill_payment":
		return 0.005 // 0.5%
	case "airtime", "data":
		return 0.03 // 3%
	default:
		return 0.002 // 0.2%
	}
}

// generateSettlementRef generates a unique settlement reference
func generateSettlementRef() string {
	return fmt.Sprintf("STL%d%s", time.Now().Unix(), uuid.New().String()[:8])
}

// SettlementPolicy controls platform-wide settlement behaviour
type SettlementPolicy struct {
	ID                    uuid.UUID `json:"id" gorm:"type:uuid;primary_key;default:gen_random_uuid()"`
	AllowAgentWithdrawal  bool      `json:"allow_agent_withdrawal" gorm:"default:true"`
	MinWithdrawalAmount   float64   `json:"min_withdrawal_amount" gorm:"default:0"`
	AutoProcessOnEod      bool      `json:"auto_process_on_eod" gorm:"default:true"`
	EodCutoffHour         int       `json:"eod_cutoff_hour" gorm:"default:23"`
	CreatedAt             time.Time `json:"created_at"`
	UpdatedAt             time.Time `json:"updated_at"`
}

// CommissionClawback represents a commission recovery case
type CommissionClawback struct {
	ID                     uuid.UUID `json:"id" gorm:"type:uuid;primary_key;default:gen_random_uuid()"`
	AgentID                uuid.UUID `json:"agent_id" gorm:"type:uuid;not null;index"`
	AgentName              string    `json:"agent_name"`
	Reason                 string    `json:"reason" gorm:"not null"`
	Amount                 float64   `json:"amount" gorm:"not null"`
	OriginalCommissionDate string    `json:"original_commission_date"`
	Status                 string    `json:"status" gorm:"default:'pending_approval';index"`
	Notes                  string    `json:"notes"`
	CreatedAt              time.Time `json:"created_at"`
	UpdatedAt              time.Time `json:"updated_at"`
}

// CreateClawbackRequest is the payload for initiating a clawback
type CreateClawbackRequest struct {
	AgentID                uuid.UUID `json:"agent_id" binding:"required"`
	AgentName              string    `json:"agent_name" binding:"required"`
	Reason                 string    `json:"reason" binding:"required"`
	Amount                 float64   `json:"amount" binding:"required,gt=0"`
	OriginalCommissionDate string    `json:"original_commission_date"`
	Notes                  string    `json:"notes"`
}

// LeaderboardEntry represents one row in the agent performance leaderboard
type LeaderboardEntry struct {
	AgentID          string  `json:"agent_id"`
	TotalVolume      float64 `json:"total_volume"`
	TotalCommission  float64 `json:"total_commission"`
	TransactionCount int64   `json:"transaction_count"`
	AvgCommission    float64 `json:"avg_commission"`
	Rank             int     `json:"rank"`
}

// AgentMetrics holds performance metrics for a single agent over a time window
type AgentMetrics struct {
	AgentID          string  `json:"agent_id"`
	Days             int     `json:"days"`
	TotalVolume      float64 `json:"total_volume"`
	TotalCommission  float64 `json:"total_commission"`
	TransactionCount int64   `json:"transaction_count"`
	AvgCommission    float64 `json:"avg_commission"`
	PendingBalance   float64 `json:"pending_balance"`
	AvailableBalance float64 `json:"available_balance"`
	TotalEarned      float64 `json:"total_earned"`
}

// PerformanceStats holds aggregate platform-level performance statistics
type PerformanceStats struct {
	TotalAgents         int64   `json:"total_agents"`
	ActiveAgents        int64   `json:"active_agents"`
	TotalCommissionPaid float64 `json:"total_commission_paid"`
	TotalVolume         float64 `json:"total_volume"`
	AvgCommissionRate   float64 `json:"avg_commission_rate"`
}

// EodAgentResult summarises the EOD outcome for a single agent
type EodAgentResult struct {
	AgentID        uuid.UUID `json:"agent_id"`
	SettlementID   uuid.UUID `json:"settlement_id"`
	SettlementRef  string    `json:"settlement_ref"`
	TotalAmount    float64   `json:"total_amount"`
	CommissionCount int      `json:"commission_count"`
	Status         string    `json:"status"`
	Error          string    `json:"error,omitempty"`
}

// EodResult summarises an entire EOD run
type EodResult struct {
	RunAt          time.Time        `json:"run_at"`
	AgentsProcessed int             `json:"agents_processed"`
	TotalPaid       float64         `json:"total_paid"`
	Succeeded       []EodAgentResult `json:"succeeded"`
	Failed          []EodAgentResult `json:"failed"`
}

// GetPolicy fetches the single global policy (creates default if missing)
func (s *CommissionService) GetPolicy() (*SettlementPolicy, error) {
	var policy SettlementPolicy
	if err := s.db.First(&policy).Error; err != nil {
		if err == gorm.ErrRecordNotFound {
			policy = SettlementPolicy{
				AllowAgentWithdrawal: true,
				MinWithdrawalAmount:  0,
				AutoProcessOnEod:     true,
				EodCutoffHour:        23,
			}
			if err := s.db.Create(&policy).Error; err != nil {
				return nil, fmt.Errorf("failed to create default policy: %w", err)
			}
		} else {
			return nil, fmt.Errorf("failed to get policy: %w", err)
		}
	}
	return &policy, nil
}

// UpdatePolicy updates the global settlement policy
func (s *CommissionService) UpdatePolicy(updates map[string]interface{}) (*SettlementPolicy, error) {
	policy, err := s.GetPolicy()
	if err != nil {
		return nil, err
	}
	if err := s.db.Model(policy).Updates(updates).Error; err != nil {
		return nil, fmt.Errorf("failed to update policy: %w", err)
	}
	return policy, nil
}

// RunEod runs end-of-day settlement for all agents with pending commissions
func (s *CommissionService) RunEod() (*EodResult, error) {
	policy, err := s.GetPolicy()
	if err != nil {
		return nil, err
	}

	// Find all agents with pending balance > min withdrawal amount
	var balances []AgentBalance
	if err := s.db.Where("pending_balance > ?", policy.MinWithdrawalAmount).Find(&balances).Error; err != nil {
		return nil, fmt.Errorf("failed to fetch agent balances: %w", err)
	}

	result := &EodResult{
		RunAt:     time.Now(),
		Succeeded: []EodAgentResult{},
		Failed:    []EodAgentResult{},
	}

	now := time.Now()
	startOfDay := time.Date(now.Year(), now.Month(), now.Day(), 0, 0, 0, 0, now.Location())

	for _, balance := range balances {
		agentResult := EodAgentResult{AgentID: balance.AgentID}

		settlement, err := s.CreateSettlement(CreateSettlementRequest{
			AgentID:        balance.AgentID,
			PaymentMethod:  "bank_transfer",
			PaymentDetails: JSON{"source": "eod_batch", "auto": true},
			StartDate:      startOfDay,
			EndDate:        now,
		})
		if err != nil {
			agentResult.Error = err.Error()
			result.Failed = append(result.Failed, agentResult)
			continue
		}

		agentResult.SettlementID = settlement.ID
		agentResult.SettlementRef = settlement.SettlementRef
		agentResult.TotalAmount = settlement.TotalAmount
		agentResult.CommissionCount = settlement.CommissionCount

		if policy.AutoProcessOnEod {
			if err := s.ProcessSettlement(settlement.ID); err != nil {
				agentResult.Error = err.Error()
				agentResult.Status = "process_failed"
				result.Failed = append(result.Failed, agentResult)
				continue
			}
			agentResult.Status = "completed"
		} else {
			agentResult.Status = "pending"
		}

		result.Succeeded = append(result.Succeeded, agentResult)
		result.TotalPaid += settlement.TotalAmount
	}

	result.AgentsProcessed = len(balances)
	return result, nil
}

// GetAgentLeaderboard returns agents ranked by commission volume, earnings, or count
func (s *CommissionService) GetAgentLeaderboard(days int, sortBy string, page, limit int) ([]LeaderboardEntry, error) {
	since := time.Now().AddDate(0, 0, -days)

	orderCol := "total_commission"
	switch sortBy {
	case "volume":
		orderCol = "total_volume"
	case "count":
		orderCol = "transaction_count"
	}

	type row struct {
		AgentID          string  `gorm:"column:agent_id"`
		TotalVolume      float64 `gorm:"column:total_volume"`
		TotalCommission  float64 `gorm:"column:total_commission"`
		TransactionCount int64   `gorm:"column:transaction_count"`
	}

	offset := (page - 1) * limit
	var rows []row
	query := `SELECT agent_id::text, COALESCE(SUM(amount),0) AS total_volume,
		COALESCE(SUM(commission_amount),0) AS total_commission, COUNT(*) AS transaction_count
		FROM commissions WHERE earned_at >= ? GROUP BY agent_id ORDER BY ` + orderCol + ` DESC LIMIT ? OFFSET ?`
	if err := s.db.Raw(query, since, limit, offset).Scan(&rows).Error; err != nil {
		return nil, fmt.Errorf("leaderboard query failed: %w", err)
	}

	entries := make([]LeaderboardEntry, len(rows))
	for i, r := range rows {
		avg := 0.0
		if r.TransactionCount > 0 {
			avg = r.TotalCommission / float64(r.TransactionCount)
		}
		entries[i] = LeaderboardEntry{
			AgentID: r.AgentID, TotalVolume: r.TotalVolume,
			TotalCommission: r.TotalCommission, TransactionCount: r.TransactionCount,
			AvgCommission: avg, Rank: offset + i + 1,
		}
	}
	return entries, nil
}

// GetAgentMetrics returns commission metrics for one agent over a rolling window
func (s *CommissionService) GetAgentMetrics(agentID uuid.UUID, days int) (*AgentMetrics, error) {
	since := time.Now().AddDate(0, 0, -days)

	type agg struct {
		TotalVolume      float64 `gorm:"column:total_volume"`
		TotalCommission  float64 `gorm:"column:total_commission"`
		TransactionCount int64   `gorm:"column:transaction_count"`
	}
	var a agg
	s.db.Raw(`SELECT COALESCE(SUM(amount),0) AS total_volume,
		COALESCE(SUM(commission_amount),0) AS total_commission, COUNT(*) AS transaction_count
		FROM commissions WHERE agent_id = ? AND earned_at >= ?`, agentID, since).Scan(&a)

	avg := 0.0
	if a.TransactionCount > 0 {
		avg = a.TotalCommission / float64(a.TransactionCount)
	}

	var bal AgentBalance
	s.db.Where("agent_id = ?", agentID).First(&bal)

	return &AgentMetrics{
		AgentID: agentID.String(), Days: days,
		TotalVolume: a.TotalVolume, TotalCommission: a.TotalCommission,
		TransactionCount: a.TransactionCount, AvgCommission: avg,
		PendingBalance: bal.PendingBalance, AvailableBalance: bal.AvailableBalance,
		TotalEarned: bal.TotalEarned,
	}, nil
}

// GetPerformanceStats returns platform-level aggregate performance stats
func (s *CommissionService) GetPerformanceStats() (*PerformanceStats, error) {
	var totalAgents, activeAgents int64
	s.db.Model(&AgentBalance{}).Count(&totalAgents)
	s.db.Model(&AgentBalance{}).Where("total_earned > 0").Count(&activeAgents)

	type agg struct {
		TotalCommission float64 `gorm:"column:total_commission"`
		TotalVolume     float64 `gorm:"column:total_volume"`
		AvgRate         float64 `gorm:"column:avg_rate"`
	}
	var a agg
	s.db.Raw(`SELECT COALESCE(SUM(commission_amount),0) AS total_commission,
		COALESCE(SUM(amount),0) AS total_volume, COALESCE(AVG(rate),0) AS avg_rate
		FROM commissions WHERE status = 'settled'`).Scan(&a)

	return &PerformanceStats{
		TotalAgents: totalAgents, ActiveAgents: activeAgents,
		TotalCommissionPaid: a.TotalCommission, TotalVolume: a.TotalVolume,
		AvgCommissionRate: a.AvgRate,
	}, nil
}

// ListClawbacks returns all clawback cases ordered newest first
func (s *CommissionService) ListClawbacks() ([]CommissionClawback, error) {
	var cases []CommissionClawback
	if err := s.db.Order("created_at DESC").Find(&cases).Error; err != nil {
		return nil, fmt.Errorf("failed to list clawbacks: %w", err)
	}
	return cases, nil
}

// CreateClawback creates a new clawback case in pending_approval state
func (s *CommissionService) CreateClawback(req CreateClawbackRequest) (*CommissionClawback, error) {
	c := &CommissionClawback{
		AgentID: req.AgentID, AgentName: req.AgentName, Reason: req.Reason,
		Amount: req.Amount, OriginalCommissionDate: req.OriginalCommissionDate,
		Notes: req.Notes, Status: "pending_approval",
	}
	if err := s.db.Create(c).Error; err != nil {
		return nil, fmt.Errorf("failed to create clawback: %w", err)
	}
	return c, nil
}

// ApproveClawback moves a clawback from pending_approval → approved
func (s *CommissionService) ApproveClawback(id uuid.UUID) (*CommissionClawback, error) {
	var c CommissionClawback
	if err := s.db.First(&c, "id = ?", id).Error; err != nil {
		return nil, fmt.Errorf("clawback not found")
	}
	if c.Status != "pending_approval" {
		return nil, fmt.Errorf("clawback is not pending approval")
	}
	c.Status = "approved"
	if err := s.db.Save(&c).Error; err != nil {
		return nil, fmt.Errorf("failed to approve clawback: %w", err)
	}
	return &c, nil
}

// ExecuteClawback debits the agent balance and marks the clawback as executed
func (s *CommissionService) ExecuteClawback(id uuid.UUID) (*CommissionClawback, error) {
	var c CommissionClawback
	if err := s.db.First(&c, "id = ?", id).Error; err != nil {
		return nil, fmt.Errorf("clawback not found")
	}
	if c.Status != "approved" {
		return nil, fmt.Errorf("clawback must be approved before execution")
	}
	s.db.Model(&AgentBalance{}).Where("agent_id = ?", c.AgentID).Updates(map[string]interface{}{
		"available_balance": gorm.Expr("GREATEST(available_balance - ?, 0)", c.Amount),
		"total_earned":      gorm.Expr("GREATEST(total_earned - ?, 0)", c.Amount),
	})
	c.Status = "executed"
	if err := s.db.Save(&c).Error; err != nil {
		return nil, fmt.Errorf("failed to execute clawback: %w", err)
	}
	return &c, nil
}

// callPaymentServicePayout calls the payment-processing-service to transfer commission funds to agent
func (s *CommissionService) callPaymentServicePayout(settlement Settlement) error {
	paymentServiceURL := os.Getenv("PAYMENT_SERVICE_URL")
	if paymentServiceURL == "" {
		paymentServiceURL = "http://payment-processing-service:8000"
	}

	tenantID := os.Getenv("DEFAULT_TENANT_ID")
	if tenantID == "" {
		tenantID = "default"
	}

	payload := map[string]interface{}{
		"agent_id":       settlement.AgentID.String(),
		"amount":         settlement.TotalAmount,
		"currency":       settlement.Currency,
		"settlement_ref": settlement.SettlementRef,
		"note":           fmt.Sprintf("Commission settlement %s", settlement.SettlementRef),
		"payment_details": settlement.PaymentDetails,
	}

	body, _ := json.Marshal(payload)

	req, err := http.NewRequest("POST", paymentServiceURL+"/payment/settlement-payout", bytes.NewBuffer(body))
	if err != nil {
		return fmt.Errorf("failed to build payout request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Service-Auth", "commission-settlement-service")
	req.Header.Set("X-Tenant-Id", tenantID)

	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return fmt.Errorf("payout request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		respBody, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("payout service returned %d: %s", resp.StatusCode, string(respBody))
	}

	return nil
}

// Metrics
var (
	commissionCreatedTotal = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "commission_created_total",
			Help: "Total number of commissions created",
		},
		[]string{"transaction_type", "currency"},
	)

	commissionAmountTotal = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "commission_amount_total",
			Help: "Total amount of commissions",
		},
		[]string{"transaction_type", "currency"},
	)

	settlementCreatedTotal = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "settlement_created_total",
			Help: "Total number of settlements created",
		},
		[]string{"payment_method", "status"},
	)

	commissionRequestDuration = prometheus.NewHistogramVec(
		prometheus.HistogramOpts{
			Name: "commission_request_duration_seconds",
			Help: "Duration of commission requests",
		},
		[]string{"method", "endpoint"},
	)
)

func init() {
	prometheus.MustRegister(commissionCreatedTotal)
	prometheus.MustRegister(commissionAmountTotal)
	prometheus.MustRegister(settlementCreatedTotal)
	prometheus.MustRegister(commissionRequestDuration)
}

// HTTP Handlers
type CommissionHandler struct {
	service *CommissionService
}

func NewCommissionHandler(service *CommissionService) *CommissionHandler {
	return &CommissionHandler{service: service}
}

func (h *CommissionHandler) CreateCommission(c *gin.Context) {
	timer := prometheus.NewTimer(commissionRequestDuration.WithLabelValues("POST", "/commissions"))
	defer timer.ObserveDuration()

	var req CreateCommissionRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	commission, err := h.service.CreateCommission(req)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	commissionCreatedTotal.WithLabelValues(commission.TransactionType, commission.Currency).Inc()
	commissionAmountTotal.WithLabelValues(commission.TransactionType, commission.Currency).Add(commission.CommissionAmount)

	c.JSON(http.StatusCreated, commission)
}

func (h *CommissionHandler) GetCommission(c *gin.Context) {
	timer := prometheus.NewTimer(commissionRequestDuration.WithLabelValues("GET", "/commissions/:id"))
	defer timer.ObserveDuration()

	idStr := c.Param("id")
	id, err := uuid.Parse(idStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid commission ID"})
		return
	}

	commission, err := h.service.GetCommission(id)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "commission not found"})
		return
	}

	c.JSON(http.StatusOK, commission)
}

func (h *CommissionHandler) ListCommissions(c *gin.Context) {
	timer := prometheus.NewTimer(commissionRequestDuration.WithLabelValues("GET", "/commissions"))
	defer timer.ObserveDuration()

	page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
	limit, _ := strconv.Atoi(c.DefaultQuery("limit", "20"))

	var agentID *uuid.UUID
	if agentIDStr := c.Query("agent_id"); agentIDStr != "" {
		id, err := uuid.Parse(agentIDStr)
		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": "invalid agent_id format, expected UUID"})
			return
		}
		agentID = &id
	}

	status := CommissionStatus(c.Query("status"))

	var startDate *time.Time
	if startDateStr := c.Query("start_date"); startDateStr != "" {
		parsedStartDate, err := time.Parse("2006-01-02", startDateStr)
		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": "invalid start_date format, expected YYYY-MM-DD"})
			return
		}
		startDateUTC := parsedStartDate.UTC()
		startDate = &startDateUTC
	}

	var endDate *time.Time
	if endDateStr := c.Query("end_date"); endDateStr != "" {
		parsedEndDate, err := time.Parse("2006-01-02", endDateStr)
		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": "invalid end_date format, expected YYYY-MM-DD"})
			return
		}
		endOfDayUTC := time.Date(parsedEndDate.Year(), parsedEndDate.Month(), parsedEndDate.Day(), 23, 59, 59, int(time.Second-time.Nanosecond), time.UTC)
		endDate = &endOfDayUTC
	}

	commissions, total, err := h.service.ListCommissions(page, limit, agentID, status, startDate, endDate)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"commissions": commissions,
		"total":       total,
		"page":        page,
		"limit":       limit,
	})
}

func (h *CommissionHandler) CreateSettlement(c *gin.Context) {
	timer := prometheus.NewTimer(commissionRequestDuration.WithLabelValues("POST", "/settlements"))
	defer timer.ObserveDuration()

	var req CreateSettlementRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	settlement, err := h.service.CreateSettlement(req)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	settlementCreatedTotal.WithLabelValues(settlement.PaymentMethod, string(settlement.Status)).Inc()

	c.JSON(http.StatusCreated, settlement)
}

func (h *CommissionHandler) GetSettlement(c *gin.Context) {
	timer := prometheus.NewTimer(commissionRequestDuration.WithLabelValues("GET", "/settlements/:id"))
	defer timer.ObserveDuration()

	idStr := c.Param("id")
	id, err := uuid.Parse(idStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid settlement ID"})
		return
	}

	settlement, err := h.service.GetSettlement(id)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "settlement not found"})
		return
	}

	c.JSON(http.StatusOK, settlement)
}

func (h *CommissionHandler) ListSettlements(c *gin.Context) {
	timer := prometheus.NewTimer(commissionRequestDuration.WithLabelValues("GET", "/settlements"))
	defer timer.ObserveDuration()

	page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
	limit, _ := strconv.Atoi(c.DefaultQuery("limit", "20"))

	var agentID *uuid.UUID
	if agentIDStr := c.Query("agent_id"); agentIDStr != "" {
		id, err := uuid.Parse(agentIDStr)
		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": "invalid agent_id format, expected UUID"})
			return
		}
		agentID = &id
	}

	status := SettlementStatus(c.Query("status"))

	settlements, total, err := h.service.ListSettlements(page, limit, agentID, status, nil, nil)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"settlements": settlements,
		"total":       total,
		"page":        page,
		"limit":       limit,
	})
}

func (h *CommissionHandler) UpdateSettlement(c *gin.Context) {
	timer := prometheus.NewTimer(commissionRequestDuration.WithLabelValues("PUT", "/settlements/:id"))
	defer timer.ObserveDuration()

	idStr := c.Param("id")
	id, err := uuid.Parse(idStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid settlement ID"})
		return
	}

	var req UpdateSettlementRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	settlement, err := h.service.UpdateSettlement(id, req)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, settlement)
}

func (h *CommissionHandler) ProcessSettlement(c *gin.Context) {
	timer := prometheus.NewTimer(commissionRequestDuration.WithLabelValues("POST", "/settlements/:id/process"))
	defer timer.ObserveDuration()

	idStr := c.Param("id")
	id, err := uuid.Parse(idStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid settlement ID"})
		return
	}

	if err := h.service.ProcessSettlement(id); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"message": "settlement processing started"})
}

func (h *CommissionHandler) GetAgentBalance(c *gin.Context) {
	timer := prometheus.NewTimer(commissionRequestDuration.WithLabelValues("GET", "/agents/:id/balance"))
	defer timer.ObserveDuration()

	idStr := c.Param("id")
	id, err := uuid.Parse(idStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid agent ID"})
		return
	}

	balance, err := h.service.GetAgentBalance(id)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	policy, _ := h.service.GetPolicy()
	withdrawalAllowed := true
	minWithdrawal := 0.0
	if policy != nil {
		withdrawalAllowed = policy.AllowAgentWithdrawal
		minWithdrawal = policy.MinWithdrawalAmount
	}

	c.JSON(http.StatusOK, gin.H{
		"id":                  balance.ID,
		"agent_id":            balance.AgentID,
		"pending_balance":     balance.PendingBalance,
		"available_balance":   balance.AvailableBalance,
		"settled_balance":     balance.SettledBalance,
		"total_earned":        balance.TotalEarned,
		"currency":            balance.Currency,
		"last_settlement_at":  balance.LastSettlementAt,
		"created_at":          balance.CreatedAt,
		"updated_at":          balance.UpdatedAt,
		"withdrawal_allowed":  withdrawalAllowed,
		"min_withdrawal_amount": minWithdrawal,
	})
}

func (h *CommissionHandler) GetPolicy(c *gin.Context) {
	policy, err := h.service.GetPolicy()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, policy)
}

func (h *CommissionHandler) UpdatePolicy(c *gin.Context) {
	var updates map[string]interface{}
	if err := c.ShouldBindJSON(&updates); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	policy, err := h.service.UpdatePolicy(updates)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, policy)
}

func (h *CommissionHandler) RunEod(c *gin.Context) {
	result, err := h.service.RunEod()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, result)
}

func (h *CommissionHandler) ListAgentBalances(c *gin.Context) {
	page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
	limit, _ := strconv.Atoi(c.DefaultQuery("limit", "50"))
	balances, total, err := h.service.ListAgentBalances(page, limit)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"balances": balances, "total": total, "page": page, "limit": limit})
}

func (h *CommissionHandler) ListCommissionRules(c *gin.Context) {
	activeOnly := c.Query("active_only") == "true"
	rules, err := h.service.ListCommissionRules(activeOnly)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"rules": rules, "total": len(rules)})
}

func (h *CommissionHandler) GetCommissionRule(c *gin.Context) {
	id, err := uuid.Parse(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid rule ID"})
		return
	}
	rule, err := h.service.GetCommissionRule(id)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, rule)
}

func (h *CommissionHandler) CreateCommissionRule(c *gin.Context) {
	var req CreateCommissionRuleRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	rule, err := h.service.CreateCommissionRule(req)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusCreated, rule)
}

func (h *CommissionHandler) UpdateCommissionRule(c *gin.Context) {
	id, err := uuid.Parse(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid rule ID"})
		return
	}
	var req UpdateCommissionRuleRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	rule, err := h.service.UpdateCommissionRule(id, req)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, rule)
}

func (h *CommissionHandler) DeleteCommissionRule(c *gin.Context) {
	id, err := uuid.Parse(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid rule ID"})
		return
	}
	if err := h.service.DeleteCommissionRule(id); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"message": "rule deactivated"})
}

// ── Leaderboard & Performance ─────────────────────────────────────────────────

func (h *CommissionHandler) GetAgentLeaderboard(c *gin.Context) {
	days, _ := strconv.Atoi(c.DefaultQuery("days", "30"))
	sortBy := c.DefaultQuery("sort_by", "commission")
	page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
	limit, _ := strconv.Atoi(c.DefaultQuery("limit", "50"))
	entries, err := h.service.GetAgentLeaderboard(days, sortBy, page, limit)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"leaderboard": entries, "days": days, "sort_by": sortBy, "page": page, "limit": limit})
}

func (h *CommissionHandler) GetAgentMetrics(c *gin.Context) {
	id, err := uuid.Parse(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid agent ID"})
		return
	}
	days, _ := strconv.Atoi(c.DefaultQuery("days", "30"))
	metrics, err := h.service.GetAgentMetrics(id, days)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, metrics)
}

func (h *CommissionHandler) GetPerformanceStats(c *gin.Context) {
	stats, err := h.service.GetPerformanceStats()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, stats)
}

// ── Clawbacks ─────────────────────────────────────────────────────────────────

func (h *CommissionHandler) ListClawbacks(c *gin.Context) {
	cases, err := h.service.ListClawbacks()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"cases": cases})
}

func (h *CommissionHandler) CreateClawback(c *gin.Context) {
	var req CreateClawbackRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	clawback, err := h.service.CreateClawback(req)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusCreated, clawback)
}

func (h *CommissionHandler) ApproveClawback(c *gin.Context) {
	id, err := uuid.Parse(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid clawback ID"})
		return
	}
	clawback, err := h.service.ApproveClawback(id)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, clawback)
}

func (h *CommissionHandler) ExecuteClawback(c *gin.Context) {
	id, err := uuid.Parse(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid clawback ID"})
		return
	}
	clawback, err := h.service.ExecuteClawback(id)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, clawback)
}

// ── Commission Cascade ─────────────────────────────────────────────────────────

// CascadeEntry represents one level in the commission distribution chain.
type CascadeEntry struct {
	Level       int     `json:"level"`
	AgentID     string  `json:"agent_id"`
	AgentTier   string  `json:"agent_tier"`
	Rate        float64 `json:"rate"`
	Amount      float64 `json:"amount"`
	Currency    string  `json:"currency"`
	Description string  `json:"description"`
}

// CascadeResult is returned by CalculateCommissionCascade.
type CascadeResult struct {
	TransactionAmount float64        `json:"transaction_amount"`
	TransactionType   string         `json:"transaction_type"`
	TotalCommission   float64        `json:"total_commission"`
	Currency          string         `json:"currency"`
	CascadeEntries    []CascadeEntry `json:"cascade_entries"`
}

// CalculateCommissionCascade computes how commission is distributed across the
// agent hierarchy for a given transaction.
func (s *CommissionService) CalculateCommissionCascade(
	agentID uuid.UUID,
	transactionType string,
	amount float64,
	currency string,
) (*CascadeResult, error) {
	if s.db == nil {
		return &CascadeResult{
			TransactionAmount: amount,
			TransactionType:   transactionType,
			TotalCommission:   0,
			Currency:          currency,
			CascadeEntries:    []CascadeEntry{},
		}, nil
	}

	agentInfo, err := s.getAgentInfo(agentID)
	if err != nil || agentInfo == nil {
		agentInfo = &AgentInfo{ID: agentID, Tier: "agent", Territory: ""}
	}

	// Tier hierarchy: agent < super-agent < aggregator < platform
	tierChain := []struct {
		tier  string
		level int
	}{
		{agentInfo.Tier, 1},
		{"super-agent", 2},
		{"aggregator", 3},
		{"platform", 4},
	}

	seen := map[string]bool{}
	var entries []CascadeEntry
	totalCommission := 0.0

	for _, tc := range tierChain {
		if seen[tc.tier] {
			continue
		}
		seen[tc.tier] = true

		var rule CommissionRule
		err := s.db.Where(
			"agent_tier = ? AND transaction_type = ? AND min_amount <= ? AND max_amount >= ? AND is_active = true",
			tc.tier, transactionType, amount, amount,
		).First(&rule).Error

		if err != nil {
			// try wildcard tier
			err = s.db.Where(
				"(agent_tier IS NULL OR agent_tier = '') AND transaction_type = ? AND min_amount <= ? AND max_amount >= ? AND is_active = true",
				transactionType, amount, amount,
			).First(&rule).Error
		}

		if err != nil {
			continue
		}

		commAmt := amount * rule.Rate / 100
		if rule.FlatFee > 0 && commAmt < rule.FlatFee {
			commAmt = rule.FlatFee
		}
		totalCommission += commAmt
		entries = append(entries, CascadeEntry{
			Level:       tc.level,
			AgentID:     agentID.String(),
			AgentTier:   tc.tier,
			Rate:        rule.Rate,
			Amount:      commAmt,
			Currency:    currency,
			Description: fmt.Sprintf("%s commission for %s transaction", tc.tier, transactionType),
		})
	}

	return &CascadeResult{
		TransactionAmount: amount,
		TransactionType:   transactionType,
		TotalCommission:   totalCommission,
		Currency:          currency,
		CascadeEntries:    entries,
	}, nil
}

func (h *CommissionHandler) GetCommissionCascade(c *gin.Context) {
	type cascadeReq struct {
		AgentID         string  `json:"agent_id" binding:"required"`
		TransactionType string  `json:"transaction_type" binding:"required"`
		Amount          float64 `json:"amount" binding:"required,gt=0"`
		Currency        string  `json:"currency"`
	}
	var req cascadeReq
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	agentID, err := uuid.Parse(req.AgentID)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid agent_id"})
		return
	}
	currency := req.Currency
	if currency == "" {
		currency = "NGN"
	}
	result, err := h.service.CalculateCommissionCascade(agentID, req.TransactionType, req.Amount, currency)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, result)
}

func setupRoutes(handler *CommissionHandler) *gin.Engine {
	gin.SetMode(gin.ReleaseMode)
	r := gin.Default()

	// CORS middleware
	r.Use(func(c *gin.Context) {
		c.Header("Access-Control-Allow-Origin", "*")
		c.Header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
		c.Header("Access-Control-Allow-Headers", "Origin, Content-Type, Accept, Authorization")

		if c.Request.Method == "OPTIONS" {
			c.AbortWithStatus(204)
			return
		}

		c.Next()
	})

	// Health check
	r.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"status": "healthy"})
	})

	// Metrics endpoint
	r.GET("/metrics", gin.WrapH(promhttp.Handler()))

	// API routes
	v1 := r.Group("/api/v1")
	{
		commissions := v1.Group("/commissions")
		{
			commissions.POST("", handler.CreateCommission)
			commissions.GET("", handler.ListCommissions)
			commissions.GET("/:id", handler.GetCommission)
		}

		settlements := v1.Group("/settlements")
		{
			settlements.POST("", handler.CreateSettlement)
			settlements.GET("", handler.ListSettlements)
			settlements.GET("/:id", handler.GetSettlement)
			settlements.PUT("/:id", handler.UpdateSettlement)
			settlements.POST("/:id/process", handler.ProcessSettlement)
		}

		agents := v1.Group("/agents")
		{
			agents.GET("", handler.ListAgentBalances)
			// static paths before parametric to ensure correct gin routing
			agents.GET("/leaderboard", handler.GetAgentLeaderboard)
			agents.GET("/performance/stats", handler.GetPerformanceStats)
			agents.GET("/:id/balance", handler.GetAgentBalance)
			agents.GET("/:id/metrics", handler.GetAgentMetrics)
		}

		clawbacks := v1.Group("/clawbacks")
		{
			clawbacks.GET("", handler.ListClawbacks)
			clawbacks.POST("", handler.CreateClawback)
			clawbacks.POST("/:id/approve", handler.ApproveClawback)
			clawbacks.POST("/:id/execute", handler.ExecuteClawback)
		}

		rules := v1.Group("/commission-rules")
		{
			rules.GET("", handler.ListCommissionRules)
			rules.POST("", handler.CreateCommissionRule)
			rules.GET("/:id", handler.GetCommissionRule)
			rules.PUT("/:id", handler.UpdateCommissionRule)
			rules.DELETE("/:id", handler.DeleteCommissionRule)
		}

		// Settlement policy (platform-wide controls)
		policy := v1.Group("/policy")
		{
			policy.GET("", handler.GetPolicy)
			policy.PUT("", handler.UpdatePolicy)
		}

		// EOD batch processing
		v1.POST("/eod/run", handler.RunEod)

		// Commission cascade calculation
		v1.POST("/commissions/cascade", handler.GetCommissionCascade)
	}

	return r
}

func main() {
	// Database connection
	dsn := os.Getenv("DATABASE_URL")
	if dsn == "" {
		dsn = "postgres://remittance:remittance@postgresql:5432/remittance?sslmode=disable"
	}

	db, err := gorm.Open(postgres.Open(dsn), &gorm.Config{
		Logger: logger.Default.LogMode(logger.Info),
	})
	if err != nil {
		log.Fatal("Failed to connect to database:", err)
	}

	// Deduplicate commissions before adding unique index to avoid SQLSTATE 23505.
	// Keeps the earliest row per (agent_id, transaction_ref); safe to run repeatedly.
	if err := db.Exec(`
		DELETE FROM commissions
		WHERE id NOT IN (
			SELECT DISTINCT ON (agent_id, transaction_ref) id
			FROM commissions
			ORDER BY agent_id, transaction_ref, created_at ASC
		)
	`).Error; err != nil {
		log.Printf("Warning: commission deduplication query failed (table may not exist yet): %v", err)
	}

	// Auto migrate
	if err := db.AutoMigrate(&Settlement{}, &Commission{}, &CommissionRule{}, &AgentBalance{}, &SettlementPolicy{}, &CommissionClawback{}); err != nil {
		log.Fatal("Failed to migrate database:", err)
	}

	// Seed data (only on first run)
	if err := SeedData(db); err != nil {
		log.Printf("Warning: Failed to seed data: %v", err)
	}

	// Initialize service and handler
	service := NewCommissionService(db)
	handler := NewCommissionHandler(service)

	// Setup routes
	router := setupRoutes(handler)

	// Start server
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	srv := &http.Server{
		Addr:    "0.0.0.0:" + port,
		Handler: router,
	}

	// Graceful shutdown
	go func() {
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("Failed to start server: %v", err)
		}
	}()

	log.Printf("Commission Settlement Service started on port %s", port)

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
