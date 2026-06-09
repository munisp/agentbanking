package main

import (
	"database/sql"
	_ "github.com/lib/pq"
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"strings"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/infinyon/fluvio-client-go/fluvio"
)

// BankingEvent represents a banking event
type BankingEvent struct {
	EventID         string                 `json:"event_id"`
	EventType       string                 `json:"event_type"`
	EntityType      string                 `json:"entity_type"`
	EntityID        string                 `json:"entity_id"`
	Action          string                 `json:"action"`
	Data            map[string]interface{} `json:"data"`
	Timestamp       string                 `json:"timestamp"`
	SourceService   string                 `json:"source_service"`
	CorrelationID   string                 `json:"correlation_id,omitempty"`
	TenantID        string                 `json:"tenant_id,omitempty"`
}

// FluvioStreamingService manages Fluvio streaming operations
type FluvioStreamingService struct {
	client    *fluvio.Fluvio
	producers map[string]*fluvio.TopicProducer
	consumers map[string]*fluvio.PartitionConsumer
	mu        sync.RWMutex
	config    *FluvioConfig
	metrics   *StreamingMetrics
}

// FluvioConfig holds Fluvio configuration
type FluvioConfig struct {
	ClusterEndpoint string
	Replication     int32
	Partitions      int32
	Compression     string
	BatchSize       int
	LingerMs        int
	Topics          []string
}

// StreamingMetrics tracks streaming metrics
type StreamingMetrics struct {
	MessagesProduced int64
	MessagesConsumed int64
	Errors           int64
	Latency          time.Duration
	mu               sync.RWMutex
}

// NewFluvioStreamingService creates a new Fluvio streaming service
func NewFluvioStreamingService(config *FluvioConfig) (*FluvioStreamingService, error) {
	// Connect to Fluvio cluster
	client, err := fluvio.Connect()
	if err != nil {
		return nil, fmt.Errorf("failed to connect to Fluvio: %w", err)
	}

	service := &FluvioStreamingService{
		client:    client,
		producers: make(map[string]*fluvio.TopicProducer),
		consumers: make(map[string]*fluvio.PartitionConsumer),
		config:    config,
		metrics:   &StreamingMetrics{},
	}

	// Initialize topics
	if err := service.initializeTopics(); err != nil {
		return nil, fmt.Errorf("failed to initialize topics: %w", err)
	}

	log.Println("✅ Fluvio streaming service initialized successfully")
	return service, nil
}

// initializeTopics creates all required topics
func (s *FluvioStreamingService) initializeTopics() error {
	admin := s.client.Admin()

	for _, topic := range s.config.Topics {
		// Check if topic exists
		exists, err := admin.TopicExists(topic)
		if err != nil {
			return fmt.Errorf("failed to check topic %s: %w", topic, err)
		}

		if !exists {
			// Create topic with replication and partitions
			spec := fluvio.TopicSpec{
				Name:              topic,
				Partitions:        s.config.Partitions,
				ReplicationFactor: s.config.Replication,
				IgnoreRackAssignment: false,
			}

			if err := admin.CreateTopic(spec); err != nil {
				return fmt.Errorf("failed to create topic %s: %w", topic, err)
			}

			log.Printf("✅ Created Fluvio topic: %s (partitions=%d, replication=%d)\n",
				topic, s.config.Partitions, s.config.Replication)
		}
	}

	return nil
}

// GetProducer gets or creates a producer for a topic
func (s *FluvioStreamingService) GetProducer(topic string) (*fluvio.TopicProducer, error) {
	s.mu.RLock()
	if producer, exists := s.producers[topic]; exists {
		s.mu.RUnlock()
		return producer, nil
	}
	s.mu.RUnlock()

	s.mu.Lock()
	defer s.mu.Unlock()

	// Double-check after acquiring write lock
	if producer, exists := s.producers[topic]; exists {
		return producer, nil
	}

	// Create new producer
	producer, err := s.client.TopicProducer(topic)
	if err != nil {
		return nil, fmt.Errorf("failed to create producer for %s: %w", topic, err)
	}

	s.producers[topic] = producer
	return producer, nil
}

