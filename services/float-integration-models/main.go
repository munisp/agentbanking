package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/gin-contrib/cors"
	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"github.com/redis/go-redis/v9"
	"gorm.io/driver/postgres"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"
)

// ==========================================
// INTEGRATION MODELS
// ==========================================

// IntegrationModel represents the type of float integration
type IntegrationModel string

const (
	TieredModel  IntegrationModel = "tiered"
	OptInModel   IntegrationModel = "opt_in"
	DynamicModel IntegrationModel = "dynamic"
)

// AgentTier represents agent tier levels
type AgentTier string

const (
	BasicTier    AgentTier = "basic"
	StandardTier AgentTier = "standard"
	PremiumTier  AgentTier = "premium"
	EliteTier    AgentTier = "elite"
)

// FloatAccessLevel represents access levels for float facilities
type FloatAccessLevel string

const (
	NoAccess     FloatAccessLevel = "no_access"
	LimitedAccess FloatAccessLevel = "limited_access"
	StandardAccess FloatAccessLevel = "standard_access"
	PremiumAccess FloatAccessLevel = "premium_access"
	EliteAccess   FloatAccessLevel = "elite_access"
)

// ==========================================
// DATA MODELS
// ==========================================

// AgentIntegrationProfile represents an agent's integration profile
type AgentIntegrationProfile struct {
	ID                    uuid.UUID        `json:"id" gorm:"type:uuid;primary_key;default:gen_random_uuid()"`
	AgentID               uuid.UUID        `json:"agent_id" gorm:"type:uuid;not null;uniqueIndex"`
	IntegrationModel      IntegrationModel `json:"integration_model" gorm:"type:varchar(20);not null"`
	AgentTier             AgentTier        `json:"agent_tier" gorm:"type:varchar(20);not null"`
	FloatAccessLevel      FloatAccessLevel `json:"float_access_level" gorm:"type:varchar(20);not null"`
	MaxFloatLimit         float64          `json:"max_float_limit" gorm:"type:decimal(15,2);default:0"`
	CurrentFloatLimit     float64          `json:"current_float_limit" gorm:"type:decimal(15,2);default:0"`
	PerformanceScore      float64          `json:"performance_score" gorm:"type:decimal(5,2);default:0"`
	RiskScore             float64          `json:"risk_score" gorm:"type:decimal(5,2);default:0"`
	OptInStatus           string           `json:"opt_in_status" gorm:"type:varchar(20);default:'not_enrolled'"`
	OptInDate             *time.Time       `json:"opt_in_date"`
	LastReviewDate        *time.Time       `json:"last_review_date"`
	NextReviewDate        *time.Time       `json:"next_review_date"`
	AutoUpgradeEnabled    bool             `json:"auto_upgrade_enabled" gorm:"default:true"`
	DynamicAdjustments    JSON             `json:"dynamic_adjustments" gorm:"type:jsonb"`
	IntegrationConfig     JSON             `json:"integration_config" gorm:"type:jsonb"`
	CreatedAt             time.Time        `json:"created_at"`
	UpdatedAt             time.Time        `json:"updated_at"`
	CreatedBy             uuid.UUID        `json:"created_by" gorm:"type:uuid"`
	UpdatedBy             uuid.UUID        `json:"updated_by" gorm:"type:uuid"`
}

// TierConfiguration represents tier-specific configurations
type TierConfiguration struct {
	ID                    uuid.UUID `json:"id" gorm:"type:uuid;primary_key;default:gen_random_uuid()"`
	AgentTier             AgentTier `json:"agent_tier" gorm:"type:varchar(20);not null;uniqueIndex"`
	MinFloatLimit         float64   `json:"min_float_limit" gorm:"type:decimal(15,2);not null"`
	MaxFloatLimit         float64   `json:"max_float_limit" gorm:"type:decimal(15,2);not null"`
	DefaultFloatLimit     float64   `json:"default_float_limit" gorm:"type:decimal(15,2);not null"`
	InterestRate          float64   `json:"interest_rate" gorm:"type:decimal(5,4);not null"`
	FeeRate               float64   `json:"fee_rate" gorm:"type:decimal(5,4);not null"`
	SettlementFrequency   string    `json:"settlement_frequency" gorm:"type:varchar(20);not null"`
	RequiredPerformance   float64   `json:"required_performance_score" gorm:"type:decimal(5,2);not null"`
	MaxRiskScore          float64   `json:"max_risk_score" gorm:"type:decimal(5,2);not null"`
	UpgradeThreshold      float64   `json:"upgrade_threshold" gorm:"type:decimal(5,2);not null"`
	DowngradeThreshold    float64   `json:"downgrade_threshold" gorm:"type:decimal(5,2);not null"`
	RequiredDocuments     JSON      `json:"required_documents" gorm:"type:jsonb"`
	Benefits              JSON      `json:"benefits" gorm:"type:jsonb"`
	Restrictions          JSON      `json:"restrictions" gorm:"type:jsonb"`
	IsActive              bool      `json:"is_active" gorm:"default:true"`
	CreatedAt             time.Time `json:"created_at"`
	UpdatedAt             time.Time `json:"updated_at"`
}

