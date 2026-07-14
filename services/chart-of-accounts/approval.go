package main

import (
	"context"
	"errors"
	"fmt"
	"log"
	"time"

	"github.com/google/uuid"
)

type ApprovalStatus string

const (
	ApprovalStatusPending  ApprovalStatus = "pending"
	ApprovalStatusApproved ApprovalStatus = "approved"
	ApprovalStatusRejected ApprovalStatus = "rejected"
	ApprovalStatusCanceled ApprovalStatus = "canceled"
)

type ApprovalWorkflow struct {
	ID         string                 `json:"id"`
	TenantID   string                 `json:"tenant_id"`
	Name       string                 `json:"name"`
	EntityType string                 `json:"entity_type"`
	MinAmount  int64                  `json:"min_amount,omitempty"`
	MaxAmount  int64                  `json:"max_amount,omitempty"`
	Steps      []ApprovalWorkflowStep `json:"steps"`
	IsActive   bool                   `json:"is_active"`
	CreatedAt  time.Time              `json:"created_at"`
	UpdatedAt  time.Time              `json:"updated_at"`
}

type ApprovalWorkflowStep struct {
	StepOrder      int    `json:"step_order"`
	ApproverRole   string `json:"approver_role"`
	ApproverUserID string `json:"approver_user_id,omitempty"`
	IsMandatory    bool   `json:"is_mandatory"`
}

type ApprovalRequest struct {
	ID          string                 `json:"id"`
	TenantID    string                 `json:"tenant_id"`
	WorkflowID  string                 `json:"workflow_id"`
	EntityType  string                 `json:"entity_type"`
	EntityID    string                 `json:"entity_id"`
	CurrentStep int                    `json:"current_step"`
	Status      ApprovalStatus         `json:"status"`
	RequestedBy string                 `json:"requested_by"`
	RequestedAt time.Time              `json:"requested_at"`
	CompletedAt time.Time              `json:"completed_at,omitempty"`
	Actions     []ApprovalAction       `json:"actions,omitempty"`
	Metadata    map[string]interface{} `json:"metadata,omitempty"`
}

type ApprovalAction struct {
	StepNumber int       `json:"step_number"`
	Action     string    `json:"action"`
	ActionBy   string    `json:"action_by"`
	ActionAt   time.Time `json:"action_at"`
	Comments   string    `json:"comments,omitempty"`
}

type ApprovalService struct {
	store      *PostgresStore
	coaService *ChartOfAccountsService
}

func NewApprovalService(store *PostgresStore, coaService *ChartOfAccountsService) *ApprovalService {
	return &ApprovalService{
		store:      store,
		coaService: coaService,
	}
}

func (s *ApprovalService) CreateWorkflow(ctx context.Context, tenantID string, workflow ApprovalWorkflow) (*ApprovalWorkflow, error) {
	if s.store == nil {
		return nil, errors.New("postgres store not initialized")
	}

	if workflow.Name == "" {
		return nil, errors.New("workflow name is required")
	}

	if workflow.EntityType == "" {
		return nil, errors.New("entity type is required")
	}

	if len(workflow.Steps) == 0 {
		return nil, errors.New("at least one approval step is required")
	}

	now := time.Now()
	workflow.ID = uuid.New().String()
	workflow.TenantID = tenantID
	workflow.IsActive = true
	workflow.CreatedAt = now
	workflow.UpdatedAt = now

	for i := range workflow.Steps {
		workflow.Steps[i].StepOrder = i + 1
	}

	if err := s.store.SaveApprovalWorkflow(ctx, workflow); err != nil {
		return nil, fmt.Errorf("failed to save workflow: %w", err)
	}

	return &workflow, nil
}

func (s *ApprovalService) GetWorkflow(ctx context.Context, tenantID, workflowID string) (*ApprovalWorkflow, error) {
	if s.store == nil {
		return nil, errors.New("postgres store not initialized")
	}

	return s.store.GetApprovalWorkflow(ctx, tenantID, workflowID)
}

func (s *ApprovalService) GetWorkflowForAmount(ctx context.Context, tenantID, entityType string, amount int64) (*ApprovalWorkflow, error) {
	if s.store == nil {
		return nil, errors.New("postgres store not initialized")
	}

	return s.store.GetApprovalWorkflowForAmount(ctx, tenantID, entityType, amount)
}

