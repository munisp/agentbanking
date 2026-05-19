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
