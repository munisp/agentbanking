#!/bin/bash

# Create step_executor.go
cat > internal/engine/step_executor.go << 'EOF'
package engine

import (
"bytes"
"context"
"encoding/json"
"fmt"
"io"
"net/http"
"time"

"workflow-orchestrator/internal/domain"
"workflow-orchestrator/pkg/logger"
)

type StepExecutor struct {
httpClient *http.Client
maxRetries int
}

func NewStepExecutor(maxRetries int) *StepExecutor {
return &StepExecutor{
httpClient: &http.Client{
Timeout: 30 * time.Second,
Transport: &http.Transport{
MaxIdleConns:        1000,
MaxIdleConnsPerHost: 100,
MaxConnsPerHost:     100,
IdleConnTimeout:     90 * time.Second,
DisableKeepAlives:   false,
},
},
maxRetries: maxRetries,
}
}

func (s *StepExecutor) Execute(ctx context.Context, step *domain.WorkflowStep) error {
log := logger.Logger.With(
logger.String("workflow_id", step.WorkflowID),
logger.String("step", step.StepName),
)

step.Status = domain.StepRunning
now := time.Now()
step.StartedAt = &now

var lastErr error

for attempt := 0; attempt <= s.maxRetries; attempt++ {
if attempt > 0 {
step.Status = domain.StepRetrying
step.RetryCount = attempt

backoff := time.Duration(1<<uint(attempt-1)) * time.Second
log.Info("Retrying step", logger.Int("attempt", attempt), logger.Duration("backoff", backoff))

select {
case <-time.After(backoff):
case <-ctx.Done():
return ctx.Err()
}
}

var err error
switch step.StepType {
case "service_call":
step.OutputData, err = s.executeServiceCall(ctx, step)
case "notification":
step.OutputData, err = s.executeNotification(ctx, step)
case "event_publish":
step.OutputData, err = s.executeEventPublish(ctx, step)
default:
err = fmt.Errorf("unknown step type: %s", step.StepType)
}

if err == nil {
step.Status = domain.StepCompleted
now := time.Now()
step.CompletedAt = &now
step.DurationSeconds = now.Sub(*step.StartedAt).Seconds()
log.Info("Step completed", logger.Float64("duration", step.DurationSeconds))
return nil
}

lastErr = err
log.Warn("Step attempt failed", logger.Int("attempt", attempt), logger.Error(err))
}

step.Status = domain.StepFailed
step.ErrorMessage = lastErr.Error()
now = time.Now()
step.CompletedAt = &now
step.DurationSeconds = now.Sub(*step.StartedAt).Seconds()

return lastErr
}

func (s *StepExecutor) executeServiceCall(ctx context.Context, step *domain.WorkflowStep) (map[string]interface{}, error) {
body, err := json.Marshal(step.InputData)
if err != nil {
return nil, fmt.Errorf("failed to marshal input: %w", err)
}

url := step.ServiceURL + step.Endpoint
req, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewReader(body))
if err != nil {
return nil, fmt.Errorf("failed to create request: %w", err)
}

req.Header.Set("Content-Type", "application/json")

resp, err := s.httpClient.Do(req)
if err != nil {
return nil, fmt.Errorf("failed to execute request: %w", err)
}
defer resp.Body.Close()

if resp.StatusCode >= 400 {
body, _ := io.ReadAll(resp.Body)
return nil, fmt.Errorf("service returned error %d: %s", resp.StatusCode, string(body))
}

var result map[string]interface{}
if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
return nil, fmt.Errorf("failed to decode response: %w", err)
}

return result, nil
}

func (s *StepExecutor) executeNotification(ctx context.Context, step *domain.WorkflowStep) (map[string]interface{}, error) {
return map[string]interface{}{
"notification_sent": true,
"channel":           "sms",
}, nil
}

func (s *StepExecutor) executeEventPublish(ctx context.Context, step *domain.WorkflowStep) (map[string]interface{}, error) {
return map[string]interface{}{
"event_published": true,
}, nil
}
EOF

# Create worker_pool.go
cat > internal/engine/worker_pool.go << 'EOF'
package engine

import (
"context"
"sync"

"workflow-orchestrator/internal/domain"
"workflow-orchestrator/pkg/logger"
)

