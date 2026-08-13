package services

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/google/uuid"
	"gorm.io/gorm"
	"remittance/float-management/models"
)

// EnhancedFloatService provides advanced float management with all integration models
type EnhancedFloatService struct {
	db              *gorm.DB
	tierEngine      *TierEngine
	optInEngine     *OptInEngine
	dynamicEngine   *DynamicEngine
	alertService    *AlertService
	paymentBreaker  *CircuitBreaker
	settlementQueue *QueueService
}

// CircuitBreaker implements circuit breaker pattern for external services
type CircuitBreaker struct {
	maxFailures  int
	resetTimeout time.Duration
	failures     int
	lastFailTime time.Time
	state        string // "closed", "open", "half-open"
}

// QueueService handles asynchronous settlement processing
type QueueService struct {
	db         *gorm.DB
	retryQueue chan uuid.UUID
	maxRetries int
}

// NewEnhancedFloatService creates a new enhanced float service
func NewEnhancedFloatService(db *gorm.DB) *EnhancedFloatService {
	service := &EnhancedFloatService{
		db: db,
		paymentBreaker: &CircuitBreaker{
			maxFailures:  5,
			resetTimeout: 30 * time.Second,
			state:        "closed",
		},
		settlementQueue: &QueueService{
			db:         db,
			retryQueue: make(chan uuid.UUID, 1000),
			maxRetries: 3,
		},
	}

	// Initialize engines
	service.tierEngine = NewTierEngine(db)
	service.optInEngine = NewOptInEngine(db)
	service.dynamicEngine = NewDynamicEngine(db)
	service.alertService = NewAlertService(db)

	// Start background workers
	go service.settlementQueue.processRetries(context.Background())
	go service.runPeriodicAssessments(context.Background())

	return service
}

// ==========================================
// TIERED AGENT SYSTEM
// ==========================================

// TierEngine handles tiered float access

type TierEngine struct {
	db *gorm.DB
}

// NewTierEngine creates a new tier engine
func NewTierEngine(db *gorm.DB) *TierEngine {
	return &TierEngine{db: db}
}

// TierConfig defines tier-specific float configuration
type TierConfig struct {
	Tier                models.AgentTier
	MaxFloatLimit       float64
	DefaultFloatLimit   float64
	UtilizationAlerts   []float64
	SettlementFrequency string
	RequiresApproval    bool
}

// GetTierConfigs returns configuration for all tiers
func (te *TierEngine) GetTierConfigs() map[models.AgentTier]TierConfig {
	return map[models.AgentTier]TierConfig{
		models.TierBasic: {
			Tier:                models.TierBasic,
			MaxFloatLimit:       50000.0, // ₦50k
			DefaultFloatLimit:   25000.0, // ₦25k
			UtilizationAlerts:   []float64{70.0, 85.0, 95.0},
			SettlementFrequency: "daily",
			RequiresApproval:    false,
		},
		models.TierSilver: {
			Tier:                models.TierSilver,
			MaxFloatLimit:       200000.0, // ₦200k
			DefaultFloatLimit:   100000.0, // ₦100k
			UtilizationAlerts:   []float64{75.0, 90.0},
			SettlementFrequency: "daily",
			RequiresApproval:    true,
		},
		models.TierGold: {
			Tier:                models.TierGold,
			MaxFloatLimit:       500000.0, // ₦500k
			DefaultFloatLimit:   300000.0, // ₦300k
			UtilizationAlerts:   []float64{80.0, 90.0},
			SettlementFrequency: "daily",
			RequiresApproval:    true,
		},
		models.TierPlatinum: {
			Tier:                models.TierPlatinum,
			MaxFloatLimit:       1000000.0, // ₦1M
			DefaultFloatLimit:   600000.0, // ₦600k
			UtilizationAlerts:   []float64{85.0, 95.0},
			SettlementFrequency: "daily",
			RequiresApproval:    true,
		},
	}
}

