package engine

import (
	"context"
	"fmt"
	"sync"
	"time"

	"workflow-orchestrator/internal/domain"
	"workflow-orchestrator/internal/middleware"
	"workflow-orchestrator/internal/repository"
	"workflow-orchestrator/pkg/logger"
	"workflow-orchestrator/pkg/metrics"

	"github.com/google/uuid"
)

// Executor executes workflows
type Executor struct {
	repo          repository.WorkflowRepository
	stateManager  *StateManager
	stepExecutor  *StepExecutor
	fluvio        *middleware.FluvioClient
	kafka         *middleware.KafkaClient
	redis         RedisCache
	maxConcurrent int
	semaphore     chan struct{}
	mu            sync.RWMutex
	running       map[string]context.CancelFunc
}

// NewExecutor creates a new workflow executor
func NewExecutor(
	repo repository.WorkflowRepository,
	stateManager *StateManager,
	stepExecutor *StepExecutor,
	fluvio *middleware.FluvioClient,
	kafka *middleware.KafkaClient,
	redis RedisCache,
	maxConcurrent int,
) *Executor {
	return &Executor{
		repo:          repo,
		stateManager:  stateManager,
		stepExecutor:  stepExecutor,
		fluvio:        fluvio,
		kafka:         kafka,
		redis:         redis,
		maxConcurrent: maxConcurrent,
		semaphore:     make(chan struct{}, maxConcurrent),
		running:       make(map[string]context.CancelFunc),
	}
}

// Execute executes a workflow synchronously
func (e *Executor) Execute(ctx context.Context, workflow *domain.Workflow, definition *domain.WorkflowDefinition) error {
	log := logger.WithWorkflow(workflow.WorkflowID)

	// Acquire semaphore
	select {
	case e.semaphore <- struct{}{}:
		defer func() { <-e.semaphore }()
	case <-ctx.Done():
		return ctx.Err()
	}

	// Track active workflows
	metrics.ActiveWorkflows.Inc()
	defer metrics.ActiveWorkflows.Dec()

	// Create cancellable context
	execCtx, cancel := context.WithCancel(ctx)
	defer cancel()

	// Register running workflow
	e.mu.Lock()
	e.running[workflow.WorkflowID] = cancel
	e.mu.Unlock()

	defer func() {
		e.mu.Lock()
		delete(e.running, workflow.WorkflowID)
		e.mu.Unlock()
	}()

	// Start workflow execution
	startTime := time.Now()
	workflow.Status = domain.StatusRunning
	now := time.Now()
	workflow.StartedAt = &now

	if err := e.repo.Update(ctx, workflow); err != nil {
		log.Error("Failed to update workflow", logger.Error(err))
		return fmt.Errorf("failed to update workflow: %w", err)
	}

	// Publish workflow started event
	if err := e.publishEvent(ctx, "workflow.started", workflow); err != nil {
		log.Warn("Failed to publish event", logger.Error(err))
	}

	// Cache workflow state
	if err := e.redis.CacheWorkflowState(ctx, workflow); err != nil {
		log.Warn("Failed to cache state", logger.Error(err))
	}

	// Execute steps
	workflow.TotalSteps = len(definition.Steps)

	for i, stepDef := range definition.Steps {
		select {
		case <-execCtx.Done():
			return e.handleCancellation(ctx, workflow, startTime)
		default:
		}

		// Create step
		step := &domain.WorkflowStep{
			ID:         uuid.New(),
			StepID:     fmt.Sprintf("%s-%d", workflow.WorkflowID, i+1),
			WorkflowID: workflow.WorkflowID,
			StepName:   stepDef.Name,
			StepType:   stepDef.Type,
			StepOrder:  i + 1,
			Status:     domain.StepPending,
			ServiceURL: stepDef.ServiceURL,
			Endpoint:   stepDef.Endpoint,
			InputData:  workflow.InputData,
			CreatedAt:  time.Now(),
			UpdatedAt:  time.Now(),
		}

		// Execute step
		stepStartTime := time.Now()
		if err := e.stepExecutor.Execute(execCtx, step); err != nil {
			workflow.FailedSteps++
			log.Error("Step execution failed",
				logger.String("step", step.StepName),
				logger.Error(err),
			)

			// Record step metrics
			metrics.StepDuration.WithLabelValues(workflow.WorkflowType, step.StepName).Observe(time.Since(stepStartTime).Seconds())

			return e.handleFailure(ctx, workflow, startTime, err)
		}

		// Record step metrics
		metrics.StepDuration.WithLabelValues(workflow.WorkflowType, step.StepName).Observe(time.Since(stepStartTime).Seconds())

		// Update workflow progress
		workflow.CompletedSteps++
		workflow.CurrentStep = step.StepName

		// Merge step output into workflow context
		if step.OutputData != nil {
			for k, v := range step.OutputData {
				workflow.InputData[k] = v
			}
		}

		// Update workflow state
		if err := e.repo.Update(ctx, workflow); err != nil {
			log.Error("Failed to update workflow", logger.Error(err))
			return fmt.Errorf("failed to update workflow: %w", err)
		}

		// Publish step completed event
		if err := e.publishEvent(ctx, "workflow.step.completed", step); err != nil {
			log.Warn("Failed to publish event", logger.Error(err))
		}

		// Update cache
		if err := e.redis.CacheWorkflowState(ctx, workflow); err != nil {
			log.Warn("Failed to cache state", logger.Error(err))
		}

		log.Info("Step completed",
			logger.String("step", step.StepName),
			logger.Int("order", step.StepOrder),
			logger.Float64("duration", step.DurationSeconds),
		)
	}

	// Workflow completed successfully
	return e.handleCompletion(ctx, workflow, startTime)
}

