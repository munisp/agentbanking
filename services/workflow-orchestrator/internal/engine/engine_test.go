package engine_test

import (
	"context"
	"errors"
	"testing"
	"time"

	"workflow-orchestrator/internal/domain"
	"github.com/google/uuid"
	"workflow-orchestrator/internal/engine"
)

// ─── Mock WorkflowRepository ──────────────────────────────────────────────────

type mockRepo struct {
	data map[string]*domain.Workflow
	fail bool
}

func newMockRepo() *mockRepo {
	return &mockRepo{data: make(map[string]*domain.Workflow)}
}

func (m *mockRepo) Create(ctx context.Context, wf *domain.Workflow) error {
	if m.fail {
		return errors.New("db unavailable")
	}
	m.data[wf.WorkflowID] = wf
	return nil
}

func (m *mockRepo) Update(ctx context.Context, wf *domain.Workflow) error {
	if m.fail {
		return errors.New("db unavailable")
	}
	m.data[wf.WorkflowID] = wf
	return nil
}

func (m *mockRepo) GetByID(ctx context.Context, id string) (*domain.Workflow, error) {
	if m.fail {
		return nil, errors.New("db unavailable")
	}
	parsed, err := uuid.Parse(id)
	if err != nil {
		return nil, errors.New("invalid uuid")
	}
	for _, wf := range m.data {
		if wf.ID == parsed {
			return wf, nil
		}
	}
	return nil, errors.New("not found")
}

func (m *mockRepo) GetByWorkflowID(ctx context.Context, id string) (*domain.Workflow, error) {
	if m.fail {
		return nil, errors.New("db unavailable")
	}
	wf, ok := m.data[id]
	if !ok {
		return nil, errors.New("not found")
	}
	return wf, nil
}

func (m *mockRepo) List(ctx context.Context, req *domain.ListWorkflowsRequest) ([]*domain.Workflow, error) {
	var out []*domain.Workflow
	for _, wf := range m.data {
		out = append(out, wf)
	}
	return out, nil
}

func (m *mockRepo) Close() error { return nil }

// ─── Mock Redis Cache ─────────────────────────────────────────────────────────

type mockCache struct {
	data      map[string]*domain.Workflow
	locks     map[string]bool
	fail      bool
	cacheMiss bool
}

func newMockCache() *mockCache {
	return &mockCache{
		data:  make(map[string]*domain.Workflow),
		locks: make(map[string]bool),
	}
}

func (m *mockCache) CacheWorkflowState(ctx context.Context, wf *domain.Workflow) error {
	if m.fail {
		return errors.New("redis unavailable")
	}
	m.data[wf.WorkflowID] = wf
	return nil
}

func (m *mockCache) GetWorkflowState(ctx context.Context, workflowID string) (*domain.Workflow, error) {
	if m.fail || m.cacheMiss {
		return nil, errors.New("cache miss")
	}
	wf, ok := m.data[workflowID]
	if !ok {
		return nil, errors.New("cache miss")
	}
	return wf, nil
}

func (m *mockCache) AcquireLock(ctx context.Context, resource string, ttl time.Duration) (bool, error) {
	if m.fail {
		return false, errors.New("redis unavailable")
	}
	if m.locks[resource] {
		return false, nil
	}
	m.locks[resource] = true
	return true, nil
}

func (m *mockCache) ReleaseLock(ctx context.Context, resource string) error {
	if m.fail {
		return errors.New("redis unavailable")
	}
	delete(m.locks, resource)
	return nil
}

func (m *mockCache) Close() error { return nil }

// ─── Helper ───────────────────────────────────────────────────────────────────

func makeWorkflow(id string, status domain.WorkflowStatus) *domain.Workflow {
	return &domain.Workflow{
		WorkflowID: id,
		Status:     status,
		CreatedAt:  time.Now(),
		UpdatedAt:  time.Now(),
	}
}

// ─── Tests ────────────────────────────────────────────────────────────────────

func TestStateManager_SaveAndGetFromCache(t *testing.T) {
	repo := newMockRepo()
	cache := newMockCache()
	sm := engine.NewStateManager(repo, cache)
	ctx := context.Background()

	wf := makeWorkflow("wf-001", domain.StatusRunning)
	if err := sm.SaveState(ctx, wf); err != nil {
		t.Fatalf("SaveState failed: %v", err)
	}

	got, err := sm.GetState(ctx, "wf-001")
	if err != nil {
		t.Fatalf("GetState failed: %v", err)
	}
	if got.Status != domain.StatusRunning {
		t.Errorf("expected %q, got %q", domain.StatusRunning, got.Status)
	}
}