// CreateTieredFloat creates a float facility for a tiered agent
func (te *TierEngine) CreateTieredFloat(ctx context.Context, agentID uuid.UUID, tier models.AgentTier, requestedLimit float64, currency string, createdBy uuid.UUID) (*models.AgentFloat, error) {
	configs := te.GetTierConfigs()
	config, exists := configs[tier]
	if !exists {
		return nil, fmt.Errorf("invalid agent tier: %s", tier)
	}

	// Determine float limit
	floatLimit := config.DefaultFloatLimit
	if requestedLimit > 0 {
		if requestedLimit > config.MaxFloatLimit {
			return nil, fmt.Errorf("requested limit %.2f exceeds tier maximum %.2f", requestedLimit, config.MaxFloatLimit)
		}
		floatLimit = requestedLimit
	}

	// Determine initial status
	status := models.FloatStatusActive
	if config.RequiresApproval {
		status = models.FloatStatusPending
	}

	facility := &models.AgentFloat{
		ID:                  uuid.New(),
		AgentID:             agentID,
		AgentTier:           tier,
		FloatLimit:          floatLimit,
		UtilizedAmount:      0.0,
		AvailableFloat:      floatLimit,
		ReservedAmount:      0.0,
		Status:              status,
		RiskLevel:           models.RiskLevelLow, // Default for new facilities
		UtilizationAlert1:   config.UtilizationAlerts[0],
		SettlementFrequency: config.SettlementFrequency,
		NextSettlementDate:  te.getNextSettlementDate(config.SettlementFrequency),
		Currency:            currency,
		CreatedBy:           createdBy,
	}

	if len(config.UtilizationAlerts) > 1 {
		facility.UtilizationAlert2 = &config.UtilizationAlerts[1]
	}

	if err := te.db.WithContext(ctx).Create(facility).Error; err != nil {
		return nil, fmt.Errorf("failed to create tiered float facility: %w", err)
	}

	return facility, nil
}

func (te *TierEngine) getNextSettlementDate(frequency string) time.Time {
	now := time.Now()
	switch frequency {
	case "daily":
		return time.Date(now.Year(), now.Month(), now.Day()+1, 2, 0, 0, 0, now.Location())
	case "weekly":
		daysUntilMonday := (8 - int(now.Weekday())) % 7
		if daysUntilMonday == 0 {
			daysUntilMonday = 7
		}
		return time.Date(now.Year(), now.Month(), now.Day()+daysUntilMonday, 2, 0, 0, 0, now.Location())
	case "monthly":
		nextMonth := now.AddDate(0, 1, 0)
		return time.Date(nextMonth.Year(), nextMonth.Month(), 1, 2, 0, 0, 0, now.Location())
	default:
		return now.Add(24 * time.Hour)
	}
}

// ==========================================
// OPT-IN FLOAT SYSTEM
// ==========================================

// OptInEngine handles opt-in float access

type OptInEngine struct {
	db *gorm.DB
}

// NewOptInEngine creates a new opt-in engine
func NewOptInEngine(db *gorm.DB) *OptInEngine {
	return &OptInEngine{db: db}
}

// OptInEligibility represents eligibility criteria for opt-in float
type OptInEligibility struct {
	MinTransactionHistory   int     `json:"min_transaction_history"`
	MinMonthlyVolume        float64 `json:"min_monthly_volume"`
	MinSuccessRate          float64 `json:"min_success_rate"`
	MinMonthsActive         int     `json:"min_months_active"`
	MaxChargebackRate       float64 `json:"max_chargeback_rate"`
	RequiredDocuments       []string `json:"required_documents"`
}

// GetOptInEligibility returns eligibility criteria for opt-in float
func (oe *OptInEngine) GetOptInEligibility() OptInEligibility {
	return OptInEligibility{
		MinTransactionHistory: 100,
		MinMonthlyVolume:      500000.0, // ₦500k
		MinSuccessRate:        95.0,
		MinMonthsActive:       3,
		MaxChargebackRate:     2.0,
		RequiredDocuments:     []string{"id_verification", "address_proof", "bank_statement"},
	}
}