type WorkerPool struct {
workers  int
jobs     chan *WorkflowJob
executor *Executor
wg       sync.WaitGroup
ctx      context.Context
cancel   context.CancelFunc
}

type WorkflowJob struct {
Workflow   *domain.Workflow
Definition *domain.WorkflowDefinition
}

func NewWorkerPool(workers int, executor *Executor) *WorkerPool {
return &WorkerPool{
workers:  workers,
jobs:     make(chan *WorkflowJob, workers*2),
executor: executor,
}
}

func (p *WorkerPool) Start(ctx context.Context) {
p.ctx, p.cancel = context.WithCancel(ctx)

for i := 0; i < p.workers; i++ {
p.wg.Add(1)
go p.worker(i)
}

logger.Logger.Info("Worker pool started", logger.Int("workers", p.workers))
}

func (p *WorkerPool) worker(id int) {
defer p.wg.Done()

log := logger.Logger.With(logger.Int("worker_id", id))
log.Info("Worker started")

for {
select {
case job := <-p.jobs:
if err := p.executor.Execute(p.ctx, job.Workflow, job.Definition); err != nil {
log.Error("Workflow execution failed",
logger.String("workflow_id", job.Workflow.WorkflowID),
logger.Error(err),
)
}
case <-p.ctx.Done():
log.Info("Worker stopped")
return
}
}
}

func (p *WorkerPool) Submit(workflow *domain.Workflow, definition *domain.WorkflowDefinition) {
p.jobs <- &WorkflowJob{
Workflow:   workflow,
Definition: definition,
}
}

func (p *WorkerPool) Stop() {
p.cancel()
close(p.jobs)
p.wg.Wait()
logger.Logger.Info("Worker pool stopped")
}
EOF

# Create registry.go
cat > internal/engine/registry.go << 'EOF'
package engine

import (
"fmt"
"sync"
"time"

"workflow-orchestrator/internal/domain"
)

type Registry struct {
mu          sync.RWMutex
definitions map[string]*domain.WorkflowDefinition
}

func NewRegistry() *Registry {
return &Registry{
definitions: make(map[string]*domain.WorkflowDefinition),
}
}

func (r *Registry) Register(definition *domain.WorkflowDefinition) {
r.mu.Lock()
defer r.mu.Unlock()
r.definitions[definition.Type] = definition
}

func (r *Registry) Get(workflowType string) (*domain.WorkflowDefinition, error) {
r.mu.RLock()
defer r.mu.RUnlock()

definition, ok := r.definitions[workflowType]
if !ok {
return nil, fmt.Errorf("workflow type not found: %s", workflowType)
}

return definition, nil
}

func (r *Registry) List() []*domain.WorkflowDefinition {
r.mu.RLock()
defer r.mu.RUnlock()

definitions := make([]*domain.WorkflowDefinition, 0, len(r.definitions))
for _, def := range r.definitions {
definitions = append(definitions, def)
}

return definitions
}