func (s *ApprovalService) SubmitForApproval(ctx context.Context, tenantID, entityType, entityID, requestedBy string, amount int64, metadata map[string]interface{}) (*ApprovalRequest, error) {
	if s.store == nil {
		return nil, errors.New("postgres store not initialized")
	}

	workflow, err := s.store.GetApprovalWorkflowForAmount(ctx, tenantID, entityType, amount)
	if err != nil {
		return nil, fmt.Errorf("failed to get workflow: %w", err)
	}

	if workflow == nil {
		return nil, nil
	}

	existingRequest, err := s.store.GetPendingApprovalForEntity(ctx, tenantID, entityType, entityID)
	if err != nil {
		return nil, fmt.Errorf("failed to check existing requests: %w", err)
	}
	if existingRequest != nil {
		return nil, errors.New("entity already has a pending approval request")
	}

	now := time.Now()
	request := ApprovalRequest{
		ID:          uuid.New().String(),
		TenantID:    tenantID,
		WorkflowID:  workflow.ID,
		EntityType:  entityType,
		EntityID:    entityID,
		CurrentStep: 1,
		Status:      ApprovalStatusPending,
		RequestedBy: requestedBy,
		RequestedAt: now,
		Metadata:    metadata,
	}

	if err := s.store.SaveApprovalRequest(ctx, request); err != nil {
		return nil, fmt.Errorf("failed to save approval request: %w", err)
	}

	return &request, nil
}

func (s *ApprovalService) GetApprovalRequest(ctx context.Context, tenantID, requestID string) (*ApprovalRequest, error) {
	if s.store == nil {
		return nil, errors.New("postgres store not initialized")
	}

	return s.store.GetApprovalRequest(ctx, tenantID, requestID)
}

func (s *ApprovalService) Approve(ctx context.Context, tenantID, requestID, approverID, comments string) (*ApprovalRequest, error) {
	if s.store == nil {
		return nil, errors.New("postgres store not initialized")
	}

	request, err := s.store.GetApprovalRequest(ctx, tenantID, requestID)
	if err != nil {
		return nil, err
	}
	if request == nil {
		return nil, errors.New("approval request not found")
	}

	if request.Status != ApprovalStatusPending {
		return nil, fmt.Errorf("request is not pending (status: %s)", request.Status)
	}

	workflow, err := s.store.GetApprovalWorkflow(ctx, tenantID, request.WorkflowID)
	if err != nil {
		return nil, err
	}
	if workflow == nil {
		return nil, errors.New("workflow not found")
	}

	if request.CurrentStep > len(workflow.Steps) {
		return nil, errors.New("invalid current step")
	}

	currentStepConfig := workflow.Steps[request.CurrentStep-1]
	if !s.canApprove(approverID, currentStepConfig) {
		return nil, errors.New("user is not authorized to approve this step")
	}

	action := ApprovalAction{
		StepNumber: request.CurrentStep,
		Action:     "approved",
		ActionBy:   approverID,
		ActionAt:   time.Now(),
		Comments:   comments,
	}

	if err := s.store.SaveApprovalAction(ctx, requestID, action); err != nil {
		return nil, fmt.Errorf("failed to save approval action: %w", err)
	}

	request.Actions = append(request.Actions, action)

	if request.CurrentStep >= len(workflow.Steps) {
		request.Status = ApprovalStatusApproved
		request.CompletedAt = time.Now()

		if err := s.onApprovalComplete(ctx, request); err != nil {
			return nil, fmt.Errorf("failed to process approval completion: %w", err)
		}
	} else {
		request.CurrentStep++
	}

	if err := s.store.SaveApprovalRequest(ctx, *request); err != nil {
		return nil, fmt.Errorf("failed to update approval request: %w", err)
	}

	return request, nil
}