// IntegrationModelConfig represents configuration for each integration model
type IntegrationModelConfig struct {
	ID                    uuid.UUID        `json:"id" gorm:"type:uuid;primary_key;default:gen_random_uuid()"`
	ModelType             IntegrationModel `json:"model_type" gorm:"type:varchar(20);not null;uniqueIndex"`
	ModelName             string           `json:"model_name" gorm:"type:varchar(100);not null"`
	Description           string           `json:"description" gorm:"type:text"`
	IsActive              bool             `json:"is_active" gorm:"default:true"`
	Configuration         JSON             `json:"configuration" gorm:"type:jsonb"`
	EligibilityCriteria   JSON             `json:"eligibility_criteria" gorm:"type:jsonb"`
	AutomationRules       JSON             `json:"automation_rules" gorm:"type:jsonb"`
	PerformanceMetrics    JSON             `json:"performance_metrics" gorm:"type:jsonb"`
	CreatedAt             time.Time        `json:"created_at"`
	UpdatedAt             time.Time        `json:"updated_at"`
}

// AgentPerformanceMetrics represents agent performance tracking
type AgentPerformanceMetrics struct {
	ID                     uuid.UUID `json:"id" gorm:"type:uuid;primary_key;default:gen_random_uuid()"`
	AgentID                uuid.UUID `json:"agent_id" gorm:"type:uuid;not null"`
	MetricDate             time.Time `json:"metric_date" gorm:"type:date;not null"`
	TransactionVolume      float64   `json:"transaction_volume" gorm:"type:decimal(15,2);default:0"`
	TransactionCount       int       `json:"transaction_count" gorm:"default:0"`
	SettlementSuccessRate  float64   `json:"settlement_success_rate" gorm:"type:decimal(5,2);default:0"`
	CustomerSatisfaction   float64   `json:"customer_satisfaction" gorm:"type:decimal(5,2);default:0"`
	ComplianceScore        float64   `json:"compliance_score" gorm:"type:decimal(5,2);default:0"`
	FloatUtilizationRate   float64   `json:"float_utilization_rate" gorm:"type:decimal(5,2);default:0"`
	OverallPerformanceScore float64  `json:"overall_performance_score" gorm:"type:decimal(5,2);default:0"`
	CreatedAt              time.Time `json:"created_at"`
}

// JSON type for JSONB fields
type JSON map[string]interface{}

// Value implements driver.Valuer interface
func (j JSON) Value() (interface{}, error) {
	if j == nil {
		return nil, nil
	}
	return json.Marshal(j)
}

// Scan implements sql.Scanner interface
func (j *JSON) Scan(value interface{}) error {
	if value == nil {
		*j = nil
		return nil
	}
	
	bytes, ok := value.([]byte)
	if !ok {
		return fmt.Errorf("cannot scan %T into JSON", value)
	}
	
	return json.Unmarshal(bytes, j)
}

// ==========================================
// INTEGRATION SERVICE
// ==========================================

// IntegrationService manages float integration models
type IntegrationService struct {
	DB    *gorm.DB
	Redis *redis.Client
}

// NewIntegrationService creates a new integration service
func NewIntegrationService(db *gorm.DB, redis *redis.Client) *IntegrationService {
	return &IntegrationService{
		DB:    db,
		Redis: redis,
	}
}

// ==========================================
// TIERED INTEGRATION MODEL
// ==========================================

// EvaluateAgentForTier evaluates an agent for tier assignment
func (s *IntegrationService) EvaluateAgentForTier(ctx context.Context, agentID uuid.UUID) (*AgentTier, error) {
	// Get agent performance metrics
	var metrics AgentPerformanceMetrics
	if err := s.DB.Where("agent_id = ?", agentID).
		Order("metric_date DESC").
		First(&metrics).Error; err != nil {
		// If no metrics found, assign basic tier
		basicTier := BasicTier
		return &basicTier, nil
	}
	
	// Tier evaluation logic
	performanceScore := metrics.OverallPerformanceScore
	transactionVolume := metrics.TransactionVolume
	settlementRate := metrics.SettlementSuccessRate
	
	// Elite tier criteria
	if performanceScore >= 90 && transactionVolume >= 5000000 && settlementRate >= 98 {
		eliteTier := EliteTier
		return &eliteTier, nil
	}
	
	// Premium tier criteria
	if performanceScore >= 80 && transactionVolume >= 2000000 && settlementRate >= 95 {
		premiumTier := PremiumTier
		return &premiumTier, nil
	}
	
	// Standard tier criteria
	if performanceScore >= 70 && transactionVolume >= 500000 && settlementRate >= 90 {
		standardTier := StandardTier
		return &standardTier, nil
	}
	
	// Default to basic tier
	basicTier := BasicTier
	return &basicTier, nil
}

