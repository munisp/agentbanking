#!/bin/bash

# Create repository interface
cat > internal/repository/repository.go << 'EOF'
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
EOF

# Create PostgreSQL repository implementation
cat > internal/repository/postgres.go << 'EOF'
package repository

import (
"context"
"database/sql"
"encoding/json"
"fmt"

"workflow-orchestrator/internal/domain"
"workflow-orchestrator/pkg/config"

_ "github.com/lib/pq"
)

type PostgresRepository struct {
db *sql.DB
}

func NewPostgresRepository(cfg config.DatabaseConfig) (*PostgresRepository, error) {
dsn := fmt.Sprintf("host=%s port=%d user=%s password=%s dbname=%s sslmode=disable",
cfg.Host, cfg.Port, cfg.User, cfg.Password, cfg.Database)

db, err := sql.Open("postgres", dsn)
if err != nil {
return nil, err
}

db.SetMaxOpenConns(cfg.PoolSize)
db.SetMaxIdleConns(cfg.PoolSize / 2)

if err := db.Ping(); err != nil {
return nil, err
}

return &PostgresRepository{db: db}, nil
}

func (r *PostgresRepository) Create(ctx context.Context, workflow *domain.Workflow) error {
inputData, _ := json.Marshal(workflow.InputData)
outputData, _ := json.Marshal(workflow.OutputData)
contextData, _ := json.Marshal(workflow.Context)

query := `
INSERT INTO workflows (
id, workflow_id, workflow_type, status, tenant_id, user_id, entity_id,
input_data, output_data, context, current_step, total_steps, completed_steps,
failed_steps, started_at, completed_at, failed_at, duration_seconds,
error_message, retry_count, max_retries, created_at, updated_at
) VALUES (
$1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23
)`

_, err := r.db.ExecContext(ctx, query,
workflow.ID, workflow.WorkflowID, workflow.WorkflowType, workflow.Status,
workflow.TenantID, workflow.UserID, workflow.EntityID,
inputData, outputData, contextData,
workflow.CurrentStep, workflow.TotalSteps, workflow.CompletedSteps, workflow.FailedSteps,
workflow.StartedAt, workflow.CompletedAt, workflow.FailedAt, workflow.DurationSeconds,
workflow.ErrorMessage, workflow.RetryCount, workflow.MaxRetries,
workflow.CreatedAt, workflow.UpdatedAt,
)

return err
}

func (r *PostgresRepository) Update(ctx context.Context, workflow *domain.Workflow) error {
inputData, _ := json.Marshal(workflow.InputData)
outputData, _ := json.Marshal(workflow.OutputData)
contextData, _ := json.Marshal(workflow.Context)

query := `
UPDATE workflows SET
status = $1, input_data = $2, output_data = $3, context = $4,
current_step = $5, total_steps = $6, completed_steps = $7, failed_steps = $8,
started_at = $9, completed_at = $10, failed_at = $11, duration_seconds = $12,
error_message = $13, retry_count = $14, updated_at = NOW()
WHERE workflow_id = $15`

_, err := r.db.ExecContext(ctx, query,
workflow.Status, inputData, outputData, contextData,
workflow.CurrentStep, workflow.TotalSteps, workflow.CompletedSteps, workflow.FailedSteps,
workflow.StartedAt, workflow.CompletedAt, workflow.FailedAt, workflow.DurationSeconds,
workflow.ErrorMessage, workflow.RetryCount, workflow.WorkflowID,
)

return err
}

func (r *PostgresRepository) GetByID(ctx context.Context, id string) (*domain.Workflow, error) {
query := `SELECT * FROM workflows WHERE id = $1`
return r.scanWorkflow(r.db.QueryRowContext(ctx, query, id))
}

func (r *PostgresRepository) GetByWorkflowID(ctx context.Context, workflowID string) (*domain.Workflow, error) {
query := `SELECT * FROM workflows WHERE workflow_id = $1`
return r.scanWorkflow(r.db.QueryRowContext(ctx, query, workflowID))
}