func (s *ApprovalService) Reject(ctx context.Context, tenantID, requestID, approverID, comments string) (*ApprovalRequest, error) {
	if s.store == nil {
		return nil, errors.New("postgres store not initialized")
	}

	request, err := s.store.GetApprovalRequest(ctx, tenantID, requestID)
	if err != nil {
		return nil, err
	}
	if request == nil {
		return nil, errors.New("approval request not found")
	}

	if request.Status != ApprovalStatusPending {
		return nil, fmt.Errorf("request is not pending (status: %s)", request.Status)
	}

	workflow, err := s.store.GetApprovalWorkflow(ctx, tenantID, request.WorkflowID)
	if err != nil {
		return nil, err
	}
	if workflow == nil {
		return nil, errors.New("workflow not found")
	}

	currentStepConfig := workflow.Steps[request.CurrentStep-1]
	if !s.canApprove(approverID, currentStepConfig) {
		return nil, errors.New("user is not authorized to reject this step")
	}

	action := ApprovalAction{
		StepNumber: request.CurrentStep,
		Action:     "rejected",
		ActionBy:   approverID,
		ActionAt:   time.Now(),
		Comments:   comments,
	}

	if err := s.store.SaveApprovalAction(ctx, requestID, action); err != nil {
		return nil, fmt.Errorf("failed to save rejection action: %w", err)
	}

	request.Actions = append(request.Actions, action)
	request.Status = ApprovalStatusRejected
	request.CompletedAt = time.Now()

	if err := s.store.SaveApprovalRequest(ctx, *request); err != nil {
		return nil, fmt.Errorf("failed to update approval request: %w", err)
	}

	if err := s.onApprovalRejected(ctx, request); err != nil {
		return nil, fmt.Errorf("failed to process rejection: %w", err)
	}

	return request, nil
}

func (s *ApprovalService) Cancel(ctx context.Context, tenantID, requestID, userID, reason string) (*ApprovalRequest, error) {
	if s.store == nil {
		return nil, errors.New("postgres store not initialized")
	}

	request, err := s.store.GetApprovalRequest(ctx, tenantID, requestID)
	if err != nil {
		return nil, err
	}
	if request == nil {
		return nil, errors.New("approval request not found")
	}

	if request.Status != ApprovalStatusPending {
		return nil, fmt.Errorf("request is not pending (status: %s)", request.Status)
	}

	if request.RequestedBy != userID {
		return nil, errors.New("only the requester can cancel the request")
	}

	action := ApprovalAction{
		StepNumber: request.CurrentStep,
		Action:     "canceled",
		ActionBy:   userID,
		ActionAt:   time.Now(),
		Comments:   reason,
	}

	if err := s.store.SaveApprovalAction(ctx, requestID, action); err != nil {
		return nil, fmt.Errorf("failed to save cancellation action: %w", err)
	}

	request.Actions = append(request.Actions, action)
	request.Status = ApprovalStatusCanceled
	request.CompletedAt = time.Now()

	if err := s.store.SaveApprovalRequest(ctx, *request); err != nil {
		return nil, fmt.Errorf("failed to update approval request: %w", err)
	}

	return request, nil
}

func (s *ApprovalService) canApprove(userID string, step ApprovalWorkflowStep) bool {
	if step.ApproverUserID != "" && step.ApproverUserID == userID {
		return true
	}

	return true
}

func (s *ApprovalService) onApprovalComplete(ctx context.Context, request *ApprovalRequest) error {
	switch request.EntityType {
	case "journal_entry":
		return s.postJournalEntry(ctx, request.TenantID, request.EntityID)
	default:
		return nil
	}
}

func (s *ApprovalService) postJournalEntry(ctx context.Context, tenantID, entryID string) error {
	if s.coaService == nil {
		return nil
	}

	entry, err := s.coaService.GetJournalEntry(ctx, tenantID, entryID)
	if err != nil {
		return err
	}
	if entry == nil {
		return errors.New("journal entry not found")
	}

	// Update journal entry status in PostgreSQL
	if s.coaService.postgres != nil {
		entry.Status = JournalEntryStatusPosted
		now := time.Now()
		entry.PostedAt = &now
		entry.UpdatedAt = time.Now()
		if err := s.coaService.postgres.SaveJournalEntry(ctx, *entry); err != nil {
			log.Printf("ERROR: Failed to update journal entry status: %v", err)
			return err
		}
	}

	return nil
}

func (s *ApprovalService) onApprovalRejected(ctx context.Context, request *ApprovalRequest) error {
	switch request.EntityType {
	case "journal_entry":
		return s.rejectJournalEntry(ctx, request.TenantID, request.EntityID)
	default:
		return nil
	}
}

func (s *ApprovalService) rejectJournalEntry(ctx context.Context, tenantID, entryID string) error {
	if s.coaService == nil {
		return nil
	}

	// Get journal entry from PostgreSQL
	entry, err := s.coaService.GetJournalEntry(ctx, tenantID, entryID)
	if err != nil {
		return err
	}

	// Update status
	if s.coaService.postgres != nil {
		entry.Status = JournalEntryStatusRejected
		entry.UpdatedAt = time.Now()
		if err := s.coaService.postgres.SaveJournalEntry(ctx, *entry); err != nil {
			log.Printf("ERROR: Failed to update journal entry status: %v", err)
			return err
		}
	}

	return nil
}