// AssignTieredFloatAccess assigns float access based on tier
func (s *IntegrationService) AssignTieredFloatAccess(ctx context.Context, agentID uuid.UUID, tier AgentTier) error {
	// Get tier configuration
	var tierConfig TierConfiguration
	if err := s.DB.Where("agent_tier = ? AND is_active = ?", tier, true).
		First(&tierConfig).Error; err != nil {
		return fmt.Errorf("tier configuration not found: %w", err)
	}
	
	// Create or update agent integration profile
	profile := AgentIntegrationProfile{
		AgentID:               agentID,
		IntegrationModel:      TieredModel,
		AgentTier:             tier,
		FloatAccessLevel:      s.getAccessLevelForTier(tier),
		MaxFloatLimit:         tierConfig.MaxFloatLimit,
		CurrentFloatLimit:     tierConfig.DefaultFloatLimit,
		AutoUpgradeEnabled:    true,
		LastReviewDate:        timePtr(time.Now()),
		NextReviewDate:        timePtr(time.Now().AddDate(0, 3, 0)), // 3 months
		IntegrationConfig: JSON{
			"tier_config_id":        tierConfig.ID,
			"interest_rate":         tierConfig.InterestRate,
			"fee_rate":              tierConfig.FeeRate,
			"settlement_frequency":  tierConfig.SettlementFrequency,
			"required_performance":  tierConfig.RequiredPerformance,
			"upgrade_threshold":     tierConfig.UpgradeThreshold,
			"downgrade_threshold":   tierConfig.DowngradeThreshold,
		},
		CreatedBy: agentID, // System assignment
		UpdatedBy: agentID,
	}
	
	return s.DB.Clauses().Create(&profile).Error
}

// ==========================================
// OPT-IN INTEGRATION MODEL
// ==========================================

// ProcessOptInRequest processes an agent's opt-in request
func (s *IntegrationService) ProcessOptInRequest(ctx context.Context, agentID uuid.UUID, requestedLimit float64) error {
	// Check eligibility
	eligible, reason := s.checkOptInEligibility(ctx, agentID)
	if !eligible {
		return fmt.Errorf("agent not eligible for opt-in: %s", reason)
	}
	
	// Determine appropriate tier based on requested limit and performance
	tier, err := s.EvaluateAgentForTier(ctx, agentID)
	if err != nil {
		return fmt.Errorf("failed to evaluate agent tier: %w", err)
	}
	
	// Get tier configuration
	var tierConfig TierConfiguration
	if err := s.DB.Where("agent_tier = ? AND is_active = ?", *tier, true).
		First(&tierConfig).Error; err != nil {
		return fmt.Errorf("tier configuration not found: %w", err)
	}
	
	// Adjust requested limit based on tier limits
	approvedLimit := requestedLimit
	if approvedLimit > tierConfig.MaxFloatLimit {
		approvedLimit = tierConfig.MaxFloatLimit
	}
	if approvedLimit < tierConfig.MinFloatLimit {
		approvedLimit = tierConfig.MinFloatLimit
	}
	
	// Create integration profile
	profile := AgentIntegrationProfile{
		AgentID:               agentID,
		IntegrationModel:      OptInModel,
		AgentTier:             *tier,
		FloatAccessLevel:      s.getAccessLevelForTier(*tier),
		MaxFloatLimit:         tierConfig.MaxFloatLimit,
		CurrentFloatLimit:     approvedLimit,
		OptInStatus:           "approved",
		OptInDate:             timePtr(time.Now()),
		LastReviewDate:        timePtr(time.Now()),
		NextReviewDate:        timePtr(time.Now().AddDate(0, 6, 0)), // 6 months
		AutoUpgradeEnabled:    false, // Manual upgrades for opt-in model
		IntegrationConfig: JSON{
			"requested_limit":       requestedLimit,
			"approved_limit":        approvedLimit,
			"tier_config_id":        tierConfig.ID,
			"opt_in_date":           time.Now(),
			"eligibility_criteria":  s.getOptInCriteria(),
			"performance_requirements": tierConfig.RequiredPerformance,
		},
		CreatedBy: agentID,
		UpdatedBy: agentID,
	}
	
	return s.DB.Create(&profile).Error
}

