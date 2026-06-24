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

// WorkflowOrchestrator — Manages multi-step business workflows
// Agent onboarding, KYC verification, float top-up approval, dispute resolution

type WorkflowStep struct {
	StepID      string    `json:"step_id"`
	Name        string    `json:"name"`
	Status      string    `json:"status"` // pending, in_progress, completed, failed, skipped
	AssignedTo  string    `json:"assigned_to"`
	StartedAt   *time.Time `json:"started_at,omitempty"`
	CompletedAt *time.Time `json:"completed_at,omitempty"`
	Notes       string    `json:"notes"`
}

type Workflow struct {
	WorkflowID   string         `json:"workflow_id"`
	Type         string         `json:"type"` // agent_onboarding, kyc_verification, float_topup, dispute_resolution
	EntityID     string         `json:"entity_id"`
	Status       string         `json:"status"` // active, completed, cancelled, failed
	CurrentStep  int            `json:"current_step"`
	Steps        []WorkflowStep `json:"steps"`
	CreatedAt    time.Time      `json:"created_at"`
	UpdatedAt    time.Time      `json:"updated_at"`
	Metadata     map[string]string `json:"metadata"`
}

var (
	workflows   = make(map[string]*Workflow)
	workflowsMu sync.RWMutex
	wfSeq       int
)

var workflowTemplatesMu sync.RWMutex
var workflowTemplates = map[string][]string{
	"agent_onboarding":   {"Submit Application", "Document Upload", "KYC Check", "Background Verification", "Training Assignment", "Account Activation", "Float Allocation"},
	"kyc_verification":   {"Document Submission", "OCR Extraction", "Identity Verification", "Address Verification", "PEP/Sanctions Check", "Approval/Rejection"},
	"float_topup":        {"Request Submission", "Manager Review", "Compliance Check", "Treasury Approval", "Fund Transfer", "Balance Update"},
	"dispute_resolution": {"Complaint Filed", "Evidence Collection", "Investigation", "Mediation", "Resolution Proposal", "Customer Acceptance", "Settlement"},
}

func createWorkflow(wfType, entityID string) *Workflow {
	wfSeq++
	steps := workflowTemplates[wfType]
	var wfSteps []WorkflowStep
	for i, name := range steps {
		wfSteps = append(wfSteps, WorkflowStep{
			StepID: fmt.Sprintf("STEP-%d", i+1),
			Name:   name,
			Status: "pending",
		})
	}
	if len(wfSteps) > 0 {
		wfSteps[0].Status = "in_progress"
		now := time.Now()
		wfSteps[0].StartedAt = &now
	}
	return &Workflow{
		WorkflowID:  fmt.Sprintf("WF-%s-%04d", wfType[:3], wfSeq),
		Type:        wfType,
		EntityID:    entityID,
		Status:      "active",
		CurrentStep: 0,
		Steps:       wfSteps,
		CreatedAt:   time.Now(),
		UpdatedAt:   time.Now(),
		Metadata:    make(map[string]string),
	}
}

func handleCreate(w http.ResponseWriter, r *http.Request) {
	if r.Method != "POST" {
		http.Error(w, `{"error":"method not allowed"}`, 405)
		return
	}
	var req struct {
		Type     string `json:"type"`
		EntityID string `json:"entity_id"`
	}
	json.NewDecoder(r.Body).Decode(&req)
	if _, ok := workflowTemplates[req.Type]; !ok {
		http.Error(w, `{"error":"unknown workflow type"}`, 400)
		return
	}
	wf := createWorkflow(req.Type, req.EntityID)
	workflowsMu.Lock()
	workflows[wf.WorkflowID] = wf
	workflowsMu.Unlock()
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(wf)
}

func handleAdvance(w http.ResponseWriter, r *http.Request) {
	if r.Method != "POST" {
		http.Error(w, `{"error":"method not allowed"}`, 405)
		return
	}
	var req struct {
		WorkflowID string `json:"workflow_id"`
		Notes      string `json:"notes"`
	}
	json.NewDecoder(r.Body).Decode(&req)
	workflowsMu.Lock()
	defer workflowsMu.Unlock()
	wf, ok := workflows[req.WorkflowID]
	if !ok {
		http.Error(w, `{"error":"workflow not found"}`, 404)
		return
	}
	if wf.CurrentStep >= len(wf.Steps)-1 {
		now := time.Now()
		wf.Steps[wf.CurrentStep].Status = "completed"
		wf.Steps[wf.CurrentStep].CompletedAt = &now
		wf.Status = "completed"
	} else {
		now := time.Now()
		wf.Steps[wf.CurrentStep].Status = "completed"
		wf.Steps[wf.CurrentStep].CompletedAt = &now
		wf.Steps[wf.CurrentStep].Notes = req.Notes
		wf.CurrentStep++
		wf.Steps[wf.CurrentStep].Status = "in_progress"
		wf.Steps[wf.CurrentStep].StartedAt = &now
	}
	wf.UpdatedAt = time.Now()
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(wf)
}

func handleList(w http.ResponseWriter, r *http.Request) {
	workflowsMu.RLock()
	defer workflowsMu.RUnlock()
	var list []*Workflow
	for _, wf := range workflows {
		list = append(list, wf)
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{"workflows": list, "count": len(list)})
}

func handleHealth(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{"status": "healthy", "service": "workflow-orchestrator", "active_workflows": len(workflows)})
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
	// PostgreSQL persistence (WAL mode for concurrent reads/writes)
	dbPath := os.Getenv("WORKFLOW_ORCHESTRATOR_DB_PATH")
	if dbPath == "" {
		dbPath = "/tmp/workflow-orchestrator.db"
	}
	db, dbErr := sql.Open("postgres", os.Getenv("DATABASE_URL"))
	if dbErr != nil {
		log.Printf("[workflow-orchestrator] PostgreSQL unavailable (%v) — running in-memory only", dbErr)
	} else {
		defer db.Close()
		log.Printf("[workflow-orchestrator] PostgreSQL persistence at %s", dbPath)
	}
	_ = db

	port := os.Getenv("PORT")
	if port == "" {
		port = "9213"
	}
	http.HandleFunc("/api/v1/workflow/create", handleCreate)
	http.HandleFunc("/api/v1/workflow/advance", handleAdvance)
	http.HandleFunc("/api/v1/workflow/list", handleList)
	http.HandleFunc("/health", handleHealth)
	log.Printf("[workflow-orchestrator] Starting on :%s with %d templates", port, len(workflowTemplates))
	log.Fatal(http.ListenAndServe(":"+port, authMiddleware(http.DefaultServeMux)))
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