// ExecuteAsync executes a workflow asynchronously
func (e *Executor) ExecuteAsync(workflow *domain.Workflow, definition *domain.WorkflowDefinition) {
	go func() {
		ctx := context.Background()
		if err := e.Execute(ctx, workflow, definition); err != nil {
			logger.Logger.Error("Workflow execution failed",
				logger.String("workflow_id", workflow.WorkflowID),
				logger.Error(err),
			)
		}
	}()
}

// Cancel cancels a running workflow
func (e *Executor) Cancel(workflowID string) error {
	e.mu.RLock()
	cancel, ok := e.running[workflowID]
	e.mu.RUnlock()

	if !ok {
		return fmt.Errorf("workflow not running: %s", workflowID)
	}

	cancel()
	return nil
}

func (e *Executor) handleCompletion(ctx context.Context, workflow *domain.Workflow, startTime time.Time) error {
	log := logger.WithWorkflow(workflow.WorkflowID)

	workflow.Status = domain.StatusCompleted
	now := time.Now()
	workflow.CompletedAt = &now
	workflow.DurationSeconds = time.Since(startTime).Seconds()

	if err := e.repo.Update(ctx, workflow); err != nil {
		log.Error("Failed to update workflow", logger.Error(err))
		return fmt.Errorf("failed to update workflow: %w", err)
	}

	if err := e.publishEvent(ctx, "workflow.completed", workflow); err != nil {
		log.Warn("Failed to publish event", logger.Error(err))
	}

	// Record metrics
	metrics.WorkflowsTotal.WithLabelValues(workflow.WorkflowType, string(workflow.Status)).Inc()
	metrics.WorkflowDuration.WithLabelValues(workflow.WorkflowType).Observe(workflow.DurationSeconds)

	log.Info("Workflow completed",
		logger.Float64("duration", workflow.DurationSeconds),
		logger.Int("completed_steps", workflow.CompletedSteps),
	)

	return nil
}

func (e *Executor) handleFailure(ctx context.Context, workflow *domain.Workflow, startTime time.Time, err error) error {
	log := logger.WithWorkflow(workflow.WorkflowID)

	workflow.Status = domain.StatusFailed
	workflow.ErrorMessage = err.Error()
	now := time.Now()
	workflow.FailedAt = &now
	workflow.DurationSeconds = time.Since(startTime).Seconds()

	if updateErr := e.repo.Update(ctx, workflow); updateErr != nil {
		log.Error("Failed to update workflow", logger.Error(updateErr))
		return fmt.Errorf("failed to update workflow: %w", updateErr)
	}

	if pubErr := e.publishEvent(ctx, "workflow.failed", workflow); pubErr != nil {
		log.Warn("Failed to publish event", logger.Error(pubErr))
	}

	// Record metrics
	metrics.WorkflowsTotal.WithLabelValues(workflow.WorkflowType, string(workflow.Status)).Inc()
	metrics.WorkflowDuration.WithLabelValues(workflow.WorkflowType).Observe(workflow.DurationSeconds)

	log.Error("Workflow failed",
		logger.Float64("duration", workflow.DurationSeconds),
		logger.Int("completed_steps", workflow.CompletedSteps),
		logger.Int("failed_steps", workflow.FailedSteps),
		logger.Error(err),
	)

	return err
}

func (e *Executor) handleCancellation(ctx context.Context, workflow *domain.Workflow, startTime time.Time) error {
	log := logger.WithWorkflow(workflow.WorkflowID)

	workflow.Status = domain.StatusCancelled
	now := time.Now()
	workflow.CompletedAt = &now
	workflow.DurationSeconds = time.Since(startTime).Seconds()

	if err := e.repo.Update(ctx, workflow); err != nil {
		log.Error("Failed to update workflow", logger.Error(err))
		return fmt.Errorf("failed to update workflow: %w", err)
	}

	if err := e.publishEvent(ctx, "workflow.cancelled", workflow); err != nil {
		log.Warn("Failed to publish event", logger.Error(err))
	}

	// Record metrics
	metrics.WorkflowsTotal.WithLabelValues(workflow.WorkflowType, string(workflow.Status)).Inc()

	log.Info("Workflow cancelled", logger.Float64("duration", workflow.DurationSeconds))

	return fmt.Errorf("workflow cancelled")
}

func (e *Executor) publishEvent(ctx context.Context, eventType string, data interface{}) error {
	event := map[string]interface{}{
		"event_id":   uuid.New().String(),
		"event_type": eventType,
		"timestamp":  time.Now().UTC(),
		"data":       data,
	}

	// Publish to Fluvio if available
	if e.fluvio != nil {
		if err := e.fluvio.PublishEvent(ctx, eventType, event); err != nil {
			return err
		}
	}

	// Publish to Kafka if available
	if e.kafka != nil {
		if err := e.kafka.PublishEvent(ctx, "workflow-events", event); err != nil {
			return err
		}
	}

	return nil
}

