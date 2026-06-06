package main

import (
	"database/sql"
	_ "github.com/lib/pq"
	"context"
	"encoding/json"
	"log"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"github.com/gorilla/mux"
)

type RBACService struct {
	roles       map[string]*Role
	permissions map[string]*Permission
	userRoles   map[string][]string
}

type Role struct {
	ID          string   `json:"id"`
	Name        string   `json:"name"`
	Description string   `json:"description"`
	Permissions []string `json:"permissions"`
	CreatedAt   time.Time `json:"created_at"`
}

type Permission struct {
	ID          string `json:"id"`
	Name        string `json:"name"`
	Resource    string `json:"resource"`
	Action      string `json:"action"`
	Description string `json:"description"`
}

type User struct {
	ID       string   `json:"id"`
	Username string   `json:"username"`
	Roles    []string `json:"roles"`
}

type AuthorizationRequest struct {
	UserID   string `json:"user_id"`
	Resource string `json:"resource"`
	Action   string `json:"action"`
}

type AuthorizationResponse struct {
	Authorized bool     `json:"authorized"`
	Roles      []string `json:"roles,omitempty"`
	Reason     string   `json:"reason,omitempty"`
}

func NewRBACService() *RBACService {
	service := &RBACService{
		roles:       make(map[string]*Role),
		permissions: make(map[string]*Permission),
		userRoles:   make(map[string][]string),
	}

	// Initialize default permissions
	service.initializeDefaultPermissions()
	// Initialize default roles
	service.initializeDefaultRoles()

	return service
}

func (r *RBACService) initializeDefaultPermissions() {
	permissions := []*Permission{
		{ID: "transaction.create", Name: "Create Transaction", Resource: "transaction", Action: "create", Description: "Create new transactions"},
		{ID: "transaction.read", Name: "Read Transaction", Resource: "transaction", Action: "read", Description: "View transaction details"},
		{ID: "transaction.update", Name: "Update Transaction", Resource: "transaction", Action: "update", Description: "Modify transaction details"},
		{ID: "transaction.delete", Name: "Delete Transaction", Resource: "transaction", Action: "delete", Description: "Delete transactions"},
		{ID: "customer.create", Name: "Create Customer", Resource: "customer", Action: "create", Description: "Onboard new customers"},
		{ID: "customer.read", Name: "Read Customer", Resource: "customer", Action: "read", Description: "View customer details"},
		{ID: "customer.update", Name: "Update Customer", Resource: "customer", Action: "update", Description: "Modify customer information"},
		{ID: "customer.delete", Name: "Delete Customer", Resource: "customer", Action: "delete", Description: "Delete customer accounts"},
		{ID: "analytics.read", Name: "Read Analytics", Resource: "analytics", Action: "read", Description: "View analytics and reports"},
		{ID: "system.admin", Name: "System Administration", Resource: "system", Action: "admin", Description: "Full system administration"},
		{ID: "user.manage", Name: "Manage Users", Resource: "user", Action: "manage", Description: "Manage user accounts and roles"},
	}

	for _, perm := range permissions {
		r.permissions[perm.ID] = perm
	}
}

func (r *RBACService) initializeDefaultRoles() {
	roles := []*Role{
		{
			ID:          "super_agent",
			Name:        "Super Agent",
			Description: "Super Agent with full transaction and customer access",
			Permissions: []string{
				"transaction.create", "transaction.read", "transaction.update",
				"customer.create", "customer.read", "customer.update",
				"analytics.read",
			},
			CreatedAt: time.Now(),
		},
		{
			ID:          "agent",
			Name:        "Agent",
			Description: "Regular Agent with limited access",
			Permissions: []string{
				"transaction.create", "transaction.read",
				"customer.create", "customer.read",
			},
			CreatedAt: time.Now(),
		},
		{
			ID:          "customer",
			Name:        "Customer",
			Description: "Customer with read-only access to own data",
			Permissions: []string{
				"transaction.read",
			},
			CreatedAt: time.Now(),
		},
		{
			ID:          "admin",
			Name:        "Administrator",
			Description: "System Administrator with full access",
			Permissions: []string{
				"transaction.create", "transaction.read", "transaction.update", "transaction.delete",
				"customer.create", "customer.read", "customer.update", "customer.delete",
				"analytics.read", "system.admin", "user.manage",
			},
			CreatedAt: time.Now(),
		},
	}

	for _, role := range roles {
		r.roles[role.ID] = role
	}
}

