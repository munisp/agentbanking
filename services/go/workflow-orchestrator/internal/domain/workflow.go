package domain

import (
	"time"

	"github.com/google/uuid"
)

// WorkflowStatus represents workflow execution status
type WorkflowStatus string

const (
	StatusPending   WorkflowStatus = "pending"
	StatusRunning   WorkflowStatus = "running"
	StatusCompleted WorkflowStatus = "completed"
	StatusFailed    WorkflowStatus = "failed"
	StatusCancelled WorkflowStatus = "cancelled"
	StatusPaused    WorkflowStatus = "paused"
)

// Workflow represents a workflow execution
type Workflow struct {
	ID              uuid.UUID              `json:"id" db:"id"`
	WorkflowID      string                 `json:"workflow_id" db:"workflow_id"`
	WorkflowType    string                 `json:"workflow_type" db:"workflow_type"`
	Status          WorkflowStatus         `json:"status" db:"status"`
	TenantID        string                 `json:"tenant_id" db:"tenant_id"`
	UserID          string                 `json:"user_id" db:"user_id"`
	EntityID        string                 `json:"entity_id" db:"entity_id"`
	InputData       map[string]interface{} `json:"input_data" db:"input_data"`
	OutputData      map[string]interface{} `json:"output_data" db:"output_data"`
	Context         map[string]interface{} `json:"context" db:"context"`
	CurrentStep     string                 `json:"current_step" db:"current_step"`
	TotalSteps      int                    `json:"total_steps" db:"total_steps"`
	CompletedSteps  int                    `json:"completed_steps" db:"completed_steps"`
	FailedSteps     int                    `json:"failed_steps" db:"failed_steps"`
	StartedAt       *time.Time             `json:"started_at" db:"started_at"`
	CompletedAt     *time.Time             `json:"completed_at" db:"completed_at"`
	FailedAt        *time.Time             `json:"failed_at" db:"failed_at"`
	DurationSeconds float64                `json:"duration_seconds" db:"duration_seconds"`
	ErrorMessage    string                 `json:"error_message" db:"error_message"`
	RetryCount      int                    `json:"retry_count" db:"retry_count"`
	MaxRetries      int                    `json:"max_retries" db:"max_retries"`
	CreatedAt       time.Time              `json:"created_at" db:"created_at"`
	UpdatedAt       time.Time              `json:"updated_at" db:"updated_at"`
}

// StepStatus represents step execution status
type StepStatus string

const (
	StepPending   StepStatus = "pending"
	StepRunning   StepStatus = "running"
	StepCompleted StepStatus = "completed"
	StepFailed    StepStatus = "failed"
	StepSkipped   StepStatus = "skipped"
	StepRetrying  StepStatus = "retrying"
)

// WorkflowStep represents a single step in a workflow
type WorkflowStep struct {
	ID              uuid.UUID              `json:"id" db:"id"`
	StepID          string                 `json:"step_id" db:"step_id"`
	WorkflowID      string                 `json:"workflow_id" db:"workflow_id"`
	StepName        string                 `json:"step_name" db:"step_name"`
	StepType        string                 `json:"step_type" db:"step_type"`
	StepOrder       int                    `json:"step_order" db:"step_order"`
	Status          StepStatus             `json:"status" db:"status"`
	ServiceURL      string                 `json:"service_url" db:"service_url"`
	Endpoint        string                 `json:"endpoint" db:"endpoint"`
	InputData       map[string]interface{} `json:"input_data" db:"input_data"`
	OutputData      map[string]interface{} `json:"output_data" db:"output_data"`
	StartedAt       *time.Time             `json:"started_at" db:"started_at"`
	CompletedAt     *time.Time             `json:"completed_at" db:"completed_at"`
	DurationSeconds float64                `json:"duration_seconds" db:"duration_seconds"`
	ErrorMessage    string                 `json:"error_message" db:"error_message"`
	RetryCount      int                    `json:"retry_count" db:"retry_count"`
	CreatedAt       time.Time              `json:"created_at" db:"created_at"`
	UpdatedAt       time.Time              `json:"updated_at" db:"updated_at"`
}

// WorkflowDefinition defines a workflow template
type WorkflowDefinition struct {
	Type        string           `json:"type"`
	Name        string           `json:"name"`
	Description string           `json:"description"`
	Steps       []StepDefinition `json:"steps"`
	MaxRetries  int              `json:"max_retries"`
	Timeout     time.Duration    `json:"timeout"`
}

// StepDefinition defines a workflow step template
type StepDefinition struct {
	Name       string        `json:"name"`
	Type       string        `json:"type"`
	ServiceURL string        `json:"service_url"`
	Endpoint   string        `json:"endpoint"`
	Timeout    time.Duration `json:"timeout"`
	Retryable  bool          `json:"retryable"`
}

// CreateWorkflowRequest represents a request to create a workflow
type CreateWorkflowRequest struct {
	WorkflowType string                 `json:"workflow_type" binding:"required"`
	TenantID     string                 `json:"tenant_id"`
	UserID       string                 `json:"user_id"`
	EntityID     string                 `json:"entity_id"`
	InputData    map[string]interface{} `json:"input_data" binding:"required"`
}

// WorkflowResponse represents a workflow response
type WorkflowResponse struct {
	Workflow *Workflow `json:"workflow"`
	Message  string    `json:"message,omitempty"`
}

// ListWorkflowsRequest represents a request to list workflows
type ListWorkflowsRequest struct {
	Status       WorkflowStatus `json:"status"`
	WorkflowType string         `json:"workflow_type"`
	TenantID     string         `json:"tenant_id"`
	UserID       string         `json:"user_id"`
	Limit        int            `json:"limit"`
	Offset       int            `json:"offset"`
}

