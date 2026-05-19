package temporal

import (
	"context"
	"fmt"
	"time"

	"go.temporal.io/sdk/client"
	"go.temporal.io/sdk/worker"
	"go.temporal.io/sdk/workflow"
	"workflow-orchestrator/pkg/logger"
)

// Client represents a Temporal client for long-running workflows
type Client struct {
	client    client.Client
	worker    worker.Worker
	config    *Config
}

// Config holds Temporal configuration
type Config struct {
	HostPort  string
	Namespace string
	TaskQueue string
}

// WorkflowInput represents input data for a Temporal workflow
type WorkflowInput struct {
	WorkflowID   string                 `json:"workflow_id"`
	WorkflowType string                 `json:"workflow_type"`
	TenantID     string                 `json:"tenant_id"`
	UserID       string                 `json:"user_id"`
	EntityID     string                 `json:"entity_id"`
	InputData    map[string]interface{} `json:"input_data"`
}

// WorkflowResult represents the result of a Temporal workflow
type WorkflowResult struct {
	WorkflowID string                 `json:"workflow_id"`
	Status     string                 `json:"status"`
	OutputData map[string]interface{} `json:"output_data"`
	Error      string                 `json:"error,omitempty"`
}

// NewClient creates a new Temporal client
func NewClient(config *Config) (*Client, error) {
	// Create Temporal client
	c, err := client.Dial(client.Options{
		HostPort:  config.HostPort,
		Namespace: config.Namespace,
	})
	if err != nil {
		return nil, fmt.Errorf("failed to create Temporal client: %w", err)
	}

	// Create worker
	w := worker.New(c, config.TaskQueue, worker.Options{})

	return &Client{
		client: c,
		worker: w,
		config: config,
	}, nil
}

// StartWorkflow starts a long-running workflow in Temporal
func (c *Client) StartWorkflow(ctx context.Context, workflowType string, input *WorkflowInput) (string, error) {
	logger.Logger.Info("Starting Temporal workflow",
		logger.String("workflow_type", workflowType),
		logger.String("workflow_id", input.WorkflowID),
	)

	// Start workflow execution
	options := client.StartWorkflowOptions{
		ID:        input.WorkflowID,
		TaskQueue: c.config.TaskQueue,
		WorkflowExecutionTimeout: 24 * time.Hour, // Max 24 hours
	}

	we, err := c.client.ExecuteWorkflow(ctx, options, workflowType, input)
	if err != nil {
		logger.Logger.Error("Failed to start Temporal workflow",
			logger.String("workflow_type", workflowType),
			logger.String("workflow_id", input.WorkflowID),
			logger.Error(err),
		)
		return "", fmt.Errorf("failed to start workflow: %w", err)
	}

	logger.Logger.Info("Temporal workflow started",
		logger.String("workflow_id", we.GetID()),
		logger.String("run_id", we.GetRunID()),
	)

	return we.GetRunID(), nil
}

// GetWorkflowStatus gets the status of a running workflow
func (c *Client) GetWorkflowStatus(ctx context.Context, workflowID, runID string) (*WorkflowResult, error) {
	logger.Logger.Info("Getting Temporal workflow status",
		logger.String("workflow_id", workflowID),
		logger.String("run_id", runID),
	)

	// Get workflow execution
	we := c.client.GetWorkflow(ctx, workflowID, runID)

	// Check if workflow is running
	var result WorkflowResult
	err := we.Get(ctx, &result)
	if err != nil {
		// Workflow is still running or failed
		return &WorkflowResult{
			WorkflowID: workflowID,
			Status:     "running",
			Error:      err.Error(),
		}, nil
	}

	return &result, nil
}

// CancelWorkflow cancels a running workflow
func (c *Client) CancelWorkflow(ctx context.Context, workflowID, runID string) error {
	logger.Logger.Info("Cancelling Temporal workflow",
		logger.String("workflow_id", workflowID),
		logger.String("run_id", runID),
	)

	err := c.client.CancelWorkflow(ctx, workflowID, runID)
	if err != nil {
		logger.Logger.Error("Failed to cancel Temporal workflow",
			logger.String("workflow_id", workflowID),
			logger.String("run_id", runID),
			logger.Error(err),
		)
		return fmt.Errorf("failed to cancel workflow: %w", err)
	}

	return nil
}