// checkOptInEligibility checks if agent is eligible for opt-in
func (s *IntegrationService) checkOptInEligibility(ctx context.Context, agentID uuid.UUID) (bool, string) {
	// Check agent status
	var agentStatus string
	if err := s.DB.Table("agent_onboarding").
		Select("status").
		Where("agent_id = ?", agentID).
		Scan(&agentStatus).Error; err != nil {
		return false, "agent not found"
	}
	
	if agentStatus != "active" {
		return false, "agent not active"
	}
	
	// Check KYC completion
	var kycVerified bool
	if err := s.DB.Table("agent_onboarding").
		Select("kyc_verified").
		Where("agent_id = ?", agentID).
		Scan(&kycVerified).Error; err != nil {
		return false, "KYC status unknown"
	}
	
	if !kycVerified {
		return false, "KYC not verified"
	}
	
	// Check minimum operating period (30 days)
	var createdAt time.Time
	if err := s.DB.Table("agent_onboarding").
		Select("created_at").
		Where("agent_id = ?", agentID).
		Scan(&createdAt).Error; err != nil {
		return false, "agent creation date unknown"
	}
	
	if time.Since(createdAt).Hours() < 24*30 {
		return false, "minimum 30-day operating period not met"
	}
	
	// Check transaction history
	var transactionCount int64
	s.DB.Table("transactions").
		Where("agent_id = ? AND created_at > ?", agentID, time.Now().AddDate(0, -1, 0)).
		Count(&transactionCount)
	
	if transactionCount < 50 {
		return false, "insufficient transaction history (minimum 50 transactions in last 30 days)"
	}
	
	return true, ""
}

// ==========================================
// DYNAMIC INTEGRATION MODEL
// ==========================================

// ProcessDynamicAdjustment processes dynamic float adjustments
func (s *IntegrationService) ProcessDynamicAdjustment(ctx context.Context, agentID uuid.UUID) error {
	// Get current profile
	var profile AgentIntegrationProfile
	if err := s.DB.Where("agent_id = ? AND integration_model = ?", agentID, DynamicModel).
		First(&profile).Error; err != nil {
		return fmt.Errorf("dynamic profile not found: %w", err)
	}
	
	// Get recent performance metrics
	var metrics AgentPerformanceMetrics
	if err := s.DB.Where("agent_id = ?", agentID).
		Order("metric_date DESC").
		First(&metrics).Error; err != nil {
		return fmt.Errorf("performance metrics not found: %w", err)
	}
	
	// Calculate dynamic adjustments
	adjustments := s.calculateDynamicAdjustments(profile, metrics)
	
	// Apply adjustments
	newLimit := profile.CurrentFloatLimit * adjustments.LimitMultiplier
	
	// Ensure within tier bounds
	var tierConfig TierConfiguration
	if err := s.DB.Where("agent_tier = ?", profile.AgentTier).
		First(&tierConfig).Error; err != nil {
		return fmt.Errorf("tier configuration not found: %w", err)
	}
	
	if newLimit > tierConfig.MaxFloatLimit {
		newLimit = tierConfig.MaxFloatLimit
	}
	if newLimit < tierConfig.MinFloatLimit {
		newLimit = tierConfig.MinFloatLimit
	}
	
	// Update profile
	updates := map[string]interface{}{
		"current_float_limit": newLimit,
		"performance_score":   metrics.OverallPerformanceScore,
		"last_review_date":    time.Now(),
		"next_review_date":    time.Now().AddDate(0, 0, 7), // Weekly reviews
		"dynamic_adjustments": JSON{
			"previous_limit":     profile.CurrentFloatLimit,
			"new_limit":          newLimit,
			"adjustment_factor":  adjustments.LimitMultiplier,
			"adjustment_reason":  adjustments.Reason,
			"adjustment_date":    time.Now(),
			"performance_score":  metrics.OverallPerformanceScore,
			"risk_score":         adjustments.RiskScore,
		},
		"updated_at": time.Now(),
		"updated_by": agentID,
	}
	
	return s.DB.Model(&profile).Where("id = ?", profile.ID).Updates(updates).Error
}

// DynamicAdjustment represents dynamic adjustment calculations
type DynamicAdjustment struct {
	LimitMultiplier float64
	RiskScore       float64
	Reason          string
}