func (r *PostgresRepository) List(ctx context.Context, req *domain.ListWorkflowsRequest) ([]*domain.Workflow, error) {
query := `SELECT * FROM workflows WHERE 1=1`
args := []interface{}{}
argCount := 1

if req.Status != "" {
query += fmt.Sprintf(" AND status = $%d", argCount)
args = append(args, req.Status)
argCount++
}

if req.WorkflowType != "" {
query += fmt.Sprintf(" AND workflow_type = $%d", argCount)
args = append(args, req.WorkflowType)
argCount++
}

query += " ORDER BY created_at DESC"

if req.Limit > 0 {
query += fmt.Sprintf(" LIMIT $%d", argCount)
args = append(args, req.Limit)
argCount++
}

if req.Offset > 0 {
query += fmt.Sprintf(" OFFSET $%d", argCount)
args = append(args, req.Offset)
}

rows, err := r.db.QueryContext(ctx, query, args...)
if err != nil {
return nil, err
}
defer rows.Close()

var workflows []*domain.Workflow
for rows.Next() {
workflow, err := r.scanWorkflowFromRows(rows)
if err != nil {
return nil, err
}
workflows = append(workflows, workflow)
}

return workflows, nil
}

func (r *PostgresRepository) scanWorkflow(row *sql.Row) (*domain.Workflow, error) {
var workflow domain.Workflow
var inputData, outputData, contextData []byte

err := row.Scan(
&workflow.ID, &workflow.WorkflowID, &workflow.WorkflowType, &workflow.Status,
&workflow.TenantID, &workflow.UserID, &workflow.EntityID,
&inputData, &outputData, &contextData,
&workflow.CurrentStep, &workflow.TotalSteps, &workflow.CompletedSteps, &workflow.FailedSteps,
&workflow.StartedAt, &workflow.CompletedAt, &workflow.FailedAt, &workflow.DurationSeconds,
&workflow.ErrorMessage, &workflow.RetryCount, &workflow.MaxRetries,
&workflow.CreatedAt, &workflow.UpdatedAt,
)

if err != nil {
return nil, err
}

json.Unmarshal(inputData, &workflow.InputData)
json.Unmarshal(outputData, &workflow.OutputData)
json.Unmarshal(contextData, &workflow.Context)

return &workflow, nil
}

func (r *PostgresRepository) scanWorkflowFromRows(rows *sql.Rows) (*domain.Workflow, error) {
var workflow domain.Workflow
var inputData, outputData, contextData []byte

err := rows.Scan(
&workflow.ID, &workflow.WorkflowID, &workflow.WorkflowType, &workflow.Status,
&workflow.TenantID, &workflow.UserID, &workflow.EntityID,
&inputData, &outputData, &contextData,
&workflow.CurrentStep, &workflow.TotalSteps, &workflow.CompletedSteps, &workflow.FailedSteps,
&workflow.StartedAt, &workflow.CompletedAt, &workflow.FailedAt, &workflow.DurationSeconds,
&workflow.ErrorMessage, &workflow.RetryCount, &workflow.MaxRetries,
&workflow.CreatedAt, &workflow.UpdatedAt,
)

if err != nil {
return nil, err
}

json.Unmarshal(inputData, &workflow.InputData)
json.Unmarshal(outputData, &workflow.OutputData)
json.Unmarshal(contextData, &workflow.Context)

return &workflow, nil
}

func (r *PostgresRepository) Close() error {
return r.db.Close()
}
EOF

# Create API handlers
cat > internal/api/handlers.go << 'EOF'
package api

import (
"encoding/json"
"net/http"
"time"

"workflow-orchestrator/internal/domain"
"workflow-orchestrator/internal/engine"
"workflow-orchestrator/internal/repository"
"workflow-orchestrator/pkg/logger"

"github.com/google/uuid"
"github.com/gorilla/mux"
)

type Handlers struct {
executor *engine.Executor
registry *engine.Registry
repo     repository.WorkflowRepository
}

func NewHandlers(
executor *engine.Executor,
registry *engine.Registry,
repo repository.WorkflowRepository,
) *Handlers {
return &Handlers{
executor: executor,
registry: registry,
repo:     repo,
}
}

func (h *Handlers) CreateWorkflow(w http.ResponseWriter, r *http.Request) {
var req domain.CreateWorkflowRequest
if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
respondError(w, http.StatusBadRequest, "Invalid request body")
return
}

definition, err := h.registry.Get(req.WorkflowType)
if err != nil {
respondError(w, http.StatusBadRequest, err.Error())
return
}