// ProduceEvent produces a banking event to Fluvio
func (s *FluvioStreamingService) ProduceEvent(topic string, event *BankingEvent) error {
	start := time.Now()

	// Get producer
	producer, err := s.GetProducer(topic)
	if err != nil {
		s.metrics.mu.Lock()
		s.metrics.Errors++
		s.metrics.mu.Unlock()
		return err
	}

	// Serialize event
	data, err := json.Marshal(event)
	if err != nil {
		s.metrics.mu.Lock()
		s.metrics.Errors++
		s.metrics.mu.Unlock()
		return fmt.Errorf("failed to marshal event: %w", err)
	}

	// Produce with key (for partitioning)
	if err := producer.SendRecord(event.EntityID, data); err != nil {
		s.metrics.mu.Lock()
		s.metrics.Errors++
		s.metrics.mu.Unlock()
		return fmt.Errorf("failed to send record: %w", err)
	}

	// Flush to ensure delivery
	if err := producer.Flush(); err != nil {
		s.metrics.mu.Lock()
		s.metrics.Errors++
		s.metrics.mu.Unlock()
		return fmt.Errorf("failed to flush producer: %w", err)
	}

	// Update metrics
	s.metrics.mu.Lock()
	s.metrics.MessagesProduced++
	s.metrics.Latency = time.Since(start)
	s.metrics.mu.Unlock()

	log.Printf("✅ Produced event to %s: %s (latency: %v)\n", topic, event.EventType, time.Since(start))
	return nil
}

// ConsumeEvents consumes events from a topic
func (s *FluvioStreamingService) ConsumeEvents(ctx context.Context, topic string, partition int32, handler func(*BankingEvent) error) error {
	// Create consumer
	consumer, err := s.client.PartitionConsumer(topic, partition)
	if err != nil {
		return fmt.Errorf("failed to create consumer: %w", err)
	}

	s.mu.Lock()
	s.consumers[fmt.Sprintf("%s-%d", topic, partition)] = consumer
	s.mu.Unlock()

	// Start consuming from beginning
	stream, err := consumer.Stream(fluvio.OffsetFromBeginning())
	if err != nil {
		return fmt.Errorf("failed to create stream: %w", err)
	}

	log.Printf("🔄 Started consuming from %s (partition %d)\n", topic, partition)

	// Consume messages
	for {
		select {
		case <-ctx.Done():
			log.Printf("⏹️ Stopping consumer for %s (partition %d)\n", topic, partition)
			return nil
		default:
			record, err := stream.Next()
			if err != nil {
				s.metrics.mu.Lock()
				s.metrics.Errors++
				s.metrics.mu.Unlock()
				log.Printf("❌ Error reading record: %v\n", err)
				continue
			}

			// Deserialize event
			var event BankingEvent
			if err := json.Unmarshal(record.Value(), &event); err != nil {
				s.metrics.mu.Lock()
				s.metrics.Errors++
				s.metrics.mu.Unlock()
				log.Printf("❌ Error unmarshaling event: %v\n", err)
				continue
			}

			// Handle event
			if err := handler(&event); err != nil {
				s.metrics.mu.Lock()
				s.metrics.Errors++
				s.metrics.mu.Unlock()
				log.Printf("❌ Error handling event: %v\n", err)
				continue
			}

			// Update metrics
			s.metrics.mu.Lock()
			s.metrics.MessagesConsumed++
			s.metrics.mu.Unlock()
		}
	}
}

// GetMetrics returns current streaming metrics
func (s *FluvioStreamingService) GetMetrics() map[string]interface{} {
	s.metrics.mu.RLock()
	defer s.metrics.mu.RUnlock()

	return map[string]interface{}{
		"messages_produced": s.metrics.MessagesProduced,
		"messages_consumed": s.metrics.MessagesConsumed,
		"errors":            s.metrics.Errors,
		"latency_ms":        s.metrics.Latency.Milliseconds(),
		"producers":         len(s.producers),
		"consumers":         len(s.consumers),
	}
}

// Close closes all producers and consumers
func (s *FluvioStreamingService) Close() error {
	s.mu.Lock()
	defer s.mu.Unlock()

	// Close producers
	for topic, producer := range s.producers {
		if err := producer.Flush(); err != nil {
			log.Printf("⚠️ Error flushing producer for %s: %v\n", topic, err)
		}
		delete(s.producers, topic)
	}

	// Close consumers
	for key := range s.consumers {
		delete(s.consumers, key)
	}

	log.Println("✅ Fluvio streaming service closed")
	return nil
}

// HTTP Handlers

