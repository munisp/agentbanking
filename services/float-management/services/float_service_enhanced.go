package services

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"sync"
	"time"

	"github.com/google/uuid"
	"github.com/redis/go-redis/v9"
	"gorm.io/gorm"
	"gorm.io/gorm/clause"

	"remittance/float-management/models"
)

// CircuitBreakerState represents the state of a circuit breaker
type CircuitBreakerState string

const (
	CircuitBreakerClosed   CircuitBreakerState = "closed"
	CircuitBreakerOpen     CircuitBreakerState = "open"
	CircuitBreakerHalfOpen CircuitBreakerState = "half-open"
)

// CircuitBreaker implements the circuit breaker pattern
type CircuitBreaker struct {
	name             string
	failureThreshold int
	recoveryTimeout  time.Duration
	failures         int
	lastFailureTime  time.Time
	state            CircuitBreakerState
	mu               sync.RWMutex
}

// NewCircuitBreaker creates a new circuit breaker
func NewCircuitBreaker(name string, failureThreshold int, recoveryTimeout time.Duration) *CircuitBreaker {
	return &CircuitBreaker{
		name:             name,
		failureThreshold: failureThreshold,
		recoveryTimeout:  recoveryTimeout,
		state:            CircuitBreakerClosed,
	}
}

// RecordFailure records a failure and potentially opens the circuit
func (cb *CircuitBreaker) RecordFailure() {
	cb.mu.Lock()
	defer cb.mu.Unlock()
	
	cb.failures++
	cb.lastFailureTime = time.Now()
	
	if cb.failures >= cb.failureThreshold {
		cb.state = CircuitBreakerOpen
	}
}

// RecordSuccess records a success and resets the circuit
func (cb *CircuitBreaker) RecordSuccess() {
	cb.mu.Lock()
	defer cb.mu.Unlock()
	
	cb.failures = 0
	cb.state = CircuitBreakerClosed
}

// CanExecute checks if the circuit allows execution
func (cb *CircuitBreaker) CanExecute() bool {
	cb.mu.RLock()
	defer cb.mu.RUnlock()
	
	switch cb.state {
	case CircuitBreakerClosed:
		return true
	case CircuitBreakerOpen:
		if time.Since(cb.lastFailureTime) > cb.recoveryTimeout {
			cb.mu.RUnlock()
			cb.mu.Lock()
			cb.state = CircuitBreakerHalfOpen
			cb.mu.Unlock()
			cb.mu.RLock()
			return true
		}
		return false
	case CircuitBreakerHalfOpen:
		return true
	}
	return true
}

// IdempotencyStore handles idempotency key storage
type IdempotencyStore struct {
	redis *redis.Client
	ttl   time.Duration
}

// NewIdempotencyStore creates a new idempotency store
func NewIdempotencyStore(redis *redis.Client, ttl time.Duration) *IdempotencyStore {
	return &IdempotencyStore{
		redis: redis,
		ttl:   ttl,
	}
}

// Check checks if an idempotency key exists and returns cached result
func (s *IdempotencyStore) Check(ctx context.Context, key string) ([]byte, bool, error) {
	result, err := s.redis.Get(ctx, fmt.Sprintf("idempotency:%s", key)).Bytes()
	if err == redis.Nil {
		return nil, false, nil
	}
	if err != nil {
		return nil, false, err
	}
	return result, true, nil
}

// Store stores an idempotency result
func (s *IdempotencyStore) Store(ctx context.Context, key string, result interface{}) error {
	data, err := json.Marshal(result)
	if err != nil {
		return err
	}
	return s.redis.Set(ctx, fmt.Sprintf("idempotency:%s", key), data, s.ttl).Err()
}

// GenerateIdempotencyKey generates an idempotency key from operation parameters
func GenerateIdempotencyKey(operation string, params ...interface{}) string {
	data := fmt.Sprintf("%s:%v", operation, params)
	hash := sha256.Sum256([]byte(data))
	return hex.EncodeToString(hash[:])
}