// CheckOptInEligibility checks if an agent is eligible for opt-in float
func (oe *OptInEngine) CheckOptInEligibility(ctx context.Context, agentID uuid.UUID) (bool, []string, error) {
	eligibility := oe.GetOptInEligibility()
	var failures []string

	// Check transaction history
	var txCount int64
	if err := oe.db.WithContext(ctx).Model(&models.FloatTransaction{}).
		Where("agent_id = ? AND status = ?", agentID, models.TransactionStatusCompleted).
		Count(&txCount).Error; err != nil {
		return false, nil, fmt.Errorf("failed to check transaction history: %w", err)
	}
	if txCount < int64(eligibility.MinTransactionHistory) {
		failures = append(failures, fmt.Sprintf("Insufficient transaction history: %d < %d", txCount, eligibility.MinTransactionHistory))
	}

	// Check monthly volume (last 3 months)
	threeMonthsAgo := time.Now().AddDate(0, -3, 0)
	var monthlyVolume float64
	if err := oe.db.WithContext(ctx).Model(&models.FloatTransaction{}).
		Select("COALESCE(SUM(amount), 0)").
		Where("agent_id = ? AND type = ? AND status = ? AND created_at > ?",
			agentID, models.TransactionTypeUtilization, models.TransactionStatusCompleted, threeMonthsAgo).
		Row().Scan(&monthlyVolume); err != nil {
		return false, nil, fmt.Errorf("failed to check monthly volume: %w", err)
	}
	if monthlyVolume < eligibility.MinMonthlyVolume {
		failures = append(failures, fmt.Sprintf("Insufficient monthly volume: ₦%.2f < ₦%.2f", monthlyVolume, eligibility.MinMonthlyVolume))
	}

	// Check success rate
	var totalTx, successfulTx int64
	oe.db.WithContext(ctx).Model(&models.FloatTransaction{}).
		Where("agent_id = ? AND created_at > ?", agentID, threeMonthsAgo).Count(&totalTx)
	oe.db.WithContext(ctx).Model(&models.FloatTransaction{}).
		Where("agent_id = ? AND status = ? AND created_at > ?", agentID, models.TransactionStatusCompleted, threeMonthsAgo).
		Count(&successfulTx)

	if totalTx > 0 {
		successRate := (float64(successfulTx) / float64(totalTx)) * 100
		if successRate < eligibility.MinSuccessRate {
			failures = append(failures, fmt.Sprintf("Low success rate: %.1f%% < %.1f%%", successRate, eligibility.MinSuccessRate))
		}
	}

	// Check agent tenure (would need agent creation date from auth service)
	// For now, check oldest transaction
	var oldestTx models.FloatTransaction
	if err := oe.db.WithContext(ctx).Where("agent_id = ?", agentID).
		Order("created_at ASC").First(&oldestTx).Error; err == nil {
		monthsActive := int(time.Since(oldestTx.CreatedAt).Hours() / (24 * 30))
		if monthsActive < eligibility.MinMonthsActive {
			failures = append(failures, fmt.Sprintf("Insufficient tenure: %d months < %d months", monthsActive, eligibility.MinMonthsActive))
		}
	}

	return len(failures) == 0, failures, nil
}

