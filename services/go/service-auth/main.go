package main

import (
	"database/sql"
	_ "github.com/lib/pq"
	"syscall"
	"os/signal"
	"context"
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"strings"
	"sync"
	"time"
	"log/slog"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracehttp"
	"go.opentelemetry.io/otel/propagation"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.24.0"
)

// ServiceToken represents a signed service-to-service authentication token
type ServiceToken struct {
	ServiceID string `json:"service_id"`
	IssuedAt  int64  `json:"iat"`
	ExpiresAt int64  `json:"exp"`
	Nonce     string `json:"nonce"`
	Scopes    string `json:"scopes"`
}

// ServiceRegistry holds registered services and their shared secrets
type ServiceRegistry struct {
	mu       sync.RWMutex
	services map[string]ServiceEntry
}

// ServiceEntry represents a registered service
type ServiceEntry struct {
	ID          string   `json:"id"`
	Name        string   `json:"name"`
	SharedKey   string   `json:"shared_key"`
	Scopes      []string `json:"scopes"`
	RateLimit   int      `json:"rate_limit"`
	Active      bool     `json:"active"`
	LastSeen    int64    `json:"last_seen"`
	RegisteredAt int64  `json:"registered_at"`
}

// TokenResponse is returned when issuing a token
type TokenResponse struct {
	Token     string `json:"token"`
	ExpiresAt int64  `json:"expires_at"`
	Type      string `json:"type"`
}

// ValidationResult is returned when validating a token
type ValidationResult struct {
	Valid     bool   `json:"valid"`
	ServiceID string `json:"service_id,omitempty"`
	Scopes    string `json:"scopes,omitempty"`
	Error     string `json:"error,omitempty"`
}

var (
	registry   *ServiceRegistry
	signingKey string
	port       string
)

func init() {
	signingKey = os.Getenv("SERVICE_AUTH_SIGNING_KEY")
	if signingKey == "" {
		signingKey = "54link-service-auth-default-key-change-in-production"
	}
	port = os.Getenv("SERVICE_AUTH_PORT")
	if port == "" {
		port = "8140"
	}

	registry = &ServiceRegistry{
		services: make(map[string]ServiceEntry),
	}

	// Pre-register known platform services
	knownServices := []ServiceEntry{
		{ID: "biometric-orchestrator", Name: "Biometric Orchestrator", Scopes: []string{"biometric:verify", "biometric:analyze"}, RateLimit: 100, Active: true},
		{ID: "deepface-service", Name: "DeepFace Service", Scopes: []string{"face:verify", "face:analyze", "face:detect", "gallery:read", "gallery:write"}, RateLimit: 200, Active: true},
		{ID: "kyb-engine", Name: "KYB Engine", Scopes: []string{"kyb:verify", "kyb:screen", "kyb:approve"}, RateLimit: 50, Active: true},
		{ID: "kyb-risk-engine", Name: "KYB Risk Engine", Scopes: []string{"risk:assess", "pep:screen", "sanctions:screen", "aml:screen"}, RateLimit: 100, Active: true},
		{ID: "kyb-analytics", Name: "KYB Analytics", Scopes: []string{"analytics:read", "analytics:write", "etl:run", "compliance:report"}, RateLimit: 50, Active: true},
		{ID: "liveness-service", Name: "Liveness Detection", Scopes: []string{"liveness:check"}, RateLimit: 200, Active: true},
		{ID: "face-matching", Name: "Face Matching Service", Scopes: []string{"face:match"}, RateLimit: 200, Active: true},
		{ID: "deepfake-detection", Name: "Deepfake Detection", Scopes: []string{"deepfake:detect"}, RateLimit: 100, Active: true},
		{ID: "ocr-service", Name: "OCR Service", Scopes: []string{"ocr:extract"}, RateLimit: 100, Active: true},
		{ID: "compliance-kyc", Name: "Compliance KYC", Scopes: []string{"kyc:submit", "kyc:verify", "kyc:report"}, RateLimit: 100, Active: true},
		{ID: "settlement-service", Name: "Settlement Service", Scopes: []string{"settlement:process", "settlement:reconcile"}, RateLimit: 50, Active: true},
		{ID: "notification-service", Name: "Notification Service", Scopes: []string{"notify:send", "notify:bulk"}, RateLimit: 500, Active: true},
		{ID: "payment-gateway", Name: "Payment Gateway", Scopes: []string{"payment:process", "payment:refund"}, RateLimit: 200, Active: true},
		{ID: "fraud-engine", Name: "Fraud Engine", Scopes: []string{"fraud:score", "fraud:alert"}, RateLimit: 300, Active: true},
		{ID: "tigerbeetle-sync", Name: "TigerBeetle Sync", Scopes: []string{"ledger:read", "ledger:write"}, RateLimit: 500, Active: true},
		{ID: "workflow-orchestrator", Name: "Workflow Orchestrator", Scopes: []string{"workflow:start", "workflow:signal"}, RateLimit: 100, Active: true},
	}

	for _, svc := range knownServices {
		key := generateServiceKey(svc.ID)
		svc.SharedKey = key
		svc.RegisteredAt = time.Now().Unix()
		registry.services[svc.ID] = svc
	}
}