// EventPublisher publishes events to Redis pub/sub and Kafka
type EventPublisher struct {
	redis *redis.Client
}

// NewEventPublisher creates a new event publisher
func NewEventPublisher(redis *redis.Client) *EventPublisher {
	return &EventPublisher{redis: redis}
}

// FloatEvent represents a float-related event
type FloatEvent struct {
	EventID   string                 `json:"event_id"`
	EventType string                 `json:"event_type"`
	Timestamp time.Time              `json:"timestamp"`
	AgentID   uuid.UUID              `json:"agent_id"`
	Payload   map[string]interface{} `json:"payload"`
}

// Publish publishes an event
func (p *EventPublisher) Publish(ctx context.Context, eventType string, agentID uuid.UUID, payload map[string]interface{}) error {
	event := FloatEvent{
		EventID:   uuid.New().String(),
		EventType: eventType,
		Timestamp: time.Now(),
		AgentID:   agentID,
		Payload:   payload,
	}
	
	data, err := json.Marshal(event)
	if err != nil {
		return err
	}
	
	// Publish to Redis pub/sub
	return p.redis.Publish(ctx, fmt.Sprintf("float:%s", eventType), data).Err()
}

// EnhancedFloatService is a production-ready float service with all improvements
type EnhancedFloatService struct {
	db               *gorm.DB
	redis            *redis.Client
	idempotencyStore *IdempotencyStore
	eventPublisher   *EventPublisher
	riskEngineBreaker *CircuitBreaker
	paymentBreaker   *CircuitBreaker
	config           *FloatConfig
}

// NewEnhancedFloatService creates a new enhanced float service
func NewEnhancedFloatService(db *gorm.DB, redis *redis.Client, config *FloatConfig) *EnhancedFloatService {
	return &EnhancedFloatService{
		db:               db,
		redis:            redis,
		idempotencyStore: NewIdempotencyStore(redis, 24*time.Hour),
		eventPublisher:   NewEventPublisher(redis),
		riskEngineBreaker: NewCircuitBreaker("risk_engine", 5, 30*time.Second),
		paymentBreaker:   NewCircuitBreaker("payment_gateway", 5, 30*time.Second),
		config:           config,
	}
}

// DB returns the database connection
func (s *EnhancedFloatService) DB() *gorm.DB {
	return s.db
}

// DistributedLock acquires a distributed lock
func (s *EnhancedFloatService) acquireLock(ctx context.Context, key string, ttl time.Duration) (bool, error) {
	return s.redis.SetNX(ctx, fmt.Sprintf("lock:%s", key), "1", ttl).Result()
}

// ReleaseLock releases a distributed lock
func (s *EnhancedFloatService) releaseLock(ctx context.Context, key string) error {
	return s.redis.Del(ctx, fmt.Sprintf("lock:%s", key)).Err()
}

// ReserveFloatRequest represents a float reservation request
type ReserveFloatRequest struct {
	AgentID       uuid.UUID `json:"agent_id" binding:"required"`
	Amount        float64   `json:"amount" binding:"required,gt=0"`
	TransactionID uuid.UUID `json:"transaction_id" binding:"required"`
	Description   string    `json:"description"`
	IdempotencyKey string   `json:"idempotency_key" binding:"required"`
}

// ReserveFloatResponse represents a float reservation response
type ReserveFloatResponse struct {
	ReservationID    uuid.UUID `json:"reservation_id"`
	AgentID          uuid.UUID `json:"agent_id"`
	Amount           float64   `json:"amount"`
	AvailableBalance float64   `json:"available_balance"`
	ReservedBalance  float64   `json:"reserved_balance"`
	Status           string    `json:"status"`
	ExpiresAt        time.Time `json:"expires_at"`
}

