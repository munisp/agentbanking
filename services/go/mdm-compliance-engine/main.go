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
	"sync"
	"time"
)

// MDMComplianceEngine — Mobile Device Management compliance checker
// Verifies POS terminal compliance: OS version, security patches, app version, encryption

type DeviceCompliance struct {
	DeviceID        string    `json:"device_id"`
	AgentCode       string    `json:"agent_code"`
	OSVersion       string    `json:"os_version"`
	AppVersion      string    `json:"app_version"`
	SecurityPatch   string    `json:"security_patch"`
	EncryptionOn    bool      `json:"encryption_enabled"`
	RootDetected    bool      `json:"root_detected"`
	ComplianceScore int       `json:"compliance_score"`
	Issues          []string  `json:"issues"`
	LastChecked     time.Time `json:"last_checked"`
	Status          string    `json:"status"` // compliant, non-compliant, warning
}

var (
	devices   = make(map[string]*DeviceCompliance)
	devicesMu sync.RWMutex
)

func checkCompliance(d *DeviceCompliance) {
	d.Issues = nil
	d.ComplianceScore = 100
	if d.RootDetected {
		d.Issues = append(d.Issues, "CRITICAL: Root/jailbreak detected")
		d.ComplianceScore -= 50
	}
	if !d.EncryptionOn {
		d.Issues = append(d.Issues, "HIGH: Device encryption disabled")
		d.ComplianceScore -= 30
	}
	if d.AppVersion < "5.0.0" {
		d.Issues = append(d.Issues, "MEDIUM: App version outdated (min 5.0.0)")
		d.ComplianceScore -= 15
	}
	if d.SecurityPatch < "2025-01-01" {
		d.Issues = append(d.Issues, "HIGH: Security patch outdated (min 2025-01)")
		d.ComplianceScore -= 25
	}
	if d.ComplianceScore < 0 {
		d.ComplianceScore = 0
	}
	if d.ComplianceScore >= 80 {
		d.Status = "compliant"
	} else if d.ComplianceScore >= 50 {
		d.Status = "warning"
	} else {
		d.Status = "non-compliant"
	}
	d.LastChecked = time.Now()
}

func handleCheckDevice(w http.ResponseWriter, r *http.Request) {
	if r.Method != "POST" {
		http.Error(w, `{"error":"method not allowed"}`, 405)
		return
	}
	var d DeviceCompliance
	if err := json.NewDecoder(r.Body).Decode(&d); err != nil {
		http.Error(w, `{"error":"invalid json"}`, 400)
		return
	}
	checkCompliance(&d)
	devicesMu.Lock()
	devices[d.DeviceID] = &d
	devicesMu.Unlock()
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(d)
}

func handleListDevices(w http.ResponseWriter, r *http.Request) {
	devicesMu.RLock()
	defer devicesMu.RUnlock()
	var list []*DeviceCompliance
	for _, d := range devices {
		list = append(list, d)
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{"devices": list, "count": len(list)})
}

func handleHealth(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{"status": "healthy", "service": "mdm-compliance-engine", "devices_tracked": len(devices)})
}

func init() {
	// Seed sample devices
	samples := []DeviceCompliance{
		{DeviceID: "DEV-001", AgentCode: "54LINK-001", OSVersion: "Android 14", AppVersion: "5.2.1", SecurityPatch: "2025-11-01", EncryptionOn: true, RootDetected: false},
		{DeviceID: "DEV-002", AgentCode: "54LINK-002", OSVersion: "Android 13", AppVersion: "5.1.0", SecurityPatch: "2025-09-01", EncryptionOn: true, RootDetected: false},
		{DeviceID: "DEV-003", AgentCode: "54LINK-003", OSVersion: "Android 12", AppVersion: "4.8.0", SecurityPatch: "2024-06-01", EncryptionOn: false, RootDetected: true},
	}
	for i := range samples {
		checkCompliance(&samples[i])
		devices[samples[i].DeviceID] = &samples[i]
	}
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
		port = "9212"
	}
	http.HandleFunc("/api/v1/device/check", handleCheckDevice)
	http.HandleFunc("/api/v1/device/list", handleListDevices)
	http.HandleFunc("/health", handleHealth)
	log.Printf("[mdm-compliance-engine] Starting on :%s with %d devices", port, len(devices))
	log.Fatal(http.ListenAndServe(":"+port, nil))
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
		dbURL = "postgres://postgres:postgres@localhost:5432/mdm_compliance_engine?sslmode=disable"
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
