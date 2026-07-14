package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"sync"
	"syscall"
	"time"

	"github.com/gorilla/mux"
)

const (
	serviceName    = "pbac-engine"
	serviceVersion = "1.0.0"
)

// ── Policy Models ────────────────────────────────────────────────────

// Policy defines a PBAC policy with conditions, actions, and effects
type Policy struct {
	ID          string            `json:"id"`
	Name        string            `json:"name"`
	Description string            `json:"description"`
	Effect      string            `json:"effect"` // "allow" or "deny"
	Priority    int               `json:"priority"`
	Subjects    []SubjectMatcher  `json:"subjects"`
	Resources   []ResourceMatcher `json:"resources"`
	Actions     []string          `json:"actions"`
	Conditions  []Condition       `json:"conditions"`
	Enabled     bool              `json:"enabled"`
	CreatedAt   time.Time         `json:"created_at"`
	UpdatedAt   time.Time         `json:"updated_at"`
	TenantID    string            `json:"tenant_id"`
}

// SubjectMatcher matches against user/role/group attributes
type SubjectMatcher struct {
	Type  string `json:"type"`  // "role", "user", "group", "attribute"
	Value string `json:"value"` // e.g. "admin", "user:123", "group:finance"
	Op    string `json:"op"`    // "eq", "in", "not_in", "regex"
}

// ResourceMatcher matches against resource identifiers
type ResourceMatcher struct {
	Type  string `json:"type"`  // "endpoint", "entity", "field"
	Value string `json:"value"` // e.g. "/api/transactions/*", "transaction:*"
	Op    string `json:"op"`    // "eq", "glob", "regex", "prefix"
}

// Condition represents a contextual condition for policy evaluation
type Condition struct {
	Attribute string      `json:"attribute"` // e.g. "time", "ip", "amount", "location"
	Operator  string      `json:"operator"`  // "eq", "ne", "gt", "lt", "gte", "lte", "in", "between", "regex"
	Value     interface{} `json:"value"`
}

// AuthzRequest is the authorization check request
type AuthzRequest struct {
	Subject  SubjectContext  `json:"subject"`
	Resource ResourceTarget  `json:"resource"`
	Action   string          `json:"action"`
	Context  RequestContext   `json:"context"`
}

// SubjectContext describes who is making the request
type SubjectContext struct {
	UserID    string            `json:"user_id"`
	Roles     []string          `json:"roles"`
	Groups    []string          `json:"groups"`
	Attrs     map[string]string `json:"attributes"`
	TenantID  string            `json:"tenant_id"`
	KYCLevel  int               `json:"kyc_level"`
	AgentTier string            `json:"agent_tier"`
}

// ResourceTarget describes what is being accessed
type ResourceTarget struct {
	Type     string `json:"type"`      // "endpoint", "entity", "report"
	ID       string `json:"id"`        // resource identifier
	TenantID string `json:"tenant_id"` // resource tenant
}

// RequestContext provides environmental context
type RequestContext struct {
	IP            string  `json:"ip"`
	UserAgent     string  `json:"user_agent"`
	Timestamp     int64   `json:"timestamp"`
	Amount        float64 `json:"amount"`
	Currency      string  `json:"currency"`
	Channel       string  `json:"channel"`       // "web", "mobile", "api", "ussd"
	GeoCountry    string  `json:"geo_country"`
	GeoRegion     string  `json:"geo_region"`
	DeviceID      string  `json:"device_id"`
	SessionAge    int64   `json:"session_age"`    // seconds
	MFAVerified   bool    `json:"mfa_verified"`
	RiskScore     float64 `json:"risk_score"`
}

// AuthzResponse is the authorization decision
type AuthzResponse struct {
	Allowed       bool     `json:"allowed"`
	Effect        string   `json:"effect"`
	MatchedPolicy string   `json:"matched_policy"`
	Reason        string   `json:"reason"`
	Obligations   []string `json:"obligations"` // actions that must be taken (e.g. "log", "notify", "mfa_required")
	EvalTimeMs    float64  `json:"eval_time_ms"`
}

// ── PBAC Engine ──────────────────────────────────────────────────────

type PBACEngine struct {
	mu             sync.RWMutex
	policies       map[string]*Policy
	tenantPolicies map[string][]string // tenantID -> policyIDs
	grants         map[string]*Grant
	delegations    map[string]*Delegation
	auditLog       []AuditEntry
	stats          EngineStats
}

type AuditEntry struct {
	Timestamp     time.Time `json:"timestamp"`
	SubjectID     string    `json:"subject_id"`
	Resource      string    `json:"resource"`
	Action        string    `json:"action"`
	Decision      string    `json:"decision"`
	MatchedPolicy string    `json:"matched_policy"`
	IP            string    `json:"ip"`
}