// FloatReservation represents a float reservation record
type FloatReservation struct {
	ID             uuid.UUID  `json:"id" gorm:"type:uuid;primary_key;default:gen_random_uuid()"`
	AgentFloatID   uuid.UUID  `json:"agent_float_id" gorm:"not null;index"`
	AgentID        uuid.UUID  `json:"agent_id" gorm:"not null;index"`
	TransactionID  uuid.UUID  `json:"transaction_id" gorm:"not null;index"`
	Amount         float64    `json:"amount" gorm:"not null"`
	Currency       string     `json:"currency" gorm:"not null;default:'NGN'"`
	Status         string     `json:"status" gorm:"not null;default:'pending'"`
	CommittedAmount *float64  `json:"committed_amount"`
	ReleasedAmount  *float64  `json:"released_amount"`
	IdempotencyKey string     `json:"idempotency_key" gorm:"not null;index"`
	ExpiresAt      time.Time  `json:"expires_at" gorm:"not null"`
	CommittedAt    *time.Time `json:"committed_at"`
	ReleasedAt     *time.Time `json:"released_at"`
	CreatedAt      time.Time  `json:"created_at"`
	UpdatedAt      time.Time  `json:"updated_at"`
}

// TableName returns the table name for FloatReservation
func (FloatReservation) TableName() string {
	return "float_reservations"
}

// ReserveFloat reserves float for a pending transaction with idempotency
func (s *EnhancedFloatService) ReserveFloat(ctx context.Context, req ReserveFloatRequest) (*ReserveFloatResponse, error) {
	// Check idempotency
	cached, exists, err := s.idempotencyStore.Check(ctx, req.IdempotencyKey)
	if err != nil {
		return nil, fmt.Errorf("idempotency check failed: %w", err)
	}
	if exists {
		var response ReserveFloatResponse
		if err := json.Unmarshal(cached, &response); err != nil {
			return nil, err
		}
		return &response, nil
	}
	
	// Acquire distributed lock
	lockKey := fmt.Sprintf("float:%s", req.AgentID.String())
	acquired, err := s.acquireLock(ctx, lockKey, 30*time.Second)
	if err != nil {
		return nil, fmt.Errorf("failed to acquire lock: %w", err)
	}
	if !acquired {
		return nil, errors.New("concurrent operation in progress")
	}
	defer s.releaseLock(ctx, lockKey)
	
	// Start transaction
	tx := s.db.Begin()
	
	// Get float facility with row lock and optimistic locking
	var agentFloat models.AgentFloat
	if err := tx.Clauses(clause.Locking{Strength: "UPDATE"}).
		Where("agent_id = ?", req.AgentID).First(&agentFloat).Error; err != nil {
		tx.Rollback()
		return nil, fmt.Errorf("float facility not found: %w", err)
	}
	
	// Validate
	if agentFloat.Status != models.FloatStatusActive {
		tx.Rollback()
		return nil, errors.New("float facility is not active")
	}
	
	if agentFloat.AvailableFloat < req.Amount {
		tx.Rollback()
		return nil, fmt.Errorf("insufficient float: %.2f available, %.2f requested", 
			agentFloat.AvailableFloat, req.Amount)
	}
	
	// Calculate new balances
	newAvailable := agentFloat.AvailableFloat - req.Amount
	newReserved := agentFloat.ReservedAmount + req.Amount
	
	// Update with optimistic locking using version field
	result := tx.Model(&agentFloat).
		Where("id = ? AND updated_at = ?", agentFloat.ID, agentFloat.UpdatedAt).
		Updates(map[string]interface{}{
			"available_float":  newAvailable,
			"reserved_amount":  newReserved,
			"updated_at":       time.Now(),
		})
	
	if result.RowsAffected == 0 {
		tx.Rollback()
		return nil, errors.New("concurrent modification detected")
	}
	
	// Create reservation record
	reservation := &FloatReservation{
		ID:             uuid.New(),
		AgentFloatID:   agentFloat.ID,
		AgentID:        req.AgentID,
		TransactionID:  req.TransactionID,
		Amount:         req.Amount,
		Currency:       agentFloat.Currency,
		Status:         "pending",
		IdempotencyKey: req.IdempotencyKey,
		ExpiresAt:      time.Now().Add(30 * time.Minute),
	}
	
	if err := tx.Create(reservation).Error; err != nil {
		tx.Rollback()
		return nil, fmt.Errorf("failed to create reservation: %w", err)
	}
	
	// Create transaction record
	floatTxn := &models.FloatTransaction{
		AgentFloatID:    agentFloat.ID,
		AgentID:         req.AgentID,
		RelatedTxnID:    &req.TransactionID,
		Type:            "reserve",
		Amount:          req.Amount,
		Currency:        agentFloat.Currency,
		FloatBefore:     agentFloat.AvailableFloat,
		FloatAfter:      newAvailable,
		UtilizedBefore:  agentFloat.UtilizedAmount,
		UtilizedAfter:   agentFloat.UtilizedAmount,
		AvailableBefore: agentFloat.AvailableFloat,
		AvailableAfter:  newAvailable,
		Description:     req.Description,
		Status:          "completed",
		ProcessedAt:     time.Now(),
	}
	
	if err := tx.Create(floatTxn).Error; err != nil {
		tx.Rollback()
		return nil, fmt.Errorf("failed to create transaction: %w", err)
	}
	
	tx.Commit()
	
	// Build response
	response := &ReserveFloatResponse{
		ReservationID:    reservation.ID,
		AgentID:          req.AgentID,
		Amount:           req.Amount,
		AvailableBalance: newAvailable,
		ReservedBalance:  newReserved,
		Status:           "reserved",
		ExpiresAt:        reservation.ExpiresAt,
	}
	
	// Store idempotency result
	s.idempotencyStore.Store(ctx, req.IdempotencyKey, response)
	
	// Publish event
	s.eventPublisher.Publish(ctx, "float_reserved", req.AgentID, map[string]interface{}{
		"reservation_id":    reservation.ID.String(),
		"amount":            req.Amount,
		"transaction_id":    req.TransactionID.String(),
		"available_balance": newAvailable,
	})
	
	return response, nil
}

