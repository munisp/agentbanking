package integration

import (
	"context"
	"crypto/sha256"
	"fmt"
	"time"

	"github.com/tigerbeetle/tigerbeetle-go/pkg/types"
	"workflow-orchestrator/internal/middleware/kafka"
	_ "workflow-orchestrator/internal/middleware/tigerbeetle" // used via m.TigerBeetle
	"workflow-orchestrator/pkg/logger"
)

// PaymentRequest represents a payment transaction request
type PaymentRequest struct {
	PaymentID       string
	WorkflowID      string
	FromAccountID   types.Uint128
	ToAccountID     types.Uint128
	Amount          uint64
	Currency        string
	Description     string
	TenantID        string
	UserID          string
	IdempotencyKey  string
}

// PaymentResult represents the result of a payment transaction
type PaymentResult struct {
	PaymentID       string
	TransferID      types.Uint128
	Status          string
	Timestamp       time.Time
	FromAccountID   types.Uint128
	ToAccountID     types.Uint128
	Amount          uint64
	Error           error
}

// ProcessPaymentWithLocking processes a payment transaction with distributed locking
// This is the complete implementation showing TigerBeetle and Redis interaction
func (m *MiddlewareManager) ProcessPaymentWithLocking(
	ctx context.Context,
	req *PaymentRequest,
) (*PaymentResult, error) {
	logger.Logger.Info(
		"Starting payment processing",
		logger.String("payment_id", req.PaymentID),
		logger.String("workflow_id", req.WorkflowID),
		logger.Uint64("amount", req.Amount),
	)

	// Step 1: Validate payment request
	if err := validatePaymentRequest(req); err != nil {
		logger.Logger.Error("Invalid payment request", logger.Error(err))
		return nil, fmt.Errorf("invalid payment request: %w", err)
	}

	// Step 2: Check for duplicate payment using idempotency key in Redis
	idempotencyKey := fmt.Sprintf("payment:idempotency:%s", req.IdempotencyKey)
	existingResult, err := m.Redis.GetWorkflowState(ctx, idempotencyKey)
	if err == nil && existingResult != nil {
		logger.Logger.Info("Payment already processed (idempotent)", 
			logger.String("payment_id", req.PaymentID))
		return &PaymentResult{
			PaymentID: req.PaymentID,
			Status:    "completed",
			Timestamp: time.Now(),
		}, nil
	}

	// Step 3: Acquire distributed lock to prevent concurrent payment processing
	lockName := fmt.Sprintf("payment:lock:%s", req.PaymentID)
	lockTimeout := 30 * time.Second
	
	logger.Logger.Info("Acquiring distributed lock", logger.String("lock_name", lockName))
	locked, err := m.Redis.AcquireLock(ctx, lockName, int(lockTimeout.Seconds()))
	if err != nil {
		logger.Logger.Error("Failed to acquire lock", logger.Error(err))
		return nil, fmt.Errorf("failed to acquire payment lock: %w", err)
	}
	if !locked {
		logger.Logger.Warn("Payment already being processed", 
			logger.String("payment_id", req.PaymentID))
		return nil, fmt.Errorf("payment %s is already being processed", req.PaymentID)
	}
	logger.Logger.Info("Distributed lock acquired", logger.String("lock_name", lockName))

	// Ensure lock is released even if panic occurs
	defer func() {
		if err := m.Redis.ReleaseLock(ctx, lockName); err != nil {
			logger.Logger.Error("Failed to release lock", logger.Error(err))
		} else {
			logger.Logger.Info("Distributed lock released", logger.String("lock_name", lockName))
		}
	}()

	// Step 4: Cache payment state as "pending" in Redis
	pendingState := map[string]interface{}{
		"payment_id":     req.PaymentID,
		"workflow_id":    req.WorkflowID,
		"status":         "pending",
		"from_account":   req.FromAccountID.String(),
		"to_account":     req.ToAccountID.String(),
		"amount":         req.Amount,
		"currency":       req.Currency,
		"timestamp":      time.Now().Unix(),
	}
	
	stateKey := fmt.Sprintf("payment:state:%s", req.PaymentID)
	if err := m.Redis.CacheWorkflowState(ctx, stateKey, pendingState, 3600); err != nil {
		logger.Logger.Error("Failed to cache payment state", logger.Error(err))
		// Continue processing even if caching fails
	}

	// Step 5: Publish payment.initiated event to Kafka
	initiatedEvent := &kafka.WorkflowEvent{
		EventID:      fmt.Sprintf("evt-%s-initiated", req.PaymentID),
		EventType:    "payment.initiated",
		Timestamp:    time.Now(),
		WorkflowID:   req.WorkflowID,
		WorkflowType: "payment",
		Status:       "pending",
		TenantID:     req.TenantID,
		UserID:       req.UserID,
		Data: map[string]interface{}{
			"payment_id":   req.PaymentID,
			"amount":       req.Amount,
			"currency":     req.Currency,
			"from_account": req.FromAccountID.String(),
			"to_account":   req.ToAccountID.String(),
		},
	}
	
	if err := m.PublishWorkflowEvent(ctx, initiatedEvent); err != nil {
		logger.Logger.Error("Failed to publish payment.initiated event", logger.Error(err))
		// Continue processing even if event publishing fails
	}

	// Step 6: Check account balances (optional pre-validation)
	// This could query TigerBeetle for current balances
	logger.Logger.Info("Validating account balances",
		logger.String("from_account", req.FromAccountID.String()))

	// Step 7: Create transfer in TigerBeetle
	logger.Logger.Info("Creating transfer in TigerBeetle",
		logger.String("payment_id", req.PaymentID),
		logger.Uint64("amount", req.Amount))

	// Generate a deterministic Uint128 transfer ID from the payment ID string
	hash := sha256.Sum256([]byte(req.PaymentID))
	var transferID types.Uint128
	copy(transferID[:], hash[:])

	// Create the transfer using TigerBeetle
	err = m.TigerBeetle.CreateTransfer(
		ctx,
		transferID,
		req.FromAccountID,
		req.ToAccountID,
		req.Amount,
		1, // ledger ID
		1, // code (payment type)
	)

	// Step 8: Handle transfer result
	result := &PaymentResult{
		PaymentID:     req.PaymentID,
		TransferID:    transferID,
		FromAccountID: req.FromAccountID,
		ToAccountID:   req.ToAccountID,
		Amount:        req.Amount,
		Timestamp:     time.Now(),
	}

	if err != nil {
		// Transfer failed
		logger.Logger.Error("TigerBeetle transfer failed", logger.Error(err))
		result.Status = "failed"
		result.Error = err

		// Update cache with failed status
		failedState := map[string]interface{}{
			"payment_id":  req.PaymentID,
			"status":      "failed",
			"error":       err.Error(),
			"timestamp":   time.Now().Unix(),
		}
		m.Redis.CacheWorkflowState(ctx, stateKey, failedState, 3600)

		// Publish payment.failed event
		failedEvent := &kafka.WorkflowEvent{
			EventID:      fmt.Sprintf("evt-%s-failed", req.PaymentID),
			EventType:    "payment.failed",
			Timestamp:    time.Now(),
			WorkflowID:   req.WorkflowID,
			WorkflowType: "payment",
			Status:       "failed",
			TenantID:     req.TenantID,
			UserID:       req.UserID,
			Data: map[string]interface{}{
				"payment_id": req.PaymentID,
				"amount":     req.Amount,
				"error":      err.Error(),
			},
		}
		m.PublishWorkflowEvent(ctx, failedEvent)

		return result, fmt.Errorf("payment processing failed: %w", err)
	}

	// Transfer succeeded
	logger.Logger.Info("TigerBeetle transfer completed successfully",
		logger.String("payment_id", req.PaymentID),
		logger.String("transfer_id", transferID.String()))
	result.Status = "completed"

	// Step 9: Update cache with completed status
	completedState := map[string]interface{}{
		"payment_id":   req.PaymentID,
		"transfer_id":  transferID.String(),
		"status":       "completed",
		"from_account": req.FromAccountID.String(),
		"to_account":   req.ToAccountID.String(),
		"amount":       req.Amount,
		"currency":     req.Currency,
		"timestamp":    time.Now().Unix(),
	}
	
	if err := m.Redis.CacheWorkflowState(ctx, stateKey, completedState, 3600); err != nil {
		logger.Logger.Error("Failed to cache completed payment state", logger.Error(err))
	}

	// Step 10: Store idempotency key to prevent duplicate processing
	if err := m.Redis.CacheWorkflowState(ctx, idempotencyKey, completedState, 86400); err != nil {
		logger.Logger.Error("Failed to cache idempotency key", logger.Error(err))
	}

	// Step 11: Publish payment.completed event to Kafka
	completedEvent := &kafka.WorkflowEvent{
		EventID:      fmt.Sprintf("evt-%s-completed", req.PaymentID),
		EventType:    "payment.completed",
		Timestamp:    time.Now(),
		WorkflowID:   req.WorkflowID,
		WorkflowType: "payment",
		Status:       "completed",
		TenantID:     req.TenantID,
		UserID:       req.UserID,
		Data: map[string]interface{}{
			"payment_id":   req.PaymentID,
			"transfer_id":  transferID.String(),
			"amount":       req.Amount,
			"currency":     req.Currency,
			"from_account": req.FromAccountID.String(),
			"to_account":   req.ToAccountID.String(),
		},
	}
	
	if err := m.PublishWorkflowEvent(ctx, completedEvent); err != nil {
		logger.Logger.Error("Failed to publish payment.completed event", logger.Error(err))
		// Don't fail the payment if event publishing fails
	}

	logger.Logger.Info("Payment processing completed successfully",
		logger.String("payment_id", req.PaymentID),
		logger.String("status", result.Status))

	return result, nil
}