// calculateDynamicAdjustments calculates dynamic adjustments based on performance
func (s *IntegrationService) calculateDynamicAdjustments(profile AgentIntegrationProfile, metrics AgentPerformanceMetrics) DynamicAdjustment {
	baseMultiplier := 1.0
	reason := "stable performance"
	
	// Performance-based adjustments
	performanceScore := metrics.OverallPerformanceScore
	if performanceScore >= 90 {
		baseMultiplier = 1.2 // 20% increase
		reason = "excellent performance"
	} else if performanceScore >= 80 {
		baseMultiplier = 1.1 // 10% increase
		reason = "good performance"
	} else if performanceScore < 60 {
		baseMultiplier = 0.9 // 10% decrease
		reason = "performance concerns"
	} else if performanceScore < 40 {
		baseMultiplier = 0.8 // 20% decrease
		reason = "poor performance"
	}
	
	// Settlement success rate adjustments
	if metrics.SettlementSuccessRate < 90 {
		baseMultiplier *= 0.95 // Additional 5% reduction
		reason += ", settlement issues"
	}
	
	// Utilization rate adjustments
	utilizationRate := metrics.FloatUtilizationRate
	if utilizationRate > 90 {
		baseMultiplier *= 1.05 // 5% increase for high utilization
		reason += ", high utilization"
	} else if utilizationRate < 30 {
		baseMultiplier *= 0.95 // 5% decrease for low utilization
		reason += ", low utilization"
	}
	
	// Risk score calculation
	riskScore := 100 - performanceScore + (100-metrics.SettlementSuccessRate)*2
	if riskScore > 100 {
		riskScore = 100
	}
	
	return DynamicAdjustment{
		LimitMultiplier: baseMultiplier,
		RiskScore:       riskScore,
		Reason:          reason,
	}
}

// ==========================================
// HELPER FUNCTIONS
// ==========================================

// getAccessLevelForTier returns the appropriate access level for a tier
func (s *IntegrationService) getAccessLevelForTier(tier AgentTier) FloatAccessLevel {
	switch tier {
	case BasicTier:
		return LimitedAccess
	case StandardTier:
		return StandardAccess
	case PremiumTier:
		return PremiumAccess
	case EliteTier:
		return EliteAccess
	default:
		return NoAccess
	}
}

// getOptInCriteria returns opt-in eligibility criteria
func (s *IntegrationService) getOptInCriteria() JSON {
	return JSON{
		"minimum_operating_days": 30,
		"minimum_transactions":   50,
		"kyc_required":           true,
		"active_status_required": true,
		"minimum_performance":    60.0,
	}
}

// timePtr returns a pointer to time.Time
func timePtr(t time.Time) *time.Time {
	return &t
}

// ==========================================
// HTTP HANDLERS
// ==========================================

// IntegrationHandler handles integration model requests
type IntegrationHandler struct {
	service *IntegrationService
}

// NewIntegrationHandler creates a new integration handler
func NewIntegrationHandler(service *IntegrationService) *IntegrationHandler {
	return &IntegrationHandler{service: service}
}

// EvaluateAgentTier evaluates an agent for tier assignment
func (h *IntegrationHandler) EvaluateAgentTier(c *gin.Context) {
	agentIDStr := c.Param("agent_id")
	agentID, err := uuid.Parse(agentIDStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid agent ID"})
		return
	}
	
	tier, err := h.service.EvaluateAgentForTier(c.Request.Context(), agentID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	
	c.JSON(http.StatusOK, gin.H{
		"agent_id":      agentID,
		"recommended_tier": *tier,
		"evaluation_date": time.Now(),
	})
}

// AssignTieredAccess assigns tiered float access
func (h *IntegrationHandler) AssignTieredAccess(c *gin.Context) {
	var req struct {
		AgentID uuid.UUID `json:"agent_id" binding:"required"`
		Tier    AgentTier `json:"tier" binding:"required"`
	}
	
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	
	if err := h.service.AssignTieredFloatAccess(c.Request.Context(), req.AgentID, req.Tier); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	
	c.JSON(http.StatusOK, gin.H{
		"message":   "Tiered access assigned successfully",
		"agent_id":  req.AgentID,
		"tier":      req.Tier,
		"model":     TieredModel,
	})
}

// ProcessOptIn processes opt-in request
func (h *IntegrationHandler) ProcessOptIn(c *gin.Context) {
	var req struct {
		AgentID        uuid.UUID `json:"agent_id" binding:"required"`
		RequestedLimit float64   `json:"requested_limit" binding:"required,gt=0"`
	}
	
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	
	if err := h.service.ProcessOptInRequest(c.Request.Context(), req.AgentID, req.RequestedLimit); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	
	c.JSON(http.StatusOK, gin.H{
		"message":         "Opt-in request processed successfully",
		"agent_id":        req.AgentID,
		"requested_limit": req.RequestedLimit,
		"model":           OptInModel,
	})
}

// ProcessDynamicAdjustment processes dynamic adjustment
func (h *IntegrationHandler) ProcessDynamicAdjustment(c *gin.Context) {
	agentIDStr := c.Param("agent_id")
	agentID, err := uuid.Parse(agentIDStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid agent ID"})
		return
	}
	
	if err := h.service.ProcessDynamicAdjustment(c.Request.Context(), agentID); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	
	c.JSON(http.StatusOK, gin.H{
		"message":  "Dynamic adjustment processed successfully",
		"agent_id": agentID,
		"model":    DynamicModel,
	})
}

// GetIntegrationModels returns available integration models
func (h *IntegrationHandler) GetIntegrationModels(c *gin.Context) {
	var models []IntegrationModelConfig
	if err := h.service.DB.Where("is_active = ?", true).Find(&models).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	
	c.JSON(http.StatusOK, gin.H{
		"models": models,
		"count":  len(models),
	})
}

// GetAgentProfile returns agent integration profile
func (h *IntegrationHandler) GetAgentProfile(c *gin.Context) {
	agentIDStr := c.Param("agent_id")
	agentID, err := uuid.Parse(agentIDStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid agent ID"})
		return
	}
	
	var profile AgentIntegrationProfile
	if err := h.service.DB.Where("agent_id = ?", agentID).First(&profile).Error; err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "Integration profile not found"})
		return
	}
	
	c.JSON(http.StatusOK, gin.H{
		"profile": profile,
	})
}

