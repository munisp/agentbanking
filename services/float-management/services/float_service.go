package services

import (
	"errors"
	"fmt"
	"time"
	"context"
	"encoding/json"
	"net/http"
	"bytes"

	"github.com/google/uuid"
	"gorm.io/gorm"
	"github.com/redis/go-redis/v9"
	
	"remittance/float-management/models"
)

// FloatService handles all float-related operations
type FloatService struct {
	db           *gorm.DB
	redis        *redis.Client
	riskEngine   *RiskEngineClient
	settlement   *SettlementEngineClient
	config       *FloatConfig
}

// DB returns the underlying gorm.DB so handlers can run ad-hoc queries.
func (s *FloatService) DB() *gorm.DB { return s.db }

// FloatConfig holds configuration for float operations
type FloatConfig struct {
	DefaultInterestRate    float64
	DefaultFeeRate        float64
	MaxFloatLimit         float64
	MinCreditScore        float64
	DefaultSettlementDays int
	RiskEngineURL         string
	SettlementEngineURL   string
}

// RiskEngineClient for communicating with Python risk engine
type RiskEngineClient struct {
	BaseURL    string
	HTTPClient *http.Client
}

// SettlementEngineClient for communicating with Python settlement engine
type SettlementEngineClient struct {
	BaseURL    string
	HTTPClient *http.Client
}

// NewFloatService creates a new float service instance
func NewFloatService(db *gorm.DB, redis *redis.Client, config *FloatConfig) *FloatService {
	riskEngine := &RiskEngineClient{
		BaseURL:    config.RiskEngineURL,
		HTTPClient: &http.Client{Timeout: 30 * time.Second},
	}
	
	settlement := &SettlementEngineClient{
		BaseURL:    config.SettlementEngineURL,
		HTTPClient: &http.Client{Timeout: 30 * time.Second},
	}
	
	return &FloatService{
		db:         db,
		redis:      redis,
		riskEngine: riskEngine,
		settlement: settlement,
		config:     config,
	}
}

// ==========================================
// FLOAT FACILITY MANAGEMENT
// ==========================================

// CreateFloatFacility creates a new float facility for an agent
func (s *FloatService) CreateFloatFacility(ctx context.Context, req CreateFloatRequest) (*models.AgentFloat, error) {
	// Validate agent eligibility
	if err := s.validateAgentEligibility(ctx, req.AgentID); err != nil {
		return nil, fmt.Errorf("agent eligibility validation failed: %w", err)
	}
	
	// Check if float facility already exists
	var existingFloat models.AgentFloat
	if err := s.db.Where("agent_id = ?", req.AgentID).First(&existingFloat).Error; err == nil {
		return nil, errors.New("float facility already exists for this agent")
	}
	
	// Perform risk assessment
	assessment, err := s.performRiskAssessment(ctx, req.AgentID, "initial")
	if err != nil {
		return nil, fmt.Errorf("risk assessment failed: %w", err)
	}
	
	// Determine float limit based on risk assessment
	floatLimit := s.calculateInitialFloatLimit(assessment, req.AgentTier)
	
	// Create float facility
	agentFloat := &models.AgentFloat{
		AgentID:               req.AgentID,
		AgentTier:             req.AgentTier,
		FloatLimit:            floatLimit,
		UtilizedAmount:        0,
		AvailableFloat:        floatLimit,
		InterestRate:          s.getInterestRateByRisk(assessment.RiskLevel),
		FeeRate:               s.config.DefaultFeeRate,
		Currency:              req.Currency,
		Status:                models.FloatStatusPending,
		RiskLevel:             assessment.RiskLevel,
		CreditScore:           assessment.OverallScore,
		LastAssessmentDate:    &assessment.AssessmentDate,
		NextAssessmentDate:    s.calculateNextAssessmentDate(assessment.AssessmentDate),
		SettlementFrequency:   req.SettlementFrequency,
		AutoSettlement:        req.AutoSettlement,
		CollateralRequired:    assessment.OverallScore < 60,
		GuarantorRequired:     assessment.OverallScore < 50,
		MaxDaysOutstanding:    s.getMaxDaysOutstanding(assessment.RiskLevel),
		CreatedBy:             &req.CreatedBy,
	}
	
	// Start database transaction
	tx := s.db.Begin()
	
	// Create float facility
	if err := tx.Create(agentFloat).Error; err != nil {
		tx.Rollback()
		return nil, fmt.Errorf("failed to create float facility: %w", err)
	}
	
	// Create initial risk assessment record
	assessment.AgentFloatID = agentFloat.ID
	if err := tx.Create(assessment).Error; err != nil {
		tx.Rollback()
		return nil, fmt.Errorf("failed to create risk assessment: %w", err)
	}
	
	// Create initial float limit record
	limitRecord := &models.FloatLimit{
		AgentFloatID:    agentFloat.ID,
		AgentID:         req.AgentID,
		AgentTier:       req.AgentTier,
		BaseLimit:       floatLimit,
		AdjustedLimit:   floatLimit,
		AvailableLimit:  floatLimit,
		EffectiveFrom:   time.Now(),
		IsActive:        true,
	}

	if err := tx.Create(limitRecord).Error; err != nil {
		tx.Rollback()
		return nil, fmt.Errorf("failed to create float limit: %w", err)
	}
	
	tx.Commit()
	
	// Cache float facility
	s.cacheFloatFacility(ctx, agentFloat)
	
	// Create alert for new facility
	s.createAlert(ctx, agentFloat.ID, "facility_created", "info", 
		"New float facility created", nil, nil)
	
	return agentFloat, nil
}

