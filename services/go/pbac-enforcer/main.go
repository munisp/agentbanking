// PBAC Enforcer — Sprint 76
// Policy-Based Access Control engine with Permify integration
// Evaluates fine-grained policies for financial platform operations
package main

import (
	"syscall"
	"os/signal"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"strings"
	"sync"
	"time"
)

const (
	ServiceName    = "pbac-enforcer"
	ServiceVersion = "1.0.0"
	DefaultPort    = "9103"
)

type Policy struct {
	ID          string   `json:"id"`
	Name        string   `json:"name"`
	Description string   `json:"description"`
	Effect      string   `json:"effect"` // allow, deny
	Subjects    []string `json:"subjects"` // roles, user IDs
	Resources   []string `json:"resources"` // resource patterns
	Actions     []string `json:"actions"` // CRUD + custom
	Conditions  []Condition `json:"conditions"`
	Priority    int      `json:"priority"`
	Enabled     bool     `json:"enabled"`
	CreatedAt   int64    `json:"createdAt"`
}

type Condition struct {
	Field    string      `json:"field"`
	Operator string      `json:"operator"` // eq, neq, gt, lt, gte, lte, in, contains
	Value    interface{} `json:"value"`
}

type AccessRequest struct {
	Subject    string            `json:"subject"`
	SubjectRole string           `json:"subjectRole"`
	Resource   string            `json:"resource"`
	Action     string            `json:"action"`
	Context    map[string]interface{} `json:"context"`
}

type AccessDecision struct {
	Allowed    bool   `json:"allowed"`
	PolicyID   string `json:"policyId"`
	PolicyName string `json:"policyName"`
	Reason     string `json:"reason"`
	EvalTimeMs int64  `json:"evalTimeMs"`
}

type PBACEngine struct {
	mu         sync.RWMutex
	policies   []Policy
	auditLog   []AuditEntry
	permifyURL string
}

type AuditEntry struct {
	Timestamp  int64          `json:"timestamp"`
	Request    AccessRequest  `json:"request"`
	Decision   AccessDecision `json:"decision"`
}

func NewPBACEngine() *PBACEngine {
	engine := &PBACEngine{
		auditLog:   make([]AuditEntry, 0),
		permifyURL: getEnv("PERMIFY_URL", "http://localhost:3476"),
	}
	engine.loadDefaultPolicies()
	return engine
}

func (e *PBACEngine) loadDefaultPolicies() {
	e.policies = []Policy{
		{ID: "pol-001", Name: "Admin Full Access", Effect: "allow", Subjects: []string{"admin", "super_admin"}, Resources: []string{"*"}, Actions: []string{"*"}, Priority: 100, Enabled: true, CreatedAt: time.Now().UnixMilli()},
		{ID: "pol-002", Name: "Agent Transaction Limits", Effect: "allow", Subjects: []string{"agent"}, Resources: []string{"transaction:*"}, Actions: []string{"create", "read"}, Conditions: []Condition{{Field: "amount", Operator: "lte", Value: 5000000}}, Priority: 80, Enabled: true, CreatedAt: time.Now().UnixMilli()},
		{ID: "pol-003", Name: "Agent Float Management", Effect: "allow", Subjects: []string{"agent"}, Resources: []string{"float:own"}, Actions: []string{"read", "topup_request"}, Priority: 70, Enabled: true, CreatedAt: time.Now().UnixMilli()},
		{ID: "pol-004", Name: "Supervisor Agent Oversight", Effect: "allow", Subjects: []string{"supervisor"}, Resources: []string{"agent:*", "transaction:*", "float:*"}, Actions: []string{"read", "approve", "reject"}, Priority: 90, Enabled: true, CreatedAt: time.Now().UnixMilli()},
		{ID: "pol-005", Name: "Deny Suspended Agents", Effect: "deny", Subjects: []string{"agent_suspended"}, Resources: []string{"*"}, Actions: []string{"*"}, Priority: 200, Enabled: true, CreatedAt: time.Now().UnixMilli()},
		{ID: "pol-006", Name: "KYC Required for High Value", Effect: "deny", Subjects: []string{"agent"}, Resources: []string{"transaction:*"}, Actions: []string{"create"}, Conditions: []Condition{{Field: "amount", Operator: "gt", Value: 1000000}, {Field: "kyc_level", Operator: "lt", Value: 2}}, Priority: 150, Enabled: true, CreatedAt: time.Now().UnixMilli()},
		{ID: "pol-007", Name: "Geo-Fence Restriction", Effect: "deny", Subjects: []string{"agent"}, Resources: []string{"transaction:*"}, Actions: []string{"create"}, Conditions: []Condition{{Field: "outside_geofence", Operator: "eq", Value: true}}, Priority: 160, Enabled: true, CreatedAt: time.Now().UnixMilli()},
		{ID: "pol-008", Name: "Rate Limit USSD", Effect: "deny", Subjects: []string{"agent"}, Resources: []string{"ussd:session"}, Actions: []string{"create"}, Conditions: []Condition{{Field: "sessions_per_minute", Operator: "gt", Value: 10}}, Priority: 140, Enabled: true, CreatedAt: time.Now().UnixMilli()},
		{ID: "pol-009", Name: "Customer Read Own Data", Effect: "allow", Subjects: []string{"customer"}, Resources: []string{"customer:own", "transaction:own"}, Actions: []string{"read"}, Priority: 60, Enabled: true, CreatedAt: time.Now().UnixMilli()},
		{ID: "pol-010", Name: "Merchant Settlement Access", Effect: "allow", Subjects: []string{"merchant"}, Resources: []string{"settlement:own", "transaction:own"}, Actions: []string{"read", "export"}, Priority: 65, Enabled: true, CreatedAt: time.Now().UnixMilli()},
	}
}