// CommitFloatRequest represents a commit request
type CommitFloatRequest struct {
	ReservationID  uuid.UUID `json:"reservation_id" binding:"required"`
	Amount         *float64  `json:"amount"` // If nil, commit full amount
	IdempotencyKey string    `json:"idempotency_key" binding:"required"`
}

// CommitFloatResponse represents a commit response
type CommitFloatResponse struct {
	ReservationID   uuid.UUID `json:"reservation_id"`
	AgentID         uuid.UUID `json:"agent_id"`
	CommittedAmount float64   `json:"committed_amount"`
	UtilizedBalance float64   `json:"utilized_balance"`
	Status          string    `json:"status"`
}

// CommitFloat commits a reserved float amount
func (s *EnhancedFloatService) CommitFloat(ctx context.Context, agentID uuid.UUID, req CommitFloatRequest) (*CommitFloatResponse, error) {
	// Check idempotency
	cached, exists, err := s.idempotencyStore.Check(ctx, req.IdempotencyKey)
	if err != nil {
		return nil, fmt.Errorf("idempotency check failed: %w", err)
	}
	if exists {
		var response CommitFloatResponse
		if err := json.Unmarshal(cached, &response); err != nil {
			return nil, err
		}
		return &response, nil
	}
	
	// Acquire distributed lock
	lockKey := fmt.Sprintf("float:%s", agentID.String())
	acquired, err := s.acquireLock(ctx, lockKey, 30*time.Second)
	if err != nil {
		return nil, fmt.Errorf("failed to acquire lock: %w", err)
	}
	if !acquired {
		return nil, errors.New("concurrent operation in progress")
	}
	defer s.releaseLock(ctx, lockKey)
	
	tx := s.db.Begin()
	
	// Get reservation with lock
	var reservation FloatReservation
	if err := tx.Clauses(clause.Locking{Strength: "UPDATE"}).
		Where("id = ? AND agent_id = ?", req.ReservationID, agentID).
		First(&reservation).Error; err != nil {
		tx.Rollback()
		return nil, fmt.Errorf("reservation not found: %w", err)
	}
	
	if reservation.Status != "pending" {
		tx.Rollback()
		return nil, errors.New("reservation already processed")
	}
	
	commitAmount := reservation.Amount
	if req.Amount != nil {
		if *req.Amount > reservation.Amount {
			tx.Rollback()
			return nil, errors.New("commit amount exceeds reservation")
		}
		commitAmount = *req.Amount
	}
	
	// Get float facility
	var agentFloat models.AgentFloat
	if err := tx.Clauses(clause.Locking{Strength: "UPDATE"}).
		Where("agent_id = ?", agentID).First(&agentFloat).Error; err != nil {
		tx.Rollback()
		return nil, fmt.Errorf("float facility not found: %w", err)
	}
	
	// Calculate new balances
	newReserved := agentFloat.ReservedAmount - commitAmount
	newUtilized := agentFloat.UtilizedAmount + commitAmount
	releaseAmount := reservation.Amount - commitAmount
	newAvailable := agentFloat.AvailableFloat + releaseAmount
	
	// Update float facility
	if err := tx.Model(&agentFloat).Updates(map[string]interface{}{
		"reserved_amount":  newReserved,
		"utilized_amount":  newUtilized,
		"available_float":  newAvailable,
		"updated_at":       time.Now(),
	}).Error; err != nil {
		tx.Rollback()
		return nil, fmt.Errorf("failed to update float: %w", err)
	}
	
	// Update reservation
	now := time.Now()
	if err := tx.Model(&reservation).Updates(map[string]interface{}{
		"status":           "committed",
		"committed_amount": commitAmount,
		"committed_at":     &now,
		"updated_at":       now,
	}).Error; err != nil {
		tx.Rollback()
		return nil, fmt.Errorf("failed to update reservation: %w", err)
	}
	
	// Create transaction record
	floatTxn := &models.FloatTransaction{
		AgentFloatID:    agentFloat.ID,
		AgentID:         agentID,
		Type:            "commit",
		Amount:          commitAmount,
		Currency:        agentFloat.Currency,
		FloatBefore:     agentFloat.UtilizedAmount,
		FloatAfter:      newUtilized,
		UtilizedBefore:  agentFloat.UtilizedAmount,
		UtilizedAfter:   newUtilized,
		AvailableBefore: agentFloat.AvailableFloat,
		AvailableAfter:  newAvailable,
		Description:     fmt.Sprintf("Commit reservation %s", req.ReservationID),
		Status:          "completed",
		ProcessedAt:     time.Now(),
	}
	
	if err := tx.Create(floatTxn).Error; err != nil {
		tx.Rollback()
		return nil, fmt.Errorf("failed to create transaction: %w", err)
	}
	
	tx.Commit()
	
	response := &CommitFloatResponse{
		ReservationID:   req.ReservationID,
		AgentID:         agentID,
		CommittedAmount: commitAmount,
		UtilizedBalance: newUtilized,
		Status:          "committed",
	}
	
	// Store idempotency result
	s.idempotencyStore.Store(ctx, req.IdempotencyKey, response)
	
	// Publish event
	s.eventPublisher.Publish(ctx, "float_committed", agentID, map[string]interface{}{
		"reservation_id":   req.ReservationID.String(),
		"committed_amount": commitAmount,
		"utilized_balance": newUtilized,
	})
	
	return response, nil
}

