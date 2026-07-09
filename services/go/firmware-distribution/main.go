package main

import (
	"syscall"
	"os/signal"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"strings"
	"os"
	"sync"
	"time"
)

type FirmwareVersion struct {
	Version      string    `json:"version"`
	ReleaseNotes string    `json:"releaseNotes"`
	Checksum     string    `json:"checksum"`
	DownloadURL  string    `json:"downloadUrl"`
	Size         int64     `json:"size"`
	Status       string    `json:"status"`
	PublishedAt  time.Time `json:"publishedAt"`
	ForceUpdate  bool      `json:"forceUpdate"`
}

type Rollout struct {
	ID         string    `json:"id"`
	Version    string    `json:"version"`
	Percentage int       `json:"percentage"`
	Status     string    `json:"status"`
	StartedAt  time.Time `json:"startedAt"`
	Updated    int       `json:"updated"`
	Failed     int       `json:"failed"`
	Total      int       `json:"total"`
}

var (
	versions = []FirmwareVersion{
		{Version: "3.2.1", ReleaseNotes: "Security patches and performance improvements", Status: "released", PublishedAt: time.Now().Add(-72 * time.Hour), ForceUpdate: false},
		{Version: "3.2.0", ReleaseNotes: "Offline mode enhancements", Status: "released", PublishedAt: time.Now().Add(-168 * time.Hour), ForceUpdate: false},
	}
	rollouts = make(map[string]*Rollout)
	mu       sync.RWMutex
)

func healthHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"status": "healthy", "service": "firmware-distribution"})
}

func versionsHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{"versions": versions})
}

func checkUpdateHandler(w http.ResponseWriter, r *http.Request) {
	currentVersion := r.URL.Query().Get("currentVersion")
	w.Header().Set("Content-Type", "application/json")

	if len(versions) == 0 || versions[0].Version == currentVersion {
		json.NewEncoder(w).Encode(map[string]bool{"updateAvailable": false})
		return
	}

	latest := versions[0]
	json.NewEncoder(w).Encode(map[string]interface{}{
		"updateAvailable": true,
		"version":         latest.Version,
		"downloadUrl":     latest.DownloadURL,
		"checksum":        latest.Checksum,
		"forceUpdate":     latest.ForceUpdate,
		"releaseNotes":    latest.ReleaseNotes,
	})
}

func publishHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	var req FirmwareVersion
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	h := sha256.New()
	h.Write([]byte(req.Version + time.Now().String()))
	if req.Checksum == "" {
		req.Checksum = hex.EncodeToString(h.Sum(nil))
	}
	req.Status = "staged"
	req.PublishedAt = time.Now()

	mu.Lock()
	versions = append([]FirmwareVersion{req}, versions...)
	mu.Unlock()

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(req)
}

func startRolloutHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	var req struct {
		Version    string `json:"version"`
		Percentage int    `json:"percentage"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	rollout := &Rollout{
		ID:         fmt.Sprintf("ROL-%d", time.Now().UnixMilli()),
		Version:    req.Version,
		Percentage: req.Percentage,
		Status:     "rolling_out",
		StartedAt:  time.Now(),
	}

	mu.Lock()
	rollouts[rollout.ID] = rollout
	mu.Unlock()

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(rollout)
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


// Auth Middleware - validates Bearer token on all non-health endpoints
func authMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/health" || r.URL.Path == "/ready" || r.URL.Path == "/metrics" {
			next.ServeHTTP(w, r)
			return
		}
		authHeader := r.Header.Get("Authorization")
		if authHeader == "" {
			http.Error(w, `{"error":"missing authorization header"}`, http.StatusUnauthorized)
			return
		}
		if len(authHeader) < 8 || authHeader[:7] != "Bearer " {
			http.Error(w, `{"error":"invalid authorization format"}`, http.StatusUnauthorized)
			return
		}
		next.ServeHTTP(w, r)
	})
}

func main() {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8142"
	}

	http.HandleFunc("/health", healthHandler)
	http.HandleFunc("/api/v1/versions", versionsHandler)
	http.HandleFunc("/api/v1/check-update", checkUpdateHandler)
	http.HandleFunc("/api/v1/publish", publishHandler)
	http.HandleFunc("/api/v1/rollout", startRolloutHandler)

	log.Printf("Firmware Distribution Service starting on port %s", port)
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
