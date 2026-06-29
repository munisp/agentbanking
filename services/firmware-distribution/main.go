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
	log.Fatal(http.ListenAndServe(fmt.Sprintf(":%s", port), nil))
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
