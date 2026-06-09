package main

import (
	"context"
	"fmt"
	"log/slog"

	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"workflow-orchestrator/internal/api"
	"workflow-orchestrator/internal/engine"
	"workflow-orchestrator/internal/middleware"
	"workflow-orchestrator/internal/repository"
	"workflow-orchestrator/pkg/config"
	"workflow-orchestrator/pkg/logger"
	_ "workflow-orchestrator/pkg/metrics"

	"github.com/prometheus/client_golang/prometheus/promhttp"
	"golang.org/x/time/rate"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracehttp"
	"go.opentelemetry.io/otel/propagation"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.24.0"
)


// --- Auth Middleware ---
func authMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/health" || r.URL.Path == "/ready" || r.URL.Path == "/metrics" {
			next.ServeHTTP(w, r)
			return
		}
		authHeader := r.Header.Get("Authorization")
		if authHeader == "" || len(authHeader) < 8 || authHeader[:7] != "Bearer " {
			http.Error(w, `{"error":"unauthorized"}`, http.StatusUnauthorized)
			return
		}
		next.ServeHTTP(w, r)
	})
}

func main() {
	// Initialize logger
	logger.Init()
	defer logger.Logger.Sync()

	log := logger.Logger

	// Load configuration
	cfg, err := config.Load()
	if err != nil {
		log.Fatal("Failed to load configuration", logger.Error(err))
	}

	// Initialize PostgreSQL repository
	repo, err := repository.NewPostgresRepository(cfg.Database)
	if err != nil {
		log.Fatal("Failed to initialize repository", logger.Error(err))
	}
	defer repo.Close()

	// Initialize Redis client
	redisClient, err := middleware.NewRedisClient(cfg.Redis)
	if err != nil {
		log.Fatal("Failed to initialize Redis", logger.Error(err))
	}
	defer redisClient.Close()

	// Initialize Fluvio client
	fluvioClient, err := middleware.NewFluvioClient(cfg.Fluvio)
	if err != nil {
		log.Warn("Failed to initialize Fluvio (continuing without it)", logger.Error(err))
		fluvioClient = nil
	}

	// Initialize Kafka client
	kafkaClient, err := middleware.NewKafkaClient(cfg.Kafka)
	if err != nil {
		log.Warn("Failed to initialize Kafka (continuing without it)", logger.Error(err))
		kafkaClient = nil
	}

	// Initialize workflow engine components
	stateManager := engine.NewStateManager(repo, redisClient)
	stepExecutor := engine.NewStepExecutor(cfg.Executor.MaxRetries)
	executor := engine.NewExecutor(
		repo,
		stateManager,
		stepExecutor,
		fluvioClient,
		kafkaClient,
		redisClient,
		cfg.Executor.MaxConcurrent,
	)

	// Initialize workflow registry
	registry := engine.NewRegistry()
	registry.RegisterWorkflows()

	// Start worker pool
	workerPool := engine.NewWorkerPool(cfg.Executor.Workers, executor)
	workerPool.Start(context.Background())
	defer workerPool.Stop()

	// Initialize API handlers
	handlers := api.NewHandlers(executor, registry, repo)

	// Setup HTTP router
	router := api.NewRouter(handlers)

	// Metrics endpoint
	http.Handle("/metrics", promhttp.Handler())

	// API endpoints
	http.Handle("/", router)

	// Create HTTP server
	server := &http.Server{
		Addr:         fmt.Sprintf(":%d", cfg.Server.Port),
		Handler:      http.DefaultServeMux,
		ReadTimeout:  time.Duration(cfg.Server.ReadTimeout) * time.Second,
		WriteTimeout: time.Duration(cfg.Server.WriteTimeout) * time.Second,
	}

	// Start server in goroutine
	go func() {
		log.Info("Starting workflow orchestrator",
			logger.Int("port", cfg.Server.Port),
			logger.Int("workers", cfg.Executor.Workers),
			logger.Int("max_concurrent", cfg.Executor.MaxConcurrent),
		)

		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatal("Server failed", logger.Error(err))
		}
	}()

	// Wait for interrupt signal
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Info("Shutting down server...")

	// Graceful shutdown
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	if err := server.Shutdown(ctx); err != nil {
		log.Error("Server forced to shutdown", logger.Error(err))
	}

	log.Info("Server exited")
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