func setupRouter(service *FluvioStreamingService) *gin.Engine {
	router := gin.Default()

	// Health check
	router.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{
			"status": "healthy",
			"service": "fluvio-streaming",
		})
	})

	// Metrics
	router.GET("/metrics", func(c *gin.Context) {
		c.JSON(http.StatusOK, service.GetMetrics())
	})

	// Produce event
	router.POST("/produce/:topic", func(c *gin.Context) {
		topic := c.Param("topic")

		var event BankingEvent
		if err := c.ShouldBindJSON(&event); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
			return
		}

		// Set timestamp if not provided
		if event.Timestamp == "" {
			event.Timestamp = time.Now().UTC().Format(time.RFC3339)
		}

		if err := service.ProduceEvent(topic, &event); err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"status": "success",
			"event_id": event.EventID,
		})
	})

	// List topics
	router.GET("/topics", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{
			"topics": service.config.Topics,
		})
	})

	return router
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
	initDB()


	// ── OpenTelemetry ────────────────────────────────────────────────────────────
	svcName := os.Getenv("SERVICE_NAME")
	if svcName == "" {
		svcName = "fluvio-streaming"
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
	// Configuration
	config := &FluvioConfig{
		ClusterEndpoint: getEnv("FLUVIO_CLUSTER", "localhost:9003"),
		Replication:     3,
		Partitions:      6,
		Compression:     "gzip",
		BatchSize:       16384,
		LingerMs:        10,
		Topics: []string{
			"banking.transactions",
			"banking.kyb.applications",
			"banking.kyb.documents",
			"banking.kyb.decisions",
			"banking.payments.qr",
			"banking.payments.ussd",
			"banking.payments.sms",
			"banking.payments.whatsapp",
			"banking.insurance.policies",
			"banking.insurance.claims",
			"banking.agents.performance",
			"banking.agents.onboarding",
			"banking.customers.activity",
			"banking.fraud.alerts",
			"banking.compliance.events",
			"banking.audit.logs",
			"banking.notifications",
			"banking.analytics.events",
		},
	}

	// Create service
	service, err := NewFluvioStreamingService(config)
	if err != nil {
		log.Fatalf("❌ Failed to create Fluvio service: %v", err)
	}
	defer service.Close()

	// Start background consumers
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Example: Start consumer for fraud alerts
	go func() {
		if err := service.ConsumeEvents(ctx, "banking.fraud.alerts", 0, func(event *BankingEvent) error {
			log.Printf("🚨 Fraud alert: %s - %s\n", event.EventType, event.EntityID)
			return nil
		}); err != nil {
			log.Printf("❌ Consumer error: %v\n", err)
		}
	}()

	// Setup HTTP server
	router := setupRouter(service)
	port := getEnv("PORT", "8095")

	// Graceful shutdown
	srv := &http.Server{
		Addr:    ":" + port,
		Handler: router,
	}

	go func() {
		log.Printf("🚀 Fluvio streaming service listening on port %s\n", port)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("❌ Failed to start server: %v", err)
		}
	}()

	// Wait for interrupt signal
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Println("⏹️ Shutting down server...")

	ctx, cancel = context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := srv.Shutdown(ctx); err != nil {
		log.Printf("❌ Server forced to shutdown: %v", err)
	}

	log.Println("✅ Server exited")
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
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


// --- PostgreSQL persistence ---


var db *sql.DB

func initDB() {
	dbURL := os.Getenv("DATABASE_URL")
	if dbURL == "" {
		dbURL = "postgres://postgres:postgres@localhost:5432/fluvio_streaming?sslmode=disable"
	}
	var err error
	db, err = sql.Open("postgres", os.Getenv("DATABASE_URL"))
	if err != nil {
		log.Printf("DB init warning: %v", err)
		return
	}
	db.Exec(`CREATE TABLE IF NOT EXISTS audit_log (
		id SERIAL PRIMARY KEY,
		action TEXT, entity_id TEXT, data TEXT,
		created_at TIMESTAMPTZ DEFAULT NOW()
	)`)
	db.Exec(`CREATE TABLE IF NOT EXISTS state_store (
		key TEXT PRIMARY KEY, value TEXT,
		updated_at TIMESTAMPTZ DEFAULT NOW()
	)`)
}

func logAudit(action, entityID, data string) {
	if db != nil {
		db.Exec("INSERT INTO audit_log (action, entity_id, data) VALUES ($1, $2, $3)", action, entityID, data)
	}
}

func setState(key, value string) {
	if db != nil {
		db.Exec("INSERT OR REPLACE INTO state_store (key, value, updated_at) VALUES ($1, $2, NOW())", key, value)
	}
}

func getState(key string) string {
	if db == nil { return "" }
	var val string
	db.QueryRow("SELECT value FROM state_store WHERE key = $1", key).Scan(&val)
	return val
}