// ==========================================
// MAIN APPLICATION
// ==========================================

func main() {
	// Database connection
	db, err := initializeDatabase()
	if err != nil {
		log.Fatal("Failed to connect to database:", err)
	}
	
	// Redis connection
	redis := initializeRedis()
	
	// Initialize services
	integrationService := NewIntegrationService(db, redis)
	integrationHandler := NewIntegrationHandler(integrationService)
	
	// Initialize Gin router
	router := gin.Default()
	
	// CORS middleware
	router.Use(cors.New(cors.Config{
		AllowOrigins:     []string{"*"},
		AllowMethods:     []string{"GET", "POST", "PUT", "DELETE", "OPTIONS"},
		AllowHeaders:     []string{"*"},
		ExposeHeaders:    []string{"Content-Length"},
		AllowCredentials: true,
		MaxAge:           12 * time.Hour,
	}))
	
	// Health check
	router.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{
			"status":    "healthy",
			"service":   "float-integration-models",
			"version":   "1.0.0",
			"timestamp": time.Now().UTC(),
		})
	})
	
	// API routes
	v1 := router.Group("/api/v1")
	{
		// Integration models
		integration := v1.Group("/integration")
		{
			// Model management
			integration.GET("/models", integrationHandler.GetIntegrationModels)
			
			// Agent evaluation and assignment
			integration.GET("/agents/:agent_id/evaluate-tier", integrationHandler.EvaluateAgentTier)
			integration.GET("/agents/:agent_id/profile", integrationHandler.GetAgentProfile)
			
			// Tiered model
			tiered := integration.Group("/tiered")
			{
				tiered.POST("/assign", integrationHandler.AssignTieredAccess)
			}
			
			// Opt-in model
			optIn := integration.Group("/opt-in")
			{
				optIn.POST("/request", integrationHandler.ProcessOptIn)
			}
			
			// Dynamic model
			dynamic := integration.Group("/dynamic")
			{
				dynamic.POST("/agents/:agent_id/adjust", integrationHandler.ProcessDynamicAdjustment)
			}
		}
	}
	
	// Start server
	port := getEnv("PORT", "8098")
	srv := &http.Server{
		Addr:    ":" + port,
		Handler: router,
	}
	
	// Graceful shutdown
	go func() {
		log.Printf("Float Integration Models Service starting on port %s", port)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("Failed to start server: %v", err)
		}
	}()
	
	// Wait for interrupt signal
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit
	
	log.Println("Shutting down Float Integration Models Service...")
	
	// Graceful shutdown with timeout
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	
	if err := srv.Shutdown(ctx); err != nil {
		log.Fatal("Server forced to shutdown:", err)
	}
	
	log.Println("Float Integration Models Service stopped")
}

