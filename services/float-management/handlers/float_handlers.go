package handlers

import (
	"net/http"
	"strconv"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	
	"remittance/float-management/models"
	"remittance/float-management/services"
)

// FloatHandler handles float-related HTTP requests
type FloatHandler struct {
	floatService *services.FloatService
}

// NewFloatHandler creates a new float handler
func NewFloatHandler(floatService *services.FloatService) *FloatHandler {
	return &FloatHandler{
		floatService: floatService,
	}
}

// ==========================================
// FLOAT FACILITY ENDPOINTS
// ==========================================

// CreateFloatFacility creates a new float facility
// POST /api/v1/float/facilities
func (h *FloatHandler) CreateFloatFacility(c *gin.Context) {
	var req services.CreateFloatRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error":   "Invalid request format",
			"details": err.Error(),
		})
		return
	}
	
	// Set default currency if not provided
	if req.Currency == "" {
		req.Currency = "NGN"
	}
	
	// Set default settlement frequency if not provided
	if req.SettlementFrequency == "" {
		req.SettlementFrequency = "daily"
	}
	
	facility, err := h.floatService.CreateFloatFacility(c.Request.Context(), req)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error":   "Failed to create float facility",
			"details": err.Error(),
		})
		return
	}
	
	c.JSON(http.StatusCreated, gin.H{
		"message": "Float facility created successfully",
		"data":    facility,
	})
}

// GetFloatFacility retrieves a float facility
// GET /api/v1/float/facilities/:id
func (h *FloatHandler) GetFloatFacility(c *gin.Context) {
	facilityID, err := uuid.Parse(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "Invalid facility ID format",
		})
		return
	}
	
	var facility models.AgentFloat
	if err := h.floatService.DB().Preload("Transactions").Preload("Settlements").
		Preload("Assessments").First(&facility, facilityID).Error; err != nil {
		c.JSON(http.StatusNotFound, gin.H{
			"error": "Float facility not found",
		})
		return
	}
	
	c.JSON(http.StatusOK, gin.H{
		"data": facility,
	})
}

// GetAgentFloatFacility retrieves float facility by agent ID
// GET /api/v1/float/agents/:agent_id/facility
func (h *FloatHandler) GetAgentFloatFacility(c *gin.Context) {
	agentID, err := uuid.Parse(c.Param("agent_id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "Invalid agent ID format",
		})
		return
	}
	
	var facility models.AgentFloat
	if err := h.floatService.DB().Where("agent_id = ?", agentID).
		Preload("Transactions", "created_at > ?", time.Now().AddDate(0, -1, 0)).
		Preload("Settlements", "created_at > ?", time.Now().AddDate(0, -1, 0)).
		First(&facility).Error; err != nil {
		c.JSON(http.StatusNotFound, gin.H{
			"error": "Float facility not found for agent",
		})
		return
	}
	
	c.JSON(http.StatusOK, gin.H{
		"data": facility,
	})
}

// ListFloatFacilities lists all float facilities with pagination
// GET /api/v1/float/facilities
func (h *FloatHandler) ListFloatFacilities(c *gin.Context) {
	page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
	limit, _ := strconv.Atoi(c.DefaultQuery("limit", "20"))
	status := c.Query("status")
	tier := c.Query("tier")
	riskLevel := c.Query("risk_level")
	
	offset := (page - 1) * limit
	
	query := h.floatService.DB().Model(&models.AgentFloat{})
	
	// Apply filters
	if status != "" {
		query = query.Where("status = ?", status)
	}
	if tier != "" {
		query = query.Where("agent_tier = ?", tier)
	}
	if riskLevel != "" {
		query = query.Where("risk_level = ?", riskLevel)
	}
	
	var total int64
	query.Count(&total)
	
	var facilities []models.AgentFloat
	if err := query.Offset(offset).Limit(limit).Order("created_at DESC").
		Find(&facilities).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Failed to retrieve float facilities",
		})
		return
	}
	
	c.JSON(http.StatusOK, gin.H{
		"data": facilities,
		"pagination": gin.H{
			"page":  page,
			"limit": limit,
			"total": total,
			"pages": (total + int64(limit) - 1) / int64(limit),
		},
	})
}

// ApproveFloatFacility approves a pending float facility
// PUT /api/v1/float/facilities/:id/approve
func (h *FloatHandler) ApproveFloatFacility(c *gin.Context) {
	facilityID, err := uuid.Parse(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "Invalid facility ID format",
		})
		return
	}
	
	var req struct {
		ApprovedBy uuid.UUID `json:"approved_by" binding:"required"`
		Notes      string    `json:"notes"`
	}
	
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error":   "Invalid request format",
			"details": err.Error(),
		})
		return
	}
	
	if err := h.floatService.ApproveFloatFacility(c.Request.Context(), facilityID, req.ApprovedBy); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error":   "Failed to approve float facility",
			"details": err.Error(),
		})
		return
	}
	
	c.JSON(http.StatusOK, gin.H{
		"message": "Float facility approved successfully",
	})
}