// RegisterWorkflow registers a workflow implementation with Temporal
func (c *Client) RegisterWorkflow(workflowFunc interface{}) {
	c.worker.RegisterWorkflow(workflowFunc)
}

// RegisterActivity registers an activity implementation with Temporal
func (c *Client) RegisterActivity(activityFunc interface{}) {
	c.worker.RegisterActivity(activityFunc)
}

// StartWorker starts the Temporal worker
func (c *Client) StartWorker() error {
	logger.Logger.Info("Starting Temporal worker",
		logger.String("task_queue", c.config.TaskQueue),
	)

	err := c.worker.Start()
	if err != nil {
		return fmt.Errorf("failed to start worker: %w", err)
	}

	return nil
}

// StopWorker stops the Temporal worker
func (c *Client) StopWorker() {
	c.worker.Stop()
}

// Close closes the Temporal client
func (c *Client) Close() error {
	c.worker.Stop()
	c.client.Close()
	return nil
}

// Example workflow implementation for agent onboarding
func AgentOnboardingWorkflow(ctx workflow.Context, input *WorkflowInput) (*WorkflowResult, error) {
	logger := workflow.GetLogger(ctx)
	logger.Info("Starting agent onboarding workflow", "workflow_id", input.WorkflowID)

	// Step 1: Validate application
	err := workflow.ExecuteActivity(ctx, ValidateApplicationActivity, input).Get(ctx, nil)
	if err != nil {
		return &WorkflowResult{
			WorkflowID: input.WorkflowID,
			Status:     "failed",
			Error:      err.Error(),
		}, err
	}

	// Step 2: Background check (30 minutes)
	err = workflow.ExecuteActivity(ctx, BackgroundCheckActivity, input).Get(ctx, nil)
	if err != nil {
		return &WorkflowResult{
			WorkflowID: input.WorkflowID,
			Status:     "failed",
			Error:      err.Error(),
		}, err
	}

	// Step 3: KYC verification (1 hour)
	err = workflow.ExecuteActivity(ctx, KYCVerificationActivity, input).Get(ctx, nil)
	if err != nil {
		return &WorkflowResult{
			WorkflowID: input.WorkflowID,
			Status:     "failed",
			Error:      err.Error(),
		}, err
	}

	// Step 4: Credit assessment (2 hours)
	err = workflow.ExecuteActivity(ctx, CreditAssessmentActivity, input).Get(ctx, nil)
	if err != nil {
		return &WorkflowResult{
			WorkflowID: input.WorkflowID,
			Status:     "failed",
			Error:      err.Error(),
		}, err
	}

	// Step 5: Create agent account
	err = workflow.ExecuteActivity(ctx, CreateAgentAccountActivity, input).Get(ctx, nil)
	if err != nil {
		return &WorkflowResult{
			WorkflowID: input.WorkflowID,
			Status:     "failed",
			Error:      err.Error(),
		}, err
	}

	return &WorkflowResult{
		WorkflowID: input.WorkflowID,
		Status:     "completed",
		OutputData: map[string]interface{}{
			"agent_id": "AGT-" + input.EntityID,
		},
	}, nil
}

// Example activity implementations
func ValidateApplicationActivity(ctx context.Context, input *WorkflowInput) error {
	// Validate application logic
	time.Sleep(5 * time.Second)
	return nil
}

func BackgroundCheckActivity(ctx context.Context, input *WorkflowInput) error {
	// Background check logic
	time.Sleep(30 * time.Minute)
	return nil
}

func KYCVerificationActivity(ctx context.Context, input *WorkflowInput) error {
	// KYC verification logic
	time.Sleep(1 * time.Hour)
	return nil
}

func CreditAssessmentActivity(ctx context.Context, input *WorkflowInput) error {
	// Credit assessment logic
	time.Sleep(2 * time.Hour)
	return nil
}

func CreateAgentAccountActivity(ctx context.Context, input *WorkflowInput) error {
	// Create agent account logic
	time.Sleep(5 * time.Second)
	return nil
}