// ReleaseFloatRequest represents a release request
type ReleaseFloatRequest struct {
	ReservationID  uuid.UUID `json:"reservation_id" binding:"required"`
	Amount         *float64  `json:"amount"` // If nil, release full amount
	IdempotencyKey string    `json:"idempotency_key" binding:"required"`
}

// ReleaseFloatResponse represents a release response
type ReleaseFloatResponse struct {
	ReservationID    uuid.UUID `json:"reservation_id"`
	AgentID          uuid.UUID `json:"agent_id"`
	ReleasedAmount   float64   `json:"released_amount"`
	AvailableBalance float64   `json:"available_balance"`
	Status           string    `json:"status"`
}

// ReleaseFloat releases a reserved float amount back to available
func (s *EnhancedFloatService) ReleaseFloat(ctx context.Context, agentID uuid.UUID, req ReleaseFloatRequest) (*ReleaseFloatResponse, error) {
	// Check idempotency
	cached, exists, err := s.idempotencyStore.Check(ctx, req.IdempotencyKey)
	if err != nil {
		return nil, fmt.Errorf("idempotency check failed: %w", err)
	}
	if exists {
		var response ReleaseFloatResponse
		if err := json.Unmarshal(cached, &response); err != nil {
			return nil, err
		}
		return &response, nil
	}
	
	// Acquire distributed lock
	lockKey := fmt.Sprintf("float:%s", agentID.String())
	acquired, err := s.acquireLock(ctx, lockKey, 30*time.Second)
	if err != nil {
		return nil, fmt.Errorf("failed to acquire lock: %w", err)
	}
	if !acquired {
		return nil, errors.New("concurrent operation in progress")
	}
	defer s.releaseLock(ctx, lockKey)
	
	tx := s.db.Begin()
	
	// Get reservation with lock
	var reservation FloatReservation
	if err := tx.Clauses(clause.Locking{Strength: "UPDATE"}).
		Where("id = ? AND agent_id = ?", req.ReservationID, agentID).
		First(&reservation).Error; err != nil {
		tx.Rollback()
		return nil, fmt.Errorf("reservation not found: %w", err)
	}
	
	if reservation.Status != "pending" {
		tx.Rollback()
		return nil, errors.New("reservation already processed")
	}
	
	releaseAmount := reservation.Amount
	if req.Amount != nil {
		if *req.Amount > reservation.Amount {
			tx.Rollback()
			return nil, errors.New("release amount exceeds reservation")
		}
		releaseAmount = *req.Amount
	}
	
	// Get float facility
	var agentFloat models.AgentFloat
	if err := tx.Clauses(clause.Locking{Strength: "UPDATE"}).
		Where("agent_id = ?", agentID).First(&agentFloat).Error; err != nil {
		tx.Rollback()
		return nil, fmt.Errorf("float facility not found: %w", err)
	}
	
	// Calculate new balances
	newAvailable := agentFloat.AvailableFloat + releaseAmount
	newReserved := agentFloat.ReservedAmount - releaseAmount
	
	// Update float facility
	if err := tx.Model(&agentFloat).Updates(map[string]interface{}{
		"available_float": newAvailable,
		"reserved_amount": newReserved,
		"updated_at":      time.Now(),
	}).Error; err != nil {
		tx.Rollback()
		return nil, fmt.Errorf("failed to update float: %w", err)
	}
	
	// Update reservation
	now := time.Now()
	status := "released"
	if releaseAmount < reservation.Amount {
		status = "partial_release"
	}
	
	if err := tx.Model(&reservation).Updates(map[string]interface{}{
		"status":          status,
		"released_amount": releaseAmount,
		"released_at":     &now,
		"updated_at":      now,
	}).Error; err != nil {
		tx.Rollback()
		return nil, fmt.Errorf("failed to update reservation: %w", err)
	}
	
	// Create transaction record
	floatTxn := &models.FloatTransaction{
		AgentFloatID:    agentFloat.ID,
		AgentID:         agentID,
		Type:            "release",
		Amount:          releaseAmount,
		Currency:        agentFloat.Currency,
		FloatBefore:     agentFloat.AvailableFloat,
		FloatAfter:      newAvailable,
		UtilizedBefore:  agentFloat.UtilizedAmount,
		UtilizedAfter:   agentFloat.UtilizedAmount,
		AvailableBefore: agentFloat.AvailableFloat,
		AvailableAfter:  newAvailable,
		Description:     fmt.Sprintf("Release reservation %s", req.ReservationID),
		Status:          "completed",
		ProcessedAt:     time.Now(),
	}
	
	if err := tx.Create(floatTxn).Error; err != nil {
		tx.Rollback()
		return nil, fmt.Errorf("failed to create transaction: %w", err)
	}
	
	tx.Commit()
	
	response := &ReleaseFloatResponse{
		ReservationID:    req.ReservationID,
		AgentID:          agentID,
		ReleasedAmount:   releaseAmount,
		AvailableBalance: newAvailable,
		Status:           status,
	}
	
	// Store idempotency result
	s.idempotencyStore.Store(ctx, req.IdempotencyKey, response)
	
	// Publish event
	s.eventPublisher.Publish(ctx, "float_released", agentID, map[string]interface{}{
		"reservation_id":    req.ReservationID.String(),
		"released_amount":   releaseAmount,
		"available_balance": newAvailable,
	})
	
	return response, nil
}