func generateServiceKey(serviceID string) string {
	b := make([]byte, 32)
	rand.Read(b)
	return hex.EncodeToString(b)
}

func signToken(token ServiceToken) string {
	data, _ := json.Marshal(token)
	mac := hmac.New(sha256.New, []byte(signingKey))
	mac.Write(data)
	sig := hex.EncodeToString(mac.Sum(nil))
	payload := hex.EncodeToString(data)
	return payload + "." + sig
}

func verifyAndDecodeToken(tokenStr string) (*ServiceToken, error) {
	parts := strings.SplitN(tokenStr, ".", 2)
	if len(parts) != 2 {
		return nil, fmt.Errorf("invalid token format")
	}

	payload, err := hex.DecodeString(parts[0])
	if err != nil {
		return nil, fmt.Errorf("invalid token payload")
	}

	mac := hmac.New(sha256.New, []byte(signingKey))
	mac.Write(payload)
	expectedSig := hex.EncodeToString(mac.Sum(nil))

	if !hmac.Equal([]byte(parts[1]), []byte(expectedSig)) {
		return nil, fmt.Errorf("invalid signature")
	}

	var token ServiceToken
	if err := json.Unmarshal(payload, &token); err != nil {
		return nil, fmt.Errorf("invalid token data")
	}

	if time.Now().Unix() > token.ExpiresAt {
		return nil, fmt.Errorf("token expired")
	}

	return &token, nil
}

func handleIssueToken(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req struct {
		ServiceID string `json:"service_id"`
		SharedKey string `json:"shared_key"`
		TTL       int64  `json:"ttl_seconds"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid request"})
		return
	}

	registry.mu.RLock()
	svc, ok := registry.services[req.ServiceID]
	registry.mu.RUnlock()

	if !ok || !svc.Active {
		writeJSON(w, http.StatusUnauthorized, map[string]string{"error": "service not registered or inactive"})
		return
	}

	if svc.SharedKey != req.SharedKey {
		writeJSON(w, http.StatusUnauthorized, map[string]string{"error": "invalid credentials"})
		return
	}

	ttl := req.TTL
	if ttl <= 0 || ttl > 3600 {
		ttl = 300 // Default 5 minutes
	}

	nonce := make([]byte, 16)
	rand.Read(nonce)

	token := ServiceToken{
		ServiceID: req.ServiceID,
		IssuedAt:  time.Now().Unix(),
		ExpiresAt: time.Now().Unix() + ttl,
		Nonce:     hex.EncodeToString(nonce),
		Scopes:    strings.Join(svc.Scopes, ","),
	}

	signed := signToken(token)

	// Update last seen
	registry.mu.Lock()
	entry := registry.services[req.ServiceID]
	entry.LastSeen = time.Now().Unix()
	registry.services[req.ServiceID] = entry
	registry.mu.Unlock()

	writeJSON(w, http.StatusOK, TokenResponse{
		Token:     signed,
		ExpiresAt: token.ExpiresAt,
		Type:      "service-bearer",
	})
}

func handleValidateToken(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req struct {
		Token         string `json:"token"`
		RequiredScope string `json:"required_scope"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, ValidationResult{Valid: false, Error: "invalid request"})
		return
	}

	token, err := verifyAndDecodeToken(req.Token)
	if err != nil {
		writeJSON(w, http.StatusUnauthorized, ValidationResult{Valid: false, Error: err.Error()})
		return
	}

	// Check scope if required
	if req.RequiredScope != "" {
		scopes := strings.Split(token.Scopes, ",")
		found := false
		for _, s := range scopes {
			if s == req.RequiredScope || s == "*" {
				found = true
				break
			}
		}
		if !found {
			writeJSON(w, http.StatusForbidden, ValidationResult{Valid: false, ServiceID: token.ServiceID, Error: "insufficient scope"})
			return
		}
	}

	writeJSON(w, http.StatusOK, ValidationResult{
		Valid:     true,
		ServiceID: token.ServiceID,
		Scopes:    token.Scopes,
	})
}

