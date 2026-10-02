package main

import (
	"context"
	"encoding/json"
	"log"
	"net/http"
	"os"
	"time"

	"github.com/gorilla/mux"
	"github.com/redis/go-redis/v9"
)

// round-11 wave-5: RBAC authz state is persisted in Redis (shared across
// replicas, survives restarts) instead of process-local maps.
// Keys: rbac:roles (hash id→JSON), rbac:permissions (hash id→JSON),
// rbac:userroles:{userID} (set of role IDs).
type RBACService struct {
	rdb *redis.Client
	ctx context.Context
}

type Role struct {
	ID          string    `json:"id"`
	Name        string    `json:"name"`
	Description string    `json:"description"`
	Permissions []string  `json:"permissions"`
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

func newRedisClient() *redis.Client {
	redisURL := os.Getenv("REDIS_URL")
	if redisURL == "" {
		redisURL = "redis://localhost:6379/0"
	}
	opt, err := redis.ParseURL(redisURL)
	if err != nil {
		log.Fatalf("invalid REDIS_URL: %v", err)
	}
	return redis.NewClient(opt)
}

func NewRBACService() *RBACService {
	service := &RBACService{
		rdb: newRedisClient(),
		ctx: context.Background(),
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
		data, err := json.Marshal(perm)
		if err != nil {
			log.Printf("marshal permission %s: %v", perm.ID, err)
			continue
		}
		if err := r.rdb.HSet(r.ctx, "rbac:permissions", perm.ID, data).Err(); err != nil {
			log.Printf("redis HSet permission %s: %v", perm.ID, err)
		}
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
		data, err := json.Marshal(role)
		if err != nil {
			log.Printf("marshal role %s: %v", role.ID, err)
			continue
		}
		if err := r.rdb.HSet(r.ctx, "rbac:roles", role.ID, data).Err(); err != nil {
			log.Printf("redis HSet role %s: %v", role.ID, err)
		}
	}
}

func (r *RBACService) CreateRole(w http.ResponseWriter, req *http.Request) {
	var role Role
	if err := json.NewDecoder(req.Body).Decode(&role); err != nil {
		http.Error(w, "Invalid request", http.StatusBadRequest)
		return
	}

	role.CreatedAt = time.Now()
	data, err := json.Marshal(&role)
	if err != nil {
		http.Error(w, "Internal error", http.StatusInternalServerError)
		return
	}
	if err := r.rdb.HSet(r.ctx, "rbac:roles", role.ID, data).Err(); err != nil {
		log.Printf("redis HSet role: %v", err)
		http.Error(w, "Storage unavailable", http.StatusServiceUnavailable)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(role)
}

func (r *RBACService) GetRole(w http.ResponseWriter, req *http.Request) {
	vars := mux.Vars(req)
	roleID := vars["roleId"]

	data, err := r.rdb.HGet(r.ctx, "rbac:roles", roleID).Result()
	if err == redis.Nil {
		http.Error(w, "Role not found", http.StatusNotFound)
		return
	}
	if err != nil {
		log.Printf("redis HGet role: %v", err)
		http.Error(w, "Storage unavailable", http.StatusServiceUnavailable)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.Write([]byte(data))
}

func (r *RBACService) ListRoles(w http.ResponseWriter, req *http.Request) {
	vals, err := r.rdb.HVals(r.ctx, "rbac:roles").Result()
	if err != nil {
		log.Printf("redis HVals roles: %v", err)
		http.Error(w, "Storage unavailable", http.StatusServiceUnavailable)
		return
	}
	roles := make([]json.RawMessage, 0, len(vals))
	for _, v := range vals {
		roles = append(roles, json.RawMessage(v))
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(roles)
}

func (r *RBACService) AssignRole(w http.ResponseWriter, req *http.Request) {
	vars := mux.Vars(req)
	userID := vars["userId"]
	roleID := vars["roleId"]

	// Check if role exists
	exists, err := r.rdb.HExists(r.ctx, "rbac:roles", roleID).Result()
	if err != nil {
		log.Printf("redis HExists role: %v", err)
		http.Error(w, "Storage unavailable", http.StatusServiceUnavailable)
		return
	}
	if !exists {
		http.Error(w, "Role not found", http.StatusNotFound)
		return
	}

	// Add role to user (Redis set add is idempotent — detect duplicates first)
	key := "rbac:userroles:" + userID
	isMember, err := r.rdb.SIsMember(r.ctx, key, roleID).Result()
	if err != nil {
		log.Printf("redis SIsMember: %v", err)
		http.Error(w, "Storage unavailable", http.StatusServiceUnavailable)
		return
	}
	if isMember {
		http.Error(w, "Role already assigned", http.StatusConflict)
		return
	}

	if err := r.rdb.SAdd(r.ctx, key, roleID).Err(); err != nil {
		log.Printf("redis SAdd: %v", err)
		http.Error(w, "Storage unavailable", http.StatusServiceUnavailable)
		return
	}

	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"message": "Role assigned successfully"})
}

func (r *RBACService) RevokeRole(w http.ResponseWriter, req *http.Request) {
	vars := mux.Vars(req)
	userID := vars["userId"]
	roleID := vars["roleId"]

	if err := r.rdb.SRem(r.ctx, "rbac:userroles:"+userID, roleID).Err(); err != nil {
		log.Printf("redis SRem: %v", err)
		http.Error(w, "Storage unavailable", http.StatusServiceUnavailable)
		return
	}

	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"message": "Role revoked successfully"})
}

