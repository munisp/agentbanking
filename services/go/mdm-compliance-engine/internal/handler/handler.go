// Package handler provides HTTP handlers for the MDM Compliance Engine.
package handler

import (
	"encoding/json"
	"log"
	"net/http"
	"time"

	"github.com/54link/mdm-compliance-engine/internal/evaluator"
	"github.com/54link/mdm-compliance-engine/internal/enforcer"
	"github.com/54link/mdm-compliance-engine/internal/models"
)

// Handler holds dependencies for HTTP handlers.
type Handler struct {
	Evaluator *evaluator.Evaluator
	Enforcer  *enforcer.Enforcer
}

// New creates a new Handler with the given dependencies.
func New(eval *evaluator.Evaluator, enf *enforcer.Enforcer) *Handler {
	return &Handler{
		Evaluator: eval,
		Enforcer:  enf,
	}
}

// RegisterRoutes registers all HTTP routes on the given mux.
func (h *Handler) RegisterRoutes(mux *http.ServeMux) {
	mux.HandleFunc("/health", h.Health)
	mux.HandleFunc("/api/v1/compliance/evaluate", h.EvaluateDevice)
	mux.HandleFunc("/api/v1/compliance/policies", h.ListPolicies)
	mux.HandleFunc("/api/v1/compliance/violations", h.ListViolations)
	mux.HandleFunc("/api/v1/compliance/enforce", h.EnforcePolicy)
}

// Health returns a 200 OK with service status.
func (h *Handler) Health(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"status":    "ok",
		"service":   "mdm-compliance-engine",
		"version":   "1.0.0",
		"timestamp": time.Now().UTC().Format(time.RFC3339),
	})
}

// EvaluateDevice evaluates a device against all active compliance policies.
// POST /api/v1/compliance/evaluate
// Body: { "deviceId": "...", "agentCode": "...", "telemetry": { ... } }
func (h *Handler) EvaluateDevice(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req struct {
		DeviceID  string                 `json:"deviceId"`
		AgentCode string                 `json:"agentCode"`
		Telemetry map[string]interface{} `json:"telemetry"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body: "+err.Error(), http.StatusBadRequest)
		return
	}

	if req.DeviceID == "" {
		http.Error(w, "deviceId is required", http.StatusBadRequest)
		return
	}

	device := &models.Device{
		ID:        req.DeviceID,
		AgentCode: req.AgentCode,
		Telemetry: req.Telemetry,
	}

	result, err := h.Evaluator.Evaluate(device)
	if err != nil {
		log.Printf("Evaluation error for device %s: %v", req.DeviceID, err)
		http.Error(w, "Evaluation failed: "+err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(result)
}

// ListPolicies returns all active compliance policies.
// GET /api/v1/compliance/policies
func (h *Handler) ListPolicies(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	policies := h.Evaluator.GetPolicies()
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"policies": policies,
		"count":    len(policies),
	})
}

// ListViolations returns recent compliance violations.
// GET /api/v1/compliance/violations?deviceId=...&limit=50
func (h *Handler) ListViolations(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	deviceID := r.URL.Query().Get("deviceId")
	violations := h.Evaluator.GetViolations(deviceID)

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"violations": violations,
		"count":      len(violations),
	})
}

// EnforcePolicy triggers enforcement actions for a device.
// POST /api/v1/compliance/enforce
// Body: { "deviceId": "...", "action": "lock|wipe|notify|restrict" }
func (h *Handler) EnforcePolicy(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req struct {
		DeviceID string `json:"deviceId"`
		Action   string `json:"action"`
		Reason   string `json:"reason"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body: "+err.Error(), http.StatusBadRequest)
		return
	}

	if req.DeviceID == "" || req.Action == "" {
		http.Error(w, "deviceId and action are required", http.StatusBadRequest)
		return
	}

	result, err := h.Enforcer.Enforce(req.DeviceID, req.Action, req.Reason)
	if err != nil {
		log.Printf("Enforcement error for device %s action %s: %v", req.DeviceID, req.Action, err)
		http.Error(w, "Enforcement failed: "+err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(result)
}
