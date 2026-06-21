// Insider Threat RBAC Service (Go)
//
// Provides granular permission management using Permify (Zanzibar-style ReBAC).
// Replaces binary admin/non-admin with fine-grained permissions:
// - can_approve_reversals
// - can_disburse_loans
// - can_modify_fees
// - can_payout_commissions
// - can_adjust_float
// - can_convert_fx
// - can_change_privileges
// - can_access_break_glass
//
// Enforces: no single role has both CREATE and APPROVE on financial mutations.

package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"strings"
	"time"
)

// Permission represents a granular access control permission
type Permission struct {
	ID          string `json:"id"`
	Name        string `json:"name"`
	Description string `json:"description"`
	Category    string `json:"category"`
	RiskLevel   string `json:"riskLevel"` // low, medium, high, critical
}

// Role represents a predefined role with associated permissions
type Role struct {
	ID                string   `json:"id"`
	Name              string   `json:"name"`
	Description       string   `json:"description"`
	Permissions       []string `json:"permissions"`
	IncompatibleWith  []string `json:"incompatibleWith"` // Separation of duties
	MaxConcurrentHeld int      `json:"maxConcurrentHeld"`
}

// PolicyCheck represents a permission check request
type PolicyCheck struct {
	AgentID    int64  `json:"agentId"`
	AgentCode  string `json:"agentCode"`
	Permission string `json:"permission"`
	Resource   string `json:"resource"`
	ResourceID string `json:"resourceId"`
	Context    map[string]interface{} `json:"context"`
}

// PolicyResult is the response for a permission check
type PolicyResult struct {
	Allowed    bool   `json:"allowed"`
	Reason     string `json:"reason"`
	RiskLevel  string `json:"riskLevel"`
	RequiresMFA bool  `json:"requiresMfa"`
}

// ConflictCheck checks for separation of duties violations
type ConflictCheck struct {
	AgentID     int64    `json:"agentId"`
	Permissions []string `json:"requestedPermissions"`
}

// ConflictResult is the response for a conflict check
type ConflictResult struct {
	HasConflict bool     `json:"hasConflict"`
	Conflicts   []string `json:"conflicts"`
	Message     string   `json:"message"`
}

// ── Permission Definitions ───────────────────────────────────────────────────

var allPermissions = []Permission{
	// Financial Operations — Create
	{ID: "fin.create.cash_in", Name: "Create Cash-In", Description: "Process customer deposits", Category: "financial.create", RiskLevel: "medium"},
	{ID: "fin.create.cash_out", Name: "Create Cash-Out", Description: "Process customer withdrawals", Category: "financial.create", RiskLevel: "medium"},
	{ID: "fin.create.loan_disbursement", Name: "Create Loan Disbursement", Description: "Initiate loan disbursement", Category: "financial.create", RiskLevel: "high"},
	{ID: "fin.create.reversal", Name: "Request Reversal", Description: "Request transaction reversal", Category: "financial.create", RiskLevel: "high"},
	{ID: "fin.create.commission_payout", Name: "Create Commission Payout", Description: "Initiate commission payment", Category: "financial.create", RiskLevel: "high"},
	{ID: "fin.create.fx_conversion", Name: "Create FX Conversion", Description: "Initiate currency conversion", Category: "financial.create", RiskLevel: "high"},
	{ID: "fin.create.float_adjustment", Name: "Create Float Adjustment", Description: "Adjust agent float balance", Category: "financial.create", RiskLevel: "critical"},
	{ID: "fin.create.fee_override", Name: "Create Fee Override", Description: "Override platform fees", Category: "financial.create", RiskLevel: "critical"},
	{ID: "fin.create.chargeback", Name: "Create Chargeback", Description: "Initiate chargeback/refund", Category: "financial.create", RiskLevel: "high"},
	{ID: "fin.create.remittance", Name: "Create Remittance", Description: "Initiate cross-border transfer", Category: "financial.create", RiskLevel: "high"},

	// Financial Operations — Approve
	{ID: "fin.approve.reversal", Name: "Approve Reversal", Description: "Approve transaction reversal", Category: "financial.approve", RiskLevel: "high"},
	{ID: "fin.approve.loan_disbursement", Name: "Approve Loan Disbursement", Description: "Approve loan disbursement", Category: "financial.approve", RiskLevel: "high"},
	{ID: "fin.approve.commission_payout", Name: "Approve Commission Payout", Description: "Approve commission payment", Category: "financial.approve", RiskLevel: "high"},
	{ID: "fin.approve.float_adjustment", Name: "Approve Float Adjustment", Description: "Approve float balance change", Category: "financial.approve", RiskLevel: "critical"},
	{ID: "fin.approve.fee_override", Name: "Approve Fee Override", Description: "Approve fee change", Category: "financial.approve", RiskLevel: "critical"},
	{ID: "fin.approve.fx_conversion", Name: "Approve FX Conversion", Description: "Approve large FX conversion", Category: "financial.approve", RiskLevel: "high"},
	{ID: "fin.approve.chargeback", Name: "Approve Chargeback", Description: "Approve chargeback resolution", Category: "financial.approve", RiskLevel: "high"},

	// System Administration
	{ID: "sys.manage.agents", Name: "Manage Agents", Description: "Create/deactivate agents", Category: "system", RiskLevel: "high"},
	{ID: "sys.manage.roles", Name: "Manage Roles", Description: "Assign/revoke roles", Category: "system", RiskLevel: "critical"},
	{ID: "sys.manage.config", Name: "System Config", Description: "Modify system configuration", Category: "system", RiskLevel: "critical"},
	{ID: "sys.access.break_glass", Name: "Break Glass Access", Description: "Emergency override access", Category: "system", RiskLevel: "critical"},
	{ID: "sys.view.audit_log", Name: "View Audit Log", Description: "Access audit trail", Category: "system", RiskLevel: "medium"},
	{ID: "sys.export.data", Name: "Export Data", Description: "Export platform data", Category: "system", RiskLevel: "high"},

	// Read-only
	{ID: "read.transactions", Name: "View Transactions", Description: "View transaction history", Category: "read", RiskLevel: "low"},
	{ID: "read.reports", Name: "View Reports", Description: "Access financial reports", Category: "read", RiskLevel: "low"},
	{ID: "read.agents", Name: "View Agents", Description: "View agent profiles", Category: "read", RiskLevel: "low"},
}