func TestStateManager_FallsBackToDBOnCacheMiss(t *testing.T) {
	repo := newMockRepo()
	cache := newMockCache()
	cache.cacheMiss = true
	sm := engine.NewStateManager(repo, cache)
	ctx := context.Background()

	wf := makeWorkflow("wf-002", domain.StatusPending)
	_ = repo.Create(ctx, wf)

	got, err := sm.GetState(ctx, "wf-002")
	if err != nil {
		t.Fatalf("GetState (DB fallback) failed: %v", err)
	}
	if got.Status != domain.StatusPending {
		t.Errorf("expected %q, got %q", domain.StatusPending, got.Status)
	}
}

func TestStateManager_MissingWorkflow(t *testing.T) {
	repo := newMockRepo()
	cache := newMockCache()
	cache.cacheMiss = true
	sm := engine.NewStateManager(repo, cache)
	ctx := context.Background()

	_, err := sm.GetState(ctx, "nonexistent-wf")
	if err == nil {
		t.Error("expected error for missing workflow, got nil")
	}
}

func TestStateManager_DBFailureOnSave(t *testing.T) {
	repo := newMockRepo()
	repo.fail = true
	cache := newMockCache()
	sm := engine.NewStateManager(repo, cache)
	ctx := context.Background()

	wf := makeWorkflow("wf-003", domain.StatusRunning)
	if err := sm.SaveState(ctx, wf); err == nil {
		t.Error("expected error when DB is unavailable, got nil")
	}
}

func TestStateManager_StateTransitions(t *testing.T) {
	repo := newMockRepo()
	cache := newMockCache()
	sm := engine.NewStateManager(repo, cache)
	ctx := context.Background()

	wf := makeWorkflow("wf-004", domain.StatusPending)
	_ = sm.SaveState(ctx, wf)

	states := []domain.WorkflowStatus{
		domain.StatusRunning,
		domain.StatusCompleted,
		domain.StatusFailed,
		domain.StatusPaused,
		domain.StatusCancelled,
	}
	for _, s := range states {
		wf.Status = s
		if err := sm.SaveState(ctx, wf); err != nil {
			t.Fatalf("SaveState(%q) failed: %v", s, err)
		}
		got, err := sm.GetState(ctx, wf.WorkflowID)
		if err != nil {
			t.Fatalf("GetState after %q failed: %v", s, err)
		}
		if got.Status != s {
			t.Errorf("expected %q, got %q", s, got.Status)
		}
	}
}

func TestDistributedLock_AcquireAndRelease(t *testing.T) {
	cache := newMockCache()
	ctx := context.Background()

	ok1, err := cache.AcquireLock(ctx, "payment:txn-001", 30*time.Second)
	if err != nil || !ok1 {
		t.Fatalf("first AcquireLock failed: err=%v ok=%v", err, ok1)
	}

	ok2, err := cache.AcquireLock(ctx, "payment:txn-001", 30*time.Second)
	if err != nil || ok2 {
		t.Errorf("second AcquireLock should be denied: err=%v ok=%v", err, ok2)
	}

	if err := cache.ReleaseLock(ctx, "payment:txn-001"); err != nil {
		t.Fatalf("ReleaseLock failed: %v", err)
	}

	ok3, err := cache.AcquireLock(ctx, "payment:txn-001", 30*time.Second)
	if err != nil || !ok3 {
		t.Errorf("third AcquireLock should succeed after release: err=%v ok=%v", err, ok3)
	}
}

func TestDistributedLock_IndependentResources(t *testing.T) {
	cache := newMockCache()
	ctx := context.Background()

	a, _ := cache.AcquireLock(ctx, "resource-A", 10*time.Second)
	b, _ := cache.AcquireLock(ctx, "resource-B", 10*time.Second)
	if !a || !b {
		t.Error("independent resources should both be lockable simultaneously")
	}
}

func TestDistributedLock_RedisFailure(t *testing.T) {
	cache := newMockCache()
	cache.fail = true
	ctx := context.Background()

	_, err := cache.AcquireLock(ctx, "resource-X", 10*time.Second)
	if err == nil {
		t.Error("expected error when Redis is unavailable, got nil")
	}
}