func (s *ApprovalService) GetPendingApprovalsForUser(ctx context.Context, tenantID, userID, userRole string) ([]ApprovalRequest, error) {
	if s.store == nil {
		return nil, errors.New("postgres store not initialized")
	}

	return nil, nil
}

func (s *ApprovalService) CreateDefaultWorkflows(ctx context.Context, tenantID string) error {
	if s.store == nil {
		return errors.New("postgres store not initialized")
	}

	workflows := []ApprovalWorkflow{
		{
			Name:       "Small Journal Entry Approval",
			EntityType: "journal_entry",
			MinAmount:  0,
			MaxAmount:  100000000,
			Steps: []ApprovalWorkflowStep{
				{StepOrder: 1, ApproverRole: "finance_admin", IsMandatory: true},
			},
		},
		{
			Name:       "Medium Journal Entry Approval",
			EntityType: "journal_entry",
			MinAmount:  100000001,
			MaxAmount:  1000000000,
			Steps: []ApprovalWorkflowStep{
				{StepOrder: 1, ApproverRole: "finance_admin", IsMandatory: true},
				{StepOrder: 2, ApproverRole: "bank_admin", IsMandatory: true},
			},
		},
		{
			Name:       "Large Journal Entry Approval",
			EntityType: "journal_entry",
			MinAmount:  1000000001,
			MaxAmount:  0,
			Steps: []ApprovalWorkflowStep{
				{StepOrder: 1, ApproverRole: "finance_admin", IsMandatory: true},
				{StepOrder: 2, ApproverRole: "bank_admin", IsMandatory: true},
				{StepOrder: 3, ApproverRole: "super_admin", IsMandatory: true},
			},
		},
		{
			Name:       "Account Creation Approval",
			EntityType: "account",
			Steps: []ApprovalWorkflowStep{
				{StepOrder: 1, ApproverRole: "bank_admin", IsMandatory: true},
			},
		},
		{
			Name:       "Period Close Approval",
			EntityType: "period_close",
			Steps: []ApprovalWorkflowStep{
				{StepOrder: 1, ApproverRole: "finance_admin", IsMandatory: true},
				{StepOrder: 2, ApproverRole: "bank_admin", IsMandatory: true},
				{StepOrder: 3, ApproverRole: "auditor", IsMandatory: false},
			},
		},
	}

	for _, workflow := range workflows {
		if _, err := s.CreateWorkflow(ctx, tenantID, workflow); err != nil {
			return fmt.Errorf("failed to create workflow %s: %w", workflow.Name, err)
		}
	}

	return nil
}

type JournalEntryWithApproval struct {
	JournalEntry
	ApprovalRequest  *ApprovalRequest `json:"approval_request,omitempty"`
	RequiresApproval bool             `json:"requires_approval"`
	CanApprove       bool             `json:"can_approve"`
	CanReject        bool             `json:"can_reject"`
}

func (s *ApprovalService) GetJournalEntryWithApproval(ctx context.Context, tenantID, entryID, userID, userRole string) (*JournalEntryWithApproval, error) {
	if s.coaService == nil {
		return nil, errors.New("coa service not initialized")
	}

	entry, err := s.coaService.GetJournalEntry(ctx, tenantID, entryID)
	if err != nil {
		return nil, err
	}
	if entry == nil {
		return nil, errors.New("journal entry not found")
	}

	result := &JournalEntryWithApproval{
		JournalEntry: *entry,
	}

	if s.store != nil {
		approvalRequest, err := s.store.GetPendingApprovalForEntity(ctx, tenantID, "journal_entry", entryID)
		if err == nil && approvalRequest != nil {
			result.ApprovalRequest = approvalRequest
			result.RequiresApproval = true

			workflow, err := s.store.GetApprovalWorkflow(ctx, tenantID, approvalRequest.WorkflowID)
			if err == nil && workflow != nil && approvalRequest.CurrentStep <= len(workflow.Steps) {
				currentStep := workflow.Steps[approvalRequest.CurrentStep-1]
				result.CanApprove = s.canApprove(userID, currentStep)
				result.CanReject = result.CanApprove
			}
		}
	}

	return result, nil
}