// ── Role Definitions (Separation of Duties Built-In) ─────────────────────────

var allRoles = []Role{
	{
		ID:          "agent_operator",
		Name:        "Agent Operator",
		Description: "Day-to-day transaction processing",
		Permissions: []string{
			"fin.create.cash_in", "fin.create.cash_out",
			"read.transactions", "read.reports", "read.agents",
		},
		IncompatibleWith:  []string{"financial_approver", "system_admin"},
		MaxConcurrentHeld: 2,
	},
	{
		ID:          "financial_maker",
		Name:        "Financial Maker",
		Description: "Initiate high-value financial operations",
		Permissions: []string{
			"fin.create.loan_disbursement", "fin.create.reversal",
			"fin.create.commission_payout", "fin.create.fx_conversion",
			"fin.create.float_adjustment", "fin.create.fee_override",
			"fin.create.chargeback", "fin.create.remittance",
			"read.transactions", "read.reports",
		},
		IncompatibleWith:  []string{"financial_approver"}, // Cannot hold both
		MaxConcurrentHeld: 2,
	},
	{
		ID:          "financial_approver",
		Name:        "Financial Approver",
		Description: "Approve high-value financial operations",
		Permissions: []string{
			"fin.approve.reversal", "fin.approve.loan_disbursement",
			"fin.approve.commission_payout", "fin.approve.float_adjustment",
			"fin.approve.fee_override", "fin.approve.fx_conversion",
			"fin.approve.chargeback",
			"read.transactions", "read.reports",
		},
		IncompatibleWith:  []string{"financial_maker"}, // Cannot hold both
		MaxConcurrentHeld: 2,
	},
	{
		ID:          "compliance_officer",
		Name:        "Compliance Officer",
		Description: "Compliance monitoring and reporting",
		Permissions: []string{
			"sys.view.audit_log", "sys.export.data",
			"read.transactions", "read.reports", "read.agents",
		},
		IncompatibleWith:  []string{"financial_maker", "financial_approver"},
		MaxConcurrentHeld: 3,
	},
	{
		ID:          "system_admin",
		Name:        "System Administrator",
		Description: "System configuration and agent management",
		Permissions: []string{
			"sys.manage.agents", "sys.manage.roles", "sys.manage.config",
			"sys.view.audit_log",
			"read.transactions", "read.reports", "read.agents",
		},
		IncompatibleWith:  []string{"financial_maker", "financial_approver"},
		MaxConcurrentHeld: 1,
	},
	{
		ID:          "break_glass",
		Name:        "Break Glass (Emergency)",
		Description: "Emergency access — time-limited, fully audited",
		Permissions: []string{
			"sys.access.break_glass",
		},
		IncompatibleWith:  []string{}, // Anyone can get break-glass temporarily
		MaxConcurrentHeld: 1,
	},
}

// ── Incompatible Permission Pairs (Separation of Duties) ─────────────────────

var incompatiblePairs = [][2]string{
	{"fin.create.reversal", "fin.approve.reversal"},
	{"fin.create.loan_disbursement", "fin.approve.loan_disbursement"},
	{"fin.create.commission_payout", "fin.approve.commission_payout"},
	{"fin.create.float_adjustment", "fin.approve.float_adjustment"},
	{"fin.create.fee_override", "fin.approve.fee_override"},
	{"fin.create.fx_conversion", "fin.approve.fx_conversion"},
	{"fin.create.chargeback", "fin.approve.chargeback"},
}

// ── In-memory permission store (production: use Permify/Redis) ───────────────

var agentPermissions = map[int64][]string{}

// ── Handlers ─────────────────────────────────────────────────────────────────