// initializeDatabase initializes database connection
func initializeDatabase() (*gorm.DB, error) {
	dsn := fmt.Sprintf("host=%s user=%s password=%s dbname=%s port=%s sslmode=%s",
		getEnv("DB_HOST", "localhost"),
		getEnv("DB_USER", "postgres"),
		getEnv("DB_PASSWORD", "password"),
		getEnv("DB_NAME", "remittance"),
		getEnv("DB_PORT", "5432"),
		getEnv("DB_SSLMODE", "disable"),
	)
	
	db, err := gorm.Open(postgres.Open(dsn), &gorm.Config{
		Logger: logger.Default.LogMode(logger.Info),
	})
	if err != nil {
		return nil, fmt.Errorf("failed to connect to database: %w", err)
	}
	
	// Run migrations
	if err := runMigrations(db); err != nil {
		return nil, fmt.Errorf("failed to run migrations: %w", err)
	}
	
	// Seed default configurations
	if err := seedDefaultConfigurations(db); err != nil {
		log.Printf("Warning: Failed to seed default configurations: %v", err)
	}
	
	return db, nil
}

// initializeRedis initializes Redis connection
func initializeRedis() *redis.Client {
	rdb := redis.NewClient(&redis.Options{
		Addr:     getEnv("REDIS_ADDR", "localhost:6379"),
		Password: getEnv("REDIS_PASSWORD", ""),
		DB:       0,
	})
	
	// Test connection
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	
	if err := rdb.Ping(ctx).Err(); err != nil {
		log.Printf("Warning: Redis connection failed: %v", err)
	}
	
	return rdb
}

// runMigrations runs database migrations
func runMigrations(db *gorm.DB) error {
	return db.AutoMigrate(
		&AgentIntegrationProfile{},
		&TierConfiguration{},
		&IntegrationModelConfig{},
		&AgentPerformanceMetrics{},
	)
}

// seedDefaultConfigurations seeds default configurations
func seedDefaultConfigurations(db *gorm.DB) error {
	// Seed tier configurations
	tiers := []TierConfiguration{
		{
			AgentTier:             BasicTier,
			MinFloatLimit:         50000,
			MaxFloatLimit:         500000,
			DefaultFloatLimit:     100000,
			InterestRate:          0.035,
			FeeRate:               0.01,
			SettlementFrequency:   "daily",
			RequiredPerformance:   50.0,
			MaxRiskScore:          80.0,
			UpgradeThreshold:      70.0,
			DowngradeThreshold:    40.0,
			RequiredDocuments:     JSON{"kyc": true, "business_registration": false},
			Benefits:              JSON{"basic_support": true, "standard_rates": true},
			Restrictions:          JSON{"max_daily_transactions": 50},
		},
		{
			AgentTier:             StandardTier,
			MinFloatLimit:         100000,
			MaxFloatLimit:         2000000,
			DefaultFloatLimit:     500000,
			InterestRate:          0.030,
			FeeRate:               0.008,
			SettlementFrequency:   "daily",
			RequiredPerformance:   70.0,
			MaxRiskScore:          60.0,
			UpgradeThreshold:      80.0,
			DowngradeThreshold:    60.0,
			RequiredDocuments:     JSON{"kyc": true, "business_registration": true},
			Benefits:              JSON{"priority_support": true, "reduced_rates": true},
			Restrictions:          JSON{"max_daily_transactions": 200},
		},
		{
			AgentTier:             PremiumTier,
			MinFloatLimit:         500000,
			MaxFloatLimit:         5000000,
			DefaultFloatLimit:     2000000,
			InterestRate:          0.025,
			FeeRate:               0.005,
			SettlementFrequency:   "weekly",
			RequiredPerformance:   80.0,
			MaxRiskScore:          40.0,
			UpgradeThreshold:      90.0,
			DowngradeThreshold:    70.0,
			RequiredDocuments:     JSON{"kyc": true, "business_registration": true, "financial_statements": true},
			Benefits:              JSON{"dedicated_support": true, "premium_rates": true, "extended_limits": true},
			Restrictions:          JSON{"max_daily_transactions": 1000},
		},
		{
			AgentTier:             EliteTier,
			MinFloatLimit:         2000000,
			MaxFloatLimit:         10000000,
			DefaultFloatLimit:     5000000,
			InterestRate:          0.020,
			FeeRate:               0.003,
			SettlementFrequency:   "weekly",
			RequiredPerformance:   90.0,
			MaxRiskScore:          20.0,
			UpgradeThreshold:      95.0,
			DowngradeThreshold:    80.0,
			RequiredDocuments:     JSON{"kyc": true, "business_registration": true, "financial_statements": true, "audited_accounts": true},
			Benefits:              JSON{"vip_support": true, "best_rates": true, "unlimited_transactions": true, "custom_solutions": true},
			Restrictions:          JSON{},
		},
	}
	
	for _, tier := range tiers {
		var existing TierConfiguration
		if err := db.Where("agent_tier = ?", tier.AgentTier).First(&existing).Error; err != nil {
			if err == gorm.ErrRecordNotFound {
				if err := db.Create(&tier).Error; err != nil {
					return err
				}
			}
		}
	}
	
	// Seed integration model configurations
	models := []IntegrationModelConfig{
		{
			ModelType:   TieredModel,
			ModelName:   "Tiered Agent System",
			Description: "Automatic tier assignment based on performance metrics",
			Configuration: JSON{
				"auto_upgrade":        true,
				"review_frequency":    "quarterly",
				"performance_weight":  0.6,
				"risk_weight":         0.4,
			},
			EligibilityCriteria: JSON{
				"minimum_operating_days": 0,
				"kyc_required":           true,
			},
			AutomationRules: JSON{
				"auto_tier_assignment": true,
				"performance_monitoring": true,
				"risk_based_adjustments": true,
			},
		},
		{
			ModelType:   OptInModel,
			ModelName:   "Opt-in Float System",
			Description: "Voluntary enrollment with manual approval process",
			Configuration: JSON{
				"manual_approval":     true,
				"review_frequency":    "biannual",
				"eligibility_strict":  true,
			},
			EligibilityCriteria: JSON{
				"minimum_operating_days": 30,
				"minimum_transactions":   50,
				"kyc_required":           true,
				"performance_threshold":  60.0,
			},
			AutomationRules: JSON{
				"auto_tier_assignment": false,
				"manual_limit_setting": true,
				"performance_monitoring": true,
			},
		},
		{
			ModelType:   DynamicModel,
			ModelName:   "Dynamic Hybrid System",
			Description: "AI-powered dynamic balance management with real-time adjustments",
			Configuration: JSON{
				"real_time_adjustments": true,
				"ai_powered":            true,
				"review_frequency":      "weekly",
				"adjustment_frequency":  "daily",
			},
			EligibilityCriteria: JSON{
				"minimum_operating_days": 60,
				"minimum_transactions":   100,
				"kyc_required":           true,
				"performance_threshold":  70.0,
			},
			AutomationRules: JSON{
				"dynamic_limit_adjustment": true,
				"predictive_analytics":     true,
				"risk_based_optimization":  true,
				"performance_correlation":  true,
			},
		},
	}
	
	for _, model := range models {
		var existing IntegrationModelConfig
		if err := db.Where("model_type = ?", model.ModelType).First(&existing).Error; err != nil {
			if err == gorm.ErrRecordNotFound {
				if err := db.Create(&model).Error; err != nil {
					return err
				}
			}
		}
	}
	
	return nil
}

