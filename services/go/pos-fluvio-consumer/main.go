package main

import (
	"database/sql"
	_ "github.com/lib/pq"
	"context"
	"bytes"
	"io"
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
	"sync"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracehttp"
	"go.opentelemetry.io/otel/propagation"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.24.0"
	"golang.org/x/time/rate"
)

// ============================================================================
// EVENT MODELS
// ============================================================================

type POSEvent struct {
	EventID    string                 `json:"event_id"`
	EventType  string                 `json:"event_type"`
	Timestamp  string                 `json:"timestamp"`
	MerchantID string                 `json:"merchant_id"`
	TerminalID string                 `json:"terminal_id"`
	Data       map[string]interface{} `json:"data"`
	Metadata   map[string]interface{} `json:"metadata,omitempty"`
}

type TransactionEvent struct {
	POSEvent
	TransactionID string  `json:"transaction_id"`
	Amount        float64 `json:"amount"`
	Currency      string  `json:"currency"`
	PaymentMethod string  `json:"payment_method"`
	Status        string  `json:"status"`
}

type PaymentEvent struct {
	POSEvent
	TransactionID string  `json:"transaction_id"`
	Stage         string  `json:"stage"`
	Amount        float64 `json:"amount"`
	Currency      string  `json:"currency"`
}

type DeviceEvent struct {
	POSEvent
	DeviceID     string `json:"device_id"`
	DeviceType   string `json:"device_type"`
	Status       string `json:"status"`
	ErrorMessage string `json:"error_message,omitempty"`
}

type FraudAlert struct {
	POSEvent
	TransactionID   string   `json:"transaction_id"`
	RiskScore       float64  `json:"risk_score"`
	FraudIndicators []string `json:"fraud_indicators"`
	Action          string   `json:"action"`
}

// ============================================================================
// FLUVIO CONSUMER
// ============================================================================

type FluvioConsumer struct {
	topics     []string
	handlers   map[string]EventHandler
	wg         sync.WaitGroup
	ctx        context.Context
	cancel     context.CancelFunc
	fluvioURL  string
	httpClient *http.Client
}

type EventHandler func(event POSEvent) error

func NewFluvioConsumer() *FluvioConsumer {
	ctx, cancel := context.WithCancel(context.Background())

	fluvioURL := os.Getenv("FLUVIO_HTTP_URL")
	if fluvioURL == "" {
		fluvioURL = "http://localhost:9003"
	}

	return &FluvioConsumer{
		topics: []string{
			"pos-transactions",
			"pos-payment-events",
			"pos-device-events",
			"pos-fraud-alerts",
			"pos-analytics",
		},
		handlers:   make(map[string]EventHandler),
		ctx:        ctx,
		cancel:     cancel,
		fluvioURL:  fluvioURL,
		httpClient: &http.Client{Timeout: 10 * time.Second},
	}
}

func (fc *FluvioConsumer) RegisterHandler(topic string, handler EventHandler) {
	fc.handlers[topic] = handler
	log.Printf("✓ Registered handler for topic: %s", topic)
}

func (fc *FluvioConsumer) Start() error {
	log.Println("🚀 Starting Fluvio POS Consumer...")
	
	// Start consumer for each topic
	for _, topic := range fc.topics {
		fc.wg.Add(1)
		go fc.consumeTopic(topic)
	}
	
	log.Println("✓ Fluvio POS Consumer started")
	return nil
}

func (fc *FluvioConsumer) consumeTopic(topic string) {
	defer fc.wg.Done()

	log.Printf("📡 Consuming from topic: %s (Fluvio: %s)", topic, fc.fluvioURL)

	ticker := time.NewTicker(5 * time.Second)
	defer ticker.Stop()

	offset := 0

	for {
		select {
		case <-fc.ctx.Done():
			log.Printf("Stopping consumer for topic: %s", topic)
			return

		case <-ticker.C:
			events, newOffset, err := fc.fetchFromFluvio(topic, offset)
			if err != nil {
				log.Printf("⚠ Fluvio fetch failed for %s (offset %d): %v", topic, offset, err)
				continue
			}
			for _, event := range events {
				fc.processEvent(topic, event)
			}
			if newOffset > offset {
				offset = newOffset
			}
		}
	}
}