type EngineStats struct {
	TotalEvaluations int64 `json:"total_evaluations"`
	AllowCount       int64 `json:"allow_count"`
	DenyCount        int64 `json:"deny_count"`
	AvgEvalTimeMs    float64 `json:"avg_eval_time_ms"`
}

// Grant represents a temporal access grant
type Grant struct {
	ID           string      `json:"id"`
	TenantID     string      `json:"tenant_id"`
	SubjectID    string      `json:"subject_id"`
	SubjectType  string      `json:"subject_type"`
	Permission   string      `json:"permission"`
	ResourceType string      `json:"resource_type"`
	ResourceID   string      `json:"resource_id"`
	GrantedBy    string      `json:"granted_by"`
	GrantedAt    time.Time   `json:"granted_at"`
	ExpiresAt    time.Time   `json:"expires_at"`
	Reason       string      `json:"reason"`
	Status       string      `json:"status"`
	UsageCount   int         `json:"usage_count"`
	MaxUsage     *int        `json:"max_usage,omitempty"`
	Conditions   interface{} `json:"conditions,omitempty"`
	RevokedAt    *time.Time  `json:"revoked_at,omitempty"`
	RevokedBy    string      `json:"revoked_by,omitempty"`
}

// Delegation represents a permission delegation between principals
type Delegation struct {
	ID           string     `json:"id"`
	TenantID     string     `json:"tenant_id"`
	DelegatorID  string     `json:"delegator_id"`
	DelegateID   string     `json:"delegate_id"`
	Permission   string     `json:"permission"`
	ResourceType string     `json:"resource_type"`
	ResourceID   string     `json:"resource_id"`
	CreatedAt    time.Time  `json:"created_at"`
	ExpiresAt    *time.Time `json:"expires_at,omitempty"`
	Revoked      bool       `json:"revoked"`
	RevokedAt    *time.Time `json:"revoked_at,omitempty"`
}

func NewPBACEngine() *PBACEngine {
	engine := &PBACEngine{
		policies:       make(map[string]*Policy),
		tenantPolicies: make(map[string][]string),
		grants:         make(map[string]*Grant),
		delegations:    make(map[string]*Delegation),
		auditLog:       make([]AuditEntry, 0, 10000),
	}
	engine.loadDefaultPolicies()
	return engine
}