// ApproveFloatFacility approves a pending float facility
func (s *FloatService) ApproveFloatFacility(ctx context.Context, floatID uuid.UUID, approvedBy uuid.UUID) error {
	var agentFloat models.AgentFloat
	if err := s.db.First(&agentFloat, floatID).Error; err != nil {
		return fmt.Errorf("float facility not found: %w", err)
	}
	
	if agentFloat.Status != models.FloatStatusPending {
		return errors.New("float facility is not in pending status")
	}
	
	// Update status to active
	now := time.Now()
	updates := map[string]interface{}{
		"status":       models.FloatStatusActive,
		"approved_by":  approvedBy,
		"approved_at":  &now,
		"activated_at": &now,
		"updated_at":   now,
	}
	
	if err := s.db.Model(&agentFloat).Updates(updates).Error; err != nil {
		return fmt.Errorf("failed to approve float facility: %w", err)
	}
	
	// Update cache
	agentFloat.Status = models.FloatStatusActive
	agentFloat.ApprovedBy = &approvedBy
	agentFloat.ApprovedAt = &now
	agentFloat.ActivatedAt = &now
	s.cacheFloatFacility(ctx, &agentFloat)
	
	// Create approval transaction
	s.createFloatTransaction(ctx, &agentFloat, models.FloatTransactionAdvance, 
		agentFloat.FloatLimit, "Float facility approved and activated", &approvedBy)
	
	// Create alert
	s.createAlert(ctx, agentFloat.ID, "facility_approved", "info", 
		"Float facility approved and activated", nil, nil)
	
	return nil
}

// ==========================================
// FLOAT UTILIZATION
// ==========================================