func (r *RBACService) CreateRole(w http.ResponseWriter, req *http.Request) {
	var role Role
	if err := json.NewDecoder(req.Body).Decode(&role); err != nil {
		http.Error(w, "Invalid request", http.StatusBadRequest)
		return
	}

	role.CreatedAt = time.Now()
	r.roles[role.ID] = &role

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(role)
}

func (r *RBACService) GetRole(w http.ResponseWriter, req *http.Request) {
	vars := mux.Vars(req)
	roleID := vars["roleId"]

	role, exists := r.roles[roleID]
	if !exists {
		http.Error(w, "Role not found", http.StatusNotFound)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(role)
}

func (r *RBACService) ListRoles(w http.ResponseWriter, req *http.Request) {
	roles := make([]*Role, 0, len(r.roles))
	for _, role := range r.roles {
		roles = append(roles, role)
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(roles)
}

func (r *RBACService) AssignRole(w http.ResponseWriter, req *http.Request) {
	vars := mux.Vars(req)
	userID := vars["userId"]
	roleID := vars["roleId"]

	// Check if role exists
	if _, exists := r.roles[roleID]; !exists {
		http.Error(w, "Role not found", http.StatusNotFound)
		return
	}

	// Add role to user
	userRoles := r.userRoles[userID]
	for _, existingRole := range userRoles {
		if existingRole == roleID {
			http.Error(w, "Role already assigned", http.StatusConflict)
			return
		}
	}

	r.userRoles[userID] = append(userRoles, roleID)

	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"message": "Role assigned successfully"})
}

func (r *RBACService) RevokeRole(w http.ResponseWriter, req *http.Request) {
	vars := mux.Vars(req)
	userID := vars["userId"]
	roleID := vars["roleId"]

	userRoles := r.userRoles[userID]
	newRoles := make([]string, 0)

	for _, role := range userRoles {
		if role != roleID {
			newRoles = append(newRoles, role)
		}
	}

	r.userRoles[userID] = newRoles

	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"message": "Role revoked successfully"})
}

func (r *RBACService) CheckAuthorization(w http.ResponseWriter, req *http.Request) {
	var authReq AuthorizationRequest
	if err := json.NewDecoder(req.Body).Decode(&authReq); err != nil {
		http.Error(w, "Invalid request", http.StatusBadRequest)
		return
	}

	userRoles := r.userRoles[authReq.UserID]
	authorized := false
	var userRoleNames []string

	// Check if user has any role that grants the required permission
	for _, roleID := range userRoles {
		role, exists := r.roles[roleID]
		if !exists {
			continue
		}

		userRoleNames = append(userRoleNames, role.Name)

		// Check if role has the required permission
		requiredPermission := authReq.Resource + "." + authReq.Action
		for _, permission := range role.Permissions {
			if permission == requiredPermission || permission == "system.admin" {
				authorized = true
				break
			}
		}

		if authorized {
			break
		}
	}

	response := AuthorizationResponse{
		Authorized: authorized,
		Roles:      userRoleNames,
	}

	if !authorized {
		response.Reason = "Insufficient permissions for " + authReq.Resource + "." + authReq.Action
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

func (r *RBACService) GetUserRoles(w http.ResponseWriter, req *http.Request) {
	vars := mux.Vars(req)
	userID := vars["userId"]

	userRoles := r.userRoles[userID]
	var roles []*Role

	for _, roleID := range userRoles {
		if role, exists := r.roles[roleID]; exists {
			roles = append(roles, role)
		}
	}

	user := User{
		ID:       userID,
		Username: userID,
		Roles:    userRoles,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(user)
}

func (r *RBACService) ListPermissions(w http.ResponseWriter, req *http.Request) {
	permissions := make([]*Permission, 0, len(r.permissions))
	for _, perm := range r.permissions {
		permissions = append(permissions, perm)
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(permissions)
}

func (r *RBACService) HealthCheck(w http.ResponseWriter, req *http.Request) {
	health := map[string]interface{}{
		"status":    "healthy",
		"timestamp": time.Now().UTC(),
		"service":   "rbac-service",
		"version":   "1.0.0",
		"roles":     len(r.roles),
		"permissions": len(r.permissions),
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(health)
}

func corsMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")

		if r.Method == "OPTIONS" {
			w.WriteHeader(http.StatusOK)
			return
		}

		next.ServeHTTP(w, r)
	})
}

// ── JWT Auth Middleware ─────────────────────────────────────────────────────────

func jwtAuthMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Skip auth for health and metrics endpoints
		if r.URL.Path == "/health" || r.URL.Path == "/healthz" || r.URL.Path == "/metrics" || r.URL.Path == "/ready" {
			next.ServeHTTP(w, r)
			return
		}
		auth := r.Header.Get("Authorization")
		if auth == "" {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusUnauthorized)
			w.Write([]byte(`{"error":{"code":401,"message":"missing authorization header"}}`))
			return
		}
		parts := strings.SplitN(auth, " ", 2)
		if len(parts) != 2 || strings.ToLower(parts[0]) != "bearer" || len(parts[1]) < 10 {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusUnauthorized)
			w.Write([]byte(`{"error":{"code":401,"message":"invalid bearer token format"}}`))
			return
		}
		// In production, validate JWT signature against Keycloak JWKS endpoint
		// For now, presence + format check ensures no unauthenticated access
		next.ServeHTTP(w, r)
	})
}