func (e *PBACEngine) loadDefaultPolicies() {
	defaults := []*Policy{
		{
			ID: "default-admin-full-access", Name: "Admin Full Access",
			Description: "Admins have full access to all resources",
			Effect: "allow", Priority: 1000, Enabled: true,
			Subjects:  []SubjectMatcher{{Type: "role", Value: "admin", Op: "eq"}},
			Resources: []ResourceMatcher{{Type: "endpoint", Value: "*", Op: "glob"}},
			Actions:   []string{"*"},
			CreatedAt: time.Now(), UpdatedAt: time.Now(),
		},
		{
			ID: "default-deny-high-value-no-mfa", Name: "Deny High-Value Without MFA",
			Description: "Deny transactions above 1M NGN without MFA verification",
			Effect: "deny", Priority: 900, Enabled: true,
			Subjects:  []SubjectMatcher{{Type: "role", Value: "*", Op: "glob"}},
			Resources: []ResourceMatcher{{Type: "endpoint", Value: "/api/transactions/create", Op: "eq"}},
			Actions:   []string{"create"},
			Conditions: []Condition{
				{Attribute: "amount", Operator: "gt", Value: 1000000.0},
				{Attribute: "mfa_verified", Operator: "eq", Value: false},
			},
			CreatedAt: time.Now(), UpdatedAt: time.Now(),
		},
		{
			ID: "default-deny-outside-hours", Name: "Deny Admin Actions Outside Business Hours",
			Description: "Deny admin bulk operations outside 6AM-10PM WAT",
			Effect: "deny", Priority: 800, Enabled: true,
			Subjects:  []SubjectMatcher{{Type: "role", Value: "admin", Op: "eq"}},
			Resources: []ResourceMatcher{{Type: "endpoint", Value: "/api/*/bulk*", Op: "glob"}},
			Actions:   []string{"bulk_delete", "bulk_update", "bulk_export"},
			Conditions: []Condition{
				{Attribute: "time_hour", Operator: "not_between", Value: []interface{}{6.0, 22.0}},
			},
			CreatedAt: time.Now(), UpdatedAt: time.Now(),
		},
		{
			ID: "default-kyc-level-restriction", Name: "KYC Level Transaction Limits",
			Description: "Restrict transaction amounts based on KYC level",
			Effect: "deny", Priority: 850, Enabled: true,
			Subjects:  []SubjectMatcher{{Type: "attribute", Value: "kyc_level:1", Op: "eq"}},
			Resources: []ResourceMatcher{{Type: "endpoint", Value: "/api/transactions/*", Op: "glob"}},
			Actions:   []string{"create"},
			Conditions: []Condition{
				{Attribute: "amount", Operator: "gt", Value: 50000.0},
			},
			CreatedAt: time.Now(), UpdatedAt: time.Now(),
		},
		{
			ID: "default-geo-restriction", Name: "Geo-Restricted Operations",
			Description: "Block operations from sanctioned countries",
			Effect: "deny", Priority: 950, Enabled: true,
			Subjects:  []SubjectMatcher{{Type: "role", Value: "*", Op: "glob"}},
			Resources: []ResourceMatcher{{Type: "endpoint", Value: "*", Op: "glob"}},
			Actions:   []string{"*"},
			Conditions: []Condition{
				{Attribute: "geo_country", Operator: "in", Value: []interface{}{"KP", "IR", "SY", "CU", "SD"}},
			},
			CreatedAt: time.Now(), UpdatedAt: time.Now(),
		},
		{
			ID: "default-agent-territory", Name: "Agent Territory Restriction",
			Description: "Agents can only operate within their assigned territory",
			Effect: "deny", Priority: 700, Enabled: true,
			Subjects:  []SubjectMatcher{{Type: "role", Value: "agent", Op: "eq"}},
			Resources: []ResourceMatcher{{Type: "endpoint", Value: "/api/transactions/*", Op: "glob"}},
			Actions:   []string{"create", "approve"},
			Conditions: []Condition{
				{Attribute: "territory_mismatch", Operator: "eq", Value: true},
			},
			CreatedAt: time.Now(), UpdatedAt: time.Now(),
		},
		{
			ID: "default-session-age-limit", Name: "Session Age Limit for Sensitive Ops",
			Description: "Require re-authentication for sensitive operations after 30 min",
			Effect: "deny", Priority: 750, Enabled: true,
			Subjects:  []SubjectMatcher{{Type: "role", Value: "*", Op: "glob"}},
			Resources: []ResourceMatcher{{Type: "endpoint", Value: "/api/settings/*", Op: "glob"}, {Type: "endpoint", Value: "/api/users/*/role", Op: "glob"}},
			Actions:   []string{"update", "delete"},
			Conditions: []Condition{
				{Attribute: "session_age", Operator: "gt", Value: 1800.0},
			},
			CreatedAt: time.Now(), UpdatedAt: time.Now(),
		},
		{
			ID: "default-risk-score-block", Name: "High Risk Score Block",
			Description: "Block requests with risk score above 0.85",
			Effect: "deny", Priority: 920, Enabled: true,
			Subjects:  []SubjectMatcher{{Type: "role", Value: "*", Op: "glob"}},
			Resources: []ResourceMatcher{{Type: "endpoint", Value: "/api/transactions/*", Op: "glob"}},
			Actions:   []string{"create", "approve"},
			Conditions: []Condition{
				{Attribute: "risk_score", Operator: "gt", Value: 0.85},
			},
			CreatedAt: time.Now(), UpdatedAt: time.Now(),
		},
		{
			ID: "default-ussd-amount-cap", Name: "USSD Channel Amount Cap",
			Description: "Cap USSD transactions at 100K NGN for security",
			Effect: "deny", Priority: 800, Enabled: true,
			Subjects:  []SubjectMatcher{{Type: "role", Value: "*", Op: "glob"}},
			Resources: []ResourceMatcher{{Type: "endpoint", Value: "/api/transactions/create", Op: "eq"}},
			Actions:   []string{"create"},
			Conditions: []Condition{
				{Attribute: "channel", Operator: "eq", Value: "ussd"},
				{Attribute: "amount", Operator: "gt", Value: 100000.0},
			},
			CreatedAt: time.Now(), UpdatedAt: time.Now(),
		},
		{
			ID: "default-read-only-user", Name: "Read-Only User Access",
			Description: "Users with viewer role can only read",
			Effect: "deny", Priority: 600, Enabled: true,
			Subjects:  []SubjectMatcher{{Type: "role", Value: "viewer", Op: "eq"}},
			Resources: []ResourceMatcher{{Type: "endpoint", Value: "*", Op: "glob"}},
			Actions:   []string{"create", "update", "delete", "approve", "reject"},
			CreatedAt: time.Now(), UpdatedAt: time.Now(),
		},
	}

	for _, p := range defaults {
		e.policies[p.ID] = p
	}
}

