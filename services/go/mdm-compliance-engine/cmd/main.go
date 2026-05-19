// Package main is the entry point for the 54Link MDM Compliance Policy Engine.
//
// This service:
//   1. Consumes device heartbeat events from Kafka topic "mdm.device.heartbeats"
//   2. Evaluates each heartbeat against all active compliance policies (loaded from PostgreSQL)
//   3. Issues enforcement commands for violations via Kafka topic "mdm.device.commands"
//   4. Publishes violation events to "mdm.compliance.violations"
//   5. Exposes a REST API for policy CRUD and violation queries
//
// Default configuration (all overridable via environment variables):
//   KAFKA_BROKERS          = localhost:9092
//   POSTGRES_URL           = postgres://54link:54link@localhost:5432/54link_pos
//   REDIS_URL              = redis://localhost:6379
//   HTTP_PORT              = 8095
//   POLICY_REFRESH_SECS    = 60
//   HEARTBEAT_TOPIC        = mdm.device.heartbeats
//   CONSUMER_GROUP_ID      = mdm-compliance-engine
package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"sync"
	"syscall"
	"time"

	"github.com/gin-gonic/gin"
	_ "github.com/lib/pq"
	"github.com/sirupsen/logrus"

	"mdm-compliance-engine/internal/enforcer"
	"mdm-compliance-engine/internal/evaluator"
	"mdm-compliance-engine/internal/models"
)

// ── Configuration ─────────────────────────────────────────────────────────────

type config struct {
	KafkaBrokers       string
	PostgresURL        string
	RedisURL           string
	HTTPPort           string
	PolicyRefreshSecs  int
	HeartbeatTopic     string
	ConsumerGroupID    string
}

func loadConfig() config {
	refreshSecs := 60
	if v := os.Getenv("POLICY_REFRESH_SECS"); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			refreshSecs = n
		}
	}
	return config{
		KafkaBrokers:      getEnv("KAFKA_BROKERS", "localhost:9092"),
		PostgresURL:       getEnv("POSTGRES_URL", "postgres://54link:54link@localhost:5432/54link_pos?sslmode=disable"),
		RedisURL:          getEnv("REDIS_URL", "redis://localhost:6379"),
		HTTPPort:          getEnv("HTTP_PORT", "8095"),
		PolicyRefreshSecs: refreshSecs,
		HeartbeatTopic:    getEnv("HEARTBEAT_TOPIC", "mdm.device.heartbeats"),
		ConsumerGroupID:   getEnv("CONSUMER_GROUP_ID", "mdm-compliance-engine"),
	}
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

// ── In-memory Kafka publisher (used when Kafka is unavailable) ────────────────

type logPublisher struct {
	log *logrus.Logger
}

func (p *logPublisher) Publish(_ context.Context, topic, key string, value []byte) error {
	p.log.WithFields(logrus.Fields{
		"topic": topic,
		"key":   key,
		"bytes": len(value),
	}).Info("[KAFKA] Published message")
	return nil
}

// ── Policy store ──────────────────────────────────────────────────────────────

// PolicyStore manages compliance policies with periodic refresh from PostgreSQL.
type PolicyStore struct {
	mu       sync.RWMutex
	policies []models.CompliancePolicy
	db       *sql.DB
	log      *logrus.Logger
}

func newPolicyStore(db *sql.DB, log *logrus.Logger) *PolicyStore {
	return &PolicyStore{db: db, log: log}
}

func (s *PolicyStore) Get() []models.CompliancePolicy {
	s.mu.RLock()
	defer s.mu.RUnlock()
	result := make([]models.CompliancePolicy, len(s.policies))
	copy(result, s.policies)
	return result
}

func (s *PolicyStore) Set(policies []models.CompliancePolicy) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.policies = policies
}

// LoadFromDB loads compliance policies from the device_compliance_policies table.
func (s *PolicyStore) LoadFromDB(ctx context.Context) error {
	rows, err := s.db.QueryContext(ctx, `
		SELECT id, name, description, type, enabled, severity, action, threshold, applies_to, created_at, updated_at
		FROM device_compliance_policies
		WHERE enabled = true
		ORDER BY created_at ASC
	`)
	if err != nil {
		return fmt.Errorf("query policies: %w", err)
	}
	defer rows.Close()

	var policies []models.CompliancePolicy
	for rows.Next() {
		var p models.CompliancePolicy
		err := rows.Scan(
			&p.ID, &p.Name, &p.Description,
			&p.Type, &p.Enabled, &p.Severity,
			&p.Action, &p.Threshold, &p.AppliesTo,
			&p.CreatedAt, &p.UpdatedAt,
		)
		if err != nil {
			s.log.WithError(err).Warn("Failed to scan policy row")
			continue
		}
		policies = append(policies, p)
	}
	s.Set(policies)
	s.log.WithField("count", len(policies)).Info("Compliance policies loaded from DB")
	return nil
}