// CreateOptInFloat creates an opt-in float facility
func (oe *OptInEngine) CreateOptInFloat(ctx context.Context, agentID uuid.UUID, requestedLimit float64, currency string, documents []string, createdBy uuid.UUID) (*models.AgentFloat, error) {
	// Check eligibility
	eligible, failures, err := oe.CheckOptInEligibility(ctx, agentID)
	if err != nil {
		return nil, fmt.Errorf("eligibility check failed: %w", err)
	}
	if !eligible {
		return nil, fmt.Errorf("agent not eligible for opt-in float: %s", failures)
	}

	// Check required documents
	eligibility := oe.GetOptInEligibility()
	for _, requiredDoc := range eligibility.RequiredDocuments {
		found := false
		for _, doc := range documents {
			if doc == requiredDoc {
				found = true
				break
			}
		}
		if !found {
			return nil, fmt.Errorf("missing required document: %s", requiredDoc)
		}
	}

	// Create facility with pending status (requires approval)
	facility := &models.AgentFloat{
		ID:                  uuid.New(),
		AgentID:             agentID,
		AgentTier:           models.TierBasic, // Opt-in starts at basic
		FloatLimit:          requestedLimit,
		UtilizedAmount:      0.0,
		AvailableFloat:      requestedLimit,
		ReservedAmount:      0.0,
		Status:              models.FloatStatusPending,
		RiskLevel:           models.RiskLevelMedium, // Requires assessment
		UtilizationAlert1:   75.0,
		SettlementFrequency: "daily",
		NextSettlementDate:  time.Now().Add(24 * time.Hour),
		Currency:            currency,
		CreatedBy:           createdBy,
	}

	if err := oe.db.WithContext(ctx).Create(facility).Error; err != nil {
		return nil, fmt.Errorf("failed to create opt-in float facility: %w", err)
	}

	return facility, nil
}

// ==========================================
// DYNAMIC HYBRID SYSTEM
// ==========================================

// DynamicEngine handles dynamic balance management

type DynamicEngine struct {
	db *gorm.DB
}

// NewDynamicEngine creates a new dynamic engine
func NewDynamicEngine(db *gorm.DB) *DynamicEngine {
	return &DynamicEngine{db: db}
}

// DynamicBalanceStrategy defines the strategy for dynamic balance management
type DynamicBalanceStrategy struct {
	MinFloatRatio       float64 `json:"min_float_ratio"`       // Minimum float as % of daily volume
	MaxFloatRatio       float64 `json:"max_float_ratio"`       // Maximum float as % of daily volume
	RebalanceThreshold  float64 `json:"rebalance_threshold"`  // Trigger rebalancing at this deviation
	LearningWindowDays  int     `json:"learning_window_days"` // Days of history to consider
	SeasonalityEnabled  bool    `json:"seasonality_enabled"`
	EmergencyReservePct float64 `json:"emergency_reserve_pct"`
}

// GetDefaultStrategy returns the default dynamic balance strategy
func (de *DynamicEngine) GetDefaultStrategy() DynamicBalanceStrategy {
	return DynamicBalanceStrategy{
		MinFloatRatio:       20.0, // 20% of daily volume minimum
		MaxFloatRatio:       80.0, // 80% of daily volume maximum
		RebalanceThreshold:  15.0, // Rebalance if deviation > 15%
		LearningWindowDays:  30,
		SeasonalityEnabled:  true,
		EmergencyReservePct: 10.0, // 10% emergency reserve
	}
}

// OptimizeFloatBalance optimizes float balance for an agent
func (de *DynamicEngine) OptimizeFloatBalance(ctx context.Context, agentID uuid.UUID) (*models.BalanceOptimization, error) {
	strategy := de.GetDefaultStrategy()
	
	// Get current float facility
	var facility models.AgentFloat
	if err := de.db.WithContext(ctx).Where("agent_id = ?", agentID).First(&facility).Error; err != nil {
		return nil, fmt.Errorf("float facility not found: %w", err)
	}

	// Calculate optimal balance based on transaction patterns
	optimalBalance, reasoning, confidence, err := de.calculateOptimalBalance(ctx, agentID, strategy)
	if err != nil {
		return nil, fmt.Errorf("failed to calculate optimal balance: %w", err)
	}

	// Check if rebalancing is needed
	currentBalance := facility.AvailableFloat
	deviation := abs(optimalBalance - currentBalance) / currentBalance * 100

	var action string
	var newLimit *float64
	if deviation > strategy.RebalanceThreshold {
		if optimalBalance > currentBalance {
			action = "increase"
			newLimit = &optimalBalance
		} else {
			action = "decrease"
			newLimit = &optimalBalance
		}
	} else {
		action = "maintain"
	}

	// Create optimization record
	optimization := &models.BalanceOptimization{
		ID:                   uuid.New(),
		AgentID:              agentID,
		CurrentBalance:       currentBalance,
		OptimalBalance:       optimalBalance,
		RecommendedAction:    action,
		NewLimit:             newLimit,
		Reasoning:            reasoning,
		ConfidenceScore:      confidence,
		Strategy:             strategy,
		CreatedAt:            time.Now(),
	}

	if err := de.db.WithContext(ctx).Create(optimization).Error; err != nil {
		return nil, fmt.Errorf("failed to create balance optimization: %w", err)
	}

	return optimization, nil
}

