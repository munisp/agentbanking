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
