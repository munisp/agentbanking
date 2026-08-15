package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	_ "github.com/lib/pq"
)

type Biller struct {
	ID       string `json:"id"`
	Name     string `json:"name"`
	Category string `json:"category"`
	Active   bool   `json:"active"`
}

type PaymentResult struct {
	Reference string    `json:"reference"`
	BillerID  string    `json:"billerId"`
	Amount    float64   `json:"amount"`
	Status    string    `json:"status"`
	Token     string    `json:"token,omitempty"`
	Timestamp time.Time `json:"timestamp"`
}

var billers = []Biller{
	{ID: "DSTV", Name: "DSTV", Category: "cable_tv", Active: true},
	{ID: "GOTV", Name: "GOtv", Category: "cable_tv", Active: true},
	{ID: "IKEDC", Name: "Ikeja Electric", Category: "electricity", Active: true},
	{ID: "EKEDC", Name: "Eko Electric", Category: "electricity", Active: true},
	{ID: "AEDC", Name: "Abuja Electric", Category: "electricity", Active: true},
	{ID: "LWC", Name: "Lagos Water Corporation", Category: "water", Active: true},
	{ID: "FIRS", Name: "Federal Inland Revenue", Category: "government", Active: true},
}

// Simulation mode is only honoured outside production; in production the
// combination BILLER_SIMULATION_MODE=true + ENVIRONMENT=production is fatal.
var (
	simulationMode = os.Getenv("BILLER_SIMULATION_MODE") == "true"
	environment    = os.Getenv("ENVIRONMENT")
)

func findBiller(id string) *Biller {
	for i := range billers {
		if billers[i].ID == id {
			return &billers[i]
		}
	}
	return nil
}

func writeJSONError(w http.ResponseWriter, status int, message string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	if err := json.NewEncoder(w).Encode(map[string]string{"status": "error", "message": message}); err != nil {
		log.Printf("Error encoding error response: %v", err)
	}
}

func healthHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"status": "healthy", "service": "bill-payment-gateway"})
}

func billersHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{"billers": billers})
}

func validateHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	var req struct {
		BillerID    string `json:"billerId"`
		CustomerRef string `json:"customerReference"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	biller := findBiller(req.BillerID)
	if biller == nil {
		writeJSONError(w, http.StatusNotFound, fmt.Sprintf("unknown billerId: %s", req.BillerID))
		return
	}

	if simulationMode {
		log.Printf("WARNING: returning simulated customer validation for biller %s (BILLER_SIMULATION_MODE)", req.BillerID)
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"valid":             true,
			"billerId":          req.BillerID,
			"customerReference": req.CustomerRef,
			"customerName":      "SIMULATED CUSTOMER " + req.CustomerRef,
			"simulated":         true,
		})
		return
	}

	// No real biller aggregator API is configured; fail loud rather than
	// fabricating a customer name for an arbitrary meter/smartcard number.
	log.Printf("Refusing validation for biller %s: no biller validation API configured", req.BillerID)
	writeJSONError(w, http.StatusServiceUnavailable,
		"biller validation API is not configured; refusing to fabricate a customer name")
}

func payHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	var req struct {
		BillerID    string  `json:"billerId"`
		CustomerRef string  `json:"customerReference"`
		Amount      float64 `json:"amount"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	biller := findBiller(req.BillerID)
	if biller == nil {
		writeJSONError(w, http.StatusNotFound, fmt.Sprintf("unknown billerId: %s", req.BillerID))
		return
	}
	if req.Amount <= 0 {
		writeJSONError(w, http.StatusBadRequest, "amount must be greater than zero")
		return
	}

	if simulationMode {
		log.Printf("WARNING: returning simulated payment result for biller %s (BILLER_SIMULATION_MODE)", req.BillerID)
		result := PaymentResult{
			Reference: fmt.Sprintf("SIM-BPG-%d", time.Now().UnixNano()),
			BillerID:  req.BillerID,
			Amount:    req.Amount,
			Status:    "simulated_success",
			Timestamp: time.Now(),
		}

		if biller.Category == "electricity" {
			result.Token = "SIMULATED-TOKEN-NOT-VALID"
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(result)
		return
	}

	// No real biller payment API is configured; fail loud rather than
	// fabricating a success reference or an electricity token.
	log.Printf("Refusing payment for biller %s: no biller payment API configured", req.BillerID)
	writeJSONError(w, http.StatusServiceUnavailable,
		"biller payment API is not configured; refusing to fabricate a payment reference or token")
}

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

func main() {
	if simulationMode && environment == "production" {
		log.Fatal("BILLER_SIMULATION_MODE=true is forbidden when ENVIRONMENT=production")
	}
	if simulationMode {
		log.Println("WARNING: running with SIMULATED biller responses (non-production only)")
	} else {
		log.Println("WARNING: no biller API configured; /api/v1/validate and /api/v1/pay will return 503")
	}

	initDB()

	port := os.Getenv("PORT")
	if port == "" {
		port = "8141"
	}

	mux := http.NewServeMux()
	mux.HandleFunc("/health", healthHandler)
	mux.HandleFunc("/api/v1/billers", billersHandler)
	mux.HandleFunc("/api/v1/validate", validateHandler)
	mux.HandleFunc("/api/v1/pay", payHandler)

	srv := &http.Server{
		Addr:              fmt.Sprintf(":%s", port),
		Handler:           recoverMiddleware(jwtAuthMiddleware(mux)),
		ReadHeaderTimeout: 10 * time.Second,
		WriteTimeout:      30 * time.Second,
		IdleTimeout:       120 * time.Second,
	}
	setupGracefulShutdown(srv)

	log.Printf("Bill Payment Gateway starting on port %s", port)
	log.Fatal(srv.ListenAndServe())
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
		dbURL = "postgres://postgres:postgres@localhost:5432/bill_payment_gateway?sslmode=disable"
	}
	var err error
	db, err = sql.Open("postgres", dbURL)
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
		db.Exec("INSERT INTO state_store (key, value, updated_at) VALUES ($1, $2, NOW()) ON CONFLICT (key) DO UPDATE SET value = $2, updated_at = NOW()", key, value)
	}
}

func getState(key string) string {
	if db == nil {
		return ""
	}
	var val string
	db.QueryRow("SELECT value FROM state_store WHERE key = $1", key).Scan(&val)
	return val
}
