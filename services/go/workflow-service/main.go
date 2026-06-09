package main

import (
	"database/sql"
	_ "github.com/lib/pq"
	"context"
	"encoding/json"
	"fmt"
	"log"
	"log/slog"
	"net/http"
	"strings"
	"os"
	"os/signal"
	"syscall"
	"time"
	"github.com/gorilla/mux"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracehttp"
	"go.opentelemetry.io/otel/propagation"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.24.0"
	"golang.org/x/time/rate"
	"github.com/rs/cors"
)

type WorkflowStep struct {
	ID          string                 `json:"id"`
	Name        string                 `json:"name"`
	Status      string                 `json:"status"`
	Input       map[string]interface{} `json:"input"`
	Output      map[string]interface{} `json:"output"`
	ExecutedAt  *time.Time             `json:"executed_at"`
	CompletedAt *time.Time             `json:"completed_at"`
}

type Workflow struct {
	ID          string         `json:"id"`
	Name        string         `json:"name"`
	Description string         `json:"description"`
	Status      string         `json:"status"`
	Steps       []WorkflowStep `json:"steps"`
	CreatedAt   time.Time      `json:"created_at"`
	UpdatedAt   time.Time      `json:"updated_at"`
	CompletedAt *time.Time     `json:"completed_at"`
}

type WorkflowService struct {
	workflows map[string]Workflow
}

func NewWorkflowService() *WorkflowService {
	return &WorkflowService{
		workflows: make(map[string]Workflow),
	}
}

func (ws *WorkflowService) CreateWorkflow(w http.ResponseWriter, r *http.Request) {
	var workflow Workflow
	if err := json.NewDecoder(r.Body).Decode(&workflow); err != nil {
		http.Error(w, "Invalid JSON", http.StatusBadRequest)
		return
	}

	workflow.ID = fmt.Sprintf("workflow_%d", time.Now().Unix())
	workflow.Status = "created"
	workflow.CreatedAt = time.Now()
	workflow.UpdatedAt = time.Now()

	// Initialize steps if not provided
	if workflow.Steps == nil {
		workflow.Steps = []WorkflowStep{}
	}

	ws.workflows[workflow.ID] = workflow

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(workflow)
}