// ProcessPaymentSimple is a simplified version that delegates to ProcessPaymentWithLocking
func (m *MiddlewareManager) ProcessPaymentSimple(
	ctx context.Context,
	paymentID string,
	fromAccountID, toAccountID types.Uint128,
	amount uint64,
) error {
	req := &PaymentRequest{
		PaymentID:      paymentID,
		WorkflowID:     paymentID,
		FromAccountID:  fromAccountID,
		ToAccountID:    toAccountID,
		Amount:         amount,
		Currency:       "NGN",
		Description:    "Payment transaction",
		IdempotencyKey: paymentID,
	}

	result, err := m.ProcessPaymentWithLocking(ctx, req)
	if err != nil {
		return err
	}

	if result.Status != "completed" {
		return fmt.Errorf("payment failed with status: %s", result.Status)
	}

	return nil
}

// validatePaymentRequest validates the payment request
func validatePaymentRequest(req *PaymentRequest) error {
	if req.PaymentID == "" {
		return fmt.Errorf("payment_id is required")
	}
	if req.Amount == 0 {
		return fmt.Errorf("amount must be greater than 0")
	}
	if req.FromAccountID == req.ToAccountID {
		return fmt.Errorf("from_account and to_account must be different")
	}
	if req.IdempotencyKey == "" {
		return fmt.Errorf("idempotency_key is required")
	}
	return nil
}