// SuspendFloatFacility suspends a float facility
// PUT /api/v1/float/facilities/:id/suspend
func (h *FloatHandler) SuspendFloatFacility(c *gin.Context) {
	facilityID, err := uuid.Parse(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "Invalid facility ID format",
		})
		return
	}
	
	var req struct {
		SuspendedBy uuid.UUID `json:"suspended_by" binding:"required"`
		Reason      string    `json:"reason" binding:"required"`
	}
	
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error":   "Invalid request format",
			"details": err.Error(),
		})
		return
	}
	
	// Update facility status
	now := time.Now()
	updates := map[string]interface{}{
		"status":            models.FloatStatusSuspended,
		"suspended_at":      &now,
		"suspension_reason": req.Reason,
		"updated_by":        req.SuspendedBy,
		"updated_at":        now,
	}
	
	if err := h.floatService.DB().Model(&models.AgentFloat{}).
		Where("id = ?", facilityID).Updates(updates).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Failed to suspend float facility",
		})
		return
	}
	
	c.JSON(http.StatusOK, gin.H{
		"message": "Float facility suspended successfully",
	})
}

// ==========================================
// FLOAT UTILIZATION ENDPOINTS
// ==========================================

// UtilizeFloat utilizes float for a transaction
// POST /api/v1/float/utilize
func (h *FloatHandler) UtilizeFloat(c *gin.Context) {
	var req struct {
		AgentID       uuid.UUID `json:"agent_id" binding:"required"`
		Amount        float64   `json:"amount" binding:"required,gt=0"`
		TransactionID uuid.UUID `json:"transaction_id" binding:"required"`
		Description   string    `json:"description"`
	}
	
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error":   "Invalid request format",
			"details": err.Error(),
		})
		return
	}
	
	if err := h.floatService.UtilizeFloat(c.Request.Context(), req.AgentID, 
		req.Amount, req.TransactionID, req.Description); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error":   "Failed to utilize float",
			"details": err.Error(),
		})
		return
	}
	
	c.JSON(http.StatusOK, gin.H{
		"message": "Float utilized successfully",
	})
}

// SettleFloat settles outstanding float
// POST /api/v1/float/settle
func (h *FloatHandler) SettleFloat(c *gin.Context) {
	var req struct {
		AgentID      uuid.UUID `json:"agent_id" binding:"required"`
		Amount       float64   `json:"amount" binding:"required,gt=0"`
		PaymentRef   string    `json:"payment_reference" binding:"required"`
		SettledBy    uuid.UUID `json:"settled_by" binding:"required"`
		Description  string    `json:"description"`
	}
	
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error":   "Invalid request format",
			"details": err.Error(),
		})
		return
	}
	
	if err := h.floatService.SettleFloat(c.Request.Context(), req.AgentID, 
		req.Amount, req.PaymentRef, req.SettledBy); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error":   "Failed to settle float",
			"details": err.Error(),
		})
		return
	}
	
	c.JSON(http.StatusOK, gin.H{
		"message": "Float settled successfully",
	})
}

// GetFloatBalance gets current float balance for an agent
// GET /api/v1/float/agents/:agent_id/balance
func (h *FloatHandler) GetFloatBalance(c *gin.Context) {
	agentID, err := uuid.Parse(c.Param("agent_id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "Invalid agent ID format",
		})
		return
	}
	
	var facility models.AgentFloat
	if err := h.floatService.DB().Where("agent_id = ?", agentID).
		First(&facility).Error; err != nil {
		c.JSON(http.StatusNotFound, gin.H{
			"error": "Float facility not found for agent",
		})
		return
	}
	
	utilizationRate := 0.0
	if facility.FloatLimit > 0 {
		utilizationRate = (facility.UtilizedAmount / facility.FloatLimit) * 100
	}
	
	c.JSON(http.StatusOK, gin.H{
		"data": gin.H{
			"agent_id":         facility.AgentID,
			"float_limit":      facility.FloatLimit,
			"utilized_amount":  facility.UtilizedAmount,
			"available_float":  facility.AvailableFloat,
			"reserved_amount":  facility.ReservedAmount,
			"utilization_rate": utilizationRate,
			"currency":         facility.Currency,
			"status":           facility.Status,
			"risk_level":       facility.RiskLevel,
			"last_updated":     facility.UpdatedAt,
		},
	})
}