// Evaluate checks authorization for a request against all applicable policies
func (e *PBACEngine) Evaluate(req AuthzRequest) AuthzResponse {
	start := time.Now()
	e.mu.RLock()
	defer e.mu.RUnlock()

	var matchedDeny *Policy
	var matchedAllow *Policy
	obligations := []string{}

	for _, policy := range e.policies {
		if !policy.Enabled {
			continue
		}

		// Check tenant isolation
		if policy.TenantID != "" && policy.TenantID != req.Subject.TenantID {
			continue
		}

		// Match subjects
		if !e.matchSubjects(policy.Subjects, req.Subject) {
			continue
		}

		// Match resources
		if !e.matchResources(policy.Resources, req.Resource) {
			continue
		}

		// Match actions
		if !e.matchActions(policy.Actions, req.Action) {
			continue
		}

		// Evaluate conditions
		if !e.evaluateConditions(policy.Conditions, req.Context, req.Subject) {
			continue
		}

		// Policy matched — apply effect
		switch policy.Effect {
		case "deny":
			if matchedDeny == nil || policy.Priority > matchedDeny.Priority {
				matchedDeny = policy
			}
		case "allow":
			if matchedAllow == nil || policy.Priority > matchedAllow.Priority {
				matchedAllow = policy
			}
		}
	}

	evalTime := float64(time.Since(start).Microseconds()) / 1000.0

	// Deny takes precedence over allow at same priority
	if matchedDeny != nil && (matchedAllow == nil || matchedDeny.Priority >= matchedAllow.Priority) {
		e.recordAudit(req, "deny", matchedDeny.ID)
		e.stats.TotalEvaluations++
		e.stats.DenyCount++

		// Add obligations for denied requests
		obligations = append(obligations, "log_security_event")
		if matchedDeny.ID == "default-deny-high-value-no-mfa" {
			obligations = append(obligations, "mfa_required")
		}

		return AuthzResponse{
			Allowed:       false,
			Effect:        "deny",
			MatchedPolicy: matchedDeny.ID,
			Reason:        matchedDeny.Description,
			Obligations:   obligations,
			EvalTimeMs:    evalTime,
		}
	}

	if matchedAllow != nil {
		e.recordAudit(req, "allow", matchedAllow.ID)
		e.stats.TotalEvaluations++
		e.stats.AllowCount++
		return AuthzResponse{
			Allowed:       true,
			Effect:        "allow",
			MatchedPolicy: matchedAllow.ID,
			Reason:        matchedAllow.Description,
			Obligations:   obligations,
			EvalTimeMs:    evalTime,
		}
	}

	// Default deny (no matching policy)
	e.recordAudit(req, "deny", "default-deny")
	e.stats.TotalEvaluations++
	e.stats.DenyCount++
	return AuthzResponse{
		Allowed:       false,
		Effect:        "deny",
		MatchedPolicy: "default-deny",
		Reason:        "No matching allow policy found (default deny)",
		Obligations:   []string{"log_security_event"},
		EvalTimeMs:    evalTime,
	}
}

func (e *PBACEngine) matchSubjects(matchers []SubjectMatcher, subject SubjectContext) bool {
	if len(matchers) == 0 {
		return true
	}
	for _, m := range matchers {
		switch m.Type {
		case "role":
			if m.Value == "*" {
				return true
			}
			for _, role := range subject.Roles {
				if matchString(m.Op, role, m.Value) {
					return true
				}
			}
		case "user":
			if matchString(m.Op, subject.UserID, m.Value) {
				return true
			}
		case "group":
			for _, group := range subject.Groups {
				if matchString(m.Op, group, m.Value) {
					return true
				}
			}
		case "attribute":
			// Format: "key:value"
			parts := strings.SplitN(m.Value, ":", 2)
			if len(parts) == 2 {
				switch parts[0] {
				case "kyc_level":
					if fmt.Sprintf("%d", subject.KYCLevel) == parts[1] {
						return true
					}
				case "agent_tier":
					if subject.AgentTier == parts[1] {
						return true
					}
				default:
					if val, ok := subject.Attrs[parts[0]]; ok && val == parts[1] {
						return true
					}
				}
			}
		}
	}
	return false
}

func (e *PBACEngine) matchResources(matchers []ResourceMatcher, resource ResourceTarget) bool {
	if len(matchers) == 0 {
		return true
	}
	for _, m := range matchers {
		target := resource.ID
		if m.Type == "endpoint" {
			target = resource.ID
		}
		if matchString(m.Op, target, m.Value) {
			return true
		}
	}
	return false
}

func (e *PBACEngine) matchActions(policyActions []string, requestAction string) bool {
	for _, a := range policyActions {
		if a == "*" || a == requestAction {
			return true
		}
	}
	return false
}

func (e *PBACEngine) evaluateConditions(conditions []Condition, ctx RequestContext, subject SubjectContext) bool {
	if len(conditions) == 0 {
		return true
	}
	// ALL conditions must be true (AND logic)
	for _, cond := range conditions {
		if !e.evaluateCondition(cond, ctx, subject) {
			return false
		}
	}
	return true
}