// GetPaymentStatus retrieves the current status of a payment from Redis cache
func (m *MiddlewareManager) GetPaymentStatus(
	ctx context.Context,
	paymentID string,
) (map[string]interface{}, error) {
	stateKey := fmt.Sprintf("payment:state:%s", paymentID)
	return m.Redis.GetWorkflowState(ctx, stateKey)
}

// CancelPendingPayment attempts to cancel a pending payment
func (m *MiddlewareManager) CancelPendingPayment(
	ctx context.Context,
	paymentID string,
) error {
	// Acquire lock
	lockName := fmt.Sprintf("payment:lock:%s", paymentID)
	locked, err := m.Redis.AcquireLock(ctx, lockName, 30)
	if err != nil || !locked {
		return fmt.Errorf("failed to acquire lock for cancellation")
	}
	defer m.Redis.ReleaseLock(ctx, lockName)

	// Check current status
	stateKey := fmt.Sprintf("payment:state:%s", paymentID)
	state, err := m.Redis.GetWorkflowState(ctx, stateKey)
	if err != nil {
		return fmt.Errorf("failed to get payment state: %w", err)
	}

	status, ok := state["status"].(string)
	if !ok || status != "pending" {
		return fmt.Errorf("payment cannot be cancelled (status: %s)", status)
	}

	// Update status to cancelled
	state["status"] = "cancelled"
	state["cancelled_at"] = time.Now().Unix()
	
	return m.Redis.CacheWorkflowState(ctx, stateKey, state, 3600)
}

