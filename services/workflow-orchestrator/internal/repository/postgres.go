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