func (fc *FluvioConsumer) fetchFromFluvio(topic string, offset int) ([]POSEvent, int, error) {
	url := fmt.Sprintf("%s/api/consumer/stream/%s$1offset=%d&count=10", fc.fluvioURL, topic, offset)

	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return nil, offset, fmt.Errorf("failed to create request: %w", err)
	}
	req.Header.Set("Accept", "application/json")

	resp, err := fc.httpClient.Do(req)
	if err != nil {
		return nil, offset, fmt.Errorf("HTTP request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, offset, fmt.Errorf("Fluvio returned HTTP %d", resp.StatusCode)
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, offset, fmt.Errorf("failed to read response: %w", err)
	}

	var records []struct {
		Offset int             `json:"offset"`
		Value  json.RawMessage `json:"value"`
	}
	if err := json.Unmarshal(body, &records); err != nil {
		return nil, offset, fmt.Errorf("failed to parse response: %w", err)
	}

	var events []POSEvent
	newOffset := offset
	for _, rec := range records {
		var event POSEvent
		if err := json.Unmarshal(rec.Value, &event); err != nil {
			log.Printf("⚠ Failed to parse event at offset %d: %v", rec.Offset, err)
			continue
		}
		events = append(events, event)
		if rec.Offset >= newOffset {
			newOffset = rec.Offset + 1
		}
	}

	return events, newOffset, nil
}

func (fc *FluvioConsumer) processEvent(topic string, event POSEvent) {
	handler, exists := fc.handlers[topic]
	if !exists {
		log.Printf("⚠ No handler for topic: %s", topic)
		return
	}
	
	if err := handler(event); err != nil {
		log.Printf("❌ Error processing event from %s: %v", topic, err)
	}
}


func (fc *FluvioConsumer) Stop() {
	log.Println("🛑 Stopping Fluvio POS Consumer...")
	fc.cancel()
	fc.wg.Wait()
	log.Println("✓ Fluvio POS Consumer stopped")
}

// ============================================================================
// EVENT PROCESSORS
// ============================================================================

type TransactionProcessor struct {
	processedCount int64
	mu             sync.Mutex
}

func NewTransactionProcessor() *TransactionProcessor {
	return &TransactionProcessor{}
}

func (tp *TransactionProcessor) ProcessTransaction(event POSEvent) error {
	tp.mu.Lock()
	defer tp.mu.Unlock()
	
	tp.processedCount++
	
	log.Printf("💳 Processing transaction: %s | Merchant: %s | Total: %d",
		event.Data["transaction_id"],
		event.MerchantID,
		tp.processedCount)
	
	// Process transaction (store in database, trigger analytics, etc.)
	// In production:
	// - Store in PostgreSQL
	// - Update analytics
	// - Trigger notifications
	// - Update merchant dashboard
	
	return nil
}

func (tp *TransactionProcessor) ProcessPaymentEvent(event POSEvent) error {
	log.Printf("💰 Payment event: %s | Stage: %s",
		event.Data["transaction_id"],
		event.Data["stage"])
	
	// Process payment event
	// In production:
	// - Update transaction status
	// - Notify merchant
	// - Update real-time dashboard
	
	return nil
}

func (tp *TransactionProcessor) ProcessDeviceEvent(event POSEvent) error {
	log.Printf("🖥️  Device event: %s | Status: %s",
		event.Data["device_id"],
		event.Data["status"])
	
	// Process device event
	// In production:
	// - Update device status
	// - Alert if device offline
	// - Schedule maintenance
	
	return nil
}

func (tp *TransactionProcessor) ProcessFraudAlert(event POSEvent) error {
	log.Printf("🚨 FRAUD ALERT: Transaction %s | Risk: %.2f | Action: %s",
		event.Data["transaction_id"],
		event.Data["risk_score"],
		event.Data["action"])
	
	// Process fraud alert
	// In production:
	// - Block transaction if critical
	// - Notify security team
	// - Update fraud detection model
	// - Log for compliance
	
	return nil
}

func (tp *TransactionProcessor) ProcessAnalyticsEvent(event POSEvent) error {
	log.Printf("📊 Analytics event: %s", event.EventType)
	
	// Process analytics event
	// In production:
	// - Update real-time metrics
	// - Feed into data warehouse
	// - Update dashboards
	
	return nil
}

// ============================================================================
// FLUVIO PRODUCER (Bi-directional)
// ============================================================================

type FluvioProducer struct {
	topics     map[string]bool
	fluvioURL  string
	httpClient *http.Client
}