// ==========================================
// TRANSACTION ENDPOINTS
// ==========================================

// ListFloatTransactions lists float transactions
// GET /api/v1/float/transactions
func (h *FloatHandler) ListFloatTransactions(c *gin.Context) {
	page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
	limit, _ := strconv.Atoi(c.DefaultQuery("limit", "50"))
	agentID := c.Query("agent_id")
	txnType := c.Query("type")
	status := c.Query("status")
	
	offset := (page - 1) * limit
	
	query := h.floatService.DB().Model(&models.FloatTransaction{})
	
	// Apply filters
	if agentID != "" {
		if id, err := uuid.Parse(agentID); err == nil {
			query = query.Where("agent_id = ?", id)
		}
	}
	if txnType != "" {
		query = query.Where("type = ?", txnType)
	}
	if status != "" {
		query = query.Where("status = ?", status)
	}
	
	var total int64
	query.Count(&total)
	
	var transactions []models.FloatTransaction
	if err := query.Offset(offset).Limit(limit).Order("created_at DESC").
		Find(&transactions).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Failed to retrieve float transactions",
		})
		return
	}
	
	c.JSON(http.StatusOK, gin.H{
		"data": transactions,
		"pagination": gin.H{
			"page":  page,
			"limit": limit,
			"total": total,
			"pages": (total + int64(limit) - 1) / int64(limit),
		},
	})
}

// GetFloatTransaction retrieves a specific float transaction
// GET /api/v1/float/transactions/:id
func (h *FloatHandler) GetFloatTransaction(c *gin.Context) {
	transactionID, err := uuid.Parse(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "Invalid transaction ID format",
		})
		return
	}
	
	var transaction models.FloatTransaction
	if err := h.floatService.DB().Preload("AgentFloat").
		First(&transaction, transactionID).Error; err != nil {
		c.JSON(http.StatusNotFound, gin.H{
			"error": "Float transaction not found",
		})
		return
	}
	
	c.JSON(http.StatusOK, gin.H{
		"data": transaction,
	})
}

// ==========================================
// SETTLEMENT ENDPOINTS
// ==========================================

// ListFloatSettlements lists float settlements
// GET /api/v1/float/settlements
func (h *FloatHandler) ListFloatSettlements(c *gin.Context) {
	page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
	limit, _ := strconv.Atoi(c.DefaultQuery("limit", "20"))
	agentID := c.Query("agent_id")
	status := c.Query("status")
	
	offset := (page - 1) * limit
	
	query := h.floatService.DB().Model(&models.FloatSettlement{})
	
	// Apply filters
	if agentID != "" {
		if id, err := uuid.Parse(agentID); err == nil {
			query = query.Where("agent_id = ?", id)
		}
	}
	if status != "" {
		query = query.Where("status = ?", status)
	}
	
	var total int64
	query.Count(&total)
	
	var settlements []models.FloatSettlement
	if err := query.Offset(offset).Limit(limit).Order("created_at DESC").
		Find(&settlements).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Failed to retrieve float settlements",
		})
		return
	}
	
	c.JSON(http.StatusOK, gin.H{
		"data": settlements,
		"pagination": gin.H{
			"page":  page,
			"limit": limit,
			"total": total,
			"pages": (total + int64(limit) - 1) / int64(limit),
		},
	})
}

// ==========================================
// RISK ASSESSMENT ENDPOINTS
// ==========================================

// TriggerRiskAssessment triggers a new risk assessment
// POST /api/v1/float/risk-assessment
func (h *FloatHandler) TriggerRiskAssessment(c *gin.Context) {
	var req struct {
		AgentID        uuid.UUID `json:"agent_id" binding:"required"`
		AssessmentType string    `json:"assessment_type"`
		RequestedBy    uuid.UUID `json:"requested_by" binding:"required"`
	}
	
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error":   "Invalid request format",
			"details": err.Error(),
		})
		return
	}
	
	if req.AssessmentType == "" {
		req.AssessmentType = "manual"
	}
	
	// This would call the risk assessment service
	// For now, return success
	c.JSON(http.StatusAccepted, gin.H{
		"message": "Risk assessment triggered successfully",
		"data": gin.H{
			"agent_id":        req.AgentID,
			"assessment_type": req.AssessmentType,
			"status":          "processing",
		},
	})
}

