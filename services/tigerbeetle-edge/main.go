package main

import (
	"context"
	"encoding/json"
	"log"
	"log/slog"
	"net/http"
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
)

// TigerBeetle edge computing service

type Service struct {
	Name        string
	Version     string
	StartTime   time.Time
}

type HealthResponse struct {
	Status    string    `json:"status"`
	Service   string    `json:"service"`
	Timestamp time.Time `json:"timestamp"`
	Uptime    string    `json:"uptime"`
}

type ErrorResponse struct {
	Error   string `json:"error"`
	Message string `json:"message"`
}

func main() {

	// ── OpenTelemetry ────────────────────────────────────────────────────────────
	svcName := os.Getenv("SERVICE_NAME")
	if svcName == "" {
		svcName = "tigerbeetle-edge"
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
	service := &Service{
		Name:      "tigerbeetle-edge",
		Version:   "1.0.0",
		StartTime: time.Now(),
	}

	router := mux.NewRouter()
	
	// Health check
	router.HandleFunc("/health", service.healthHandler).Methods("GET")
	router.HandleFunc("/", service.rootHandler).Methods("GET")
	
	// Service-specific routes
	router.HandleFunc("/api/v1/status", service.statusHandler).Methods("GET")
	router.HandleFunc("/api/v1/metrics", service.metricsHandler).Methods("GET")
	
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	log.Printf("Starting %s on port %s\n", service.Name, port)
	log.Fatal(http.ListenAndServe(":"+port, router))
}

func (s *Service) healthHandler(w http.ResponseWriter, r *http.Request) {
	uptime := time.Since(s.StartTime)
	
	response := HealthResponse{
		Status:    "healthy",
		Service:   s.Name,
		Timestamp: time.Now(),
		Uptime:    uptime.String(),
	}
	
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

func (s *Service) rootHandler(w http.ResponseWriter, r *http.Request) {
	response := map[string]interface{}{
		"service":     s.Name,
		"version":     s.Version,
		"description": "TigerBeetle edge computing service",
		"status":      "running",
	}
	
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

func (s *Service) statusHandler(w http.ResponseWriter, r *http.Request) {
	response := map[string]interface{}{
		"service": s.Name,
		"status":  "operational",
		"uptime":  time.Since(s.StartTime).String(),
	}
	
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

func (s *Service) metricsHandler(w http.ResponseWriter, r *http.Request) {
	metrics := map[string]interface{}{
		"requests_total":    1000,
		"requests_success":  950,
		"requests_failed":   50,
		"avg_response_time": "45ms",
		"uptime_seconds":    int(time.Since(s.StartTime).Seconds()),
	}
	
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(metrics)
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