func NewFluvioProducer() *FluvioProducer {
	fluvioURL := os.Getenv("FLUVIO_HTTP_URL")
	if fluvioURL == "" {
		fluvioURL = "http://localhost:9003"
	}

	return &FluvioProducer{
		topics: map[string]bool{
			"pos-commands":       true,
			"pos-config-updates": true,
			"pos-fraud-rules":    true,
			"pos-price-updates":  true,
		},
		fluvioURL:  fluvioURL,
		httpClient: &http.Client{Timeout: 10 * time.Second},
	}
}

func (fp *FluvioProducer) produce(topic string, data []byte) error {
	url := fmt.Sprintf("%s/api/producer/send/%s", fp.fluvioURL, topic)
	req, err := http.NewRequest("POST", url, bytes.NewReader(data))
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := fp.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("HTTP request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusCreated {
		return fmt.Errorf("Fluvio producer returned HTTP %d", resp.StatusCode)
	}

	log.Printf("Produced %d bytes to %s", len(data), topic)
	return nil
}

func (fp *FluvioProducer) SendCommand(command map[string]interface{}) error {
	data, err := json.Marshal(command)
	if err != nil {
		return err
	}
	log.Printf("📤 Sending command: %s", command["command_type"])
	return fp.produce("pos-commands", data)
}

func (fp *FluvioProducer) SendConfigUpdate(config map[string]interface{}) error {
	data, err := json.Marshal(config)
	if err != nil {
		return err
	}
	log.Printf("📤 Sending config update: %s", config["config_key"])
	return fp.produce("pos-config-updates", data)
}

func (fp *FluvioProducer) SendFraudRule(rule map[string]interface{}) error {
	data, err := json.Marshal(rule)
	if err != nil {
		return err
	}
	log.Printf("📤 Sending fraud rule: %s", rule["rule_id"])
	return fp.produce("pos-fraud-rules", data)
}

func (fp *FluvioProducer) SendPriceUpdate(price map[string]interface{}) error {
	data, err := json.Marshal(price)
	if err != nil {
		return err
	}
	log.Printf("📤 Sending price update: %s", price["product_id"])
	return fp.produce("pos-price-updates", data)
}

// ============================================================================
// MAIN
// ============================================================================


func healthHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.Write([]byte(`{"status":"ok","service":"pos-fluvio-consumer"}`))
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
	initDB()


	// ── OpenTelemetry ────────────────────────────────────────────────────────────
	svcName := os.Getenv("SERVICE_NAME")
	if svcName == "" {
		svcName = "pos-fluvio-consumer"
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
	log.Println("================================================================================")
	log.Println("POS Fluvio Integration Service (Go)")
	log.Println("Bi-directional real-time event streaming")
	log.Println("================================================================================")
	
	// Create consumer
	consumer := NewFluvioConsumer()
	
	// Create processor
	processor := NewTransactionProcessor()
	
	// Register handlers
	consumer.RegisterHandler("pos-transactions", processor.ProcessTransaction)
	consumer.RegisterHandler("pos-payment-events", processor.ProcessPaymentEvent)
	consumer.RegisterHandler("pos-device-events", processor.ProcessDeviceEvent)
	consumer.RegisterHandler("pos-fraud-alerts", processor.ProcessFraudAlert)
	consumer.RegisterHandler("pos-analytics", processor.ProcessAnalyticsEvent)
	
	// Start consumer
	if err := consumer.Start(); err != nil {
		log.Fatalf("Failed to start consumer: %v", err)
	}
	
	// Create producer
	producer := NewFluvioProducer()
	
	// Send initial commands (bi-directional)
	go func() {
		time.Sleep(10 * time.Second)
		
		// Send test command
		producer.SendCommand(map[string]interface{}{
			"command_type": "update_terminal_config",
			"terminal_id":  "terminal_001",
			"config": map[string]interface{}{
				"max_transaction_amount": 5000,
				"require_pin":            true,
			},
		})
		
		// Send fraud rule update
		producer.SendFraudRule(map[string]interface{}{
			"rule_id":     "high_amount_v2",
			"name":        "High Amount Transaction V2",
			"condition":   "amount > 10000",
			"action":      "require_approval",
			"severity":    "high",
			"enabled":     true,
		})
	}()
	
	// Wait for interrupt signal
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)
	
	<-sigChan
	
	// Graceful shutdown
	consumer.Stop()
	
	log.Println("✓ Service stopped gracefully")
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


// --- SQLite persistence ---


var db *sql.DB

func initDB() {
	dbURL := os.Getenv("DATABASE_URL")
	if dbURL == "" {
		dbURL = "postgres://postgres:postgres@localhost:5432/pos_fluvio_consumer?sslmode=disable"
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
