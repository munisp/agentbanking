package repository

import (
"context"
"workflow-orchestrator/internal/domain"
)

type WorkflowRepository interface {
Create(ctx context.Context, workflow *domain.Workflow) error
Update(ctx context.Context, workflow *domain.Workflow) error
GetByID(ctx context.Context, id string) (*domain.Workflow, error)
GetByWorkflowID(ctx context.Context, workflowID string) (*domain.Workflow, error)
List(ctx context.Context, req *domain.ListWorkflowsRequest) ([]*domain.Workflow, error)
Close() error
}