workflow := &domain.Workflow{
ID:           uuid.New(),
WorkflowID:   generateWorkflowID(req.WorkflowType),
WorkflowType: req.WorkflowType,
Status:       domain.StatusPending,
TenantID:     req.TenantID,
UserID:       req.UserID,
EntityID:     req.EntityID,
InputData:    req.InputData,
OutputData:   make(map[string]interface{}),
Context:      make(map[string]interface{}),
MaxRetries:   definition.MaxRetries,
CreatedAt:    time.Now(),
UpdatedAt:    time.Now(),
}

if err := h.repo.Create(r.Context(), workflow); err != nil {
logger.Logger.Error("Failed to create workflow", logger.Error(err))
respondError(w, http.StatusInternalServerError, "Failed to create workflow")
return
}

h.executor.ExecuteAsync(workflow, definition)

respondJSON(w, http.StatusCreated, domain.WorkflowResponse{
Workflow: workflow,
Message:  "Workflow created and started",
})
}

func (h *Handlers) GetWorkflow(w http.ResponseWriter, r *http.Request) {
vars := mux.Vars(r)
workflowID := vars["workflow_id"]

workflow, err := h.repo.GetByWorkflowID(r.Context(), workflowID)
if err != nil {
respondError(w, http.StatusNotFound, "Workflow not found")
return
}

respondJSON(w, http.StatusOK, domain.WorkflowResponse{Workflow: workflow})
}

func (h *Handlers) ListWorkflows(w http.ResponseWriter, r *http.Request) {
req := &domain.ListWorkflowsRequest{
Status:       domain.WorkflowStatus(r.URL.Query().Get("status")),
WorkflowType: r.URL.Query().Get("workflow_type"),
Limit:        50,
Offset:       0,
}

workflows, err := h.repo.List(r.Context(), req)
if err != nil {
logger.Logger.Error("Failed to list workflows", logger.Error(err))
respondError(w, http.StatusInternalServerError, "Failed to list workflows")
return
}

respondJSON(w, http.StatusOK, map[string]interface{}{
"workflows": workflows,
"count":     len(workflows),
})
}

func (h *Handlers) CancelWorkflow(w http.ResponseWriter, r *http.Request) {
vars := mux.Vars(r)
workflowID := vars["workflow_id"]

if err := h.executor.Cancel(workflowID); err != nil {
respondError(w, http.StatusBadRequest, err.Error())
return
}

respondJSON(w, http.StatusOK, map[string]string{
"message": "Workflow cancelled",
})
}

func (h *Handlers) ListWorkflowTypes(w http.ResponseWriter, r *http.Request) {
definitions := h.registry.List()

respondJSON(w, http.StatusOK, map[string]interface{}{
"workflow_types": definitions,
"count":          len(definitions),
})
}

func (h *Handlers) Health(w http.ResponseWriter, r *http.Request) {
respondJSON(w, http.StatusOK, map[string]string{
"status": "healthy",
"time":   time.Now().Format(time.RFC3339),
})
}

func generateWorkflowID(workflowType string) string {
return fmt.Sprintf("WF-%s-%d", workflowType, time.Now().UnixNano())
}

func respondJSON(w http.ResponseWriter, status int, data interface{}) {
w.Header().Set("Content-Type", "application/json")
w.WriteStatus(status)
json.NewEncoder(w).Encode(data)
}

func respondError(w http.ResponseWriter, status int, message string) {
respondJSON(w, status, map[string]string{"error": message})
}
EOF

# Create router
cat > internal/api/routes.go << 'EOF'
package api

import (
"github.com/gorilla/mux"
)

func NewRouter(handlers *Handlers) *mux.Router {
router := mux.NewRouter()

router.HandleFunc("/health", handlers.Health).Methods("GET")
router.HandleFunc("/api/workflows", handlers.CreateWorkflow).Methods("POST")
router.HandleFunc("/api/workflows", handlers.ListWorkflows).Methods("GET")
router.HandleFunc("/api/workflows/{workflow_id}", handlers.GetWorkflow).Methods("GET")
router.HandleFunc("/api/workflows/{workflow_id}/cancel", handlers.CancelWorkflow).Methods("POST")
router.HandleFunc("/api/workflow-types", handlers.ListWorkflowTypes).Methods("GET")

return router
}
EOF

echo "Repository and API files created successfully"
