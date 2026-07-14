package main

import (
	"context"
	"encoding/json"
	"net/http"
	"strings"
)

type contextKey string

const (
	ContextKeyTenantID contextKey = "tenant_id"
	ContextKeyUserID   contextKey = "user_id"
	ContextKeyUserRole contextKey = "user_role"
	ContextKeyScopes   contextKey = "scopes"
)

type UserRole string

const (
	RoleSuperAdmin   UserRole = "super_admin"
	RoleBankAdmin    UserRole = "bank_admin"
	RoleFinanceAdmin UserRole = "finance_admin"
	RoleAuditor      UserRole = "auditor"
	RoleViewer       UserRole = "viewer"
)

type AuthClaims struct {
	UserID   string   `json:"user_id"`
	TenantID string   `json:"tenant_id"`
	Role     UserRole `json:"role"`
	Scopes   []string `json:"scopes"`
}

func AdminOnlyMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		tenantID := r.Header.Get("X-Tenant-ID")
		if tenantID == "" {
			writeError(w, http.StatusBadRequest, "X-Tenant-ID header is required")
			return
		}

		userRole := r.Header.Get("X-User-Role")
		if userRole == "" {
			writeError(w, http.StatusUnauthorized, "X-User-Role header is required")
			return
		}

		if !isAdminRole(UserRole(userRole)) {
			writeError(w, http.StatusForbidden, "Access denied: Admin role required for Chart of Accounts management")
			return
		}

		userID := r.Header.Get("x-keycloak-id")
		scopes := strings.Split(r.Header.Get("X-Scopes"), ",")

		ctx := r.Context()
		ctx = context.WithValue(ctx, ContextKeyTenantID, tenantID)
		ctx = context.WithValue(ctx, ContextKeyUserID, userID)
		ctx = context.WithValue(ctx, ContextKeyUserRole, UserRole(userRole))
		ctx = context.WithValue(ctx, ContextKeyScopes, scopes)

		next.ServeHTTP(w, r.WithContext(ctx))
	})
}

func ReadOnlyMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		tenantID := r.Header.Get("X-Tenant-ID")
		if tenantID == "" {
			writeError(w, http.StatusBadRequest, "X-Tenant-ID header is required")
			return
		}

		userRole := r.Header.Get("X-User-Role")
		if userRole == "" {
			writeError(w, http.StatusUnauthorized, "X-User-Role header is required")
			return
		}

		if !canViewCoA(UserRole(userRole)) {
			writeError(w, http.StatusForbidden, "Access denied: Insufficient permissions to view Chart of Accounts")
			return
		}

		userID := r.Header.Get("x-keycloak-id")
		scopes := strings.Split(r.Header.Get("X-Scopes"), ",")

		ctx := r.Context()
		ctx = context.WithValue(ctx, ContextKeyTenantID, tenantID)
		ctx = context.WithValue(ctx, ContextKeyUserID, userID)
		ctx = context.WithValue(ctx, ContextKeyUserRole, UserRole(userRole))
		ctx = context.WithValue(ctx, ContextKeyScopes, scopes)

		next.ServeHTTP(w, r.WithContext(ctx))
	})
}

func SuperAdminOnlyMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		userRole := r.Header.Get("X-User-Role")
		if userRole == "" {
			writeError(w, http.StatusUnauthorized, "X-User-Role header is required")
			return
		}

		if UserRole(userRole) != RoleSuperAdmin {
			writeError(w, http.StatusForbidden, "Access denied: Super Admin role required for tenant management")
			return
		}

		tenantID := r.Header.Get("X-Tenant-ID")
		userID := r.Header.Get("x-keycloak-id")
		scopes := strings.Split(r.Header.Get("X-Scopes"), ",")

		ctx := r.Context()
		ctx = context.WithValue(ctx, ContextKeyTenantID, tenantID)
		ctx = context.WithValue(ctx, ContextKeyUserID, userID)
		ctx = context.WithValue(ctx, ContextKeyUserRole, UserRole(userRole))
		ctx = context.WithValue(ctx, ContextKeyScopes, scopes)

		next.ServeHTTP(w, r.WithContext(ctx))
	})
}

func TenantIsolationMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		tenantID := r.Header.Get("X-Tenant-ID")
		if tenantID == "" {
			writeError(w, http.StatusBadRequest, "X-Tenant-ID header is required for multi-tenant operations")
			return
		}

		if !isValidTenantID(tenantID) {
			writeError(w, http.StatusBadRequest, "Invalid tenant ID format")
			return
		}

		ctx := context.WithValue(r.Context(), ContextKeyTenantID, tenantID)
		next.ServeHTTP(w, r.WithContext(ctx))
	})
}

func AuditLogMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		tenantID := getTenantIDFromContext(r.Context())
		userID := getUserIDFromContext(r.Context())
		userRole := getUserRoleFromContext(r.Context())

		if r.Method != http.MethodGet {
			logAuditEvent(AuditEvent{
				TenantID:  tenantID,
				UserID:    userID,
				UserRole:  string(userRole),
				Action:    r.Method + " " + r.URL.Path,
				Resource:  "chart-of-accounts",
				IPAddress: r.RemoteAddr,
				UserAgent: r.UserAgent(),
			})
		}

		next.ServeHTTP(w, r)
	})
}

func isAdminRole(role UserRole) bool {
	switch role {
	case RoleSuperAdmin, RoleBankAdmin, RoleFinanceAdmin:
		return true
	default:
		return false
	}
}

