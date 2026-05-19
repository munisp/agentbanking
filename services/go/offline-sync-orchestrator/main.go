package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"sync"
	"time"
)

type SyncSession struct {
	SessionID   string     `json:"sessionId"`
	AgentID     int        `json:"agentId"`
	DeviceToken string     `json:"deviceToken"`
	Status      string     `json:"status"`
	TxCount     int        `json:"txCount"`
	Synced      int        `json:"synced"`
	Failed      int        `json:"failed"`
	StartedAt   time.Time  `json:"startedAt"`
	CompletedAt *time.Time `json:"completedAt,omitempty"`
}

var (
	sessions = make(map[string]*SyncSession)
	mu       sync.RWMutex
)

func healthHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"status": "healthy", "service": "offline-sync-orchestrator"})
}

func startSyncHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	var req struct {
		SessionID   string `json:"sessionId"`
		AgentID     int    `json:"agentId"`
		DeviceToken string `json:"deviceToken"`
		TxCount     int    `json:"txCount"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	session := &SyncSession{
		SessionID:   req.SessionID,
		AgentID:     req.AgentID,
		DeviceToken: req.DeviceToken,
		Status:      "syncing",
		TxCount:     req.TxCount,
		StartedAt:   time.Now(),
	}

	mu.Lock()
	sessions[req.SessionID] = session
	mu.Unlock()

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(session)
}

func statusHandler(w http.ResponseWriter, r *http.Request) {
	sessionID := r.URL.Query().Get("sessionId")
	mu.RLock()
	session, ok := sessions[sessionID]
	mu.RUnlock()
	if !ok {
		http.Error(w, "Session not found", http.StatusNotFound)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(session)
}

func completeSyncHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	var req struct {
		SessionID string `json:"sessionId"`
		Synced    int    `json:"synced"`
		Failed    int    `json:"failed"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	mu.Lock()
	if session, ok := sessions[req.SessionID]; ok {
		session.Status = "completed"
		session.Synced = req.Synced
		session.Failed = req.Failed
		now := time.Now()
		session.CompletedAt = &now
	}
	mu.Unlock()

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"status": "completed"})
}

func main() {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8140"
	}

	http.HandleFunc("/health", healthHandler)
	http.HandleFunc("/api/v1/sync/start", startSyncHandler)
	http.HandleFunc("/api/v1/sync/status", statusHandler)
	http.HandleFunc("/api/v1/sync/complete", completeSyncHandler)

	log.Printf("Offline Sync Orchestrator starting on port %s", port)
	log.Fatal(http.ListenAndServe(fmt.Sprintf(":%s", port), nil))
}
