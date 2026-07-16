package main

import (
	"context"
	"encoding/json"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"strings"
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
)

const (
	serviceName    = "rbac-service"
	serviceVersion = "1.0.0"
)

// ── Permission model ──────────────────────────────────────────────────────────

// Role → permissions mapping (loaded from env or defaults)
var defaultRolePermissions = map[string][]string{
	"super_admin":    {"*"},
	"bank_admin":     {"agents:read", "agents:write", "transactions:read", "reports:read", "kyc:approve"},
	"branch_manager": {"agents:read", "transactions:read", "reports:read", "float:approve"},
	"agent":          {"transactions:create", "transactions:read:own", "kyc:submit", "reports:read:own"},
	"auditor":        {"transactions:read", "reports:read", "kyc:read"},
	"compliance":     {"transactions:read", "reports:read", "kyc:read", "cbn:submit"},
	"customer":       {"transactions:read:own", "profile:read:own", "profile:write:own"},
}

func hasPermission(role, permission string) bool {
	perms, ok := defaultRolePermissions[role]
	if !ok {
		return false
	}
	for _, p := range perms {
		if p == "*" || p == permission {
			return true
		}
		// Wildcard prefix match: "transactions:*" matches "transactions:read"
		if strings.HasSuffix(p, ":*") {
			prefix := strings.TrimSuffix(p, ":*")
			if strings.HasPrefix(permission, prefix+":") {
				return true
			}
		}
	}
	return false
}

// ── OTel ──────────────────────────────────────────────────────────────────────

func initTracer() func(context.Context) error {
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

// ── Handlers ──────────────────────────────────────────────────────────────────

type rbacServer struct{}

func (s *rbacServer) healthHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{
		"status":  "ok",
		"service": serviceName,
		"version": serviceVersion,
	})
}

// checkHandler checks if a role has a specific permission.
// POST /api/v1/rbac/check  { "role": "agent", "permission": "transactions:create" }
func (s *rbacServer) checkHandler(w http.ResponseWriter, r *http.Request) {
	_, span := otel.Tracer(serviceName).Start(r.Context(), "rbac.check")
	defer span.End()

	var req struct {
		Role       string `json:"role"`
		Permission string `json:"permission"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, `{"error":"invalid request body"}`, http.StatusBadRequest)
		return
	}
	allowed := hasPermission(req.Role, req.Permission)
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"allowed":    allowed,
		"role":       req.Role,
		"permission": req.Permission,
	})
}

// rolesHandler returns all roles and their permissions.
// GET /api/v1/rbac/roles
func (s *rbacServer) rolesHandler(w http.ResponseWriter, r *http.Request) {
	_, span := otel.Tracer(serviceName).Start(r.Context(), "rbac.roles")
	defer span.End()

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(defaultRolePermissions)
}

// permissionsHandler returns permissions for a specific role.
// GET /api/v1/rbac/roles/{role}/permissions
func (s *rbacServer) permissionsHandler(w http.ResponseWriter, r *http.Request) {
	_, span := otel.Tracer(serviceName).Start(r.Context(), "rbac.permissions")
	defer span.End()

	vars := mux.Vars(r)
	role := vars["role"]
	perms, ok := defaultRolePermissions[role]
	if !ok {
		http.Error(w, `{"error":"role not found"}`, http.StatusNotFound)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"role":        role,
		"permissions": perms,
	})
}

// ── Middleware ─────────────────────────────────────────────────────────────────

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

func otelMiddleware(next http.Handler) http.Handler {
	tracer := otel.Tracer(serviceName)
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		ctx, span := tracer.Start(r.Context(), r.Method+" "+r.URL.Path)
		defer span.End()
		next.ServeHTTP(w, r.WithContext(ctx))
	})
}

// ── Main ──────────────────────────────────────────────────────────────────────

func main() {
	shutdownTracer := initTracer()
	defer func() {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		_ = shutdownTracer(ctx)
	}()

	srv := &rbacServer{}
	router := mux.NewRouter()
	router.HandleFunc("/healthz", srv.healthHandler).Methods("GET")
	router.HandleFunc("/api/v1/rbac/check", srv.checkHandler).Methods("POST")
	router.HandleFunc("/api/v1/rbac/roles", srv.rolesHandler).Methods("GET")
	router.HandleFunc("/api/v1/rbac/roles/{role}/permissions", srv.permissionsHandler).Methods("GET")

	chain := otelMiddleware(rateLimitMiddleware(500, 100, router))

	port := os.Getenv("PORT")
	if port == "" {
		port = "8087"
	}
	httpSrv := &http.Server{
		Addr:         ":" + port,
		Handler:      chain,
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 15 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	go func() {
		slog.Info("RBAC service starting", "port", port)
		if err := httpSrv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			slog.Error("Server error", "err", err)
			os.Exit(1)
		}
	}()

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGTERM, syscall.SIGINT)
	<-quit
	slog.Info("Shutting down RBAC service...")
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	if err := httpSrv.Shutdown(ctx); err != nil {
		slog.Error("Shutdown error", "err", err)
	}
	slog.Info("RBAC service stopped")
}