// calculateOptimalBalance calculates the optimal float balance for an agent
func (de *DynamicEngine) calculateOptimalBalance(ctx context.Context, agentID uuid.UUID, strategy DynamicBalanceStrategy) (float64, string, float64, error) {
	windowStart := time.Now().AddDate(0, 0, -strategy.LearningWindowDays)
	
	// Calculate average daily volume
	var avgDailyVolume float64
	if err := de.db.WithContext(ctx).Model(&models.FloatTransaction{}).
		Select("COALESCE(AVG(daily_volume), 0) FROM (
			SELECT DATE(created_at) as date, SUM(amount) as daily_volume
			FROM float_transactions
			WHERE agent_id = ? AND type = ? AND status = ? AND created_at > ?
			GROUP BY DATE(created_at)
		) as daily_volumes", agentID, models.TransactionTypeUtilization, models.TransactionStatusCompleted, windowStart).
		Row().Scan(&avgDailyVolume); err != nil {
		return 0, "", 0, fmt.Errorf("failed to calculate average daily volume: %w", err)
	}

	// Calculate volatility (standard deviation of daily volumes)
	var volatility float64
	if err := de.db.WithContext(ctx).Model(&models.FloatTransaction{}).
		Select("COALESCE(STDDEV(daily_volume), 0) FROM (
			SELECT DATE(created_at) as date, SUM(amount) as daily_volume
			FROM float_transactions
			WHERE agent_id = ? AND type = ? AND status = ? AND created_at > ?
			GROUP BY DATE(created_at)
		) as daily_volumes", agentID, models.TransactionTypeUtilization, models.TransactionStatusCompleted, windowStart).
		Row().Scan(&volatility); err != nil {
		volatility = 0 // If we can't calculate volatility, assume 0
	}

	// Calculate optimal balance
	baseBalance := avgDailyVolume * (strategy.MinFloatRatio + strategy.MaxFloatRatio) / 200 // Average of min and max ratios
	volatilityAdjustment := volatility * 2 // Add buffer for volatility
	emergencyReserve := baseBalance * strategy.EmergencyReservePct / 100

	optimalBalance := baseBalance + volatilityAdjustment + emergencyReserve

	// Apply seasonality adjustment if enabled
	seasonalityFactor := 1.0
	if strategy.SeasonalityEnabled {
		seasonalityFactor = de.getSeasonalityFactor(time.Now())
		optimalBalance *= seasonalityFactor
	}

	reasoning := fmt.Sprintf(
		"Base: ₦%.2f (%.0f%% of avg daily volume ₦%.2f), Volatility buffer: ₦%.2f, Emergency reserve: ₦%.2f, Seasonality: %.2fx",
		baseBalance, (strategy.MinFloatRatio+strategy.MaxFloatRatio)/2, avgDailyVolume,
		volatilityAdjustment, emergencyReserve, seasonalityFactor,
	)

	// Confidence based on data availability and consistency
	confidence := 85.0
	if avgDailyVolume == 0 {
		confidence = 30.0 // Low confidence with no transaction history
	} else if volatility/avgDailyVolume > 0.5 {
		confidence = 65.0 // Medium confidence with high volatility
	}

	return optimalBalance, reasoning, confidence, nil
}