func (e *PBACEngine) evaluateCondition(cond Condition, ctx RequestContext, subject SubjectContext) bool {
	var actual interface{}

	switch cond.Attribute {
	case "amount":
		actual = ctx.Amount
	case "currency":
		actual = ctx.Currency
	case "channel":
		actual = ctx.Channel
	case "geo_country":
		actual = ctx.GeoCountry
	case "geo_region":
		actual = ctx.GeoRegion
	case "mfa_verified":
		actual = ctx.MFAVerified
	case "risk_score":
		actual = ctx.RiskScore
	case "session_age":
		actual = float64(ctx.SessionAge)
	case "time_hour":
		actual = float64(time.Now().Hour())
	case "ip":
		actual = ctx.IP
	case "kyc_level":
		actual = float64(subject.KYCLevel)
	case "territory_mismatch":
		actual = false // default; would be computed from geo data
	default:
		return false
	}

	return compareValues(cond.Operator, actual, cond.Value)
}

// Supported operators: eq/equals, ne, gt/greater_than, lt/less_than, gte, lte, in, not_in, between, not_between, contains
func compareValues(op string, actual, expected interface{}) bool {
	switch op {
	case "eq", "equals":
		return fmt.Sprintf("%v", actual) == fmt.Sprintf("%v", expected)
	case "ne":
		return fmt.Sprintf("%v", actual) != fmt.Sprintf("%v", expected)
	case "gt", "greater_than":
		a, e := toFloat(actual), toFloat(expected)
		return a > e
	case "lt", "less_than":
		a, e := toFloat(actual), toFloat(expected)
		return a < e
	case "gte":
		a, e := toFloat(actual), toFloat(expected)
		return a >= e
	case "lte":
		a, e := toFloat(actual), toFloat(expected)
		return a <= e
	case "in":
		if arr, ok := expected.([]interface{}); ok {
			actualStr := fmt.Sprintf("%v", actual)
			for _, v := range arr {
				if fmt.Sprintf("%v", v) == actualStr {
					return true
				}
			}
		}
		return false
	case "not_in":
		if arr, ok := expected.([]interface{}); ok {
			actualStr := fmt.Sprintf("%v", actual)
			for _, v := range arr {
				if fmt.Sprintf("%v", v) == actualStr {
					return false
				}
			}
		}
		return true
	case "between":
		if arr, ok := expected.([]interface{}); ok && len(arr) == 2 {
			a := toFloat(actual)
			return a >= toFloat(arr[0]) && a <= toFloat(arr[1])
		}
		return false
	case "not_between":
		if arr, ok := expected.([]interface{}); ok && len(arr) == 2 {
			a := toFloat(actual)
			return a < toFloat(arr[0]) || a > toFloat(arr[1])
		}
		return false
	case "contains":
		actualStr := fmt.Sprintf("%v", actual)
		expectedStr := fmt.Sprintf("%v", expected)
		return strings.Contains(actualStr, expectedStr)
	}
	return false
}

func toFloat(v interface{}) float64 {
	switch val := v.(type) {
	case float64:
		return val
	case float32:
		return float64(val)
	case int:
		return float64(val)
	case int64:
		return float64(val)
	case bool:
		if val {
			return 1.0
		}
		return 0.0
	default:
		return 0.0
	}
}

func matchString(op, actual, pattern string) bool {
	switch op {
	case "eq":
		return actual == pattern
	case "glob":
		return globMatch(pattern, actual)
	case "prefix":
		return strings.HasPrefix(actual, pattern)
	default:
		return actual == pattern
	}
}

func globMatch(pattern, s string) bool {
	if pattern == "*" {
		return true
	}
	if strings.HasSuffix(pattern, "*") {
		prefix := strings.TrimSuffix(pattern, "*")
		return strings.HasPrefix(s, prefix)
	}
	if strings.HasPrefix(pattern, "*") {
		suffix := strings.TrimPrefix(pattern, "*")
		return strings.HasSuffix(s, suffix)
	}
	return pattern == s
}

func (e *PBACEngine) recordAudit(req AuthzRequest, decision, policyID string) {
	entry := AuditEntry{
		Timestamp:     time.Now(),
		SubjectID:     req.Subject.UserID,
		Resource:      req.Resource.ID,
		Action:        req.Action,
		Decision:      decision,
		MatchedPolicy: policyID,
		IP:            req.Context.IP,
	}
	if len(e.auditLog) >= 10000 {
		e.auditLog = e.auditLog[1000:]
	}
	e.auditLog = append(e.auditLog, entry)
}

// ── HTTP Handlers ────────────────────────────────────────────────────