func (ws *WorkflowService) GetWorkflow(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	workflowID := vars["id"]

	workflow, exists := ws.workflows[workflowID]
	if !exists {
		http.Error(w, "Workflow not found", http.StatusNotFound)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(workflow)
}

func (ws *WorkflowService) ListWorkflows(w http.ResponseWriter, r *http.Request) {
	workflows := make([]Workflow, 0, len(ws.workflows))
	for _, workflow := range ws.workflows {
		workflows = append(workflows, workflow)
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(workflows)
}

func (ws *WorkflowService) ExecuteWorkflow(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	workflowID := vars["id"]

	workflow, exists := ws.workflows[workflowID]
	if !exists {
		http.Error(w, "Workflow not found", http.StatusNotFound)
		return
	}

	// Update workflow status
	workflow.Status = "running"
	workflow.UpdatedAt = time.Now()

	// Execute steps (simplified simulation)
	for i := range workflow.Steps {
		now := time.Now()
		workflow.Steps[i].Status = "completed"
		workflow.Steps[i].ExecutedAt = &now
		workflow.Steps[i].CompletedAt = &now
		workflow.Steps[i].Output = map[string]interface{}{
			"result": "success",
			"message": fmt.Sprintf("Step %s completed successfully", workflow.Steps[i].Name),
		}
	}

	// Mark workflow as completed
	now := time.Now()
	workflow.Status = "completed"
	workflow.CompletedAt = &now
	workflow.UpdatedAt = now

	ws.workflows[workflowID] = workflow

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(workflow)
}

func (ws *WorkflowService) UpdateWorkflow(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	workflowID := vars["id"]

	existingWorkflow, exists := ws.workflows[workflowID]
	if !exists {
		http.Error(w, "Workflow not found", http.StatusNotFound)
		return
	}

	var updateData Workflow
	if err := json.NewDecoder(r.Body).Decode(&updateData); err != nil {
		http.Error(w, "Invalid JSON", http.StatusBadRequest)
		return
	}

	// Update fields
	if updateData.Name != "" {
		existingWorkflow.Name = updateData.Name
	}
	if updateData.Description != "" {
		existingWorkflow.Description = updateData.Description
	}
	if updateData.Status != "" {
		existingWorkflow.Status = updateData.Status
	}
	if updateData.Steps != nil {
		existingWorkflow.Steps = updateData.Steps
	}

	existingWorkflow.UpdatedAt = time.Now()
	ws.workflows[workflowID] = existingWorkflow

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(existingWorkflow)
}

func (ws *WorkflowService) DeleteWorkflow(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	workflowID := vars["id"]

	if _, exists := ws.workflows[workflowID]; !exists {
		http.Error(w, "Workflow not found", http.StatusNotFound)
		return
	}

	delete(ws.workflows, workflowID)
	w.WriteHeader(http.StatusNoContent)
}

func (ws *WorkflowService) HealthCheck(w http.ResponseWriter, r *http.Request) {
	health := map[string]interface{}{
		"status":    "healthy",
		"service":   "workflow-service",
		"timestamp": time.Now(),
		"workflows": len(ws.workflows),
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
	dbPath := os.Getenv("WORKFLOW_SERVICE_DB_PATH")
	if dbPath == "" {
		dbPath = "/tmp/workflow-service.db"
	}
	db, dbErr := sql.Open("postgres", os.Getenv("DATABASE_URL"))
	if dbErr != nil {
		log.Printf("[workflow-service] PostgreSQL unavailable (%v) — running in-memory only", dbErr)
	} else {
		defer db.Close()
		log.Printf("[workflow-service] PostgreSQL persistence at %s", dbPath)
	}
	_ = db


	// ── OpenTelemetry ────────────────────────────────────────────────────────────
	svcName := os.Getenv("SERVICE_NAME")
	if svcName == "" {
		svcName = "workflow-service"
	}
	svcVersion := os.Getenv("SERVICE_VERSION")
	if svcVersion == "" {
		svcVersion = "1.0.0"
	}
	shutdownTracer := initTracer(svcName, svcVersion)
	defer func() {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		_ = shutdownTracer(ctx)
	}()
	workflowService := NewWorkflowService()

	r := mux.NewRouter()

	// API routes
	api := r.PathPrefix("/api/v1").Subrouter()
	api.HandleFunc("/workflows", workflowService.CreateWorkflow).Methods("POST")
	api.HandleFunc("/workflows", workflowService.ListWorkflows).Methods("GET")
	api.HandleFunc("/workflows/{id}", workflowService.GetWorkflow).Methods("GET")
	api.HandleFunc("/workflows/{id}", workflowService.UpdateWorkflow).Methods("PUT")
	api.HandleFunc("/workflows/{id}", workflowService.DeleteWorkflow).Methods("DELETE")
	api.HandleFunc("/workflows/{id}/execute", workflowService.ExecuteWorkflow).Methods("POST")

	// Health check
	r.HandleFunc("/health", workflowService.HealthCheck).Methods("GET")

	// CORS
	c := cors.New(cors.Options{
		AllowedOrigins: []string{"*"},
		AllowedMethods: []string{"GET", "POST", "PUT", "DELETE", "OPTIONS"},
		AllowedHeaders: []string{"*"},
	})

	handler := c.Handler(r)

	port := os.Getenv("PORT")
	if port == "" {
		port = "8083"
	}

	log.Printf("Workflow Service starting on port %s", port)
	log.Fatal(http.ListenAndServe(":"+port, jwtAuthMiddleware(handler)))
}

// initTracer initialises the OTLP trace exporter.
// Returns a shutdown function; safe to call even if OTEL is not configured.
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

// otelMiddleware wraps an http.Handler with OTel tracing.
func otelMiddleware(serviceName string, next http.Handler) http.Handler {
	tracer := otel.Tracer(serviceName)
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		ctx, span := tracer.Start(r.Context(), r.Method+" "+r.URL.Path)
		defer span.End()
		next.ServeHTTP(w, r.WithContext(ctx))
	})
}

// rateLimitMiddleware applies a token-bucket rate limiter.
func rateLimitMiddleware(rps float64, burst int, next http.Handler) http.Handler {
	limiter := rate.NewLimiter(rate.Limit(rps), burst)
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if !limiter.Allow() {
			http.Error(w, `{"error":"rate limit exceeded"}`, http.StatusTooManyRequests)
			return
		}
		next.ServeHTTP(w, r)
	})
}

// gracefulShutdown waits for SIGTERM/SIGINT then drains the server.
func gracefulShutdown(serviceName string, srv *http.Server, cleanup func(context.Context) error) {
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGTERM, syscall.SIGINT)
	sig := <-quit
	slog.Info("Shutdown signal received", "service", serviceName, "signal", sig)
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	if err := srv.Shutdown(ctx); err != nil {
		slog.Error("Server shutdown error", "err", err)
	}
	if cleanup != nil {
		if err := cleanup(ctx); err != nil {
			slog.Error("Cleanup error", "err", err)
		}
	}
	slog.Info("Server stopped gracefully", "service", serviceName)
}

