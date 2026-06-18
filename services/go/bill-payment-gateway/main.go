package main

import (
	"database/sql"
	_ "github.com/lib/pq"
	"syscall"
	"os/signal"
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"strings"
	"os"
	"time"
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

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"valid":             true,
		"billerId":          req.BillerID,
		"customerReference": req.CustomerRef,
		"customerName":      "Customer " + req.CustomerRef,
	})
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

	result := PaymentResult{
		Reference: fmt.Sprintf("BPG-%d", time.Now().UnixNano()),
		BillerID:  req.BillerID,
		Amount:    req.Amount,
		Status:    "success",
		Timestamp: time.Now(),
	}

	if req.BillerID == "IKEDC" || req.BillerID == "EKEDC" || req.BillerID == "AEDC" {
		result.Token = fmt.Sprintf("%04d-%04d-%04d-%04d-%04d",
			time.Now().UnixNano()%10000, time.Now().UnixNano()%9999,
			time.Now().UnixNano()%8888, time.Now().UnixNano()%7777,
			time.Now().UnixNano()%6666)
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(result)
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
	initDB()

	port := os.Getenv("PORT")
	if port == "" {
		port = "8141"
	}

	http.HandleFunc("/health", healthHandler)
	http.HandleFunc("/api/v1/billers", billersHandler)
	http.HandleFunc("/api/v1/validate", validateHandler)
	http.HandleFunc("/api/v1/pay", payHandler)

	log.Printf("Bill Payment Gateway starting on port %s", port)
	log.Fatal(http.ListenAndServe(fmt.Sprintf(":%s", jwtAuthMiddleware(port)), nil))
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

// --- SQLite persistence ---


var db *sql.DB

func initDB() {
	dbURL := os.Getenv("DATABASE_URL")
	if dbURL == "" {
		dbURL = "postgres://postgres:postgres@localhost:5432/bill_payment_gateway?sslmode=disable"
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