// ListRiskAssessments lists risk assessments
// GET /api/v1/float/risk-assessments
func (h *FloatHandler) ListRiskAssessments(c *gin.Context) {
	page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
	limit, _ := strconv.Atoi(c.DefaultQuery("limit", "20"))
	agentID := c.Query("agent_id")
	
	offset := (page - 1) * limit
	
	query := h.floatService.DB().Model(&models.RiskAssessment{})
	
	// Apply filters
	if agentID != "" {
		if id, err := uuid.Parse(agentID); err == nil {
			query = query.Where("agent_id = ?", id)
		}
	}
	
	var total int64
	query.Count(&total)
	
	var assessments []models.RiskAssessment
	if err := query.Offset(offset).Limit(limit).Order("assessment_date DESC").
		Find(&assessments).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Failed to retrieve risk assessments",
		})
		return
	}
	
	c.JSON(http.StatusOK, gin.H{
		"data": assessments,
		"pagination": gin.H{
			"page":  page,
			"limit": limit,
			"total": total,
			"pages": (total + int64(limit) - 1) / int64(limit),
		},
	})
}

// ==========================================
// LIMIT MANAGEMENT ENDPOINTS
// ==========================================

// UpdateFloatLimit updates float limit
// PUT /api/v1/float/facilities/:id/limit
func (h *FloatHandler) UpdateFloatLimit(c *gin.Context) {
	facilityID, err := uuid.Parse(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "Invalid facility ID format",
		})
		return
	}
	
	var req struct {
		NewLimit  float64   `json:"new_limit" binding:"required,gt=0"`
		Reason    string    `json:"reason" binding:"required"`
		UpdatedBy uuid.UUID `json:"updated_by" binding:"required"`
	}
	
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error":   "Invalid request format",
			"details": err.Error(),
		})
		return
	}
	
	if err := h.floatService.UpdateFloatLimit(c.Request.Context(), facilityID, 
		req.NewLimit, req.Reason, req.UpdatedBy); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error":   "Failed to update float limit",
			"details": err.Error(),
		})
		return
	}
	
	c.JSON(http.StatusOK, gin.H{
		"message": "Float limit updated successfully",
	})
}

// ==========================================
// ALERT ENDPOINTS
// ==========================================

// ListFloatAlerts lists float alerts
// GET /api/v1/float/alerts
func (h *FloatHandler) ListFloatAlerts(c *gin.Context) {
	page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
	limit, _ := strconv.Atoi(c.DefaultQuery("limit", "20"))
	agentID := c.Query("agent_id")
	severity := c.Query("severity")
	status := c.Query("status")
	
	offset := (page - 1) * limit
	
	query := h.floatService.DB().Model(&models.FloatAlert{})
	
	// Apply filters
	if agentID != "" {
		if id, err := uuid.Parse(agentID); err == nil {
			query = query.Where("agent_id = ?", id)
		}
	}
	if severity != "" {
		query = query.Where("severity = ?", severity)
	}
	if status != "" {
		query = query.Where("status = ?", status)
	}
	
	var total int64
	query.Count(&total)
	
	var alerts []models.FloatAlert
	if err := query.Offset(offset).Limit(limit).Order("created_at DESC").
		Find(&alerts).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Failed to retrieve float alerts",
		})
		return
	}
	
	c.JSON(http.StatusOK, gin.H{
		"data": alerts,
		"pagination": gin.H{
			"page":  page,
			"limit": limit,
			"total": total,
			"pages": (total + int64(limit) - 1) / int64(limit),
		},
	})
}

// AcknowledgeAlert acknowledges a float alert
// PUT /api/v1/float/alerts/:id/acknowledge
func (h *FloatHandler) AcknowledgeAlert(c *gin.Context) {
	alertID, err := uuid.Parse(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "Invalid alert ID format",
		})
		return
	}
	
	var req struct {
		AcknowledgedBy uuid.UUID `json:"acknowledged_by" binding:"required"`
		Notes          string    `json:"notes"`
	}
	
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error":   "Invalid request format",
			"details": err.Error(),
		})
		return
	}
	
	now := time.Now()
	updates := map[string]interface{}{
		"acknowledged_by": req.AcknowledgedBy,
		"acknowledged_at": &now,
		"status":          "acknowledged",
		"updated_at":      now,
	}
	
	if err := h.floatService.DB().Model(&models.FloatAlert{}).
		Where("id = ?", alertID).Updates(updates).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Failed to acknowledge alert",
		})
		return
	}
	
	c.JSON(http.StatusOK, gin.H{
		"message": "Alert acknowledged successfully",
	})
}

// ==========================================
// ANALYTICS ENDPOINTS
// ==========================================