func (r *RBACService) CheckAuthorization(w http.ResponseWriter, req *http.Request) {
	var authReq AuthorizationRequest
	if err := json.NewDecoder(req.Body).Decode(&authReq); err != nil {
		http.Error(w, "Invalid request", http.StatusBadRequest)
		return
	}

	userRoles, err := r.rdb.SMembers(r.ctx, "rbac:userroles:"+authReq.UserID).Result()
	if err != nil {
		log.Printf("redis SMembers: %v", err)
		http.Error(w, "Storage unavailable", http.StatusServiceUnavailable)
		return
	}
	authorized := false
	var userRoleNames []string

	// Check if user has any role that grants the required permission
	for _, roleID := range userRoles {
		data, err := r.rdb.HGet(r.ctx, "rbac:roles", roleID).Result()
		if err != nil {
			continue
		}
		var role Role
		if err := json.Unmarshal([]byte(data), &role); err != nil {
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

	userRoles, err := r.rdb.SMembers(r.ctx, "rbac:userroles:"+userID).Result()
	if err != nil {
		log.Printf("redis SMembers: %v", err)
		http.Error(w, "Storage unavailable", http.StatusServiceUnavailable)
		return
	}
	var roles []*Role

	for _, roleID := range userRoles {
		data, err := r.rdb.HGet(r.ctx, "rbac:roles", roleID).Result()
		if err != nil {
			continue
		}
		var role Role
		if json.Unmarshal([]byte(data), &role) == nil {
			roles = append(roles, &role)
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
	vals, err := r.rdb.HVals(r.ctx, "rbac:permissions").Result()
	if err != nil {
		log.Printf("redis HVals permissions: %v", err)
		http.Error(w, "Storage unavailable", http.StatusServiceUnavailable)
		return
	}
	permissions := make([]json.RawMessage, 0, len(vals))
	for _, v := range vals {
		permissions = append(permissions, json.RawMessage(v))
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(permissions)
}

func (r *RBACService) HealthCheck(w http.ResponseWriter, req *http.Request) {
	roleCount, _ := r.rdb.HLen(r.ctx, "rbac:roles").Result()
	permCount, _ := r.rdb.HLen(r.ctx, "rbac:permissions").Result()
	health := map[string]interface{}{
		"status":      "healthy",
		"timestamp":   time.Now().UTC(),
		"service":     "rbac-service",
		"version":     "1.0.0",
		"roles":       roleCount,
		"permissions": permCount,
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

// rbac_serviceMain was deleted: it was dead code (never called — verified by
// repo-wide grep) containing a timeout-less http.ListenAndServe. The live
// server with proper timeouts is in main.go.