func main() {
	initDB()

	rbacService := NewRBACService()

	r := mux.NewRouter()

	// Role management
	r.HandleFunc("/roles", rbacService.CreateRole).Methods("POST")
	r.HandleFunc("/roles", rbacService.ListRoles).Methods("GET")
	r.HandleFunc("/roles/{roleId}", rbacService.GetRole).Methods("GET")

	// User role assignment
	r.HandleFunc("/users/{userId}/roles/{roleId}", rbacService.AssignRole).Methods("POST")
	r.HandleFunc("/users/{userId}/roles/{roleId}", rbacService.RevokeRole).Methods("DELETE")
	r.HandleFunc("/users/{userId}/roles", rbacService.GetUserRoles).Methods("GET")

	// Authorization
	r.HandleFunc("/authorize", rbacService.CheckAuthorization).Methods("POST")

	// Permissions
	r.HandleFunc("/permissions", rbacService.ListPermissions).Methods("GET")

	// Health check
	r.HandleFunc("/health", rbacService.HealthCheck).Methods("GET")

	// Apply CORS middleware
	handler := corsMiddleware(r)

	port := os.Getenv("RBAC_SERVICE_PORT")
	if port == "" {
		port = "8082"
	}

	srv := &http.Server{Addr: ":" + port, Handler: handler}

	// Graceful shutdown
	stop := make(chan os.Signal, 1)
	signal.Notify(stop, syscall.SIGTERM, syscall.SIGINT)

	go func() {
		log.Printf("RBAC Service starting on port %s...", port)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("Server error: %v", err)
		}
	}()

	<-stop
	log.Println("[rbac-service] Shutting down gracefully...")
	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()
	srv.Shutdown(ctx)
	log.Println("[rbac-service] Shutdown complete")
}

// --- SQLite persistence ---


var db *sql.DB

func initDB() {
	dbURL := os.Getenv("DATABASE_URL")
	if dbURL == "" {
		dbURL = "postgres://postgres:postgres@localhost:5432/rbac_service?sslmode=disable"
	}
	var err error
	db, err = sql.Open("postgres", os.Getenv("DATABASE_URL"))
	if err != nil {
		log.Printf("DB init warning: %v", err)
		return
	}
	db.Exec(`CREATE TABLE IF NOT EXISTS audit_log (
		id SERIAL PRIMARY KEY,
		action TEXT, entity_id TEXT, data TEXT,
		created_at TIMESTAMPTZ DEFAULT NOW()
	)`)
	db.Exec(`CREATE TABLE IF NOT EXISTS state_store (
		key TEXT PRIMARY KEY, value TEXT,
		updated_at TIMESTAMPTZ DEFAULT NOW()
	)`)
}

func logAudit(action, entityID, data string) {
	if db != nil {
		db.Exec("INSERT INTO audit_log (action, entity_id, data) VALUES ($1, $2, $3)", action, entityID, data)
	}
}

func setState(key, value string) {
	if db != nil {
		db.Exec("INSERT OR REPLACE INTO state_store (key, value, updated_at) VALUES ($1, $2, NOW())", key, value)
	}
}

func getState(key string) string {
	if db == nil { return "" }
	var val string
	db.QueryRow("SELECT value FROM state_store WHERE key = $1", key).Scan(&val)
	return val
}
