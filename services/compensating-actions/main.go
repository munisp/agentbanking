package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"strconv"
	"time"

	"github.com/gin-contrib/cors"
	"github.com/gin-gonic/gin"
	"github.com/go-redis/redis/v8"
	_ "github.com/lib/pq"
	"gorm.io/driver/postgres"
	"gorm.io/gorm"
)

// Configuration
var (
	databaseURL = getEnv("DATABASE_URL", "postgresql://postgres:postgres123@localhost:5432/remittance")
	redisURL    = getEnv("REDIS_URL", "redis://localhost:6379")
	servicePort = getEnv("SERVICE_PORT", "8150")
)

// Database models
type CompensatingAction struct {
	ID          uint      `json:"id" gorm:"primaryKey"`
	ActionID    string    `json:"action_id" gorm:"uniqueIndex;not null"`
	SagaID      string    `json:"saga_id" gorm:"not null;index"`
	ActionType  string    `json:"action_type" gorm:"not null"`
	ServiceName string    `json:"service_name" gorm:"not null"`
	Payload     string    `json:"payload" gorm:"type:text"`
	Status      string    `json:"status" gorm:"default:'PENDING'"`
	RetryCount  int       `json:"retry_count" gorm:"default:0"`
	MaxRetries  int       `json:"max_retries" gorm:"default:3"`
	CreatedAt   time.Time `json:"created_at"`
	UpdatedAt   time.Time `json:"updated_at"`
	ExecutedAt  *time.Time `json:"executed_at"`
}

type ActionExecution struct {
	ID        uint      `json:"id" gorm:"primaryKey"`
	ActionID  string    `json:"action_id" gorm:"not null;index"`
	Status    string    `json:"status" gorm:"not null"`
	Result    string    `json:"result" gorm:"type:text"`
	ErrorMsg  string    `json:"error_message" gorm:"type:text"`
	Duration  int64     `json:"duration_ms"`
	CreatedAt time.Time `json:"created_at"`
}

// Request/Response models
type CreateActionRequest struct {
	ActionID    string            `json:"action_id" binding:"required"`
	SagaID      string            `json:"saga_id" binding:"required"`
	ActionType  string            `json:"action_type" binding:"required"`
	ServiceName string            `json:"service_name" binding:"required"`
	Payload     map[string]interface{} `json:"payload"`
	MaxRetries  int               `json:"max_retries"`
}

type ExecuteActionRequest struct {
	ActionID string `json:"action_id" binding:"required"`
}

type ActionResponse struct {
	ActionID    string    `json:"action_id"`
	SagaID      string    `json:"saga_id"`
	ActionType  string    `json:"action_type"`
	ServiceName string    `json:"service_name"`
	Status      string    `json:"status"`
	RetryCount  int       `json:"retry_count"`
	MaxRetries  int       `json:"max_retries"`
	CreatedAt   time.Time `json:"created_at"`
	UpdatedAt   time.Time `json:"updated_at"`
	ExecutedAt  *time.Time `json:"executed_at"`
}

// Global variables
var (
	db          *gorm.DB
	redisClient *redis.Client
	ctx         = context.Background()
)

func main() {
	// Initialize database
	if err := initDatabase(); err != nil {
		log.Fatalf("Failed to initialize database: %v", err)
	}

	// Initialize Redis
	if err := initRedis(); err != nil {
		log.Fatalf("Failed to initialize Redis: %v", err)
	}

	// Setup Gin router
	r := gin.Default()

	// CORS middleware
	config := cors.DefaultConfig()
	config.AllowAllOrigins = true
	config.AllowMethods = []string{"GET", "POST", "PUT", "DELETE", "OPTIONS"}
	config.AllowHeaders = []string{"*"}
	r.Use(cors.New(config))

	// Routes
	r.GET("/health", healthCheck)
	
	api := r.Group("/api/v1")
	{
		api.POST("/actions", createCompensatingAction)
		api.GET("/actions/:actionId", getCompensatingAction)
		api.POST("/actions/:actionId/execute", executeCompensatingAction)
		api.GET("/actions", listCompensatingActions)
		api.GET("/sagas/:sagaId/actions", getSagaActions)
		api.PUT("/actions/:actionId/status", updateActionStatus)
		api.GET("/actions/:actionId/executions", getActionExecutions)
	}

	// Start server
	port := ":" + servicePort
	log.Printf("Compensating Actions Service starting on port %s", port)
	if err := r.Run(port); err != nil {
		log.Fatalf("Failed to start server: %v", err)
	}
}