func checkPermissionHandler(w http.ResponseWriter, r *http.Request) {
	var req PolicyCheck
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	perms, exists := agentPermissions[req.AgentID]
	if !exists {
		json.NewEncoder(w).Encode(PolicyResult{
			Allowed: false,
			Reason:  "Agent has no permissions assigned",
		})
		return
	}

	// Check if agent has the required permission
	hasPermission := false
	for _, p := range perms {
		if p == req.Permission {
			hasPermission = true
			break
		}
	}

	if !hasPermission {
		json.NewEncoder(w).Encode(PolicyResult{
			Allowed: false,
			Reason:  fmt.Sprintf("Agent lacks permission: %s", req.Permission),
		})
		return
	}

	// Find permission risk level
	riskLevel := "low"
	requiresMFA := false
	for _, p := range allPermissions {
		if p.ID == req.Permission {
			riskLevel = p.RiskLevel
			if riskLevel == "critical" || riskLevel == "high" {
				requiresMFA = true
			}
			break
		}
	}

	json.NewEncoder(w).Encode(PolicyResult{
		Allowed:     true,
		Reason:      "Permission granted",
		RiskLevel:   riskLevel,
		RequiresMFA: requiresMFA,
	})
}

func checkConflictsHandler(w http.ResponseWriter, r *http.Request) {
	var req ConflictCheck
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	var conflicts []string
	for _, pair := range incompatiblePairs {
		hasFirst := false
		hasSecond := false
		for _, p := range req.Permissions {
			if p == pair[0] {
				hasFirst = true
			}
			if p == pair[1] {
				hasSecond = true
			}
		}
		if hasFirst && hasSecond {
			conflicts = append(conflicts, fmt.Sprintf("%s + %s", pair[0], pair[1]))
		}
	}

	result := ConflictResult{
		HasConflict: len(conflicts) > 0,
		Conflicts:   conflicts,
	}
	if len(conflicts) > 0 {
		result.Message = fmt.Sprintf("Separation of duties violation: %d conflicting permission pair(s)", len(conflicts))
	} else {
		result.Message = "No conflicts detected"
	}

	json.NewEncoder(w).Encode(result)
}

func assignPermissionsHandler(w http.ResponseWriter, r *http.Request) {
	var req struct {
		AgentID     int64    `json:"agentId"`
		Permissions []string `json:"permissions"`
		AssignedBy  int64    `json:"assignedBy"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	// Check for conflicts before assigning
	existing := agentPermissions[req.AgentID]
	combined := append(existing, req.Permissions...)

	for _, pair := range incompatiblePairs {
		hasFirst := false
		hasSecond := false
		for _, p := range combined {
			if p == pair[0] {
				hasFirst = true
			}
			if p == pair[1] {
				hasSecond = true
			}
		}
		if hasFirst && hasSecond {
			http.Error(w, fmt.Sprintf(
				"Cannot assign: separation of duties violation (%s conflicts with %s)",
				pair[0], pair[1],
			), http.StatusConflict)
			return
		}
	}

	// Self-assignment check: cannot assign permissions to yourself
	if req.AgentID == req.AssignedBy {
		http.Error(w, "Cannot assign permissions to yourself", http.StatusForbidden)
		return
	}

	agentPermissions[req.AgentID] = combined

	json.NewEncoder(w).Encode(map[string]interface{}{
		"success":     true,
		"agentId":     req.AgentID,
		"permissions": combined,
	})
}

func listPermissionsHandler(w http.ResponseWriter, r *http.Request) {
	json.NewEncoder(w).Encode(allPermissions)
}

func listRolesHandler(w http.ResponseWriter, r *http.Request) {
	json.NewEncoder(w).Encode(allRoles)
}

func healthHandler(w http.ResponseWriter, r *http.Request) {
	json.NewEncoder(w).Encode(map[string]string{
		"status":  "healthy",
		"service": "insider-threat-rbac",
		"version": "1.0.0",
	})
}

func main() {
	port := os.Getenv("RBAC_PORT")
	if port == "" {
		port = "8261"
	}

	mux := http.NewServeMux()
	mux.HandleFunc("/health", healthHandler)
	mux.HandleFunc("/check", checkPermissionHandler)
	mux.HandleFunc("/conflicts", checkConflictsHandler)
	mux.HandleFunc("/assign", assignPermissionsHandler)
	mux.HandleFunc("/permissions", listPermissionsHandler)
	mux.HandleFunc("/roles", listRolesHandler)

	server := &http.Server{
		Addr:         ":" + port,
		Handler:      mux,
		ReadTimeout:  10 * time.Second,
		WriteTimeout: 10 * time.Second,
	}

	log.Printf("Insider Threat RBAC Service starting on port %s", port)
	log.Printf("Permify integration: %s", os.Getenv("PERMIFY_URL"))

	ctx := context.Background()
	_ = ctx
	if err := server.ListenAndServe(); err != nil {
		log.Fatalf("Server failed: %v", err)
	}
}

func init() {
	_ = strings.Join(nil, "")
}