// UtilizeFloat utilizes float for a transaction
func (s *FloatService) UtilizeFloat(ctx context.Context, agentID uuid.UUID, amount float64, 
	transactionID uuid.UUID, description string) error {
	
	// Get float facility
	agentFloat, err := s.getFloatFacility(ctx, agentID)
	if err != nil {
		return fmt.Errorf("failed to get float facility: %w", err)
	}
	
	// Validate utilization
	if err := s.validateFloatUtilization(agentFloat, amount); err != nil {
		return fmt.Errorf("float utilization validation failed: %w", err)
	}
	
	// Start transaction
	tx := s.db.Begin()
	
	// Update float utilization
	newUtilized := agentFloat.UtilizedAmount + amount
	newAvailable := agentFloat.FloatLimit - newUtilized - agentFloat.ReservedAmount
	
	updates := map[string]interface{}{
		"utilized_amount": newUtilized,
		"available_float": newAvailable,
		"updated_at":      time.Now(),
	}
	
	if err := tx.Model(&agentFloat).Where("id = ?", agentFloat.ID).Updates(updates).Error; err != nil {
		tx.Rollback()
		return fmt.Errorf("failed to update float utilization: %w", err)
	}
	
	// Create transaction record
	floatTxn := &models.FloatTransaction{
		AgentFloatID:    agentFloat.ID,
		AgentID:         agentID,
		RelatedTxnID:    &transactionID,
		Type:            models.FloatTransactionUtilization,
		Amount:          amount,
		Currency:        agentFloat.Currency,
		FloatBefore:     agentFloat.AvailableFloat,
		FloatAfter:      newAvailable,
		UtilizedBefore:  agentFloat.UtilizedAmount,
		UtilizedAfter:   newUtilized,
		AvailableBefore: agentFloat.AvailableFloat,
		AvailableAfter:  newAvailable,
		Description:     description,
		Status:          "completed",
		ProcessedAt:     time.Now(),
	}
	
	if err := tx.Create(floatTxn).Error; err != nil {
		tx.Rollback()
		return fmt.Errorf("failed to create float transaction: %w", err)
	}
	
	tx.Commit()
	
	// Update cache
	agentFloat.UtilizedAmount = newUtilized
	agentFloat.AvailableFloat = newAvailable
	s.cacheFloatFacility(ctx, agentFloat)
	
	// Check for alerts
	s.checkUtilizationAlerts(ctx, agentFloat)
	
	return nil
}

// SettleFloat settles outstanding float amount
func (s *FloatService) SettleFloat(ctx context.Context, agentID uuid.UUID, amount float64, 
	paymentRef string, settledBy uuid.UUID) error {
	
	// Get float facility
	agentFloat, err := s.getFloatFacility(ctx, agentID)
	if err != nil {
		return fmt.Errorf("failed to get float facility: %w", err)
	}
	
	if agentFloat.UtilizedAmount == 0 {
		return errors.New("no outstanding float to settle")
	}
	
	// Calculate settlement amount (cannot exceed utilized amount)
	settlementAmount := amount
	if settlementAmount > agentFloat.UtilizedAmount {
		settlementAmount = agentFloat.UtilizedAmount
	}
	
	// Start transaction
	tx := s.db.Begin()
	
	// Update float utilization
	newUtilized := agentFloat.UtilizedAmount - settlementAmount
	newAvailable := agentFloat.FloatLimit - newUtilized - agentFloat.ReservedAmount
	
	updates := map[string]interface{}{
		"utilized_amount":        newUtilized,
		"available_float":        newAvailable,
		"last_settlement_date":   time.Now(),
		"total_settlements":      gorm.Expr("total_settlements + 1"),
		"successful_settlements": gorm.Expr("successful_settlements + 1"),
		"days_outstanding":       0,
		"updated_at":             time.Now(),
	}
	
	if err := tx.Model(&agentFloat).Where("id = ?", agentFloat.ID).Updates(updates).Error; err != nil {
		tx.Rollback()
		return fmt.Errorf("failed to update float settlement: %w", err)
	}
	
	// Create settlement transaction
	floatTxn := &models.FloatTransaction{
		AgentFloatID:    agentFloat.ID,
		AgentID:         agentID,
		Type:            models.FloatTransactionSettlement,
		Amount:          settlementAmount,
		Currency:        agentFloat.Currency,
		FloatBefore:     agentFloat.AvailableFloat,
		FloatAfter:      newAvailable,
		UtilizedBefore:  agentFloat.UtilizedAmount,
		UtilizedAfter:   newUtilized,
		AvailableBefore: agentFloat.AvailableFloat,
		AvailableAfter:  newAvailable,
		Description:     fmt.Sprintf("Float settlement - Payment Ref: %s", paymentRef),
		Status:          "completed",
		ProcessedBy:     &settledBy,
		ProcessedAt:     time.Now(),
		Metadata:        models.JSON{"payment_reference": paymentRef},
	}
	
	if err := tx.Create(floatTxn).Error; err != nil {
		tx.Rollback()
		return fmt.Errorf("failed to create settlement transaction: %w", err)
	}
	
	tx.Commit()
	
	// Update cache
	agentFloat.UtilizedAmount = newUtilized
	agentFloat.AvailableFloat = newAvailable
	agentFloat.TotalSettlements++
	agentFloat.SuccessfulSettlements++
	s.cacheFloatFacility(ctx, agentFloat)
	
	// Create alert for successful settlement
	s.createAlert(ctx, agentFloat.ID, "settlement_completed", "info", 
		fmt.Sprintf("Float settlement completed: %s %.2f", agentFloat.Currency, settlementAmount), 
		&settlementAmount, nil)
	
	return nil
}