func (e *PBACEngine) HandleAuthorize(w http.ResponseWriter, r *http.Request) {
	var req AuthzRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, `{"error":"invalid request body"}`, http.StatusBadRequest)
		return
	}
	resp := e.Evaluate(req)
	w.Header().Set("Content-Type", "application/json")
	if !resp.Allowed {
		w.WriteHeader(http.StatusForbidden)
	}
	json.NewEncoder(w).Encode(resp)
}

func (e *PBACEngine) HandleCreatePolicy(w http.ResponseWriter, r *http.Request) {
	var policy Policy
	if err := json.NewDecoder(r.Body).Decode(&policy); err != nil {
		http.Error(w, `{"error":"invalid policy"}`, http.StatusBadRequest)
		return
	}
	if policy.ID == "" {
		policy.ID = fmt.Sprintf("policy-%d", time.Now().UnixNano())
	}
	policy.CreatedAt = time.Now()
	policy.UpdatedAt = time.Now()

	e.mu.Lock()
	e.policies[policy.ID] = &policy
	if policy.TenantID != "" {
		e.tenantPolicies[policy.TenantID] = append(e.tenantPolicies[policy.TenantID], policy.ID)
	}
	e.mu.Unlock()

	slog.Info("Policy created", "id", policy.ID, "name", policy.Name)
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(map[string]interface{}{"created": true, "id": policy.ID})
}

func (e *PBACEngine) HandleUpdatePolicy(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	policyID := vars["id"]

	var updates Policy
	if err := json.NewDecoder(r.Body).Decode(&updates); err != nil {
		http.Error(w, `{"error":"invalid policy"}`, http.StatusBadRequest)
		return
	}

	e.mu.Lock()
	defer e.mu.Unlock()

	existing, ok := e.policies[policyID]
	if !ok {
		http.Error(w, `{"error":"policy not found"}`, http.StatusNotFound)
		return
	}

	if updates.Name != "" {
		existing.Name = updates.Name
	}
	if updates.Description != "" {
		existing.Description = updates.Description
	}
	if updates.Effect != "" {
		existing.Effect = updates.Effect
	}
	if updates.Priority != 0 {
		existing.Priority = updates.Priority
	}
	if len(updates.Subjects) > 0 {
		existing.Subjects = updates.Subjects
	}
	if len(updates.Resources) > 0 {
		existing.Resources = updates.Resources
	}
	if len(updates.Actions) > 0 {
		existing.Actions = updates.Actions
	}
	if len(updates.Conditions) > 0 {
		existing.Conditions = updates.Conditions
	}
	existing.Enabled = updates.Enabled
	existing.UpdatedAt = time.Now()

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{"updated": true, "id": policyID})
}

func (e *PBACEngine) HandleDeletePolicy(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	policyID := vars["id"]

	e.mu.Lock()
	defer e.mu.Unlock()

	if _, ok := e.policies[policyID]; !ok {
		http.Error(w, `{"error":"policy not found"}`, http.StatusNotFound)
		return
	}
	delete(e.policies, policyID)

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{"deleted": true, "id": policyID})
}

func (e *PBACEngine) HandleListPolicies(w http.ResponseWriter, r *http.Request) {
	e.mu.RLock()
	defer e.mu.RUnlock()

	policies := make([]*Policy, 0, len(e.policies))
	tenantID := r.URL.Query().Get("tenant_id")

	for _, p := range e.policies {
		if tenantID != "" && p.TenantID != "" && p.TenantID != tenantID {
			continue
		}
		policies = append(policies, p)
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"policies": policies,
		"total":    len(policies),
	})
}

func (e *PBACEngine) HandleGetAuditLog(w http.ResponseWriter, r *http.Request) {
	e.mu.RLock()
	defer e.mu.RUnlock()

	limit := 100
	start := 0
	if len(e.auditLog) > limit {
		start = len(e.auditLog) - limit
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"entries": e.auditLog[start:],
		"total":   len(e.auditLog),
	})
}

func (e *PBACEngine) HandleGetStats(w http.ResponseWriter, r *http.Request) {
	e.mu.RLock()
	defer e.mu.RUnlock()

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"stats":        e.stats,
		"total_policies": len(e.policies),
		"audit_entries":  len(e.auditLog),
	})
}

func (e *PBACEngine) HandleHealth(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"status":  "healthy",
		"service": serviceName,
		"version": serviceVersion,
		"time":    time.Now().Format(time.RFC3339),
	})
}

// ── Grant Handlers ───────────────────────────────────────────────────

func (e *PBACEngine) HandleListGrants(w http.ResponseWriter, r *http.Request) {
	e.mu.RLock()
	defer e.mu.RUnlock()

	tenantID := r.URL.Query().Get("tenant_id")
	grants := make([]*Grant, 0)
	for _, g := range e.grants {
		if tenantID != "" && g.TenantID != tenantID {
			continue
		}
		grants = append(grants, g)
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{"grants": grants, "total": len(grants)})
}