func initDatabase() error {
	var err error
	db, err = gorm.Open(postgres.Open(databaseURL), &gorm.Config{})
	if err != nil {
		return fmt.Errorf("failed to connect to database: %w", err)
	}

	// Auto-migrate tables
	if err := db.AutoMigrate(&CompensatingAction{}, &ActionExecution{}); err != nil {
		return fmt.Errorf("failed to migrate database: %w", err)
	}

	log.Println("Database initialized successfully")
	return nil
}

func initRedis() error {
	opt, err := redis.ParseURL(redisURL)
	if err != nil {
		return fmt.Errorf("failed to parse Redis URL: %w", err)
	}

	redisClient = redis.NewClient(opt)

	// Test connection
	if err := redisClient.Ping(ctx).Err(); err != nil {
		return fmt.Errorf("failed to connect to Redis: %w", err)
	}

	log.Println("Redis connection established")
	return nil
}

func healthCheck(c *gin.Context) {
	// Check database connection
	sqlDB, err := db.DB()
	if err != nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{
			"status":  "unhealthy",
			"error":   "database connection failed",
			"details": err.Error(),
		})
		return
	}

	if err := sqlDB.Ping(); err != nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{
			"status":  "unhealthy",
			"error":   "database ping failed",
			"details": err.Error(),
		})
		return
	}

	// Check Redis connection
	if err := redisClient.Ping(ctx).Err(); err != nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{
			"status":  "unhealthy",
			"error":   "redis connection failed",
			"details": err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"status":    "healthy",
		"service":   "compensating-actions",
		"version":   "1.0.0",
		"timestamp": time.Now().Format(time.RFC3339),
		"database":  "connected",
		"redis":     "connected",
	})
}

func createCompensatingAction(c *gin.Context) {
	var req CreateActionRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// Convert payload to JSON string
	payloadJSON, err := json.Marshal(req.Payload)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid payload format"})
		return
	}

	// Set default max retries if not provided
	if req.MaxRetries == 0 {
		req.MaxRetries = 3
	}

	action := CompensatingAction{
		ActionID:    req.ActionID,
		SagaID:      req.SagaID,
		ActionType:  req.ActionType,
		ServiceName: req.ServiceName,
		Payload:     string(payloadJSON),
		Status:      "PENDING",
		MaxRetries:  req.MaxRetries,
		CreatedAt:   time.Now(),
		UpdatedAt:   time.Now(),
	}

	if err := db.Create(&action).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to create compensating action"})
		return
	}

	// Cache action in Redis for quick access
	actionJSON, _ := json.Marshal(action)
	redisClient.SetEX(ctx, fmt.Sprintf("action:%s", action.ActionID), actionJSON, time.Hour)

	c.JSON(http.StatusCreated, convertToActionResponse(action))
}

func getCompensatingAction(c *gin.Context) {
	actionID := c.Param("actionId")

	// Try Redis cache first
	cached, err := redisClient.Get(ctx, fmt.Sprintf("action:%s", actionID)).Result()
	if err == nil {
		var action CompensatingAction
		if json.Unmarshal([]byte(cached), &action) == nil {
			c.JSON(http.StatusOK, convertToActionResponse(action))
			return
		}
	}

	// Get from database
	var action CompensatingAction
	if err := db.Where("action_id = ?", actionID).First(&action).Error; err != nil {
		if err == gorm.ErrRecordNotFound {
			c.JSON(http.StatusNotFound, gin.H{"error": "compensating action not found"})
		} else {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to get compensating action"})
		}
		return
	}

	// Update cache
	actionJSON, _ := json.Marshal(action)
	redisClient.SetEX(ctx, fmt.Sprintf("action:%s", actionID), actionJSON, time.Hour)

	c.JSON(http.StatusOK, convertToActionResponse(action))
}

