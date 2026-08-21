package main

import (
	"bytes"
	"context"
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

// Models
type Commission struct {
	ID               uuid.UUID `gorm:"type:uuid;primary_key;default:gen_random_uuid()"`
	AgentID          uuid.UUID `gorm:"type:uuid;not null"`
	AgentName        string    `gorm:"not null"`
	TransactionID    string    `gorm:"not null;uniqueIndex:idx_commission_dedup"`
	TransactionRef   string    `gorm:"uniqueIndex:idx_commission_dedup"`
	TransactionType  string    `gorm:"not null"` // "pos_sale", "withdrawal", "deposit", "transfer", "bill_payment"
	Amount           float64   `gorm:"not null"`
	CommissionAmount float64   `gorm:"not null"`
	Rate             float64   `gorm:"not null"`
	RateType         string    `gorm:"not null"` // "percentage", "flat"
	Currency         string    `gorm:"default:'NGN'"`
	Status           string    `gorm:"default:'pending'"` // "pending", "settled", "cancelled"
	SettlementID     *uuid.UUID `gorm:"type:uuid"`
	EarnedAt         time.Time `gorm:"not null"`
	SettledAt        *time.Time
	CreatedAt        time.Time
	UpdatedAt        time.Time
}

type Settlement struct {
	ID              uuid.UUID `gorm:"type:uuid;primary_key;default:gen_random_uuid()"`
	AgentID         uuid.UUID `gorm:"type:uuid;not null"`
	AgentName       string    `gorm:"not null"`
	SettlementRef   string    `gorm:"unique;not null"`
	TotalAmount     float64   `gorm:"not null"`
	CommissionCount int       `gorm:"not null"`
	Currency        string    `gorm:"default:'NGN'"`
	Status          SettlementStatus `gorm:"default:'pending'"`
	PaymentMethod   string    `gorm:"not null"` // "bank_transfer", "wallet_credit", "cash_pickup"
	PaymentDetails  string    `gorm:"type:jsonb"`
	ProcessedAt     *time.Time
	FailureReason   string
	PeriodStart     time.Time `gorm:"not null"`
	PeriodEnd       time.Time `gorm:"not null"`
	CreatedAt       time.Time
	UpdatedAt       time.Time
}

type CommissionRule struct {
	ID              uuid.UUID `gorm:"type:uuid;primary_key;default:gen_random_uuid()"`
	Name            string    `gorm:"not null"`
	TransactionType string    `gorm:"not null"`
	MinAmount       float64   `gorm:"not null"`
	MaxAmount       float64   `gorm:"not null"`
	Rate            float64   `gorm:"not null"`
	RateType        string    `gorm:"not null"`
	AgentTier       string    // "bronze", "silver", "gold", "platinum"
	IsActive        bool      `gorm:"default:true"`
	Priority        int       `gorm:"default:0"`
	FlatFee         float64   `gorm:"default:0"`
	CreatedAt       time.Time
	UpdatedAt       time.Time
}

type AgentBalance struct {
	ID                uuid.UUID `gorm:"type:uuid;primary_key;default:gen_random_uuid()"`
	AgentID           uuid.UUID `gorm:"type:uuid;unique;not null"`
	AgentName         string    `gorm:"not null"`
	PendingBalance    float64   `gorm:"default:0"`
	AvailableBalance  float64   `gorm:"default:0"`
	SettledBalance    float64   `gorm:"default:0"`
	TotalEarned       float64   `gorm:"default:0"`
	Currency          string    `gorm:"default:'NGN'"`
	LastSettlementAt  *time.Time
	CreatedAt         time.Time
	UpdatedAt         time.Time
}

// SettlementPolicy controls platform-wide settlement behaviour
type SettlementPolicy struct {
	ID                    uuid.UUID `gorm:"type:uuid;primary_key;default:gen_random_uuid()"`
	AutoProcessOnEod      bool      `gorm:"default:false"`
	MinWithdrawalAmount   float64   `gorm:"default:0"`
	AllowAgentWithdrawal  bool      `gorm:"default:true"`
	UpdatedAt             time.Time
}

// CommissionClawback represents a clawback/debit-adjustment case
type CommissionClawback struct {
	ID                     uuid.UUID `gorm:"type:uuid;primary_key;default:gen_random_uuid()"`
	AgentID                uuid.UUID `gorm:"type:uuid;not null"`
	AgentName              string    `gorm:"not null"`
	Reason                 string    `gorm:"not null"`
	Amount                 float64   `gorm:"not null"`
	OriginalCommissionDate string    `gorm:"not null"`
	Notes                  string
	Status                 string    `gorm:"default:'pending_approval'"`
	CreatedAt              time.Time
	UpdatedAt              time.Time
}

// Request/Response types
type CreateCommissionRequest struct {
	AgentID         string  `json:"agent_id" binding:"required"`
	AgentName       string  `json:"agent_name" binding:"required"`
	TransactionID   string  `json:"transaction_id" binding:"required"`
	TransactionRef  string  `json:"transaction_ref" binding:"required"`
	TransactionType string  `json:"transaction_type" binding:"required"`
	Amount          float64 `json:"amount" binding:"required,gt=0"`
	Currency        string  `json:"currency"`
}

type CreateSettlementRequest struct {
	AgentID        string `json:"agent_id" binding:"required"`
	PaymentMethod  string `json:"payment_method" binding:"required"`
	PaymentDetails string `json:"payment_details"`
	PeriodStart    string `json:"period_start" binding:"required"`
	PeriodEnd      string `json:"period_end" binding:"required"`
}

type UpdateSettlementRequest struct {
	Status        string `json:"status"`
	FailureReason string `json:"failure_reason"`
}

type CreateCommissionRuleRequest struct {
	Name            string  `json:"name" binding:"required"`
	TransactionType string  `json:"transaction_type" binding:"required"`
	MinAmount       float64 `json:"min_amount" binding:"required"`
	MaxAmount       float64 `json:"max_amount" binding:"required"`
	Rate            float64 `json:"rate" binding:"required"`
	RateType        string  `json:"rate_type" binding:"required"`
	AgentTier       string  `json:"agent_tier"`
	Priority        int     `json:"priority"`
	FlatFee         float64 `json:"flat_fee"`
}

type UpdateCommissionRuleRequest struct {
	Name      *string  `json:"name"`
	MinAmount *float64 `json:"min_amount"`
	MaxAmount *float64 `json:"max_amount"`
	Rate      *float64 `json:"rate"`
	AgentTier *string  `json:"agent_tier"`
	IsActive  *bool    `json:"is_active"`
	Priority  *int     `json:"priority"`
	FlatFee   *float64 `json:"flat_fee"`
}

type SettlementStatus string

const (
	SettlementPending   SettlementStatus = "pending"
	SettlementApproved  SettlementStatus = "approved"
	SettlementRejected  SettlementStatus = "rejected"
	SettlementCompleted SettlementStatus = "completed"
	SettlementFailed    SettlementStatus = "failed"
)

type CommissionStatus string

const (
	CommissionPending   CommissionStatus = "pending"
	CommissionSettled   CommissionStatus = "settled"
	CommissionCancelled CommissionStatus = "cancelled"
)

// EOD result types
type EodAgentResult struct {
	AgentID         string  `json:"agent_id"`
	SettlementID    string  `json:"settlement_id,omitempty"`
	SettlementRef   string  `json:"settlement_ref,omitempty"`
	TotalAmount     float64 `json:"total_amount"`
	CommissionCount int     `json:"commission_count"`
	Status          string  `json:"status"`
	Error           string  `json:"error,omitempty"`
}

type EodRunResult struct {
	AgentsProcessed int               `json:"agents_processed"`
	Succeeded       []EodAgentResult  `json:"succeeded"`
	Failed          []EodAgentResult  `json:"failed"`
	TotalPaid       float64           `json:"total_paid"`
}

// Leaderboard types
type LeaderboardEntry struct {
	AgentID          string  `json:"agent_id"`
	TotalVolume      float64 `json:"total_volume"`
	TotalCommission  float64 `json:"total_commission"`
	TransactionCount int64   `json:"transaction_count"`
	AvgCommission    float64 `json:"avg_commission"`
	Rank             int     `json:"rank"`
}

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

type PerformanceStats struct {
	TotalAgents         int64   `json:"total_agents"`
	ActiveAgents        int64   `json:"active_agents"`
	TotalCommissionPaid float64 `json:"total_commission_paid"`
	TotalVolume         float64 `json:"total_volume"`
	AvgCommissionRate   float64 `json:"avg_commission_rate"`
}

// CreateClawbackRequest is the payload for a new clawback
type CreateClawbackRequest struct {
	AgentID                uuid.UUID `json:"agent_id" binding:"required"`
	AgentName              string    `json:"agent_name" binding:"required"`
	Reason                 string    `json:"reason" binding:"required"`
	Amount                 float64   `json:"amount" binding:"required,gt=0"`
	OriginalCommissionDate string    `json:"original_commission_date" binding:"required"`
	Notes                  string    `json:"notes"`
}

// Service
type CommissionService struct {
	db *gorm.DB
}

type AgentInfo struct {
	ID        uuid.UUID
	Tier      string
	Territory string
}

func NewCommissionService(db *gorm.DB) *CommissionService {
	return &CommissionService{db: db}
}

func (s *CommissionService) CreateCommission(req CreateCommissionRequest) (*Commission, error) {
	agentID, err := uuid.Parse(req.AgentID)
	if err != nil {
		return nil, fmt.Errorf("invalid agent ID")
	}

	// Find applicable commission rule
	rule, err := s.findApplicableRule(req.TransactionType, req.Amount, agentID)
	if err != nil {
		return nil, fmt.Errorf("no applicable commission rule found")
	}

	var commissionAmount float64
	if rule.RateType == "percentage" {
		commissionAmount = req.Amount * rule.Rate / 100
		if rule.FlatFee > 0 && commissionAmount < rule.FlatFee {
			commissionAmount = rule.FlatFee
		}
	} else {
		commissionAmount = rule.Rate
	}

	currency := req.Currency
	if currency == "" {
		currency = "NGN"
	}

	commission := Commission{
		AgentID:          agentID,
		AgentName:        req.AgentName,
		TransactionID:    req.TransactionID,
		TransactionRef:   req.TransactionRef,
		TransactionType:  req.TransactionType,
		Amount:           req.Amount,
		CommissionAmount: commissionAmount,
		Rate:             rule.Rate,
		RateType:         rule.RateType,
		Currency:         currency,
		Status:           "pending",
		EarnedAt:         time.Now(),
	}

	if err := s.db.Create(&commission).Error; err != nil {
		return nil, fmt.Errorf("failed to create commission: %w", err)
	}

	// Update agent balance
	if err := s.updateAgentBalance(agentID, req.AgentName, commissionAmount, "pending"); err != nil {
		return nil, fmt.Errorf("failed to update agent balance: %w", err)
	}

	return &commission, nil
}

func (s *CommissionService) findApplicableRule(transactionType string, amount float64, agentID uuid.UUID) (*CommissionRule, error) {
	var rules []CommissionRule

	// Get agent info for tier-specific rules
	agentInfo, err := s.getAgentInfo(agentID)
	if err != nil {
		agentInfo = &AgentInfo{Tier: "bronze"} // Default tier
	}

	query := s.db.Where(
		"transaction_type = ? AND min_amount <= ? AND max_amount >= ? AND is_active = true",
		transactionType, amount, amount,
	).Order("priority DESC, agent_tier DESC")

	if err := query.Find(&rules).Error; err != nil {
		return nil, err
	}

	// Find tier-specific rule first, then general rule
	for _, rule := range rules {
		if rule.AgentTier == agentInfo.Tier {
			return &rule, nil
		}
	}

	// Return first general rule (no tier specified)
	for _, rule := range rules {
		if rule.AgentTier == "" {
			return &rule, nil
		}
	}

	return nil, fmt.Errorf("no applicable rule found")
}

func (s *CommissionService) getAgentInfo(agentID uuid.UUID) (*AgentInfo, error) {
	// This would typically call the agent service
	// For now, return a mock response
	return &AgentInfo{
		ID:   agentID,
		Tier: "bronze",
	}, nil
}

func (s *CommissionService) updateAgentBalance(agentID uuid.UUID, agentName string, amount float64, status string) error {
	var balance AgentBalance

	err := s.db.Where("agent_id = ?", agentID).First(&balance).Error
	if err == gorm.ErrRecordNotFound {
		// Create new balance record
		balance = AgentBalance{
			AgentID:   agentID,
			AgentName: agentName,
			Currency:  "NGN",
		}
		if status == "pending" {
			balance.PendingBalance = amount
		}
		balance.TotalEarned = amount
		return s.db.Create(&balance).Error
	} else if err != nil {
		return err
	}

	// Update existing balance
	updates := map[string]interface{}{
		"agent_name":   agentName,
		"total_earned": gorm.Expr("total_earned + ?", amount),
		"updated_at":   time.Now(),
	}

	if status == "pending" {
		updates["pending_balance"] = gorm.Expr("pending_balance + ?", amount)
	} else if status == "available" {
		updates["available_balance"] = gorm.Expr("available_balance + ?", amount)
	}

	return s.db.Model(&balance).Updates(updates).Error
}

func (s *CommissionService) CreateSettlement(req CreateSettlementRequest) (*Settlement, error) {
	agentID, err := uuid.Parse(req.AgentID)
	if err != nil {
		return nil, fmt.Errorf("invalid agent ID")
	}

	periodStart, err := time.Parse("2006-01-02", req.PeriodStart)
	if err != nil {
		return nil, fmt.Errorf("invalid period_start format, expected YYYY-MM-DD")
	}

	periodEnd, err := time.Parse("2006-01-02", req.PeriodEnd)
	if err != nil {
		return nil, fmt.Errorf("invalid period_end format, expected YYYY-MM-DD")
	}

	// Get agent name and validate balance
	var balance AgentBalance
	if err := s.db.Where("agent_id = ?", agentID).First(&balance).Error; err != nil {
		return nil, fmt.Errorf("agent balance not found")
	}

	// Get pending commissions for the period
	var commissions []Commission
	if err := s.db.Where(
		"agent_id = ? AND status = 'pending' AND earned_at BETWEEN ? AND ?",
		agentID, periodStart, periodEnd,
	).Find(&commissions).Error; err != nil {
		return nil, fmt.Errorf("failed to get pending commissions")
	}

	if len(commissions) == 0 {
		return nil, fmt.Errorf("no pending commissions found for the specified period")
	}

	var totalAmount float64
	for _, commission := range commissions {
		totalAmount += commission.CommissionAmount
	}

	settlement := Settlement{
		AgentID:         agentID,
		AgentName:       balance.AgentName,
		SettlementRef:   fmt.Sprintf("SETTLE_%s_%s", agentID.String()[:8], time.Now().Format("20060102150405")),
		TotalAmount:     totalAmount,
		CommissionCount: len(commissions),
		Currency:        balance.Currency,
		Status:          "pending",
		PaymentMethod:   req.PaymentMethod,
		PaymentDetails:  req.PaymentDetails,
		PeriodStart:     periodStart,
		PeriodEnd:       periodEnd,
	}

	if err := s.db.Create(&settlement).Error; err != nil {
		return nil, fmt.Errorf("failed to create settlement: %w", err)
	}

	return &settlement, nil
}

func (s *CommissionService) GetSettlement(id uuid.UUID) (*Settlement, error) {
	var settlement Settlement
	if err := s.db.First(&settlement, "id = ?", id).Error; err != nil {
		return nil, err
	}
	return &settlement, nil
}

func (s *CommissionService) ListSettlements(page, limit int, agentID *uuid.UUID, status SettlementStatus, startDate, endDate *time.Time) ([]Settlement, int64, error) {
	var settlements []Settlement
	var total int64

	query := s.db.Model(&Settlement{})

	if agentID != nil {
		query = query.Where("agent_id = ?", *agentID)
	}
	if status != "" {
		query = query.Where("status = ?", status)
	}
	if startDate != nil {
		query = query.Where("period_start >= ?", *startDate)
	}
	if endDate != nil {
		query = query.Where("period_end <= ?", *endDate)
	}

	query.Count(&total)

	offset := (page - 1) * limit
	if err := query.Offset(offset).Limit(limit).Order("created_at DESC").Find(&settlements).Error; err != nil {
		return nil, 0, err
	}

	return settlements, total, nil
}

func (s *CommissionService) UpdateSettlement(id uuid.UUID, req UpdateSettlementRequest) (*Settlement, error) {
	var settlement Settlement
	if err := s.db.First(&settlement, "id = ?", id).Error; err != nil {
		return nil, fmt.Errorf("settlement not found")
	}

	updates := map[string]interface{}{
		"updated_at": time.Now(),
	}

	if req.Status != "" {
		updates["status"] = req.Status
		if req.Status == "completed" {
			now := time.Now()
			updates["processed_at"] = &now

			// Update commission statuses and agent balances
			if err := s.processSettlementCommissions(&settlement); err != nil {
				return nil, fmt.Errorf("failed to process settlement commissions: %w", err)
			}
		}
	}

	if req.FailureReason != "" {
		updates["failure_reason"] = req.FailureReason
	}

	if err := s.db.Model(&settlement).Updates(updates).Error; err != nil {
		return nil, fmt.Errorf("failed to update settlement: %w", err)
	}

	return &settlement, nil
}

func (s *CommissionService) ProcessSettlement(id uuid.UUID) error {
	var settlement Settlement
	if err := s.db.First(&settlement, "id = ?", id).Error; err != nil {
		return fmt.Errorf("settlement not found")
	}

	if settlement.Status != "pending" {
		return fmt.Errorf("settlement is not in pending status")
	}

	// Process payment based on payment method
	switch settlement.PaymentMethod {
	case "bank_transfer":
		return s.processBankTransfer(&settlement)
	case "wallet_credit":
		return s.processWalletCredit(&settlement)
	case "cash_pickup":
		return s.processCashPickup(&settlement)
	default:
		return fmt.Errorf("unsupported payment method")
	}
}

func (s *CommissionService) processBankTransfer(settlement *Settlement) error {
	// In a real implementation, this would integrate with banking APIs
	// For now, simulate processing

	// Simulate success (90% success rate)
	if time.Now().Unix()%10 != 0 {
		settlement.Status = "completed"
		now := time.Now()
		settlement.ProcessedAt = &now

		if err := s.db.Save(settlement).Error; err != nil {
			return err
		}

		return s.processSettlementCommissions(settlement)
	}

	settlement.Status = "failed"
	settlement.FailureReason = "Bank transfer failed - insufficient funds"
	return s.db.Save(settlement).Error
}

func (s *CommissionService) processWalletCredit(settlement *Settlement) error {
	// Credit agent's wallet
	if err := s.updateAgentBalance(settlement.AgentID, settlement.AgentName, settlement.TotalAmount, "available"); err != nil {
		settlement.Status = "failed"
		settlement.FailureReason = "Failed to credit wallet"
		s.db.Save(settlement)
		return err
	}

	settlement.Status = "completed"
	now := time.Now()
	settlement.ProcessedAt = &now

	if err := s.db.Save(settlement).Error; err != nil {
		return err
	}

	return s.processSettlementCommissions(settlement)
}

func (s *CommissionService) processCashPickup(settlement *Settlement) error {
	// Mark as pending for manual processing
	settlement.Status = "pending"
	settlement.FailureReason = "Awaiting manual cash pickup processing"
	return s.db.Save(settlement).Error
}

func (s *CommissionService) processSettlementCommissions(settlement *Settlement) error {
	// Update all commissions in this settlement to settled
	if err := s.db.Model(&Commission{}).
		Where("agent_id = ? AND status = 'pending' AND earned_at BETWEEN ? AND ?",
			settlement.AgentID, settlement.PeriodStart, settlement.PeriodEnd).
		Updates(map[string]interface{}{
			"status":        "settled",
			"settled_at":    time.Now(),
			"settlement_id": settlement.ID,
		}).Error; err != nil {
		return err
	}

	// Update agent balances
	if err := s.db.Model(&AgentBalance{}).
		Where("agent_id = ?", settlement.AgentID).
		Updates(map[string]interface{}{
			"pending_balance":     gorm.Expr("GREATEST(pending_balance - ?, 0)", settlement.TotalAmount),
			"settled_balance":     gorm.Expr("settled_balance + ?", settlement.TotalAmount),
			"last_settlement_at":  time.Now(),
			"updated_at":          time.Now(),
		}).Error; err != nil {
		return err
	}

	return nil
}

func (s *CommissionService) GetAgentBalance(agentID uuid.UUID) (*AgentBalance, error) {
	var balance AgentBalance
	if err := s.db.Where("agent_id = ?", agentID).First(&balance).Error; err != nil {
		return nil, err
	}
	return &balance, nil
}

func (s *CommissionService) ListAgentBalances(page, limit int) ([]AgentBalance, int64, error) {
	var balances []AgentBalance
	var total int64

	s.db.Model(&AgentBalance{}).Count(&total)

	offset := (page - 1) * limit
	if err := s.db.Offset(offset).Limit(limit).Order("total_earned DESC").Find(&balances).Error; err != nil {
		return nil, 0, err
	}

	return balances, total, nil
}

func (s *CommissionService) ListCommissionRules(activeOnly bool) ([]CommissionRule, error) {
	var rules []CommissionRule
	query := s.db.Order("priority DESC, created_at DESC")

	if activeOnly {
		query = query.Where("is_active = true")
	}

	if err := query.Find(&rules).Error; err != nil {
		return nil, err
	}

	return rules, nil
}

func (s *CommissionService) GetCommissionRule(id uuid.UUID) (*CommissionRule, error) {
	var rule CommissionRule
	if err := s.db.First(&rule, "id = ?", id).Error; err != nil {
		return nil, err
	}
	return &rule, nil
}

func (s *CommissionService) CreateCommissionRule(req CreateCommissionRuleRequest) (*CommissionRule, error) {
	rule := CommissionRule{
		Name:            req.Name,
		TransactionType: req.TransactionType,
		MinAmount:       req.MinAmount,
		MaxAmount:       req.MaxAmount,
		Rate:            req.Rate,
		RateType:        req.RateType,
		AgentTier:       req.AgentTier,
		IsActive:        true,
		Priority:        req.Priority,
		FlatFee:         req.FlatFee,
	}

	if err := s.db.Create(&rule).Error; err != nil {
		return nil, fmt.Errorf("failed to create commission rule: %w", err)
	}

	return &rule, nil
}

func (s *CommissionService) UpdateCommissionRule(id uuid.UUID, req UpdateCommissionRuleRequest) (*CommissionRule, error) {
	var rule CommissionRule
	if err := s.db.First(&rule, "id = ?", id).Error; err != nil {
		return nil, fmt.Errorf("commission rule not found")
	}

	updates := map[string]interface{}{
		"updated_at": time.Now(),
	}

	if req.Name != nil {
		updates["name"] = *req.Name
	}
	if req.MinAmount != nil {
		updates["min_amount"] = *req.MinAmount
	}
	if req.MaxAmount != nil {
		updates["max_amount"] = *req.MaxAmount
	}
	if req.Rate != nil {
		updates["rate"] = *req.Rate
	}
	if req.AgentTier != nil {
		updates["agent_tier"] = *req.AgentTier
	}
	if req.IsActive != nil {
		updates["is_active"] = *req.IsActive
	}
	if req.Priority != nil {
		updates["priority"] = *req.Priority
	}
	if req.FlatFee != nil {
		updates["flat_fee"] = *req.FlatFee
	}

	if err := s.db.Model(&rule).Updates(updates).Error; err != nil {
		return nil, fmt.Errorf("failed to update commission rule: %w", err)
	}

	return &rule, nil
}

func (s *CommissionService) DeleteCommissionRule(id uuid.UUID) error {
	// Soft delete by deactivating
	return s.db.Model(&CommissionRule{}).Where("id = ?", id).Update("is_active", false).Error
}

func (s *CommissionService) GetCommission(id uuid.UUID) (*Commission, error) {
	var commission Commission
	if err := s.db.First(&commission, "id = ?", id).Error; err != nil {
		return nil, err
	}
	return &commission, nil
}

func (s *CommissionService) ListCommissions(page, limit int, agentID *uuid.UUID, status CommissionStatus, startDate, endDate *time.Time) ([]Commission, int64, error) {
	var commissions []Commission
	var total int64

	query := s.db.Model(&Commission{})

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

	query.Count(&total)

	offset := (page - 1) * limit
	if err := query.Offset(offset).Limit(limit).Order("earned_at DESC").Find(&commissions).Error; err != nil {
		return nil, 0, err
	}

	return commissions, total, nil
}

// GetPolicy returns the platform settlement policy, creating a default one if absent
func (s *CommissionService) GetPolicy() (*SettlementPolicy, error) {
	var policy SettlementPolicy
	err := s.db.First(&policy).Error
	if err == gorm.ErrRecordNotFound {
		policy = SettlementPolicy{AutoProcessOnEod: false, MinWithdrawalAmount: 0, AllowAgentWithdrawal: true}
		if err := s.db.Create(&policy).Error; err != nil {
			return nil, fmt.Errorf("failed to create default policy: %w", err)
		}
		return &policy, nil
	}
	if err != nil {
		return nil, err
	}
	return &policy, nil
}

// UpdatePolicy applies partial updates to the settlement policy
func (s *CommissionService) UpdatePolicy(updates map[string]interface{}) (*SettlementPolicy, error) {
	policy, err := s.GetPolicy()
	if err != nil {
		return nil, err
	}
	allowed := map[string]bool{"auto_process_on_eod": true, "min_withdrawal_amount": true, "allow_agent_withdrawal": true}
	filtered := map[string]interface{}{"updated_at": time.Now()}
	for k, v := range updates {
		if allowed[k] {
			filtered[k] = v
		}
	}
	if err := s.db.Model(policy).Updates(filtered).Error; err != nil {
		return nil, fmt.Errorf("failed to update policy: %w", err)
	}
	return policy, nil
}

// RunEod creates (and optionally processes) settlements for all agents with pending commissions
func (s *CommissionService) RunEod() (*EodRunResult, error) {
	result := &EodRunResult{
		Succeeded: []EodAgentResult{},
		Failed:    []EodAgentResult{},
	}

	// Find all agents with pending commissions
	var balances []AgentBalance
	if err := s.db.Where("pending_balance > 0").Find(&balances).Error; err != nil {
		return nil, fmt.Errorf("failed to list agent balances: %w", err)
	}

	policy, _ := s.GetPolicy()
	now := time.Now()

	for _, bal := range balances {
		agentResult := EodAgentResult{AgentID: bal.AgentID.String()}

		settlement, err := s.CreateSettlement(CreateSettlementRequest{
			AgentID:       bal.AgentID.String(),
			PaymentMethod: "wallet_credit",
			PeriodStart:   now.AddDate(0, 0, -30).Format("2006-01-02"),
			PeriodEnd:     now.Format("2006-01-02"),
		})
		if err != nil {
			agentResult.Error = err.Error()
			result.Failed = append(result.Failed, agentResult)
			continue
		}

		agentResult.SettlementID = settlement.ID.String()
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
		// NF-SEC-6: no hardcoded DSN/credential fallback — fail closed.
		log.Fatal("DATABASE_URL environment variable must be set")
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
