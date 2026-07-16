package api

import (
"encoding/json"
"fmt"
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
w.WriteHeader(status)
json.NewEncoder(w).Encode(data)
}

func respondError(w http.ResponseWriter, status int, message string) {
respondJSON(w, status, map[string]string{"error": message})
}