func executeCompensatingAction(c *gin.Context) {
	actionID := c.Param("actionId")

	// Get action from database
	var action CompensatingAction
	if err := db.Where("action_id = ?", actionID).First(&action).Error; err != nil {
		if err == gorm.ErrRecordNotFound {
			c.JSON(http.StatusNotFound, gin.H{"error": "compensating action not found"})
		} else {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to get compensating action"})
		}
		return
	}

	// Check if action can be executed
	if action.Status == "COMPLETED" {
		c.JSON(http.StatusConflict, gin.H{"error": "action already completed"})
		return
	}

	if action.Status == "FAILED" && action.RetryCount >= action.MaxRetries {
		c.JSON(http.StatusConflict, gin.H{"error": "action failed and max retries exceeded"})
		return
	}

	// Execute the compensating action
	startTime := time.Now()
	result, err := performCompensatingAction(action)
	duration := time.Since(startTime).Milliseconds()

	// Create execution record
	execution := ActionExecution{
		ActionID:  actionID,
		Status:    "SUCCESS",
		Result:    result,
		Duration:  duration,
		CreatedAt: time.Now(),
	}

	if err != nil {
		execution.Status = "FAILED"
		execution.ErrorMsg = err.Error()
	}

	// Save execution record
	db.Create(&execution)

	// Update action status
	now := time.Now()
	if err != nil {
		action.Status = "FAILED"
		action.RetryCount++
		action.UpdatedAt = now
	} else {
		action.Status = "COMPLETED"
		action.ExecutedAt = &now
		action.UpdatedAt = now
	}

	db.Save(&action)

	// Update cache
	actionJSON, _ := json.Marshal(action)
	redisClient.SetEX(ctx, fmt.Sprintf("action:%s", actionID), actionJSON, time.Hour)

	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":      "action execution failed",
			"details":    err.Error(),
			"retry_count": action.RetryCount,
			"max_retries": action.MaxRetries,
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"status":      "success",
		"message":     "compensating action executed successfully",
		"result":      result,
		"duration_ms": duration,
		"action":      convertToActionResponse(action),
	})
}

func performCompensatingAction(action CompensatingAction) (string, error) {
	// Simulate compensating action execution based on action type
	switch action.ActionType {
	case "REFUND_PAYMENT":
		return performRefund(action)
	case "REVERSE_TRANSACTION":
		return performReversal(action)
	case "UNLOCK_ACCOUNT":
		return performAccountUnlock(action)
	case "RESTORE_BALANCE":
		return performBalanceRestore(action)
	case "CANCEL_ORDER":
		return performOrderCancellation(action)
	case "ROLLBACK_UPDATE":
		return performUpdateRollback(action)
	default:
		return performGenericCompensation(action)
	}
}

func performRefund(action CompensatingAction) (string, error) {
	// Simulate refund processing
	time.Sleep(100 * time.Millisecond)
	
	var payload map[string]interface{}
	json.Unmarshal([]byte(action.Payload), &payload)
	
	amount := payload["amount"]
	accountID := payload["account_id"]
	
	result := map[string]interface{}{
		"action":           "refund_processed",
		"account_id":       accountID,
		"refund_amount":    amount,
		"refund_id":        fmt.Sprintf("REF_%s_%d", action.ActionID, time.Now().Unix()),
		"processing_time":  "100ms",
	}
	
	resultJSON, _ := json.Marshal(result)
	return string(resultJSON), nil
}

func performReversal(action CompensatingAction) (string, error) {
	// Simulate transaction reversal
	time.Sleep(150 * time.Millisecond)
	
	var payload map[string]interface{}
	json.Unmarshal([]byte(action.Payload), &payload)
	
	result := map[string]interface{}{
		"action":           "transaction_reversed",
		"original_tx_id":   payload["transaction_id"],
		"reversal_id":      fmt.Sprintf("REV_%s_%d", action.ActionID, time.Now().Unix()),
		"processing_time":  "150ms",
	}
	
	resultJSON, _ := json.Marshal(result)
	return string(resultJSON), nil
}

func performAccountUnlock(action CompensatingAction) (string, error) {
	// Simulate account unlock
	time.Sleep(50 * time.Millisecond)
	
	var payload map[string]interface{}
	json.Unmarshal([]byte(action.Payload), &payload)
	
	result := map[string]interface{}{
		"action":           "account_unlocked",
		"account_id":       payload["account_id"],
		"unlock_reason":    "compensating_action",
		"processing_time":  "50ms",
	}
	
	resultJSON, _ := json.Marshal(result)
	return string(resultJSON), nil
}

func performBalanceRestore(action CompensatingAction) (string, error) {
	// Simulate balance restoration
	time.Sleep(120 * time.Millisecond)
	
	var payload map[string]interface{}
	json.Unmarshal([]byte(action.Payload), &payload)
	
	result := map[string]interface{}{
		"action":           "balance_restored",
		"account_id":       payload["account_id"],
		"restored_amount":  payload["amount"],
		"processing_time":  "120ms",
	}
	
	resultJSON, _ := json.Marshal(result)
	return string(resultJSON), nil
}

func performOrderCancellation(action CompensatingAction) (string, error) {
	// Simulate order cancellation
	time.Sleep(80 * time.Millisecond)
	
	var payload map[string]interface{}
	json.Unmarshal([]byte(action.Payload), &payload)
	
	result := map[string]interface{}{
		"action":           "order_cancelled",
		"order_id":         payload["order_id"],
		"cancellation_id":  fmt.Sprintf("CAN_%s_%d", action.ActionID, time.Now().Unix()),
		"processing_time":  "80ms",
	}
	
	resultJSON, _ := json.Marshal(result)
	return string(resultJSON), nil
}