// ==========================================
// RISK ASSESSMENT
// ==========================================

// PerformRiskAssessment performs comprehensive risk assessment
func (s *FloatService) performRiskAssessment(ctx context.Context, agentID uuid.UUID, 
	assessmentType string) (*models.RiskAssessment, error) {
	
	// Call Python risk engine
	riskData, err := s.callRiskEngine(ctx, agentID, assessmentType)
	if err != nil {
		return nil, fmt.Errorf("risk engine call failed: %w", err)
	}
	
	// Create risk assessment record
	assessment := &models.RiskAssessment{
		AgentID:                   agentID,
		AssessmentType:            assessmentType,
		OverallScore:              riskData.OverallScore,
		CreditScore:               riskData.CreditScore,
		TransactionVolumeScore:    riskData.TransactionVolumeScore,
		SettlementHistoryScore:    riskData.SettlementHistoryScore,
		BusinessStabilityScore:    riskData.BusinessStabilityScore,
		GeographicRiskScore:       riskData.GeographicRiskScore,
		KYCComplianceScore:        riskData.KYCComplianceScore,
		FinancialHealthScore:      riskData.FinancialHealthScore,
		BehavioralScore:           riskData.BehavioralScore,
		RiskLevel:                 s.determineRiskLevel(riskData.OverallScore),
		RecommendedLimit:          s.calculateRecommendedLimit(riskData),
		RiskFactors:               riskData.RiskFactors,
		PositiveFactors:           riskData.PositiveFactors,
		Recommendations:           riskData.Recommendations,
		ModelVersion:              riskData.ModelVersion,
		AssessmentDate:            time.Now(),
		ValidUntil:                time.Now().AddDate(0, 3, 0), // Valid for 3 months
	}
	
	return assessment, nil
}

// UpdateFloatLimit updates float limit based on risk assessment
func (s *FloatService) UpdateFloatLimit(ctx context.Context, floatID uuid.UUID, 
	newLimit float64, reason string, updatedBy uuid.UUID) error {
	
	var agentFloat models.AgentFloat
	if err := s.db.First(&agentFloat, floatID).Error; err != nil {
		return fmt.Errorf("float facility not found: %w", err)
	}
	
	// Validate new limit
	if newLimit < agentFloat.UtilizedAmount {
		return errors.New("new limit cannot be less than utilized amount")
	}
	
	// Start transaction
	tx := s.db.Begin()
	
	// Update float limit
	oldLimit := agentFloat.FloatLimit
	newAvailable := newLimit - agentFloat.UtilizedAmount - agentFloat.ReservedAmount
	
	updates := map[string]interface{}{
		"float_limit":     newLimit,
		"available_float": newAvailable,
		"updated_at":      time.Now(),
		"updated_by":      updatedBy,
	}
	
	if err := tx.Model(&agentFloat).Where("id = ?", floatID).Updates(updates).Error; err != nil {
		tx.Rollback()
		return fmt.Errorf("failed to update float limit: %w", err)
	}
	
	// Create limit adjustment record
	limitRecord := &models.FloatLimit{
		AgentFloatID:     floatID,
		AgentID:          agentFloat.AgentID,
		AgentTier:        agentFloat.AgentTier,
		BaseLimit:        oldLimit,
		AdjustedLimit:    newLimit,
		AvailableLimit:   newAvailable,
		EffectiveFrom:    time.Now(),
		IsActive:         true,
		AdjustmentReason: reason,
		AdjustedBy:       &updatedBy,
		AdjustedAt:       &time.Time{},
	}
	
	if err := tx.Create(limitRecord).Error; err != nil {
		tx.Rollback()
		return fmt.Errorf("failed to create limit record: %w", err)
	}
	
	// Create adjustment transaction
	adjustmentAmount := newLimit - oldLimit
	floatTxn := &models.FloatTransaction{
		AgentFloatID:    floatID,
		AgentID:         agentFloat.AgentID,
		Type:            models.FloatTransactionAdjustment,
		Amount:          adjustmentAmount,
		Currency:        agentFloat.Currency,
		FloatBefore:     oldLimit,
		FloatAfter:      newLimit,
		UtilizedBefore:  agentFloat.UtilizedAmount,
		UtilizedAfter:   agentFloat.UtilizedAmount,
		AvailableBefore: agentFloat.AvailableFloat,
		AvailableAfter:  newAvailable,
		Description:     fmt.Sprintf("Float limit adjustment: %s", reason),
		Status:          "completed",
		ProcessedBy:     &updatedBy,
		ProcessedAt:     time.Now(),
	}
	
	if err := tx.Create(floatTxn).Error; err != nil {
		tx.Rollback()
		return fmt.Errorf("failed to create adjustment transaction: %w", err)
	}
	
	tx.Commit()
	
	// Update cache
	agentFloat.FloatLimit = newLimit
	agentFloat.AvailableFloat = newAvailable
	s.cacheFloatFacility(ctx, &agentFloat)
	
	// Create alert
	alertType := "limit_increased"
	if adjustmentAmount < 0 {
		alertType = "limit_decreased"
	}
	
	s.createAlert(ctx, floatID, alertType, "info", 
		fmt.Sprintf("Float limit adjusted from %.2f to %.2f: %s", 
			oldLimit, newLimit, reason), &newLimit, &oldLimit)
	
	return nil
}

