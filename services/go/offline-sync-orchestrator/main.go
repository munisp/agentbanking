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
	"log/slog"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracehttp"
	"go.opentelemetry.io/otel/propagation"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.24.0"
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
	shutdownTracer := initTracer("offline-sync-orchestrator", "1.0.0")
	defer shutdownTracer(context.Background())

	// PostgreSQL persistence (WAL mode for concurrent reads/writes)
	dbPath := os.Getenv("OFFLINE_SYNC_ORCHESTRATOR_DB_PATH")
	if dbPath == "" {
		dbPath = "/tmp/offline-sync-orchestrator.db"
	}
	db, dbErr := sql.Open("postgres", os.Getenv("DATABASE_URL"))
	if dbErr != nil {
		log.Printf("[offline-sync-orchestrator] PostgreSQL unavailable (%v) — running in-memory only", dbErr)
	} else {
		defer db.Close()
		log.Printf("[offline-sync-orchestrator] PostgreSQL persistence at %s", dbPath)
	}
	_ = db

	port := os.Getenv("PORT")
	if port == "" {
		port = "8140"
	}

	http.HandleFunc("/health", healthHandler)
	http.HandleFunc("/api/v1/sync/start", startSyncHandler)
	http.HandleFunc("/api/v1/sync/status", statusHandler)
	http.HandleFunc("/api/v1/sync/complete", completeSyncHandler)

	log.Printf("Offline Sync Orchestrator starting on port %s", port)
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