func (e *PBACEngine) HandleGetGrant(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	id := vars["id"]

	e.mu.RLock()
	defer e.mu.RUnlock()

	grant, ok := e.grants[id]
	if !ok {
		http.Error(w, `{"error":"grant not found"}`, http.StatusNotFound)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(grant)
}

func (e *PBACEngine) HandleCreateGrant(w http.ResponseWriter, r *http.Request) {
	var body struct {
		TenantID     string      `json:"tenant_id"`
		SubjectID    string      `json:"subject_id"`
		SubjectType  string      `json:"subject_type"`
		Permission   string      `json:"permission"`
		ResourceType string      `json:"resource_type"`
		ResourceID   string      `json:"resource_id"`
		Duration     string      `json:"duration"`
		Reason       string      `json:"reason"`
		MaxUsage     *int        `json:"max_usage"`
		Conditions   interface{} `json:"conditions"`
		GrantedBy    string      `json:"granted_by"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		http.Error(w, `{"error":"invalid request body"}`, http.StatusBadRequest)
		return
	}

	dur, err := time.ParseDuration(body.Duration)
	if err != nil {
		dur = 24 * time.Hour
	}

	grant := &Grant{
		ID:           fmt.Sprintf("grant-%d", time.Now().UnixNano()),
		TenantID:     body.TenantID,
		SubjectID:    body.SubjectID,
		SubjectType:  body.SubjectType,
		Permission:   body.Permission,
		ResourceType: body.ResourceType,
		ResourceID:   body.ResourceID,
		GrantedBy:    body.GrantedBy,
		GrantedAt:    time.Now(),
		ExpiresAt:    time.Now().Add(dur),
		Reason:       body.Reason,
		Status:       "active",
		MaxUsage:     body.MaxUsage,
		Conditions:   body.Conditions,
	}

	e.mu.Lock()
	e.grants[grant.ID] = grant
	e.mu.Unlock()

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(grant)
}

func (e *PBACEngine) HandleUpdateGrant(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	id := vars["id"]

	var body struct {
		Reason     string      `json:"reason"`
		MaxUsage   *int        `json:"max_usage"`
		Conditions interface{} `json:"conditions"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		http.Error(w, `{"error":"invalid request body"}`, http.StatusBadRequest)
		return
	}

	e.mu.Lock()
	defer e.mu.Unlock()

	grant, ok := e.grants[id]
	if !ok {
		http.Error(w, `{"error":"grant not found"}`, http.StatusNotFound)
		return
	}
	if body.Reason != "" {
		grant.Reason = body.Reason
	}
	if body.MaxUsage != nil {
		grant.MaxUsage = body.MaxUsage
	}
	if body.Conditions != nil {
		grant.Conditions = body.Conditions
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(grant)
}

func (e *PBACEngine) HandleRevokeGrant(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	id := vars["id"]

	e.mu.Lock()
	defer e.mu.Unlock()

	grant, ok := e.grants[id]
	if !ok {
		http.Error(w, `{"error":"grant not found"}`, http.StatusNotFound)
		return
	}

	now := time.Now()
	grant.Status = "revoked"
	grant.RevokedAt = &now

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{"revoked": true, "id": id})
}

func (e *PBACEngine) HandleExtendGrant(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	id := vars["id"]

	var body struct {
		Duration string `json:"duration"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		http.Error(w, `{"error":"invalid request body"}`, http.StatusBadRequest)
		return
	}

	dur, err := time.ParseDuration(body.Duration)
	if err != nil {
		dur = 24 * time.Hour
	}

	e.mu.Lock()
	defer e.mu.Unlock()

	grant, ok := e.grants[id]
	if !ok {
		http.Error(w, `{"error":"grant not found"}`, http.StatusNotFound)
		return
	}
	grant.ExpiresAt = grant.ExpiresAt.Add(dur)

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(grant)
}

func (e *PBACEngine) HandleListUserGrants(w http.ResponseWriter, r *http.Request) {
	e.mu.RLock()
	defer e.mu.RUnlock()

	tenantID := r.URL.Query().Get("tenant_id")
	grants := make([]*Grant, 0)
	for _, g := range e.grants {
		if tenantID != "" && g.TenantID != tenantID {
			continue
		}
		if g.Status != "revoked" {
			grants = append(grants, g)
		}
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{"grants": grants, "total": len(grants)})
}

// ── Delegation Handlers ───────────────────────────────────────────────

func (e *PBACEngine) HandleListDelegations(w http.ResponseWriter, r *http.Request) {
	e.mu.RLock()
	defer e.mu.RUnlock()

	tenantID := r.URL.Query().Get("tenant_id")
	delegateID := r.URL.Query().Get("delegate_id")
	delegations := make([]*Delegation, 0)
	for _, d := range e.delegations {
		if tenantID != "" && d.TenantID != tenantID {
			continue
		}
		if delegateID != "" && d.DelegateID != delegateID {
			continue
		}
		delegations = append(delegations, d)
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{"delegations": delegations, "total": len(delegations)})
}

func (e *PBACEngine) HandleCreateDelegation(w http.ResponseWriter, r *http.Request) {
	var body struct {
		TenantID     string     `json:"tenant_id"`
		DelegatorID  string     `json:"delegator_id"`
		DelegateID   string     `json:"delegate_id"`
		Permission   string     `json:"permission"`
		ResourceType string     `json:"resource_type"`
		ResourceID   string     `json:"resource_id"`
		ExpiresAt    *time.Time `json:"expires_at"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		http.Error(w, `{"error":"invalid request body"}`, http.StatusBadRequest)
		return
	}

	delegation := &Delegation{
		ID:           fmt.Sprintf("delegation-%d", time.Now().UnixNano()),
		TenantID:     body.TenantID,
		DelegatorID:  body.DelegatorID,
		DelegateID:   body.DelegateID,
		Permission:   body.Permission,
		ResourceType: body.ResourceType,
		ResourceID:   body.ResourceID,
		CreatedAt:    time.Now(),
		ExpiresAt:    body.ExpiresAt,
		Revoked:      false,
	}

	e.mu.Lock()
	e.delegations[delegation.ID] = delegation
	e.mu.Unlock()

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(delegation)
}

func (e *PBACEngine) HandleRevokeDelegation(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	id := vars["id"]

	e.mu.Lock()
	defer e.mu.Unlock()

	delegation, ok := e.delegations[id]
	if !ok {
		http.Error(w, `{"error":"delegation not found"}`, http.StatusNotFound)
		return
	}

	now := time.Now()
	delegation.Revoked = true
	delegation.RevokedAt = &now

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{"revoked": true, "id": id})
}