func performUpdateRollback(action CompensatingAction) (string, error) {
	// Simulate update rollback
	time.Sleep(90 * time.Millisecond)
	
	var payload map[string]interface{}
	json.Unmarshal([]byte(action.Payload), &payload)
	
	result := map[string]interface{}{
		"action":           "update_rolled_back",
		"entity_id":        payload["entity_id"],
		"rollback_id":      fmt.Sprintf("RB_%s_%d", action.ActionID, time.Now().Unix()),
		"processing_time":  "90ms",
	}
	
	resultJSON, _ := json.Marshal(result)
	return string(resultJSON), nil
}

func performGenericCompensation(action CompensatingAction) (string, error) {
	// Generic compensation handler
	time.Sleep(100 * time.Millisecond)
	
	result := map[string]interface{}{
		"action":           "generic_compensation",
		"action_type":      action.ActionType,
		"service":          action.ServiceName,
		"compensation_id":  fmt.Sprintf("COMP_%s_%d", action.ActionID, time.Now().Unix()),
		"processing_time":  "100ms",
	}
	
	resultJSON, _ := json.Marshal(result)
	return string(resultJSON), nil
}

func listCompensatingActions(c *gin.Context) {
	// Parse query parameters
	sagaID := c.Query("saga_id")
	status := c.Query("status")
	limitStr := c.DefaultQuery("limit", "100")
	offsetStr := c.DefaultQuery("offset", "0")

	limit, _ := strconv.Atoi(limitStr)
	offset, _ := strconv.Atoi(offsetStr)

	query := db.Model(&CompensatingAction{})

	if sagaID != "" {
		query = query.Where("saga_id = ?", sagaID)
	}

	if status != "" {
		query = query.Where("status = ?", status)
	}

	var actions []CompensatingAction
	if err := query.Limit(limit).Offset(offset).Order("created_at DESC").Find(&actions).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to list compensating actions"})
		return
	}

	var responses []ActionResponse
	for _, action := range actions {
		responses = append(responses, convertToActionResponse(action))
	}

	c.JSON(http.StatusOK, gin.H{
		"actions": responses,
		"count":   len(responses),
		"limit":   limit,
		"offset":  offset,
	})
}

func getSagaActions(c *gin.Context) {
	sagaID := c.Param("sagaId")

	var actions []CompensatingAction
	if err := db.Where("saga_id = ?", sagaID).Order("created_at ASC").Find(&actions).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to get saga actions"})
		return
	}

	var responses []ActionResponse
	for _, action := range actions {
		responses = append(responses, convertToActionResponse(action))
	}

	c.JSON(http.StatusOK, gin.H{
		"saga_id": sagaID,
		"actions": responses,
		"count":   len(responses),
	})
}

func updateActionStatus(c *gin.Context) {
	actionID := c.Param("actionId")

	var req struct {
		Status string `json:"status" binding:"required"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	var action CompensatingAction
	if err := db.Where("action_id = ?", actionID).First(&action).Error; err != nil {
		if err == gorm.ErrRecordNotFound {
			c.JSON(http.StatusNotFound, gin.H{"error": "compensating action not found"})
		} else {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to get compensating action"})
		}
		return
	}

	action.Status = req.Status
	action.UpdatedAt = time.Now()

	if err := db.Save(&action).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to update action status"})
		return
	}

	// Update cache
	actionJSON, _ := json.Marshal(action)
	redisClient.SetEX(ctx, fmt.Sprintf("action:%s", actionID), actionJSON, time.Hour)

	c.JSON(http.StatusOK, convertToActionResponse(action))
}

func getActionExecutions(c *gin.Context) {
	actionID := c.Param("actionId")

	var executions []ActionExecution
	if err := db.Where("action_id = ?", actionID).Order("created_at DESC").Find(&executions).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to get action executions"})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"action_id":  actionID,
		"executions": executions,
		"count":      len(executions),
	})
}

func convertToActionResponse(action CompensatingAction) ActionResponse {
	return ActionResponse{
		ActionID:    action.ActionID,
		SagaID:      action.SagaID,
		ActionType:  action.ActionType,
		ServiceName: action.ServiceName,
		Status:      action.Status,
		RetryCount:  action.RetryCount,
		MaxRetries:  action.MaxRetries,
		CreatedAt:   action.CreatedAt,
		UpdatedAt:   action.UpdatedAt,
		ExecutedAt:  action.ExecutedAt,
	}
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