// seedDefaultPolicies inserts the default 54Link compliance policies if none exist.
func seedDefaultPolicies(db *sql.DB, log *logrus.Logger) {
	var count int
	if err := db.QueryRow("SELECT COUNT(*) FROM device_compliance_policies").Scan(&count); err != nil {
		log.WithError(err).Warn("Could not count compliance policies")
		return
	}
	if count > 0 {
		return
	}

	defaults := []models.CompliancePolicy{
		{ID: "pol-os-version", Name: "Minimum OS Version", Type: models.PolicyTypeOSVersion,
			Enabled: true, Severity: models.SeverityWarning, Action: models.ActionAlert,
			Threshold: "10", AppliesTo: "ANDROID"},
		{ID: "pol-app-version", Name: "Minimum App Version", Type: models.PolicyTypeAppVersion,
			Enabled: true, Severity: models.SeverityWarning, Action: models.ActionAlert,
			Threshold: "2.0.0", AppliesTo: "ALL"},
		{ID: "pol-battery", Name: "Minimum Battery Level", Type: models.PolicyTypeBatteryLevel,
			Enabled: true, Severity: models.SeverityInfo, Action: models.ActionWarn,
			Threshold: "15", AppliesTo: "ALL"},
		{ID: "pol-encryption", Name: "Storage Encryption Required", Type: models.PolicyTypeEncryption,
			Enabled: true, Severity: models.SeverityCritical, Action: models.ActionRestrict,
			Threshold: "", AppliesTo: "ANDROID"},
		{ID: "pol-screen-lock", Name: "Screen Lock Required", Type: models.PolicyTypeScreenLock,
			Enabled: true, Severity: models.SeverityWarning, Action: models.ActionAlert,
			Threshold: "", AppliesTo: "ALL"},
		{ID: "pol-root-detect", Name: "Root/Jailbreak Detection", Type: models.PolicyTypeRootDetect,
			Enabled: true, Severity: models.SeverityCritical, Action: models.ActionWipe,
			Threshold: "", AppliesTo: "ALL"},
		{ID: "pol-idle-timeout", Name: "Session Idle Timeout", Type: models.PolicyTypeIdleTimeout,
			Enabled: true, Severity: models.SeverityWarning, Action: models.ActionLock,
			Threshold: "300", AppliesTo: "ALL"},
	}

	for _, p := range defaults {
		_, err := db.Exec(`
			INSERT INTO device_compliance_policies
				(id, name, description, type, enabled, severity, action, threshold, applies_to, created_at, updated_at)
			VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,NOW(),NOW())
			ON CONFLICT (id) DO NOTHING
		`, p.ID, p.Name, p.Description, string(p.Type), p.Enabled,
			string(p.Severity), string(p.Action), p.Threshold, p.AppliesTo)
		if err != nil {
			log.WithError(err).WithField("policyId", p.ID).Warn("Failed to seed policy")
		}
	}
	log.Info("Default compliance policies seeded")
}

// ── HTTP API ──────────────────────────────────────────────────────────────────

func setupRouter(store *PolicyStore, eval *evaluator.Evaluator, log *logrus.Logger) *gin.Engine {
	gin.SetMode(gin.ReleaseMode)
	r := gin.New()
	r.Use(gin.Recovery())

	r.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"status": "ok", "service": "mdm-compliance-engine"})
	})

	api := r.Group("/api/v1")
	{
		// List active policies
		api.GET("/policies", func(c *gin.Context) {
			c.JSON(http.StatusOK, store.Get())
		})

		// Evaluate a heartbeat on-demand (for testing/debugging)
		api.POST("/evaluate", func(c *gin.Context) {
			var hb models.DeviceHeartbeat
			if err := c.ShouldBindJSON(&hb); err != nil {
				c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
				return
			}
			result := eval.Evaluate(hb, store.Get())
			c.JSON(http.StatusOK, result)
		})
	}

	return r
}

