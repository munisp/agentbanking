package engine

import (
"context"
"time"

"workflow-orchestrator/internal/domain"
"workflow-orchestrator/internal/repository"
)

// RedisCache is the interface the engine uses for workflow state caching.
// Both *middleware.RedisClient (legacy) and *redis.Client (new) satisfy this interface.
type RedisCache interface {
CacheWorkflowState(ctx context.Context, workflow *domain.Workflow) error
GetWorkflowState(ctx context.Context, workflowID string) (*domain.Workflow, error)
AcquireLock(ctx context.Context, workflowID string, ttl time.Duration) (bool, error)
ReleaseLock(ctx context.Context, workflowID string) error
Close() error
}

// StateManager persists workflow state to both the database and Redis cache.
type StateManager struct {
repo  repository.WorkflowRepository
redis RedisCache
}

// NewStateManager creates a new StateManager.
func NewStateManager(repo repository.WorkflowRepository, redis RedisCache) *StateManager {
return &StateManager{
repo:  repo,
redis: redis,
}
}

// SaveState persists the workflow to the DB and updates the Redis cache.
func (s *StateManager) SaveState(ctx context.Context, workflow *domain.Workflow) error {
if err := s.repo.Update(ctx, workflow); err != nil {
return err
}
if err := s.redis.CacheWorkflowState(ctx, workflow); err != nil {
return err
}
return nil
}

// GetState retrieves the workflow from Redis (fast path) or falls back to the DB.
func (s *StateManager) GetState(ctx context.Context, workflowID string) (*domain.Workflow, error) {
workflow, err := s.redis.GetWorkflowState(ctx, workflowID)
if err == nil && workflow != nil {
return workflow, nil
}
return s.repo.GetByWorkflowID(ctx, workflowID)
}