// GetFloatAnalytics gets float analytics and statistics
// GET /api/v1/float/analytics
func (h *FloatHandler) GetFloatAnalytics(c *gin.Context) {
	// Get overall statistics
	var stats struct {
		TotalFacilities    int64   `json:"total_facilities"`
		ActiveFacilities   int64   `json:"active_facilities"`
		TotalFloatLimit    float64 `json:"total_float_limit"`
		TotalUtilized      float64 `json:"total_utilized"`
		TotalAvailable     float64 `json:"total_available"`
		OverallUtilization float64 `json:"overall_utilization"`
	}
	
	h.floatService.DB().Model(&models.AgentFloat{}).Count(&stats.TotalFacilities)
	h.floatService.DB().Model(&models.AgentFloat{}).Where("status = ?", "active").Count(&stats.ActiveFacilities)
	
	h.floatService.DB().Model(&models.AgentFloat{}).
		Select("COALESCE(SUM(float_limit), 0)").Row().Scan(&stats.TotalFloatLimit)
	h.floatService.DB().Model(&models.AgentFloat{}).
		Select("COALESCE(SUM(utilized_amount), 0)").Row().Scan(&stats.TotalUtilized)
	h.floatService.DB().Model(&models.AgentFloat{}).
		Select("COALESCE(SUM(available_float), 0)").Row().Scan(&stats.TotalAvailable)
	
	if stats.TotalFloatLimit > 0 {
		stats.OverallUtilization = (stats.TotalUtilized / stats.TotalFloatLimit) * 100
	}
	
	// Get risk distribution
	var riskDistribution []struct {
		RiskLevel string `json:"risk_level"`
		Count     int64  `json:"count"`
	}
	
	h.floatService.DB().Model(&models.AgentFloat{}).
		Select("risk_level, COUNT(*) as count").
		Group("risk_level").
		Find(&riskDistribution)
	
	// Get tier distribution
	var tierDistribution []struct {
		AgentTier string `json:"agent_tier"`
		Count     int64  `json:"count"`
	}
	
	h.floatService.DB().Model(&models.AgentFloat{}).
		Select("agent_tier, COUNT(*) as count").
		Group("agent_tier").
		Find(&tierDistribution)
	
	c.JSON(http.StatusOK, gin.H{
		"data": gin.H{
			"overall_stats":      stats,
			"risk_distribution":  riskDistribution,
			"tier_distribution":  tierDistribution,
		},
	})
}

// ==========================================
// INTEGRATION MODEL ENDPOINTS
// ==========================================

// GetIntegrationModels returns available integration models
// GET /api/v1/float/integration-models
func (h *FloatHandler) GetIntegrationModels(c *gin.Context) {
	models := []gin.H{
		{
			"id":          "tiered",
			"name":        "Tiered Agent System",
			"description": "Different float access based on agent tiers",
			"features": []string{
				"Tier-based float limits",
				"Graduated access levels",
				"Performance-based upgrades",
			},
		},
		{
			"id":          "opt_in",
			"name":        "Opt-in Float System",
			"description": "Voluntary float access for qualified agents",
			"features": []string{
				"Voluntary enrollment",
				"Performance-based eligibility",
				"Risk-based approval",
			},
		},
		{
			"id":          "dynamic",
			"name":        "Dynamic Hybrid System",
			"description": "AI-powered dynamic balance management",
			"features": []string{
				"Intelligent balance optimization",
				"Predictive float allocation",
				"Real-time risk adjustments",
			},
		},
	}
	
	c.JSON(http.StatusOK, gin.H{
		"data": models,
	})
}

// SetIntegrationModel sets the integration model for an agent
// PUT /api/v1/float/agents/:agent_id/integration-model
func (h *FloatHandler) SetIntegrationModel(c *gin.Context) {
	agentID, err := uuid.Parse(c.Param("agent_id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "Invalid agent ID format",
		})
		return
	}
	
	var req struct {
		ModelType string    `json:"model_type" binding:"required"`
		UpdatedBy uuid.UUID `json:"updated_by" binding:"required"`
		Config    gin.H     `json:"config"`
	}
	
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error":   "Invalid request format",
			"details": err.Error(),
		})
		return
	}
	
	// Update agent's integration model
	updates := map[string]interface{}{
		"updated_at": time.Now(),
		"updated_by": req.UpdatedBy,
		"metadata": models.JSON{
			"integration_model": req.ModelType,
			"model_config":      req.Config,
		},
	}
	
	if err := h.floatService.DB().Model(&models.AgentFloat{}).
		Where("agent_id = ?", agentID).Updates(updates).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Failed to update integration model",
		})
		return
	}
	
	c.JSON(http.StatusOK, gin.H{
		"message": "Integration model updated successfully",
	})
}