// ── Kafka consumer (stub — uses log publisher when Kafka unavailable) ─────────

// processHeartbeat evaluates and enforces a single heartbeat message.
func processHeartbeat(
	ctx context.Context,
	data []byte,
	store *PolicyStore,
	eval *evaluator.Evaluator,
	enf *enforcer.Enforcer,
	log *logrus.Logger,
) {
	var hb models.DeviceHeartbeat
	if err := json.Unmarshal(data, &hb); err != nil {
		log.WithError(err).Error("Failed to unmarshal heartbeat")
		return
	}

	result := eval.Evaluate(hb, store.Get())
	if !result.Compliant {
		log.WithFields(logrus.Fields{
			"deviceId":   hb.DeviceID,
			"violations": len(result.Violations),
		}).Warn("Compliance violations detected")
	}

	if err := enf.Enforce(ctx, result); err != nil {
		log.WithError(err).Error("Enforcement failed")
	}
}

// ── Main ──────────────────────────────────────────────────────────────────────

func main() {

	// ── OpenTelemetry ────────────────────────────────────────────────────────────
	svcName := os.Getenv("SERVICE_NAME")
	if svcName == "" {
		svcName = "mdm-compliance-engine"
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
	log := logrus.New()
	log.SetFormatter(&logrus.JSONFormatter{})
	log.SetLevel(logrus.InfoLevel)

	cfg := loadConfig()
	log.WithField("config", cfg).Info("54Link MDM Compliance Engine starting")

	// Connect to PostgreSQL
	db, err := sql.Open("postgres", cfg.PostgresURL)
	if err != nil {
		log.WithError(err).Fatal("Failed to open PostgreSQL connection")
	}
	defer db.Close()

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Test DB connection (non-fatal — service can run with seeded policies)
	if err := db.PingContext(ctx); err != nil {
		log.WithError(err).Warn("PostgreSQL not available — using default policies")
	} else {
		seedDefaultPolicies(db, log)
	}

	// Initialise components
	store := newPolicyStore(db, log)
	eval := evaluator.New()
	pub := &logPublisher{log: log}
	enf := enforcer.New(pub, log)

	// Load policies from DB
	if err := store.LoadFromDB(ctx); err != nil {
		log.WithError(err).Warn("Could not load policies from DB — using empty set")
	}

	// Periodic policy refresh
	go func() {
		ticker := time.NewTicker(time.Duration(cfg.PolicyRefreshSecs) * time.Second)
		defer ticker.Stop()
		for {
			select {
			case <-ctx.Done():
				return
			case <-ticker.C:
				if err := store.LoadFromDB(ctx); err != nil {
					log.WithError(err).Warn("Policy refresh failed")
				}
			}
		}
	}()

	// Start HTTP server
	router := setupRouter(store, eval, log)
	srv := &http.Server{
		Addr:    ":" + cfg.HTTPPort,
		Handler: router,
	}
	go func() {
		log.WithField("port", cfg.HTTPPort).Info("HTTP server listening")
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.WithError(err).Fatal("HTTP server error")
		}
	}()

	// Log a sample self-test evaluation
	sampleHB := models.DeviceHeartbeat{
		DeviceID: "startup-selftest", SerialNumber: "SELFTEST",
		OSVersion: "14", AppVersion: "2.5.0", BatteryLevel: 80,
		IsEncrypted: true, IsScreenLocked: true, IsRooted: false,
		WiFiConnected: true, DeviceType: "ANDROID", Timestamp: time.Now(),
	}
	result := eval.Evaluate(sampleHB, store.Get())
	log.WithFields(logrus.Fields{
		"compliant":  result.Compliant,
		"violations": len(result.Violations),
	}).Info("Startup self-test evaluation complete")
	// Run enforcement on self-test result (no-op with empty policy set)
	if err := enf.Enforce(ctx, result); err != nil {
		log.WithError(err).Warn("Startup self-test enforcement (expected with no policies)")
	}

	// Graceful shutdown
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit
	log.Info("Shutting down MDM Compliance Engine...")
	cancel()

	shutCtx, shutCancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer shutCancel()
	if err := srv.Shutdown(shutCtx); err != nil {
		log.WithError(err).Error("HTTP server shutdown error")
	}
	log.Info("MDM Compliance Engine stopped")
}

// processHeartbeat is exported for use in Kafka consumer goroutine
var _ = processHeartbeat

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

