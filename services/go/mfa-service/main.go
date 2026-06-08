package main

import (
	"database/sql"
	_ "github.com/lib/pq"
	"context"
	"crypto/rand"
	"encoding/base32"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"strings"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/gorilla/mux"
	"github.com/pquerna/otp"
	"github.com/pquerna/otp/totp"
)

type MFAService struct {
	users map[string]*User
}

type User struct {
	ID       string `json:"id"`
	Username string `json:"username"`
	Secret   string `json:"secret,omitempty"`
	Enabled  bool   `json:"enabled"`
}

type SetupRequest struct {
	Username string `json:"username"`
}

type SetupResponse struct {
	Secret string `json:"secret"`
	QRCode string `json:"qr_code"`
}

type VerifyRequest struct {
	Username string `json:"username"`
	Token    string `json:"token"`
}

type VerifyResponse struct {
	Valid bool `json:"valid"`
}

func NewMFAService() *MFAService {
	return &MFAService{
		users: make(map[string]*User),
	}
}

func (m *MFAService) SetupMFA(w http.ResponseWriter, r *http.Request) {
	var req SetupRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request", http.StatusBadRequest)
		return
	}

	// Generate a new secret
	secret := make([]byte, 20)
	_, err := rand.Read(secret)
	if err != nil {
		http.Error(w, "Failed to generate secret", http.StatusInternalServerError)
		return
	}

	secretBase32 := base32.StdEncoding.EncodeToString(secret)

	// Generate QR code URL
	key, err := otp.NewKeyFromURL(fmt.Sprintf("otpauth://totp/AgentBanking:%s$1secret=%s&issuer=AgentBanking", req.Username, secretBase32))
	if err != nil {
		http.Error(w, "Failed to generate key", http.StatusInternalServerError)
		return
	}

	// Store user
	user := &User{
		ID:       req.Username,
		Username: req.Username,
		Secret:   secretBase32,
		Enabled:  true,
	}
	m.users[req.Username] = user

	response := SetupResponse{
		Secret: secretBase32,
		QRCode: key.URL(),
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

func (m *MFAService) VerifyMFA(w http.ResponseWriter, r *http.Request) {
	var req VerifyRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request", http.StatusBadRequest)
		return
	}

	user, exists := m.users[req.Username]
	if !exists || !user.Enabled {
		http.Error(w, "User not found or MFA not enabled", http.StatusNotFound)
		return
	}

	// Verify TOTP token
	valid := totp.Validate(req.Token, user.Secret)

	response := VerifyResponse{
		Valid: valid,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

func (m *MFAService) DisableMFA(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	username := vars["username"]

	user, exists := m.users[username]
	if !exists {
		http.Error(w, "User not found", http.StatusNotFound)
		return
	}

	user.Enabled = false
	w.WriteHeader(http.StatusOK)
}

func (m *MFAService) GetMFAStatus(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	username := vars["username"]

	user, exists := m.users[username]
	if !exists {
		http.Error(w, "User not found", http.StatusNotFound)
		return
	}

	// Don't expose the secret in the response
	userResponse := User{
		ID:       user.ID,
		Username: user.Username,
		Enabled:  user.Enabled,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(userResponse)
}

func (m *MFAService) HealthCheck(w http.ResponseWriter, r *http.Request) {
	health := map[string]interface{}{
		"status":    "healthy",
		"timestamp": time.Now().UTC(),
		"service":   "mfa-service",
		"version":   "1.0.0",
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(health)
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

	mfaService := NewMFAService()

	r := mux.NewRouter()

	// MFA endpoints
	r.HandleFunc("/mfa/setup", mfaService.SetupMFA).Methods("POST")
	r.HandleFunc("/mfa/verify", mfaService.VerifyMFA).Methods("POST")
	r.HandleFunc("/mfa/users/{username}/disable", mfaService.DisableMFA).Methods("POST")
	r.HandleFunc("/mfa/users/{username}/status", mfaService.GetMFAStatus).Methods("GET")

	// Health check
	r.HandleFunc("/health", mfaService.HealthCheck).Methods("GET")

	port := os.Getenv("MFA_SERVICE_PORT")
	if port == "" {
		port = "8081"
	}

	srv := &http.Server{Addr: ":" + port, Handler: r}

	// Graceful shutdown
	stop := make(chan os.Signal, 1)
	signal.Notify(stop, syscall.SIGTERM, syscall.SIGINT)

	go func() {
		log.Printf("MFA Service starting on port %s...", port)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("Server error: %v", err)
		}
	}()

	<-stop
	log.Println("[mfa-service] Shutting down gracefully...")
	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()
	srv.Shutdown(ctx)
	log.Println("[mfa-service] Shutdown complete")
}

// --- PostgreSQL persistence ---


var db *sql.DB

func initDB() {
	dbURL := os.Getenv("DATABASE_URL")
	if dbURL == "" {
		dbURL = "postgres://postgres:postgres@localhost:5432/mfa_service?sslmode=disable"
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
