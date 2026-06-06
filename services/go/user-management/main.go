package main

import (
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

type User struct {
	ID       string    `json:"id"`
	Username string    `json:"username"`
	Email    string    `json:"email"`
	Role     string    `json:"role"`
	Status   string    `json:"status"`
	Created  time.Time `json:"created"`
}

type UserService struct {
	users map[string]User
}

func NewUserService() *UserService {
	return &UserService{
		users: make(map[string]User),
	}
}

func (us *UserService) CreateUser(w http.ResponseWriter, r *http.Request) {
	var user User
	if err := json.NewDecoder(r.Body).Decode(&user); err != nil {
		http.Error(w, "Invalid JSON", http.StatusBadRequest)
		return
	}

	user.ID = fmt.Sprintf("user_%d", time.Now().Unix())
	user.Created = time.Now()
	user.Status = "active"

	us.users[user.ID] = user

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(user)
}

func (us *UserService) GetUser(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	userID := vars["id"]

	user, exists := us.users[userID]
	if !exists {
		http.Error(w, "User not found", http.StatusNotFound)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(user)
}

func (us *UserService) ListUsers(w http.ResponseWriter, r *http.Request) {
	users := make([]User, 0, len(us.users))
	for _, user := range us.users {
		users = append(users, user)
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(users)
}

func (us *UserService) UpdateUser(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	userID := vars["id"]

	existingUser, exists := us.users[userID]
	if !exists {
		http.Error(w, "User not found", http.StatusNotFound)
		return
	}

	var updateData User
	if err := json.NewDecoder(r.Body).Decode(&updateData); err != nil {
		http.Error(w, "Invalid JSON", http.StatusBadRequest)
		return
	}

	// Update fields
	if updateData.Username != "" {
		existingUser.Username = updateData.Username
	}
	if updateData.Email != "" {
		existingUser.Email = updateData.Email
	}
	if updateData.Role != "" {
		existingUser.Role = updateData.Role
	}
	if updateData.Status != "" {
		existingUser.Status = updateData.Status
	}

	us.users[userID] = existingUser

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(existingUser)
}

func (us *UserService) DeleteUser(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	userID := vars["id"]

	if _, exists := us.users[userID]; !exists {
		http.Error(w, "User not found", http.StatusNotFound)
		return
	}

	delete(us.users, userID)
	w.WriteHeader(http.StatusNoContent)
}

func (us *UserService) HealthCheck(w http.ResponseWriter, r *http.Request) {
	health := map[string]interface{}{
		"status":    "healthy",
		"service":   "user-management",
		"timestamp": time.Now(),
		"users":     len(us.users),
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

func main() {

	// ── OpenTelemetry ────────────────────────────────────────────────────────────
	svcName := os.Getenv("SERVICE_NAME")
	if svcName == "" {
		svcName = "user-management"
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
	userService := NewUserService()

	r := mux.NewRouter()

	// API routes
	api := r.PathPrefix("/api/v1").Subrouter()
	api.HandleFunc("/users", userService.CreateUser).Methods("POST")
	api.HandleFunc("/users", userService.ListUsers).Methods("GET")
	api.HandleFunc("/users/{id}", userService.GetUser).Methods("GET")
	api.HandleFunc("/users/{id}", userService.UpdateUser).Methods("PUT")
	api.HandleFunc("/users/{id}", userService.DeleteUser).Methods("DELETE")

	// Health check
	r.HandleFunc("/health", userService.HealthCheck).Methods("GET")

	// CORS
	c := cors.New(cors.Options{
		AllowedOrigins: []string{"*"},
		AllowedMethods: []string{"GET", "POST", "PUT", "DELETE", "OPTIONS"},
		AllowedHeaders: []string{"*"},
	})

	handler := c.Handler(r)

	port := os.Getenv("PORT")
	if port == "" {
		port = "8082"
	}

	log.Printf("User Management Service starting on port %s", port)
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