func (e *PBACEngine) Evaluate(req AccessRequest) AccessDecision {
	start := time.Now()
	e.mu.RLock()
	defer e.mu.RUnlock()

	// Sort by priority (higher = evaluated first)
	var matched *Policy
	for i := range e.policies {
		p := &e.policies[i]
		if !p.Enabled { continue }
		if !matchSubject(p.Subjects, req.SubjectRole, req.Subject) { continue }
		if !matchResource(p.Resources, req.Resource) { continue }
		if !matchAction(p.Actions, req.Action) { continue }
		if !evaluateConditions(p.Conditions, req.Context) { continue }
		if matched == nil || p.Priority > matched.Priority {
			matched = p
		}
	}

	decision := AccessDecision{EvalTimeMs: time.Since(start).Milliseconds()}
	if matched == nil {
		decision.Allowed = false
		decision.Reason = "No matching policy found — default deny"
	} else {
		decision.Allowed = matched.Effect == "allow"
		decision.PolicyID = matched.ID
		decision.PolicyName = matched.Name
		decision.Reason = fmt.Sprintf("Matched policy: %s (%s)", matched.Name, matched.Effect)
	}

	e.mu.RUnlock()
	e.mu.Lock()
	e.auditLog = append(e.auditLog, AuditEntry{Timestamp: time.Now().UnixMilli(), Request: req, Decision: decision})
	e.mu.Unlock()
	e.mu.RLock()

	return decision
}

func matchSubject(subjects []string, role, id string) bool {
	for _, s := range subjects {
		if s == "*" || s == role || s == id { return true }
	}
	return false
}

func matchResource(resources []string, resource string) bool {
	for _, r := range resources {
		if r == "*" { return true }
		if r == resource { return true }
		if strings.HasSuffix(r, ":*") && strings.HasPrefix(resource, strings.TrimSuffix(r, "*")) { return true }
	}
	return false
}

func matchAction(actions []string, action string) bool {
	for _, a := range actions {
		if a == "*" || a == action { return true }
	}
	return false
}

func evaluateConditions(conditions []Condition, ctx map[string]interface{}) bool {
	for _, c := range conditions {
		val, ok := ctx[c.Field]
		if !ok { return false }
		if !evaluateCondition(c, val) { return false }
	}
	return true
}

func evaluateCondition(c Condition, val interface{}) bool {
	switch c.Operator {
	case "eq": return fmt.Sprintf("%v", val) == fmt.Sprintf("%v", c.Value)
	case "neq": return fmt.Sprintf("%v", val) != fmt.Sprintf("%v", c.Value)
	case "gt": return toFloat(val) > toFloat(c.Value)
	case "lt": return toFloat(val) < toFloat(c.Value)
	case "gte": return toFloat(val) >= toFloat(c.Value)
	case "lte": return toFloat(val) <= toFloat(c.Value)
	}
	return true
}

func toFloat(v interface{}) float64 {
	switch t := v.(type) {
	case float64: return t
	case int: return float64(t)
	case json.Number: f, _ := t.Float64(); return f
	}
	return 0
}

func main() {
	engine := NewPBACEngine()
	mux := http.NewServeMux()

	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(map[string]interface{}{
			"service": ServiceName, "version": ServiceVersion, "status": "healthy",
			"policies": len(engine.policies), "auditEntries": len(engine.auditLog),
		})
	})

	mux.HandleFunc("/api/pbac/evaluate", func(w http.ResponseWriter, r *http.Request) {
		var req AccessRequest
		json.NewDecoder(r.Body).Decode(&req)
		decision := engine.Evaluate(req)
		json.NewEncoder(w).Encode(decision)
	})

	mux.HandleFunc("/api/pbac/policies", func(w http.ResponseWriter, r *http.Request) {
		engine.mu.RLock()
		defer engine.mu.RUnlock()
		json.NewEncoder(w).Encode(engine.policies)
	})

	mux.HandleFunc("/api/pbac/audit", func(w http.ResponseWriter, r *http.Request) {
		engine.mu.RLock()
		defer engine.mu.RUnlock()
		limit := 100
		start := 0
		if len(engine.auditLog) > limit { start = len(engine.auditLog) - limit }
		json.NewEncoder(w).Encode(engine.auditLog[start:])
	})

	port := getEnv("PORT", DefaultPort)
	log.Printf("[%s] v%s listening on :%s (permify=%s)", ServiceName, ServiceVersion, port, engine.permifyURL)
	log.Fatal(http.ListenAndServe(":"+port, mux))
}

func getEnv(key, def string) string {
	if v := os.Getenv(key); v != "" { return v }
	return def
}

// --- Production: Graceful Shutdown ---
func setupGracefulShutdown(srv *http.Server) {
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		sig := <-quit
		log.Printf("[shutdown] Received signal %s, shutting down gracefully...", sig)
		ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
		defer cancel()
		if err := srv.Shutdown(ctx); err != nil {
			log.Printf("[shutdown] Server forced to shutdown: %v", err)
		}
		log.Println("[shutdown] Server exited")
	}()
}
