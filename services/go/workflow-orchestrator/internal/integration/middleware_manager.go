package integration

import (
	"context"
	"fmt"
	"time"

	"github.com/tigerbeetle/tigerbeetle-go/pkg/types"
	"workflow-orchestrator/internal/middleware/apisix"
	"workflow-orchestrator/internal/middleware/dapr"
	"workflow-orchestrator/internal/middleware/fluvio"
	"workflow-orchestrator/internal/middleware/kafka"
	"workflow-orchestrator/internal/middleware/keycloak"
	"workflow-orchestrator/internal/middleware/lakehouse"
	"workflow-orchestrator/internal/middleware/permify"
	"workflow-orchestrator/internal/middleware/redis"
	"workflow-orchestrator/internal/middleware/temporal"
	"workflow-orchestrator/internal/middleware/tigerbeetle"
	"workflow-orchestrator/pkg/logger"
)

// MiddlewareManager manages all middleware integrations
type MiddlewareManager struct {
	Kafka        *kafka.Client
	Dapr         *dapr.Client
	Fluvio       *fluvio.Client
	Temporal     *temporal.Client
	Keycloak     *keycloak.Client
	Permify      *permify.Client
	Redis        *redis.Client
	TigerBeetle  *tigerbeetle.Client
	Lakehouse    *lakehouse.Client
	APISIX       *apisix.Client
}

// Config holds configuration for all middleware services
type Config struct {
	Kafka       *kafka.Config
	Dapr        *dapr.Config
	Fluvio      *fluvio.Config
	Temporal    *temporal.Config
	Keycloak    *keycloak.Config
	Permify     *permify.Config
	Redis       *redis.Config
	TigerBeetle *tigerbeetle.Config
	Lakehouse   *lakehouse.Config
	APISIX      *apisix.Config
}

// NewMiddlewareManager creates a new middleware manager with all integrations
func NewMiddlewareManager(config *Config) (*MiddlewareManager, error) {
	logger.Logger.Info("Initializing middleware manager")

	// Initialize Kafka
	kafkaClient, err := kafka.NewClient(config.Kafka)
	if err != nil {
		return nil, fmt.Errorf("failed to initialize Kafka: %w", err)
	}

	// Initialize Dapr
	daprClient, err := dapr.NewClient(config.Dapr)
	if err != nil {
		return nil, fmt.Errorf("failed to initialize Dapr: %w", err)
	}

	// Initialize Fluvio
	fluvioClient, err := fluvio.NewClient(config.Fluvio)
	if err != nil {
		return nil, fmt.Errorf("failed to initialize Fluvio: %w", err)
	}

	// Initialize Temporal
	temporalClient, err := temporal.NewClient(config.Temporal)
	if err != nil {
		return nil, fmt.Errorf("failed to initialize Temporal: %w", err)
	}

	// Initialize Keycloak
	keycloakClient, err := keycloak.NewClient(config.Keycloak)
	if err != nil {
		return nil, fmt.Errorf("failed to initialize Keycloak: %w", err)
	}

	// Initialize Permify
	permifyClient, err := permify.NewClient(config.Permify)
	if err != nil {
		return nil, fmt.Errorf("failed to initialize Permify: %w", err)
	}

	// Initialize Redis
	redisClient, err := redis.NewClient(config.Redis)
	if err != nil {
		return nil, fmt.Errorf("failed to initialize Redis: %w", err)
	}

	// Initialize TigerBeetle
	tigerBeetleClient, err := tigerbeetle.NewClient(config.TigerBeetle)
	if err != nil {
		return nil, fmt.Errorf("failed to initialize TigerBeetle: %w", err)
	}

	// Initialize Lakehouse
	lakehouseClient, err := lakehouse.NewClient(config.Lakehouse)
	if err != nil {
		return nil, fmt.Errorf("failed to initialize Lakehouse: %w", err)
	}

	// Initialize APISIX
	apisixClient, err := apisix.NewClient(config.APISIX)
	if err != nil {
		return nil, fmt.Errorf("failed to initialize APISIX: %w", err)
	}

	logger.Logger.Info("All middleware services initialized successfully")

	return &MiddlewareManager{
		Kafka:       kafkaClient,
		Dapr:        daprClient,
		Fluvio:      fluvioClient,
		Temporal:    temporalClient,
		Keycloak:    keycloakClient,
		Permify:     permifyClient,
		Redis:       redisClient,
		TigerBeetle: tigerBeetleClient,
		Lakehouse:   lakehouseClient,
		APISIX:      apisixClient,
	}, nil
}