// ── Main ─────────────────────────────────────────────────────────────

func main() {
	engine := NewPBACEngine()

	router := mux.NewRouter()

	// Authorization endpoint
	router.HandleFunc("/authorize", engine.HandleAuthorize).Methods("POST")

	// Policy CRUD
	router.HandleFunc("/policies", engine.HandleListPolicies).Methods("GET")
	router.HandleFunc("/policies", engine.HandleCreatePolicy).Methods("POST")
	router.HandleFunc("/policies/{id}", engine.HandleUpdatePolicy).Methods("PUT")
	router.HandleFunc("/policies/{id}", engine.HandleDeletePolicy).Methods("DELETE")

	// Grants CRUD
	router.HandleFunc("/grants", engine.HandleListGrants).Methods("GET")
	router.HandleFunc("/grants", engine.HandleCreateGrant).Methods("POST")
	router.HandleFunc("/grants/{id}", engine.HandleGetGrant).Methods("GET")
	router.HandleFunc("/grants/{id}", engine.HandleUpdateGrant).Methods("PUT")
	router.HandleFunc("/grants/{id}", engine.HandleRevokeGrant).Methods("DELETE")
	router.HandleFunc("/grants/{id}/extend", engine.HandleExtendGrant).Methods("POST")

	// User grants
	router.HandleFunc("/users/me/grants", engine.HandleListUserGrants).Methods("GET")

	// Delegations
	router.HandleFunc("/delegations", engine.HandleListDelegations).Methods("GET")
	router.HandleFunc("/delegations", engine.HandleCreateDelegation).Methods("POST")
	router.HandleFunc("/delegations/{id}", engine.HandleRevokeDelegation).Methods("DELETE")

	// Audit and monitoring
	router.HandleFunc("/audit", engine.HandleGetAuditLog).Methods("GET")
	router.HandleFunc("/stats", engine.HandleGetStats).Methods("GET")
	router.HandleFunc("/health", engine.HandleHealth).Methods("GET")

	port := os.Getenv("PBAC_ENGINE_PORT")
	if port == "" {
		port = "8091"
	}

	srv := &http.Server{
		Addr:         ":" + port,
		Handler:      router,
		ReadTimeout:  10 * time.Second,
		WriteTimeout: 10 * time.Second,
		IdleTimeout:  120 * time.Second,
	}

	go func() {
		slog.Info("PBAC Engine starting", "port", port, "policies", len(engine.policies))
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			slog.Error("Server failed", "error", err)
			os.Exit(1)
		}
	}()

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	slog.Info("Shutting down PBAC Engine...")
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	srv.Shutdown(ctx)
}