// ==========================================
// HELPER FUNCTIONS
// ==========================================

// validateAgentEligibility validates if agent is eligible for float facility
func (s *FloatService) validateAgentEligibility(ctx context.Context, agentID uuid.UUID) error {
	// Check if agent exists and is active
	// Check KYC status
	// Check minimum operational period
	// Check transaction history
	// This would integrate with existing agent management service
	return nil
}

// validateFloatUtilization validates float utilization request
func (s *FloatService) validateFloatUtilization(agentFloat *models.AgentFloat, amount float64) error {
	if agentFloat.Status != models.FloatStatusActive {
		return errors.New("float facility is not active")
	}
	
	if amount <= 0 {
		return errors.New("utilization amount must be positive")
	}
	
	if amount > agentFloat.AvailableFloat {
		return fmt.Errorf("insufficient float available: %.2f requested, %.2f available", 
			amount, agentFloat.AvailableFloat)
	}
	
	return nil
}

// getFloatFacility retrieves float facility from cache or database
func (s *FloatService) getFloatFacility(ctx context.Context, agentID uuid.UUID) (*models.AgentFloat, error) {
	// Try cache first
	cacheKey := fmt.Sprintf("float:agent:%s", agentID.String())
	cached, err := s.redis.Get(ctx, cacheKey).Result()
	if err == nil {
		var agentFloat models.AgentFloat
		if err := json.Unmarshal([]byte(cached), &agentFloat); err == nil {
			return &agentFloat, nil
		}
	}
	
	// Fallback to database
	var agentFloat models.AgentFloat
	if err := s.db.Where("agent_id = ?", agentID).First(&agentFloat).Error; err != nil {
		return nil, fmt.Errorf("float facility not found: %w", err)
	}
	
	// Cache for future use
	s.cacheFloatFacility(ctx, &agentFloat)
	
	return &agentFloat, nil
}

// cacheFloatFacility caches float facility data
func (s *FloatService) cacheFloatFacility(ctx context.Context, agentFloat *models.AgentFloat) {
	cacheKey := fmt.Sprintf("float:agent:%s", agentFloat.AgentID.String())
	data, _ := json.Marshal(agentFloat)
	s.redis.Set(ctx, cacheKey, data, 15*time.Minute)
}