func (r *Registry) RegisterWorkflows() {
// E-commerce Order Workflow
r.Register(&domain.WorkflowDefinition{
Type:        "ecommerce_order",
Name:        "E-commerce Order Processing",
Description: "Process customer orders from validation to fulfillment",
MaxRetries:  3,
Timeout:     5 * time.Minute,
Steps: []domain.StepDefinition{
{Name: "Validate Order", Type: "service_call", ServiceURL: "http://localhost:8020", Endpoint: "/orders/validate", Timeout: 5 * time.Second, Retryable: true},
{Name: "Check Inventory", Type: "service_call", ServiceURL: "http://localhost:8020", Endpoint: "/inventory/check", Timeout: 5 * time.Second, Retryable: true},
{Name: "Fraud Screening", Type: "service_call", ServiceURL: "http://localhost:8010", Endpoint: "/fraud/check", Timeout: 10 * time.Second, Retryable: true},
{Name: "Process Payment", Type: "service_call", ServiceURL: "http://localhost:8021", Endpoint: "/payments", Timeout: 30 * time.Second, Retryable: true},
{Name: "Create Order", Type: "service_call", ServiceURL: "http://localhost:8020", Endpoint: "/orders", Timeout: 5 * time.Second, Retryable: false},
{Name: "Update Inventory", Type: "service_call", ServiceURL: "http://localhost:8020", Endpoint: "/inventory/update", Timeout: 5 * time.Second, Retryable: true},
{Name: "Send Confirmation", Type: "notification", ServiceURL: "", Endpoint: "", Timeout: 5 * time.Second, Retryable: true},
},
})

// Banking Transaction Workflow
r.Register(&domain.WorkflowDefinition{
Type:        "banking_transaction",
Name:        "Banking Transaction Processing",
Description: "Process financial transactions with fraud detection",
MaxRetries:  3,
Timeout:     1 * time.Minute,
Steps: []domain.StepDefinition{
{Name: "Validate Transaction", Type: "service_call", ServiceURL: "http://localhost:8005", Endpoint: "/validate", Timeout: 2 * time.Second, Retryable: true},
{Name: "Fraud Detection", Type: "service_call", ServiceURL: "http://localhost:8010", Endpoint: "/fraud/check", Timeout: 5 * time.Second, Retryable: true},
{Name: "Process Transaction", Type: "service_call", ServiceURL: "http://localhost:8005", Endpoint: "/process", Timeout: 10 * time.Second, Retryable: false},
{Name: "Update Balances", Type: "service_call", ServiceURL: "http://localhost:8005", Endpoint: "/sync", Timeout: 5 * time.Second, Retryable: true},
{Name: "Send Notification", Type: "notification", ServiceURL: "", Endpoint: "", Timeout: 5 * time.Second, Retryable: true},
},
})

// Agent Onboarding Workflow
r.Register(&domain.WorkflowDefinition{
Type:        "agent_onboarding",
Name:        "Agent Onboarding",
Description: "Onboard new agents with verification and approval",
MaxRetries:  2,
Timeout:     24 * time.Hour,
Steps: []domain.StepDefinition{
{Name: "Validate Application", Type: "service_call", ServiceURL: "http://localhost:8010", Endpoint: "/agents/validate", Timeout: 5 * time.Second, Retryable: true},
{Name: "Background Check", Type: "service_call", ServiceURL: "http://localhost:8027", Endpoint: "/background-check", Timeout: 30 * time.Second, Retryable: true},
{Name: "KYC Verification", Type: "service_call", ServiceURL: "http://localhost:8021", Endpoint: "/kyc/verify", Timeout: 60 * time.Second, Retryable: true},
{Name: "Credit Assessment", Type: "service_call", ServiceURL: "http://localhost:8027", Endpoint: "/credit/assess", Timeout: 30 * time.Second, Retryable: true},
{Name: "Create Agent Account", Type: "service_call", ServiceURL: "http://localhost:8010", Endpoint: "/agents", Timeout: 5 * time.Second, Retryable: false},
{Name: "Assign Territory", Type: "service_call", ServiceURL: "http://localhost:8010", Endpoint: "/agents/territory", Timeout: 5 * time.Second, Retryable: true},
{Name: "Send Welcome Kit", Type: "notification", ServiceURL: "", Endpoint: "", Timeout: 5 * time.Second, Retryable: true},
},
})
}
EOF

# Create state_manager.go
cat > internal/engine/state_manager.go << 'EOF'
package engine

import (
"context"

"workflow-orchestrator/internal/domain"
"workflow-orchestrator/internal/middleware"
"workflow-orchestrator/internal/repository"
)

type StateManager struct {
repo  repository.WorkflowRepository
redis *middleware.RedisClient
}

func NewStateManager(repo repository.WorkflowRepository, redis *middleware.RedisClient) *StateManager {
return &StateManager{
repo:  repo,
redis: redis,
}
}

func (s *StateManager) SaveState(ctx context.Context, workflow *domain.Workflow) error {
if err := s.repo.Update(ctx, workflow); err != nil {
return err
}

if err := s.redis.CacheWorkflowState(ctx, workflow); err != nil {
return err
}

return nil
}

func (s *StateManager) GetState(ctx context.Context, workflowID string) (*domain.Workflow, error) {
workflow, err := s.redis.GetWorkflowState(ctx, workflowID)
if err == nil && workflow != nil {
return workflow, nil
}

return s.repo.GetByWorkflowID(ctx, workflowID)
}
EOF

echo "All engine files created successfully"
