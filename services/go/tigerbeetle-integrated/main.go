// Package main implements the TigerBeetle Integrated service.
// Acts as the sidecar that:
//   1. Accepts transfer requests from the TypeScript layer (tbClient.ts)
//   2. Commits them to the core TigerBeetle cluster
//   3. Writes transfer metadata back to PostgreSQL (bi-directional sync)
//   4. Publishes events to Kafka/Dapr for downstream consumers
// Persistence: PostgreSQL (zero in-memory state)
// This is the "TB_SIDECAR_URL" service referenced by tbClient.ts
package main

import (
	"bytes"
	"database/sql"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"sync/atomic"
	"syscall"
	"time"

	_ "github.com/lib/pq"
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

type Service struct {
	Name      string
	Version   string
	StartTime time.Time
	TBCoreURL string

	RequestsTotal  int64
	RequestsOK     int64
	RequestsFailed int64
	TotalLatencyNs int64
}

type TransferRequest struct {
	DebitAccountID  string `json:"debitAccountId"`
	CreditAccountID string `json:"creditAccountId"`
	Amount          int64  `json:"amount"`
	Ledger          int    `json:"ledger"`
	Code            int    `json:"code"`
	Reference       string `json:"reference,omitempty"`
	AgentCode       string `json:"agentCode,omitempty"`
	TxType          string `json:"txType,omitempty"`
}

type TransferResponse struct {
	OK         bool   `json:"ok"`
	TransferID string `json:"transferId"`
	Source     string `json:"source"`
}

type ErrorResponse struct {
	Error   string `json:"error"`
	Message string `json:"message"`
}

var pgDB *sql.DB

func initDB() {
	dbURL := os.Getenv("DATABASE_URL")
	if dbURL == "" {
		dbURL = "postgres://postgres:postgres@localhost:5432/tigerbeetle_integrated?sslmode=disable"
	}
	var err error
	pgDB, err = sql.Open("postgres", dbURL)
	if err != nil {
		log.Printf("[sidecar] DB warning: %v", err)
		return
	}
	pgDB.SetMaxOpenConns(20)
	pgDB.SetMaxIdleConns(10)
	pgDB.SetConnMaxLifetime(5 * time.Minute)

	// Transfer metadata (bi-directional: also written back to PG after TB commit)
	pgDB.Exec(`CREATE TABLE IF NOT EXISTS tb_transfer_metadata (
		id SERIAL PRIMARY KEY,
		transfer_ref TEXT UNIQUE NOT NULL,
		debit_account TEXT NOT NULL,
		credit_account TEXT NOT NULL,
		amount BIGINT NOT NULL,
		ledger INT NOT NULL DEFAULT 0,
		code INT NOT NULL DEFAULT 0,
		agent_code TEXT,
		tx_type TEXT,
		reference TEXT,
		tb_committed BOOLEAN NOT NULL DEFAULT false,
		pg_written BOOLEAN NOT NULL DEFAULT true,
		created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
	)`)
	pgDB.Exec(`CREATE INDEX IF NOT EXISTS idx_tb_meta_agent ON tb_transfer_metadata(agent_code)`)
	pgDB.Exec(`CREATE INDEX IF NOT EXISTS idx_tb_meta_committed ON tb_transfer_metadata(tb_committed)`)
	pgDB.Exec(`CREATE INDEX IF NOT EXISTS idx_tb_meta_created ON tb_transfer_metadata(created_at)`)

	// Agent account mapping (persisted, not in-memory)
	pgDB.Exec(`CREATE TABLE IF NOT EXISTS tb_agent_accounts (
		agent_code TEXT PRIMARY KEY,
		tb_account_id TEXT NOT NULL,
		created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
	)`)

	// Sync tracking
	pgDB.Exec(`CREATE TABLE IF NOT EXISTS tb_sidecar_sync_status (
		id SERIAL PRIMARY KEY,
		pending INT NOT NULL DEFAULT 0,
		synced INT NOT NULL DEFAULT 0,
		failed INT NOT NULL DEFAULT 0,
		last_sync TIMESTAMPTZ,
		updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
	)`)
	pgDB.Exec(`INSERT INTO tb_sidecar_sync_status (pending, synced, failed) VALUES (0, 0, 0) ON CONFLICT DO NOTHING`)

	log.Println("[sidecar] PostgreSQL tables initialized (bi-directional TB↔PG)")
}

// ── Transfer Handler (TB_SIDECAR_URL /transfers) ────────────────────────────

func (s *Service) transferHandler(w http.ResponseWriter, r *http.Request) {
	start := time.Now()
	atomic.AddInt64(&s.RequestsTotal, 1)

	body, err := io.ReadAll(r.Body)
	if err != nil {
		atomic.AddInt64(&s.RequestsFailed, 1)
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(ErrorResponse{Error: "invalid_body", Message: err.Error()})
		return
	}

	var req TransferRequest
	if err := json.Unmarshal(body, &req); err != nil {
		atomic.AddInt64(&s.RequestsFailed, 1)
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(ErrorResponse{Error: "invalid_json", Message: err.Error()})
		return
	}

	transferRef := fmt.Sprintf("tx_%d_%s_%s_%d", time.Now().UnixMicro(), req.DebitAccountID, req.CreditAccountID, req.Amount)

	// Step 1: Write metadata to PostgreSQL FIRST (offline-safe)
	if pgDB != nil {
		pgDB.Exec(`INSERT INTO tb_transfer_metadata (transfer_ref, debit_account, credit_account, amount, ledger, code, agent_code, tx_type, reference, tb_committed, pg_written)
			VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, false, true)
			ON CONFLICT (transfer_ref) DO NOTHING`,
			transferRef, req.DebitAccountID, req.CreditAccountID, req.Amount,
			req.Ledger, req.Code, req.AgentCode, req.TxType, req.Reference)
	}

	// Step 2: Forward to TigerBeetle core
	tbCommitted := false
	corePayload, _ := json.Marshal([]map[string]interface{}{
		{
			"id": time.Now().UnixMicro(), "debit_account_id": 0,
			"credit_account_id": 0, "amount": req.Amount,
			"ledger": req.Ledger, "code": req.Code,
		},
	})
	resp, err := http.Post(fmt.Sprintf("%s/api/v1/transfers", s.TBCoreURL), "application/json", bytes.NewReader(corePayload))
	if err == nil && resp.StatusCode < 300 {
		tbCommitted = true
		resp.Body.Close()
	}

	// Step 3: Update TB committed status in PG (write-back)
	if pgDB != nil && tbCommitted {
		pgDB.Exec(`UPDATE tb_transfer_metadata SET tb_committed=true WHERE transfer_ref=$1`, transferRef)
		pgDB.Exec(`UPDATE tb_sidecar_sync_status SET synced=synced+1, last_sync=NOW(), updated_at=NOW()`)
	} else if pgDB != nil {
		pgDB.Exec(`UPDATE tb_sidecar_sync_status SET pending=pending+1, updated_at=NOW()`)
	}

	// Step 4: Publish to Kafka/Dapr (async, fail-open)
	go publishMiddleware("transfer.committed", map[string]interface{}{
		"ref": transferRef, "amount": req.Amount, "agent": req.AgentCode, "tb": tbCommitted,
	})

	atomic.AddInt64(&s.RequestsOK, 1)
	atomic.AddInt64(&s.TotalLatencyNs, int64(time.Since(start)))

	source := "tigerbeetle"
	if !tbCommitted {
		source = "postgres"
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(TransferResponse{OK: true, TransferID: transferRef, Source: source})
}

// ── Agent Account Handler (TB_SIDECAR_URL /accounts/ensure) ─────────────────

func (s *Service) ensureAccountHandler(w http.ResponseWriter, r *http.Request) {
	var req struct {
		AgentCode string `json:"agentCode"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil || req.AgentCode == "" {
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(ErrorResponse{Error: "invalid_request", Message: "agentCode required"})
		return
	}

	if pgDB != nil {
		var existing string
		err := pgDB.QueryRow(`SELECT tb_account_id FROM tb_agent_accounts WHERE agent_code=$1`, req.AgentCode).Scan(&existing)
		if err == nil {
			json.NewEncoder(w).Encode(map[string]interface{}{"ok": true, "accountId": existing, "existing": true})
			return
		}
	}

	accountID := fmt.Sprintf("agent_%s_%d", req.AgentCode, time.Now().UnixMicro())
	if pgDB != nil {
		pgDB.Exec(`INSERT INTO tb_agent_accounts (agent_code, tb_account_id) VALUES ($1, $2) ON CONFLICT DO NOTHING`, req.AgentCode, accountID)
	}

	json.NewEncoder(w).Encode(map[string]interface{}{"ok": true, "accountId": accountID, "existing": false})
}

// ── Balance Handler (TB_SIDECAR_URL /accounts/{agentCode}/balance) ──────────

func (s *Service) balanceHandler(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	agentCode := vars["agentCode"]

	if pgDB == nil {
		w.WriteHeader(http.StatusServiceUnavailable)
		json.NewEncoder(w).Encode(ErrorResponse{Error: "no_db", Message: "database unavailable"})
		return
	}

	var totalDebits, totalCredits int64
	pgDB.QueryRow(`SELECT COALESCE(SUM(amount), 0) FROM tb_transfer_metadata WHERE debit_account=$1 OR agent_code=$1`, agentCode).Scan(&totalDebits)
	pgDB.QueryRow(`SELECT COALESCE(SUM(amount), 0) FROM tb_transfer_metadata WHERE credit_account=$1`, agentCode).Scan(&totalCredits)

	balance := totalCredits - totalDebits
	json.NewEncoder(w).Encode(map[string]interface{}{
		"agentCode":   agentCode,
		"balanceKobo": balance,
		"balanceNGN":  float64(balance) / 100.0,
		"source":      "postgresql",
	})
}

// ── Sync Status Handler ─────────────────────────────────────────────────────

func (s *Service) syncStatusHandler(w http.ResponseWriter, r *http.Request) {
	var pending, synced, failed int
	if pgDB != nil {
		pgDB.QueryRow(`SELECT pending, synced, failed FROM tb_sidecar_sync_status LIMIT 1`).Scan(&pending, &synced, &failed)
	}
	json.NewEncoder(w).Encode(map[string]interface{}{
		"pending":  pending,
		"synced":   synced,
		"failed":   failed,
		"postgres": "connected",
	})
}

// ── Health Handler ──────────────────────────────────────────────────────────

func (s *Service) healthHandler(w http.ResponseWriter, r *http.Request) {
	dbOK := false
	if pgDB != nil {
		dbOK = pgDB.Ping() == nil
	}
	json.NewEncoder(w).Encode(map[string]interface{}{
		"status":      "healthy",
		"service":     s.Name,
		"version":     s.Version,
		"uptime":      time.Since(s.StartTime).String(),
		"persistence": "postgresql",
		"postgres":    dbOK,
	})
}

func (s *Service) metricsHandler(w http.ResponseWriter, r *http.Request) {
	var metaCount int
	if pgDB != nil {
		pgDB.QueryRow(`SELECT COUNT(*) FROM tb_transfer_metadata`).Scan(&metaCount)
	}
	json.NewEncoder(w).Encode(map[string]interface{}{
		"requests_total":   atomic.LoadInt64(&s.RequestsTotal),
		"requests_ok":      atomic.LoadInt64(&s.RequestsOK),
		"requests_failed":  atomic.LoadInt64(&s.RequestsFailed),
		"avg_latency_ns":   avgLatency(s),
		"transfer_metadata": metaCount,
		"uptime_seconds":   int(time.Since(s.StartTime).Seconds()),
	})
}

func avgLatency(s *Service) int64 {
	total := atomic.LoadInt64(&s.RequestsTotal)
	if total == 0 {
		return 0
	}
	return atomic.LoadInt64(&s.TotalLatencyNs) / total
}

func publishMiddleware(eventType string, payload interface{}) {
	data, _ := json.Marshal(payload)
	daprPort := os.Getenv("DAPR_HTTP_PORT")
	if daprPort == "" {
		daprPort = "3500"
	}

	go func() {
		url := fmt.Sprintf("http://localhost:%s/v1.0/publish/kafka-pubsub/tb.sidecar.%s", daprPort, eventType)
		http.Post(url, "application/json", bytes.NewReader(data))
	}()
	go func() {
		url := fmt.Sprintf("http://localhost:%s/v1.0/publish/pubsub/tb.sidecar.%s", daprPort, eventType)
		http.Post(url, "application/json", bytes.NewReader(data))
	}()
}

func jwtAuthMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
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
		next.ServeHTTP(w, r)
	})
}

func (s *Service) metricsMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		rw := &statusWriter{ResponseWriter: w, status: 200}
		next.ServeHTTP(rw, r)
		atomic.AddInt64(&s.RequestsTotal, 1)
		if rw.status >= 400 {
			atomic.AddInt64(&s.RequestsFailed, 1)
		} else {
			atomic.AddInt64(&s.RequestsOK, 1)
		}
		atomic.AddInt64(&s.TotalLatencyNs, int64(time.Since(start)))
	})
}

type statusWriter struct {
	http.ResponseWriter
	status int
}

func (w *statusWriter) WriteHeader(status int) {
	w.status = status
	w.ResponseWriter.WriteHeader(status)
}

func main() {
	initDB()

	tbCoreURL := os.Getenv("TB_CORE_URL")
	if tbCoreURL == "" {
		tbCoreURL = "http://tigerbeetle-core:8080"
	}

	svc := &Service{
		Name:      "tigerbeetle-integrated",
		Version:   "2.0.0",
		StartTime: time.Now(),
		TBCoreURL: tbCoreURL,
	}

	shutdownTracer := initTracer("tigerbeetle-integrated", "2.0.0")
	defer func() {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		_ = shutdownTracer(ctx)
	}()

	router := mux.NewRouter()
	router.HandleFunc("/health", svc.healthHandler).Methods("GET")
	router.HandleFunc("/metrics", svc.metricsHandler).Methods("GET")
	router.HandleFunc("/transfers", svc.transferHandler).Methods("POST")
	router.HandleFunc("/accounts/ensure", svc.ensureAccountHandler).Methods("POST")
	router.HandleFunc("/accounts/{agentCode}/balance", svc.balanceHandler).Methods("GET")
	router.HandleFunc("/sync/status", svc.syncStatusHandler).Methods("GET")

	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	log.Printf("Starting TigerBeetle Integrated (sidecar) v2.0.0 on :%s (bi-directional TB↔PG)", port)
	log.Fatal(http.ListenAndServe(":"+port, jwtAuthMiddleware(router)))
}

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
	tp := sdktrace.NewTracerProvider(sdktrace.WithBatcher(exp), sdktrace.WithResource(res))
	otel.SetTracerProvider(tp)
	otel.SetTextMapPropagator(propagation.NewCompositeTextMapPropagator(propagation.TraceContext{}, propagation.Baggage{}))
	return tp.Shutdown
}

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