// calculateInitialFloatLimit calculates initial float limit based on risk assessment
func (s *FloatService) calculateInitialFloatLimit(assessment *models.RiskAssessment, tier models.AgentTier) float64 {
	baseLimit := s.getBaseLimitByTier(tier)
	riskMultiplier := s.getRiskMultiplier(assessment.RiskLevel)
	scoreMultiplier := assessment.OverallScore / 100.0
	
	return baseLimit * riskMultiplier * scoreMultiplier
}

// getBaseLimitByTier returns base limit by agent tier
func (s *FloatService) getBaseLimitByTier(tier models.AgentTier) float64 {
	switch tier {
	case models.AgentTierBasic:
		return 100000 // ₦100,000
	case models.AgentTierStandard:
		return 500000 // ₦500,000
	case models.AgentTierPremium:
		return 1000000 // ₦1,000,000
	case models.AgentTierElite:
		return 2000000 // ₦2,000,000
	default:
		return 100000
	}
}

// getRiskMultiplier returns risk multiplier based on risk level
func (s *FloatService) getRiskMultiplier(riskLevel models.RiskLevel) float64 {
	switch riskLevel {
	case models.RiskLevelLow:
		return 1.2
	case models.RiskLevelMedium:
		return 1.0
	case models.RiskLevelHigh:
		return 0.7
	case models.RiskLevelCritical:
		return 0.5
	default:
		return 1.0
	}
}

// getInterestRateByRisk returns interest rate based on risk level
func (s *FloatService) getInterestRateByRisk(riskLevel models.RiskLevel) float64 {
	switch riskLevel {
	case models.RiskLevelLow:
		return 0.025 // 2.5%
	case models.RiskLevelMedium:
		return 0.030 // 3.0%
	case models.RiskLevelHigh:
		return 0.040 // 4.0%
	case models.RiskLevelCritical:
		return 0.050 // 5.0%
	default:
		return 0.030
	}
}

// getMaxDaysOutstanding returns max days outstanding based on risk level
func (s *FloatService) getMaxDaysOutstanding(riskLevel models.RiskLevel) int {
	switch riskLevel {
	case models.RiskLevelLow:
		return 14
	case models.RiskLevelMedium:
		return 7
	case models.RiskLevelHigh:
		return 3
	case models.RiskLevelCritical:
		return 1
	default:
		return 7
	}
}

// determineRiskLevel determines risk level based on overall score
func (s *FloatService) determineRiskLevel(score float64) models.RiskLevel {
	if score >= 80 {
		return models.RiskLevelLow
	} else if score >= 60 {
		return models.RiskLevelMedium
	} else if score >= 40 {
		return models.RiskLevelHigh
	} else {
		return models.RiskLevelCritical
	}
}

// calculateNextAssessmentDate calculates next assessment date
func (s *FloatService) calculateNextAssessmentDate(lastAssessment time.Time) *time.Time {
	next := lastAssessment.AddDate(0, 3, 0) // 3 months
	return &next
}

// createFloatTransaction creates a float transaction record
func (s *FloatService) createFloatTransaction(ctx context.Context, agentFloat *models.AgentFloat, 
	txnType models.FloatTransactionType, amount float64, description string, processedBy *uuid.UUID) error {
	
	floatTxn := &models.FloatTransaction{
		AgentFloatID:    agentFloat.ID,
		AgentID:         agentFloat.AgentID,
		Type:            txnType,
		Amount:          amount,
		Currency:        agentFloat.Currency,
		FloatBefore:     agentFloat.AvailableFloat,
		FloatAfter:      agentFloat.AvailableFloat,
		UtilizedBefore:  agentFloat.UtilizedAmount,
		UtilizedAfter:   agentFloat.UtilizedAmount,
		AvailableBefore: agentFloat.AvailableFloat,
		AvailableAfter:  agentFloat.AvailableFloat,
		Description:     description,
		Status:          "completed",
		ProcessedBy:     processedBy,
		ProcessedAt:     time.Now(),
	}
	
	return s.db.Create(floatTxn).Error
}