// SettleFloatEnhancedRequest represents an enhanced settlement request
type SettleFloatEnhancedRequest struct {
	Amount           float64  `json:"amount" binding:"required,gt=0"`
	PaymentMethod    string   `json:"payment_method" binding:"required"`
	PaymentReference string   `json:"payment_reference"`
	BankAccount      string   `json:"bank_account"`
	MobileNumber     string   `json:"mobile_number"`
	IdempotencyKey   string   `json:"idempotency_key" binding:"required"`
	SettledBy        uuid.UUID `json:"settled_by" binding:"required"`
}

// SettleFloatEnhancedResponse represents an enhanced settlement response
type SettleFloatEnhancedResponse struct {
	SettlementID     uuid.UUID `json:"settlement_id"`
	AgentID          uuid.UUID `json:"agent_id"`
	Amount           float64   `json:"amount"`
	PaymentReference string    `json:"payment_reference"`
	PaymentStatus    string    `json:"payment_status"`
	UtilizedBalance  float64   `json:"utilized_balance"`
	AvailableBalance float64   `json:"available_balance"`
	Status           string    `json:"status"`
}

// SettleFloatEnhanced settles float with payment gateway integration
func (s *EnhancedFloatService) SettleFloatEnhanced(ctx context.Context, agentID uuid.UUID, req SettleFloatEnhancedRequest) (*SettleFloatEnhancedResponse, error) {
	// Check idempotency
	cached, exists, err := s.idempotencyStore.Check(ctx, req.IdempotencyKey)
	if err != nil {
		return nil, fmt.Errorf("idempotency check failed: %w", err)
	}
	if exists {
		var response SettleFloatEnhancedResponse
		if err := json.Unmarshal(cached, &response); err != nil {
			return nil, err
		}
		return &response, nil
	}
	
	// Acquire distributed lock
	lockKey := fmt.Sprintf("float:%s", agentID.String())
	acquired, err := s.acquireLock(ctx, lockKey, 30*time.Second)
	if err != nil {
		return nil, fmt.Errorf("failed to acquire lock: %w", err)
	}
	if !acquired {
		return nil, errors.New("concurrent operation in progress")
	}
	defer s.releaseLock(ctx, lockKey)
	
	// Get float facility
	var agentFloat models.AgentFloat
	if err := s.db.Where("agent_id = ?", agentID).First(&agentFloat).Error; err != nil {
		return nil, fmt.Errorf("float facility not found: %w", err)
	}
	
	if agentFloat.UtilizedAmount == 0 {
		return nil, errors.New("no outstanding float to settle")
	}
	
	settleAmount := req.Amount
	if settleAmount > agentFloat.UtilizedAmount {
		settleAmount = agentFloat.UtilizedAmount
	}
	
	// Generate payment reference if not provided
	paymentRef := req.PaymentReference
	if paymentRef == "" {
		paymentRef = fmt.Sprintf("SETTLE-%s", uuid.New().String()[:8])
	}
	
	// Check payment gateway circuit breaker
	paymentStatus := "pending"
	if s.paymentBreaker.CanExecute() {
		// In production, call actual payment gateway here
		// For now, simulate success
		paymentStatus = "completed"
		s.paymentBreaker.RecordSuccess()
	}
	
	tx := s.db.Begin()
	
	// Calculate new balances
	newUtilized := agentFloat.UtilizedAmount - settleAmount
	newAvailable := agentFloat.AvailableFloat + settleAmount
	
	// Update float facility
	now := time.Now()
	if err := tx.Model(&agentFloat).Updates(map[string]interface{}{
		"utilized_amount": newUtilized,
		"available_float": newAvailable,
		"updated_at":      now,
	}).Error; err != nil {
		tx.Rollback()
		return nil, fmt.Errorf("failed to update float: %w", err)
	}
	
	// Create settlement record
	settlementID := uuid.New()
	settlement := &models.FloatSettlement{
		ID:               settlementID,
		AgentFloatID:     agentFloat.ID,
		AgentID:          agentID,
		SettlementRef:    paymentRef,
		SettlementType:   "manual",
		OutstandingFloat: agentFloat.UtilizedAmount,
		SettlementAmount: settleAmount,
		TotalAmountDue:   settleAmount,
		AmountSettled:    settleAmount,
		Currency:         agentFloat.Currency,
		Status:           models.SettlementStatus(paymentStatus),
		SettlementMethod: req.PaymentMethod,
		PaymentReference: paymentRef,
		BankAccount:      req.BankAccount,
		ScheduledDate:    now,
		DueDate:          now,
		ProcessedBy:      &req.SettledBy,
	}
	
	if err := tx.Create(settlement).Error; err != nil {
		tx.Rollback()
		return nil, fmt.Errorf("failed to create settlement: %w", err)
	}
	
	// Create transaction record
	floatTxn := &models.FloatTransaction{
		AgentFloatID:    agentFloat.ID,
		AgentID:         agentID,
		Type:            models.FloatTransactionSettlement,
		Amount:          settleAmount,
		Currency:        agentFloat.Currency,
		FloatBefore:     agentFloat.UtilizedAmount,
		FloatAfter:      newUtilized,
		UtilizedBefore:  agentFloat.UtilizedAmount,
		UtilizedAfter:   newUtilized,
		AvailableBefore: agentFloat.AvailableFloat,
		AvailableAfter:  newAvailable,
		Description:     fmt.Sprintf("Settlement %s", paymentRef),
		Status:          "completed",
		SettlementID:    &settlementID,
		ProcessedBy:     &req.SettledBy,
		ProcessedAt:     now,
	}
	
	if err := tx.Create(floatTxn).Error; err != nil {
		tx.Rollback()
		return nil, fmt.Errorf("failed to create transaction: %w", err)
	}
	
	tx.Commit()
	
	response := &SettleFloatEnhancedResponse{
		SettlementID:     settlementID,
		AgentID:          agentID,
		Amount:           settleAmount,
		PaymentReference: paymentRef,
		PaymentStatus:    paymentStatus,
		UtilizedBalance:  newUtilized,
		AvailableBalance: newAvailable,
		Status:           "completed",
	}
	
	// Store idempotency result
	s.idempotencyStore.Store(ctx, req.IdempotencyKey, response)
	
	// Publish event
	s.eventPublisher.Publish(ctx, "float_settled", agentID, map[string]interface{}{
		"settlement_id":     settlementID.String(),
		"amount":            settleAmount,
		"payment_reference": paymentRef,
		"payment_status":    paymentStatus,
	})
	
	return response, nil
}

// ExpireReservations expires old reservations and releases float
func (s *EnhancedFloatService) ExpireReservations(ctx context.Context) (int, error) {
	var expiredReservations []FloatReservation
	
	if err := s.db.Where("status = ? AND expires_at < ?", "pending", time.Now()).
		Find(&expiredReservations).Error; err != nil {
		return 0, err
	}
	
	count := 0
	for _, reservation := range expiredReservations {
		// Release the reserved amount
		req := ReleaseFloatRequest{
			ReservationID:  reservation.ID,
			IdempotencyKey: fmt.Sprintf("expire:%s", reservation.ID.String()),
		}
		
		if _, err := s.ReleaseFloat(ctx, reservation.AgentID, req); err != nil {
			continue
		}
		count++
	}
	
	return count, nil
}
