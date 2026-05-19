package engine

import (
	"context"
	"testing"
	"time"

	"workflow-orchestrator/internal/domain"

	"github.com/google/uuid"
)

// BenchmarkWorkflowExecution benchmarks workflow execution performance
func BenchmarkWorkflowExecution(b *testing.B) {
	executor := setupBenchmarkExecutor()
	definition := createBenchmarkDefinition()

	b.ResetTimer()
	b.RunParallel(func(pb *testing.PB) {
		for pb.Next() {
			workflow := createBenchmarkWorkflow()
			_ = executor.Execute(context.Background(), workflow, definition)
		}
	})
}

// BenchmarkConcurrentWorkflows benchmarks concurrent workflow execution
func BenchmarkConcurrentWorkflows(b *testing.B) {
	executor := setupBenchmarkExecutor()
	definition := createBenchmarkDefinition()

	workflows := make([]*domain.Workflow, b.N)
	for i := 0; i < b.N; i++ {
		workflows[i] = createBenchmarkWorkflow()
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		go executor.Execute(context.Background(), workflows[i], definition)
	}
}

// BenchmarkWorkflowStart benchmarks workflow start latency
func BenchmarkWorkflowStart(b *testing.B) {
	_ = setupBenchmarkExecutor()
	_ = createBenchmarkDefinition()

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		workflow := createBenchmarkWorkflow()
		workflow.Status = domain.StatusRunning
		now := time.Now()
		workflow.StartedAt = &now
	}
}

// BenchmarkStepExecution benchmarks step execution performance
func BenchmarkStepExecution(b *testing.B) {
	stepExecutor := NewStepExecutor(3)

	b.ResetTimer()
	b.RunParallel(func(pb *testing.PB) {
		for pb.Next() {
			step := createBenchmarkStep()
			_ = stepExecutor.Execute(context.Background(), step)
		}
	})
}

// BenchmarkStateManagement benchmarks state persistence
func BenchmarkStateManagement(b *testing.B) {
	// Mock repository for benchmarking
	repo := &mockRepository{}
	redis := &mockRedisClient{}
	stateManager := NewStateManager(repo, redis)

	workflow := createBenchmarkWorkflow()

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_ = stateManager.SaveState(context.Background(), workflow)
	}
}

// Helper functions

func setupBenchmarkExecutor() *Executor {
	repo := &mockRepository{}
	redis := &mockRedisClient{}
	stateManager := NewStateManager(repo, redis)
	stepExecutor := NewStepExecutor(3)

	return NewExecutor(
		repo,
		stateManager,
		stepExecutor,
		nil, // fluvio
		nil, // kafka
		redis,
		1000, // maxConcurrent
	)
}

func createBenchmarkDefinition() *domain.WorkflowDefinition {
	return &domain.WorkflowDefinition{
		Type:        "benchmark",
		Name:        "Benchmark Workflow",
		Description: "Workflow for benchmarking",
		MaxRetries:  3,
		Timeout:     1 * time.Minute,
		Steps: []domain.StepDefinition{
			{Name: "Step 1", Type: "service_call", ServiceURL: "http://localhost:8000", Endpoint: "/api/test", Timeout: 5 * time.Second, Retryable: true},
			{Name: "Step 2", Type: "service_call", ServiceURL: "http://localhost:8000", Endpoint: "/api/test", Timeout: 5 * time.Second, Retryable: true},
			{Name: "Step 3", Type: "notification", ServiceURL: "", Endpoint: "", Timeout: 5 * time.Second, Retryable: true},
		},
	}
}

func createBenchmarkWorkflow() *domain.Workflow {
	return &domain.Workflow{
		ID:           uuid.New(),
		WorkflowID:   "WF-BENCH-" + uuid.New().String(),
		WorkflowType: "benchmark",
		Status:       domain.StatusPending,
		TenantID:     "tenant-1",
		UserID:       "user-1",
		EntityID:     "entity-1",
		InputData:    map[string]interface{}{"test": "data"},
		OutputData:   make(map[string]interface{}),
		Context:      make(map[string]interface{}),
		MaxRetries:   3,
		CreatedAt:    time.Now(),
		UpdatedAt:    time.Now(),
	}
}

func createBenchmarkStep() *domain.WorkflowStep {
	return &domain.WorkflowStep{
		ID:         uuid.New(),
		StepID:     "STEP-" + uuid.New().String(),
		WorkflowID: "WF-BENCH-123",
		StepName:   "Benchmark Step",
		StepType:   "service_call",
		StepOrder:  1,
		Status:     domain.StepPending,
		ServiceURL: "http://localhost:8000",
		Endpoint:   "/api/test",
		InputData:  map[string]interface{}{"test": "data"},
		CreatedAt:  time.Now(),
		UpdatedAt:  time.Now(),
	}
}

// Mock implementations

type mockRepository struct{}

func (m *mockRepository) Create(ctx context.Context, workflow *domain.Workflow) error {
	return nil
}

func (m *mockRepository) Update(ctx context.Context, workflow *domain.Workflow) error {
	return nil
}

func (m *mockRepository) GetByID(ctx context.Context, id string) (*domain.Workflow, error) {
	return createBenchmarkWorkflow(), nil
}

func (m *mockRepository) GetByWorkflowID(ctx context.Context, workflowID string) (*domain.Workflow, error) {
	return createBenchmarkWorkflow(), nil
}

func (m *mockRepository) List(ctx context.Context, req *domain.ListWorkflowsRequest) ([]*domain.Workflow, error) {
	return []*domain.Workflow{createBenchmarkWorkflow()}, nil
}

func (m *mockRepository) Close() error {
	return nil
}

type mockRedisClient struct{}

func (m *mockRedisClient) CacheWorkflowState(ctx context.Context, workflow *domain.Workflow) error {
	return nil
}

func (m *mockRedisClient) GetWorkflowState(ctx context.Context, workflowID string) (*domain.Workflow, error) {
	return nil, nil
}

func (m *mockRedisClient) AcquireLock(ctx context.Context, workflowID string, ttl time.Duration) (bool, error) {
	return true, nil
}

func (m *mockRedisClient) ReleaseLock(ctx context.Context, workflowID string) error {
	return nil
}

func (m *mockRedisClient) Close() error {
	return nil
}