// getSeasonalityFactor returns a multiplier based on the time of year
func (de *DynamicEngine) getSeasonalityFactor(date time.Time) float64 {
	month := date.Month()
	day := date.Day()

	// Higher volumes during festive seasons
	if month == time.December && day > 15 {
		return 1.3 // 30% increase during Christmas season
	}
	if month == time.January && day < 10 {
		return 1.2 // 20% increase during New Year
	}
	if month == time.August {
		return 1.1 // 10% increase during Sallah
	}

	// Weekend factor
	if date.Weekday() == time.Saturday || date.Weekday() == time.Sunday {
		return 1.15 // 15% increase on weekends
	}

	return 1.0 // No adjustment
}

// ==========================================
// ENHANCED SETTLEMENT PROCESSING
// ==========================================

// SettleFloatEnhanced processes float settlement with circuit breaker and retry logic
func (s *EnhancedFloatService) SettleFloatEnhanced(ctx context.Context, req SettleFloatEnhancedRequest) (*models.FloatSettlement, error) {
	if !s.paymentBreaker.CanExecute() {
		return nil, errors.New("payment gateway circuit breaker is open")
	}

	// Start transaction
	tx := s.db.WithContext(ctx).Begin()
	if tx.Error != nil {
		return nil, fmt.Errorf("failed to start transaction: %w", tx.Error)
	}
	defer func() {
		if r := recover(); r != nil {
			tx.Rollback()
		}
	}()

	// Get float facility
	var facility models.AgentFloat
	if err := tx.Where("agent_id = ?", req.AgentID).First(&facility).Error; err != nil {
		tx.Rollback()
		return nil, fmt.Errorf("float facility not found: %w", err)
	}

	// Calculate settlement amount
	settleAmount := req.Amount
	if settleAmount <= 0 {
		settleAmount = facility.UtilizedAmount // Full settlement
	}

	if settleAmount > facility.UtilizedAmount {
		tx.Rollback()
		return nil, fmt.Errorf("settlement amount %.2f exceeds utilized amount %.2f", settleAmount, facility.UtilizedAmount)
	}

	// Create settlement record
	settlement := &models.FloatSettlement{
		ID:              uuid.New(),
		AgentFloatID:    facility.ID,
		AgentID:         req.AgentID,
		SettlementDate:  time.Now(),
		SettlementType:  req.SettlementType,
		Amount:          settleAmount,
		UtilizedBefore:  facility.UtilizedAmount,
		UtilizedAfter:   facility.UtilizedAmount - settleAmount,
		PaymentMethod:   req.PaymentMethod,
		PaymentReference: req.PaymentRef,
		Status:          models.SettlementStatusPending,
		Description:     req.Description,
		InitiatedBy:     req.SettledBy,
		Metadata:        models.JSON{"enhanced": true, "version": "2.0"},
	}

	if err := tx.Create(settlement).Error; err != nil {
		tx.Rollback()
		return nil, fmt.Errorf("failed to create settlement: %w", err)
	}

	// Process payment with circuit breaker and retry logic — real gateway call,
	// never simulated success.
	paymentStatus, err := s.callPaymentGateway(ctx, req.PaymentRef, settleAmount, req)
	if err != nil {
		s.paymentBreaker.RecordFailure()
		settlement.Status = models.SettlementStatusFailed
		settlement.FailureReason = err.Error()
		tx.Save(settlement)
		tx.Commit()
		// Queue for retry if this was a transient payment failure
		s.settlementQueue.QueueRetry(settlement.ID)
		return nil, fmt.Errorf("payment gateway settlement failed: %w", err)
	}

	s.paymentBreaker.RecordSuccess()
	settlement.Status = models.SettlementStatus(paymentStatus)
	if settlement.Status == models.SettlementStatusFailed {
		settlement.FailureReason = "payment gateway reported failure"
		tx.Save(settlement)
		tx.Commit()
		s.settlementQueue.QueueRetry(settlement.ID)
		return nil, errors.New("payment gateway reported settlement failure")
	}

	// Update float facility if payment succeeded
	if settlement.Status == models.SettlementStatusCompleted {
		newUtilized := facility.UtilizedAmount - settleAmount
		newAvailable := facility.AvailableFloat + settleAmount
		
		facilityUpdates := map[string]interface{}{
			"utilized_amount":      newUtilized,
			"available_float":      newAvailable,
			"last_settlement_date": time.Now(),
			"updated_at":           time.Now(),
		}
		
		if err := tx.Model(&facility).Updates(facilityUpdates).Error; err != nil {
			tx.Rollback()
			return nil, fmt.Errorf("failed to update float facility: %w", err)
		}

		// Create settlement transaction
		transaction := &models.FloatTransaction{
			ID:              uuid.New(),
			AgentFloatID:    facility.ID,
			AgentID:         req.AgentID,
			Type:            models.TransactionTypeSettlement,
			Amount:          settleAmount,
			UtilizedBefore:  facility.UtilizedAmount,
			UtilizedAfter:   newUtilized,
			AvailableBefore: facility.AvailableFloat,
			AvailableAfter:  newAvailable,
			Reference:       &req.PaymentRef,
			Description:     req.Description,
			Status:          models.TransactionStatusCompleted,
			ProcessedBy:     req.SettledBy,
			Metadata:        models.JSON{"settlement_id": settlement.ID},
		}
		
		if err := tx.Create(transaction).Error; err != nil {
			tx.Rollback()
			return nil, fmt.Errorf("failed to create settlement transaction: %w", err)
		}
	}

	// Commit transaction
	if err := tx.Commit().Error; err != nil {
		return nil, fmt.Errorf("failed to commit settlement: %w", err)
	}

	return settlement, nil
}