// PublishWorkflowEvent publishes a workflow event to both Kafka and Fluvio
func (m *MiddlewareManager) PublishWorkflowEvent(ctx context.Context, event *kafka.WorkflowEvent) error {
	// Publish to Kafka for asynchronous processing
	if err := m.Kafka.PublishWorkflowEvent(ctx, event); err != nil {
		logger.Logger.Error("Failed to publish event to Kafka", logger.Error(err))
		return err
	}

	// Publish to Fluvio for real-time streaming
	fluvioEvent := &fluvio.WorkflowEvent{
		EventID:      event.EventID,
		EventType:    event.EventType,
		Timestamp:    event.Timestamp,
		WorkflowID:   event.WorkflowID,
		WorkflowType: event.WorkflowType,
		Status:       event.Status,
		TenantID:     event.TenantID,
		UserID:       event.UserID,
		Data:         event.Data,
	}
	if err := m.Fluvio.PublishWorkflowEvent(ctx, fluvioEvent); err != nil {
		logger.Warn("Failed to publish event to Fluvio", logger.Error(err))
		// Don't return error - Fluvio is optional for real-time updates
	}

	// Stream to Lakehouse for analytics
	lakehouseEvent := &lakehouse.WorkflowEvent{
		EventID:      event.EventID,
		EventType:    event.EventType,
		Timestamp:    event.Timestamp,
		WorkflowID:   event.WorkflowID,
		WorkflowType: event.WorkflowType,
		Status:       event.Status,
		TenantID:     event.TenantID,
		UserID:       event.UserID,
		EntityID:     "",
		Duration:     0,
		StepCount:    0,
		Metadata:     event.Data,
	}
	if err := m.Lakehouse.StreamWorkflowEvent(ctx, lakehouseEvent); err != nil {
		logger.Warn("Failed to stream event to Lakehouse", logger.Error(err))
		// Don't return error - Lakehouse is optional for analytics
	}

	return nil
}

// CacheWorkflowState caches workflow state in Redis
func (m *MiddlewareManager) CacheWorkflowState(ctx context.Context, workflowID string, state map[string]interface{}) error {
	return m.Redis.CacheWorkflowState(ctx, workflowID, state, 3600)
}

// GetCachedWorkflowState retrieves cached workflow state from Redis
func (m *MiddlewareManager) GetCachedWorkflowState(ctx context.Context, workflowID string) (map[string]interface{}, error) {
	return m.Redis.GetWorkflowState(ctx, workflowID)
}

// ValidateUserToken validates a JWT token with Keycloak
func (m *MiddlewareManager) ValidateUserToken(ctx context.Context, accessToken string) (*keycloak.UserInfo, error) {
	return m.Keycloak.ValidateToken(ctx, accessToken)
}

// CheckWorkflowPermission checks if a user has permission to access a workflow
func (m *MiddlewareManager) CheckWorkflowPermission(ctx context.Context, userID, workflowID, action string) (bool, error) {
	return m.Permify.CheckWorkflowPermission(ctx, userID, workflowID, action)
}

// InvokeService invokes a service via Dapr
func (m *MiddlewareManager) InvokeService(ctx context.Context, appID, method string, data interface{}) ([]byte, error) {
	return m.Dapr.InvokeService(ctx, appID, method, data)
}

// DelegateToTemporal delegates a long-running workflow to Temporal
func (m *MiddlewareManager) DelegateToTemporal(ctx context.Context, workflowType string, input *temporal.WorkflowInput) (string, error) {
	return m.Temporal.StartWorkflow(ctx, workflowType, input)
}

// ProcessPayment processes a payment via TigerBeetle
func (m *MiddlewareManager) ProcessPayment(ctx context.Context, paymentID string, fromAccountID, toAccountID types.Uint128, amount uint64) error {
	return m.TigerBeetle.ProcessPayment(ctx, paymentID, fromAccountID, toAccountID, amount)
}

// AcquireDistributedLock acquires a distributed lock via Redis
func (m *MiddlewareManager) AcquireDistributedLock(ctx context.Context, lockName string, timeout time.Duration) (bool, error) {
	return m.Redis.AcquireLock(ctx, lockName, int(timeout.Seconds()))
}

// ReleaseDistributedLock releases a distributed lock via Redis
func (m *MiddlewareManager) ReleaseDistributedLock(ctx context.Context, lockName string) error {
	return m.Redis.ReleaseLock(ctx, lockName)
}

// Close closes all middleware connections
func (m *MiddlewareManager) Close() error {
	logger.Logger.Info("Closing all middleware connections")

	var errors []error

	if err := m.Kafka.Close(); err != nil {
		errors = append(errors, fmt.Errorf("Kafka close error: %w", err))
	}

	if err := m.Dapr.Close(); err != nil {
		errors = append(errors, fmt.Errorf("Dapr close error: %w", err))
	}

	if err := m.Fluvio.Close(); err != nil {
		errors = append(errors, fmt.Errorf("Fluvio close error: %w", err))
	}

	if err := m.Temporal.Close(); err != nil {
		errors = append(errors, fmt.Errorf("Temporal close error: %w", err))
	}

	if err := m.Keycloak.Close(); err != nil {
		errors = append(errors, fmt.Errorf("Keycloak close error: %w", err))
	}

	if err := m.Permify.Close(); err != nil {
		errors = append(errors, fmt.Errorf("Permify close error: %w", err))
	}

	if err := m.Redis.Close(); err != nil {
		errors = append(errors, fmt.Errorf("Redis close error: %w", err))
	}

	if err := m.TigerBeetle.Close(); err != nil {
		errors = append(errors, fmt.Errorf("TigerBeetle close error: %w", err))
	}

	if err := m.Lakehouse.Close(); err != nil {
		errors = append(errors, fmt.Errorf("Lakehouse close error: %w", err))
	}

	if err := m.APISIX.Close(); err != nil {
		errors = append(errors, fmt.Errorf("APISIX close error: %w", err))
	}

	if len(errors) > 0 {
		return fmt.Errorf("errors closing middleware: %v", errors)
	}

	logger.Logger.Info("All middleware connections closed successfully")
	return nil
}