// createAlert creates a float alert
func (s *FloatService) createAlert(ctx context.Context, floatID uuid.UUID, alertType, severity, 
	message string, triggerValue, thresholdValue *float64) error {
	
	var agentFloat models.AgentFloat
	if err := s.db.First(&agentFloat, floatID).Error; err != nil {
		return err
	}
	
	alert := &models.FloatAlert{
		AgentFloatID:   floatID,
		AgentID:        agentFloat.AgentID,
		AlertType:      alertType,
		Severity:       severity,
		Title:          fmt.Sprintf("Float Alert: %s", alertType),
		Message:        message,
		TriggerValue:   triggerValue,
		ThresholdValue: thresholdValue,
		Currency:       agentFloat.Currency,
		Status:         "active",
	}
	
	return s.db.Create(alert).Error
}

// checkUtilizationAlerts checks for utilization-based alerts
func (s *FloatService) checkUtilizationAlerts(ctx context.Context, agentFloat *models.AgentFloat) {
	utilizationRate := (agentFloat.UtilizedAmount / agentFloat.FloatLimit) * 100
	
	if utilizationRate >= 90 {
		s.createAlert(ctx, agentFloat.ID, "high_utilization", "high", 
			fmt.Sprintf("Float utilization is %.1f%%", utilizationRate), 
			&utilizationRate, &[]float64{90}[0])
	} else if utilizationRate >= 75 {
		s.createAlert(ctx, agentFloat.ID, "medium_utilization", "medium", 
			fmt.Sprintf("Float utilization is %.1f%%", utilizationRate), 
			&utilizationRate, &[]float64{75}[0])
	}
}

// Request/Response structures
type CreateFloatRequest struct {
	AgentID             uuid.UUID         `json:"agent_id" binding:"required"`
	AgentTier           models.AgentTier  `json:"agent_tier" binding:"required"`
	Currency            string            `json:"currency"`
	SettlementFrequency string            `json:"settlement_frequency"`
	AutoSettlement      bool              `json:"auto_settlement"`
	CreatedBy           uuid.UUID         `json:"created_by" binding:"required"`
}

type RiskEngineResponse struct {
	OverallScore              float64  `json:"overall_score"`
	CreditScore               float64  `json:"credit_score"`
	TransactionVolumeScore    float64  `json:"transaction_volume_score"`
	SettlementHistoryScore    float64  `json:"settlement_history_score"`
	BusinessStabilityScore    float64  `json:"business_stability_score"`
	GeographicRiskScore       float64  `json:"geographic_risk_score"`
	KYCComplianceScore        float64  `json:"kyc_compliance_score"`
	FinancialHealthScore      float64  `json:"financial_health_score"`
	BehavioralScore           float64  `json:"behavioral_score"`
	RiskFactors               []string `json:"risk_factors"`
	PositiveFactors           []string `json:"positive_factors"`
	Recommendations           []string `json:"recommendations"`
	ModelVersion              string   `json:"model_version"`
}

// callRiskEngine calls the Python risk engine
func (s *FloatService) callRiskEngine(ctx context.Context, agentID uuid.UUID, 
	assessmentType string) (*RiskEngineResponse, error) {
	
	requestData := map[string]interface{}{
		"agent_id":        agentID.String(),
		"assessment_type": assessmentType,
	}
	
	jsonData, _ := json.Marshal(requestData)
	
	resp, err := s.riskEngine.HTTPClient.Post(
		s.riskEngine.BaseURL+"/assess-risk",
		"application/json",
		bytes.NewBuffer(jsonData),
	)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	
	var riskResponse RiskEngineResponse
	if err := json.NewDecoder(resp.Body).Decode(&riskResponse); err != nil {
		return nil, err
	}
	
	return &riskResponse, nil
}

// calculateRecommendedLimit calculates recommended limit based on risk data
func (s *FloatService) calculateRecommendedLimit(riskData *RiskEngineResponse) float64 {
	baseLimit := 500000.0 // Base ₦500,000
	scoreMultiplier := riskData.OverallScore / 100.0
	
	// Adjust based on specific scores
	if riskData.TransactionVolumeScore > 80 {
		scoreMultiplier *= 1.2
	}
	if riskData.SettlementHistoryScore > 90 {
		scoreMultiplier *= 1.1
	}
	if riskData.FinancialHealthScore < 50 {
		scoreMultiplier *= 0.8
	}
	
	return baseLimit * scoreMultiplier
}