// callPaymentGateway performs the real payment gateway settlement call.
// It fails loudly when the gateway is not configured or unreachable —
// settlement success is never simulated.
func (s *EnhancedFloatService) callPaymentGateway(ctx context.Context, paymentRef string, amount float64, req SettleFloatEnhancedRequest) (string, error) {
	gatewayURL := os.Getenv("PAYMENT_GATEWAY_URL")
	if gatewayURL == "" {
		return "", errors.New("PAYMENT_GATEWAY_URL not configured — settlement refused (no simulated success)")
	}

	payload, err := json.Marshal(map[string]interface{}{
		"agent_id":          req.AgentID,
		"payment_reference": paymentRef,
		"amount":            amount,
		"payment_method":    req.PaymentMethod,
		"settlement_type":   req.SettlementType,
		"description":       req.Description,
		"settled_by":        req.SettledBy,
	})
	if err != nil {
		return "", fmt.Errorf("failed to encode gateway request: %w", err)
	}

	httpReq, err := http.NewRequestWithContext(ctx, http.MethodPost,
		strings.TrimRight(gatewayURL, "/")+"/payments/settle", bytes.NewReader(payload))
	if err != nil {
		return "", err
	}
	httpReq.Header.Set("Content-Type", "application/json")

	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Do(httpReq)
	if err != nil {
		return "", fmt.Errorf("payment gateway unreachable: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		return "", fmt.Errorf("payment gateway rejected settlement: HTTP %d", resp.StatusCode)
	}

	var gatewayResp struct {
		Status string `json:"status"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&gatewayResp); err != nil {
		return "", fmt.Errorf("invalid payment gateway response: %w", err)
	}
	if gatewayResp.Status == "" {
		return "", errors.New("payment gateway returned empty status")
	}
	return gatewayResp.Status, nil
}

// ==========================================
// CIRCUIT BREAKER IMPLEMENTATION
// ==========================================

// CanExecute checks if the circuit breaker allows execution
func (cb *CircuitBreaker) CanExecute() bool {
	if cb.state == "open" {
		if time.Since(cb.lastFailTime) > cb.resetTimeout {
			cb.state = "half-open"
			return true
		}
		return false
	}
	return true
}

// RecordSuccess records a successful operation
func (cb *CircuitBreaker) RecordSuccess() {
	cb.failures = 0
	cb.state = "closed"
}

// RecordFailure records a failed operation
func (cb *CircuitBreaker) RecordFailure() {
	cb.failures++
	cb.lastFailTime = time.Now()
	if cb.failures >= cb.maxFailures {
		cb.state = "open"
	}
}

// ==========================================
// QUEUE SERVICE IMPLEMENTATION
// ==========================================

// QueueRetry queues a settlement for retry
func (qs *QueueService) QueueRetry(settlementID uuid.UUID) {
	select {
	case qs.retryQueue <- settlementID:
		// Queued successfully
	default:
		// Queue full, log error
		fmt.Printf("Retry queue full, settlement %s will not be retried\n", settlementID)
	}
}

// processRetries processes retry queue
func (qs *QueueService) processRetries(ctx context.Context) {
	for {
		select {
		case <-ctx.Done():
			return
		case settlementID := <-qs.retryQueue:
			qs.retrySettlement(ctx, settlementID)
		}
	}
}

// retrySettlement retries a failed settlement
func (qs *QueueService) retrySettlement(ctx context.Context, settlementID uuid.UUID) {
	var settlement models.FloatSettlement
	if err := qs.db.WithContext(ctx).First(&settlement, settlementID).Error; err != nil {
		fmt.Printf("Failed to find settlement %s for retry: %v\n", settlementID, err)
		return
	}

	// Check retry count
	if settlement.Metadata == nil {
		settlement.Metadata = models.JSON{}
	}
	retryCount, _ := settlement.Metadata["retry_count"].(float64)
	if int(retryCount) >= qs.maxRetries {
		fmt.Printf("Settlement %s exceeded max retries\n", settlementID)
		return
	}

	// Update retry count
	settlement.Metadata["retry_count"] = retryCount + 1
	settlement.Metadata["last_retry"] = time.Now()

	if err := qs.db.WithContext(ctx).Save(&settlement).Error; err != nil {
		fmt.Printf("Failed to update settlement retry count: %v\n", err)
	}

	// TODO: Implement actual retry logic with payment gateway
	fmt.Printf("Retrying settlement %s (attempt %d)\n", settlementID, int(retryCount)+1)
}

// ==========================================
// BACKGROUND TASKS
// ==========================================

// runPeriodicAssessments runs periodic risk assessments and balance optimizations
func (s *EnhancedFloatService) runPeriodicAssessments(ctx context.Context) {
	ticker := time.NewTicker(6 * time.Hour) // Run every 6 hours
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			s.performPeriodicAssessments(ctx)
		}
	}
}

// performPeriodicAssessments performs periodic assessments for all active facilities
func (s *EnhancedFloatService) performPeriodicAssessments(ctx context.Context) {
	var facilities []models.AgentFloat
	if err := s.db.WithContext(ctx).Where("status = ?", models.FloatStatusActive).
		Find(&facilities).Error; err != nil {
		fmt.Printf("Failed to fetch facilities for periodic assessment: %v\n", err)
		return
	}

	for _, facility := range facilities {
		// Perform balance optimization
		if _, err := s.dynamicEngine.OptimizeFloatBalance(ctx, facility.AgentID); err != nil {
			fmt.Printf("Failed to optimize balance for agent %s: %v\n", facility.AgentID, err)
		}

		// Check utilization alerts
		utilizationRate := (facility.UtilizedAmount / facility.FloatLimit) * 100
		s.alertService.CheckUtilizationAlert(ctx, facility, utilizationRate)
	}
}

// ==========================================
// REQUEST TYPES
// ==========================================

// SettleFloatEnhancedRequest represents enhanced settlement request
type SettleFloatEnhancedRequest struct {
	AgentID         uuid.UUID                    `json:"agent_id"`
	Amount          float64                      `json:"amount"`
	PaymentMethod   string                       `json:"payment_method"`
	PaymentRef      string                       `json:"payment_reference"`
	SettlementType  models.SettlementType        `json:"settlement_type"`
	SettledBy       uuid.UUID                    `json:"settled_by"`
	Description     string                       `json:"description"`
	Metadata        models.JSON                  `json:"metadata"`
}

// ==========================================
// UTILITY FUNCTIONS
// ==========================================

// abs returns the absolute value of a float64
func abs(x float64) float64 {
	if x < 0 {
		return -x
	}
	return x
}