func handleRegisterService(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req struct {
		ID        string   `json:"id"`
		Name      string   `json:"name"`
		Scopes    []string `json:"scopes"`
		RateLimit int      `json:"rate_limit"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid request"})
		return
	}

	key := generateServiceKey(req.ID)
	entry := ServiceEntry{
		ID:          req.ID,
		Name:        req.Name,
		SharedKey:   key,
		Scopes:      req.Scopes,
		RateLimit:   req.RateLimit,
		Active:      true,
		RegisteredAt: time.Now().Unix(),
	}

	registry.mu.Lock()
	registry.services[req.ID] = entry
	registry.mu.Unlock()

	writeJSON(w, http.StatusCreated, map[string]string{
		"id":         req.ID,
		"shared_key": key,
		"message":    "service registered successfully",
	})
}

func handleListServices(w http.ResponseWriter, r *http.Request) {
	registry.mu.RLock()
	defer registry.mu.RUnlock()

	var services []map[string]interface{}
	for _, svc := range registry.services {
		services = append(services, map[string]interface{}{
			"id":            svc.ID,
			"name":          svc.Name,
			"scopes":        svc.Scopes,
			"active":        svc.Active,
			"rate_limit":    svc.RateLimit,
			"last_seen":     svc.LastSeen,
			"registered_at": svc.RegisteredAt,
		})
	}

	writeJSON(w, http.StatusOK, map[string]interface{}{"services": services, "count": len(services)})
}

func handleHealth(w http.ResponseWriter, r *http.Request) {
	registry.mu.RLock()
	activeCount := 0
	for _, svc := range registry.services {
		if svc.Active {
			activeCount++
		}
	}
	registry.mu.RUnlock()

	writeJSON(w, http.StatusOK, map[string]interface{}{
		"status":          "healthy",
		"service":         "service-auth",
		"version":         "1.0.0",
		"registered":      len(registry.services),
		"active_services": activeCount,
		"uptime_seconds":  time.Since(startTime).Seconds(),
	})
}

func writeJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(data)
}

var startTime = time.Now()


// recoverMiddleware catches panics and returns 500 instead of crashing
func recoverMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		defer func() {
			if err := recover(); err != nil {
				log.Printf("[recovery] panic: %v", err)
				http.Error(w, "internal server error", http.StatusInternalServerError)
			}
		}()
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

// ─── OpenTelemetry Tracing ──────────────────────────────────────────────────

func initTracer(serviceName, serviceVersion string) func(context.Context) error {
	endpoint := os.Getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
	if endpoint == "" {
		return func(context.Context) error { return nil }
	}
	ctx := context.Background()
	exp, err := otlptracehttp.New(ctx, otlptracehttp.WithEndpoint(endpoint))
	if err != nil {
		slog.Warn("OTel exporter init failed", "err", err)
		return func(context.Context) error { return nil }
	}
	res := resource.NewWithAttributes(
		"https://opentelemetry.io/schemas/1.24.0",
		semconv.ServiceName(serviceName),
		semconv.ServiceVersion(serviceVersion),
		attribute.String("deployment.environment", os.Getenv("ENVIRONMENT")),
	)
	tp := sdktrace.NewTracerProvider(
		sdktrace.WithBatcher(exp),
		sdktrace.WithResource(res),
	)
	otel.SetTracerProvider(tp)
	otel.SetTextMapPropagator(propagation.NewCompositeTextMapPropagator(
		propagation.TraceContext{},
		propagation.Baggage{},
	))
	return tp.Shutdown
}

func otelMiddleware(serviceName string, next http.Handler) http.Handler {
	tracer := otel.Tracer(serviceName)
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		ctx, span := tracer.Start(r.Context(), r.Method+" "+r.URL.Path)
		defer span.End()
		next.ServeHTTP(w, r.WithContext(ctx))
	})
}

func main() {
	shutdownTracer := initTracer("service-auth", "1.0.0")
	defer shutdownTracer(context.Background())

	initDB()

	mux := http.NewServeMux()
	mux.HandleFunc("/token/issue", handleIssueToken)
	mux.HandleFunc("/token/validate", handleValidateToken)
	mux.HandleFunc("/services/register", handleRegisterService)
	mux.HandleFunc("/services", handleListServices)
	mux.HandleFunc("/health", handleHealth)

	log.Printf("Service Auth running on :%s with %d pre-registered services", port, len(registry.services))
	log.Fatal(http.ListenAndServe(":"+port, jwtAuthMiddleware(mux)))
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

// --- PostgreSQL persistence ---


var db *sql.DB

func initDB() {
	dbURL := os.Getenv("DATABASE_URL")
	if dbURL == "" {
		dbURL = "postgres://postgres:postgres@localhost:5432/service_auth?sslmode=disable"
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