func canViewCoA(role UserRole) bool {
	switch role {
	case RoleSuperAdmin, RoleBankAdmin, RoleFinanceAdmin, RoleAuditor, RoleViewer:
		return true
	default:
		return false
	}
}

func canModifyCoA(role UserRole) bool {
	switch role {
	case RoleSuperAdmin, RoleBankAdmin, RoleFinanceAdmin:
		return true
	default:
		return false
	}
}

func canCreateJournalEntries(role UserRole) bool {
	switch role {
	case RoleSuperAdmin, RoleBankAdmin, RoleFinanceAdmin:
		return true
	default:
		return false
	}
}

func canReverseJournalEntries(role UserRole) bool {
	switch role {
	case RoleSuperAdmin, RoleBankAdmin:
		return true
	default:
		return false
	}
}

func canGenerateCBNReturns(role UserRole) bool {
	switch role {
	case RoleSuperAdmin, RoleBankAdmin, RoleFinanceAdmin, RoleAuditor:
		return true
	default:
		return false
	}
}

func canRunReconciliation(role UserRole) bool {
	switch role {
	case RoleSuperAdmin, RoleBankAdmin, RoleFinanceAdmin:
		return true
	default:
		return false
	}
}

func canManageTenants(role UserRole) bool {
	return role == RoleSuperAdmin
}

func isValidTenantID(tenantID string) bool {
	if len(tenantID) < 3 || len(tenantID) > 64 {
		return false
	}
	for _, c := range tenantID {
		if !((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '-' || c == '_') {
			return false
		}
	}
	return true
}

func getTenantIDFromContext(ctx context.Context) string {
	if v := ctx.Value(ContextKeyTenantID); v != nil {
		return v.(string)
	}
	return ""
}

func getUserIDFromContext(ctx context.Context) string {
	if v := ctx.Value(ContextKeyUserID); v != nil {
		return v.(string)
	}
	return ""
}

func getUserRoleFromContext(ctx context.Context) UserRole {
	if v := ctx.Value(ContextKeyUserRole); v != nil {
		return v.(UserRole)
	}
	return ""
}

func getScopesFromContext(ctx context.Context) []string {
	if v := ctx.Value(ContextKeyScopes); v != nil {
		return v.([]string)
	}
	return nil
}

type AuditEvent struct {
	TenantID  string `json:"tenant_id"`
	UserID    string `json:"user_id"`
	UserRole  string `json:"user_role"`
	Action    string `json:"action"`
	Resource  string `json:"resource"`
	IPAddress string `json:"ip_address"`
	UserAgent string `json:"user_agent"`
}

func logAuditEvent(event AuditEvent) {
}

func writeError(w http.ResponseWriter, statusCode int, message string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(statusCode)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"error":   true,
		"message": message,
		"code":    statusCode,
	})
}

type Permission struct {
	Resource string `json:"resource"`
	Action   string `json:"action"`
}

var rolePermissions = map[UserRole][]Permission{
	RoleSuperAdmin: {
		{Resource: "coa:accounts", Action: "create"},
		{Resource: "coa:accounts", Action: "read"},
		{Resource: "coa:accounts", Action: "update"},
		{Resource: "coa:accounts", Action: "delete"},
		{Resource: "coa:journal-entries", Action: "create"},
		{Resource: "coa:journal-entries", Action: "read"},
		{Resource: "coa:journal-entries", Action: "reverse"},
		{Resource: "coa:reports", Action: "read"},
		{Resource: "coa:cbn-returns", Action: "generate"},
		{Resource: "coa:reconciliation", Action: "run"},
		{Resource: "coa:tenants", Action: "create"},
		{Resource: "coa:tenants", Action: "read"},
		{Resource: "coa:tenants", Action: "update"},
		{Resource: "coa:tenants", Action: "delete"},
	},
	RoleBankAdmin: {
		{Resource: "coa:accounts", Action: "create"},
		{Resource: "coa:accounts", Action: "read"},
		{Resource: "coa:accounts", Action: "update"},
		{Resource: "coa:accounts", Action: "delete"},
		{Resource: "coa:journal-entries", Action: "create"},
		{Resource: "coa:journal-entries", Action: "read"},
		{Resource: "coa:journal-entries", Action: "reverse"},
		{Resource: "coa:reports", Action: "read"},
		{Resource: "coa:cbn-returns", Action: "generate"},
		{Resource: "coa:reconciliation", Action: "run"},
	},
	RoleFinanceAdmin: {
		{Resource: "coa:accounts", Action: "create"},
		{Resource: "coa:accounts", Action: "read"},
		{Resource: "coa:accounts", Action: "update"},
		{Resource: "coa:journal-entries", Action: "create"},
		{Resource: "coa:journal-entries", Action: "read"},
		{Resource: "coa:reports", Action: "read"},
		{Resource: "coa:cbn-returns", Action: "generate"},
		{Resource: "coa:reconciliation", Action: "run"},
	},
	RoleAuditor: {
		{Resource: "coa:accounts", Action: "read"},
		{Resource: "coa:journal-entries", Action: "read"},
		{Resource: "coa:reports", Action: "read"},
		{Resource: "coa:cbn-returns", Action: "generate"},
	},
	RoleViewer: {
		{Resource: "coa:accounts", Action: "read"},
		{Resource: "coa:reports", Action: "read"},
	},
}

func hasPermission(role UserRole, resource, action string) bool {
	permissions, exists := rolePermissions[role]
	if !exists {
		return false
	}

	for _, p := range permissions {
		if p.Resource == resource && p.Action == action {
			return true
		}
	}
	return false
}