// getEnv gets environment variable with default value
func getEnv(key, defaultValue string) string {

// requireEnv returns the value of an environment variable or panics if not set
// Use this for critical configuration like database passwords, API keys, etc.
func requireEnv(key string) string {
	value := os.Getenv(key)
	if value == "" {
		log.Fatalf("CRITICAL: Required environment variable %s is not set. Cannot start service.", key)
	}
	return value
}
	if value := os.Getenv(key); value != "" {

// requireEnv returns the value of an environment variable or panics if not set
// Use this for critical configuration like database passwords, API keys, etc.
func requireEnv(key string) string {
	value := os.Getenv(key)
	if value == "" {
		log.Fatalf("CRITICAL: Required environment variable %s is not set. Cannot start service.", key)
	}
	return value
}
		return value

// requireEnv returns the value of an environment variable or panics if not set
// Use this for critical configuration like database passwords, API keys, etc.
func requireEnv(key string) string {
	value := os.Getenv(key)
	if value == "" {
		log.Fatalf("CRITICAL: Required environment variable %s is not set. Cannot start service.", key)
	}
	return value
}
	}

// requireEnv returns the value of an environment variable or panics if not set
// Use this for critical configuration like database passwords, API keys, etc.
func requireEnv(key string) string {
	value := os.Getenv(key)
	if value == "" {
		log.Fatalf("CRITICAL: Required environment variable %s is not set. Cannot start service.", key)
	}
	return value
}
	return defaultValue

// requireEnv returns the value of an environment variable or panics if not set
// Use this for critical configuration like database passwords, API keys, etc.
func requireEnv(key string) string {
	value := os.Getenv(key)
	if value == "" {
		log.Fatalf("CRITICAL: Required environment variable %s is not set. Cannot start service.", key)
	}
	return value
}
}

// requireEnv returns the value of an environment variable or panics if not set
// Use this for critical configuration like database passwords, API keys, etc.
func requireEnv(key string) string {
	value := os.Getenv(key)
	if value == "" {
		log.Fatalf("CRITICAL: Required environment variable %s is not set. Cannot start service.", key)
	}
	return value
}

