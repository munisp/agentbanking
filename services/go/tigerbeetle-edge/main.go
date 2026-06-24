// Package main implements the TigerBeetle Edge service.
// Offline-first edge proxy that commits transfers to PostgreSQL immediately
// (for offline agents) and syncs upstream to the core TigerBeetle service when
// connectivity is restored. Designed for low-bandwidth/intermittent environments.
// Persistence: PostgreSQL (zero in-memory state)
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

	requestsTotal   int64
	requestsSuccess int64
	requestsFailed  int64
}

type EdgeTransfer struct {
	ID              uint64 `json:"id"`
	DebitAccountID  uint64 `json:"debit_account_id"`
	CreditAccountID uint64 `json:"credit_account_id"`
	Amount          uint64 `json:"amount"`
	Ledger          uint32 `json:"ledger"`
	Code            uint16 `json:"code"`
	AgentCode       string `json:"agent_code"`
	Reference       string `json:"reference"`
	SyncStatus      string `json:"sync_status"`
}

type ErrorResponse struct {
	Error   string `json:"error"`
	Message string `json:"message"`
}

var pgDB *sql.DB

func initDB() {
	dbURL := os.Getenv("DATABASE_URL")
	if dbURL == "" {
		dbURL = "postgres://postgres:postgres@localhost:5432/tigerbeetle_edge?sslmode=disable"
	}
	var err error
	pgDB, err = sql.Open("postgres", dbURL)
	if err != nil {
		log.Printf("[edge] DB warning: %v", err)
		return
	}
	pgDB.SetMaxOpenConns(15)
	pgDB.SetMaxIdleConns(5)
	pgDB.SetConnMaxLifetime(5 * time.Minute)

	pgDB.Exec(`CREATE TABLE IF NOT EXISTS edge_transfers (
		id BIGINT PRIMARY KEY,
		debit_account_id BIGINT NOT NULL,
		credit_account_id BIGINT NOT NULL,
		amount BIGINT NOT NULL DEFAULT 0,
		ledger INT NOT NULL DEFAULT 0,
		code SMALLINT NOT NULL DEFAULT 0,
		agent_code TEXT,
		reference TEXT,
		sync_status TEXT NOT NULL DEFAULT 'pending',
		created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
		synced_at TIMESTAMPTZ
	)`)
	pgDB.Exec(`CREATE INDEX IF NOT EXISTS idx_edge_transfers_sync ON edge_transfers(sync_status)`)
	pgDB.Exec(`CREATE INDEX IF NOT EXISTS idx_edge_transfers_agent ON edge_transfers(agent_code)`)

	pgDB.Exec(`CREATE TABLE IF NOT EXISTS edge_sync_state (
		key TEXT PRIMARY KEY,
		value TEXT NOT NULL,
		updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
	)`)
	pgDB.Exec(`INSERT INTO edge_sync_state (key, value) VALUES ('pending_count', '0') ON CONFLICT DO NOTHING`)
	pgDB.Exec(`INSERT INTO edge_sync_state (key, value) VALUES ('synced_count', '0') ON CONFLICT DO NOTHING`)
	pgDB.Exec(`INSERT INTO edge_sync_state (key, value) VALUES ('failed_count', '0') ON CONFLICT DO NOTHING`)

	log.Println("[edge] PostgreSQL tables initialized")
}

func (s *Service) commitTransferHandler(w http.ResponseWriter, r *http.Request) {
	atomic.AddInt64(&s.requestsTotal, 1)

	body, err := io.ReadAll(r.Body)
	if err != nil {
		atomic.AddInt64(&s.requestsFailed, 1)
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(ErrorResponse{Error: "invalid_request", Message: err.Error()})
		return
	}

	var transfer EdgeTransfer
	if err := json.Unmarshal(body, &transfer); err != nil {
		atomic.AddInt64(&s.requestsFailed, 1)
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(ErrorResponse{Error: "invalid_request", Message: err.Error()})
		return
	}

	if pgDB == nil {
		w.WriteHeader(http.StatusServiceUnavailable)
		json.NewEncoder(w).Encode(ErrorResponse{Error: "no_db", Message: "database unavailable"})
		return
	}

	transfer.SyncStatus = "pending"
	_, err = pgDB.Exec(`INSERT INTO edge_transfers (id, debit_account_id, credit_account_id, amount, ledger, code, agent_code, reference, sync_status)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'pending')
		ON CONFLICT (id) DO NOTHING`,
		transfer.ID, transfer.DebitAccountID, transfer.CreditAccountID,
		transfer.Amount, transfer.Ledger, transfer.Code, transfer.AgentCode, transfer.Reference)
	if err != nil {
		atomic.AddInt64(&s.requestsFailed, 1)
		w.WriteHeader(http.StatusInternalServerError)
		json.NewEncoder(w).Encode(ErrorResponse{Error: "persist_failed", Message: err.Error()})
		return
	}

	pgDB.Exec(`UPDATE edge_sync_state SET value = (SELECT COUNT(*) FROM edge_transfers WHERE sync_status='pending')::TEXT, updated_at=NOW() WHERE key='pending_count'`)

	atomic.AddInt64(&s.requestsSuccess, 1)
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"status":     "committed_locally",
		"id":         transfer.ID,
		"sync_status": "pending",
	})
}

func (s *Service) syncToCore(ctx context.Context) {
	if pgDB == nil {
		return
	}

	rows, err := pgDB.QueryContext(ctx, `SELECT id, debit_account_id, credit_account_id, amount, ledger, code, agent_code, reference
		FROM edge_transfers WHERE sync_status='pending' ORDER BY created_at LIMIT 500 FOR UPDATE SKIP LOCKED`)
	if err != nil {
		log.Printf("[edge] sync query error: %v", err)
		return
	}
	defer rows.Close()

	var transfers []EdgeTransfer
	for rows.Next() {
		var t EdgeTransfer
		rows.Scan(&t.ID, &t.DebitAccountID, &t.CreditAccountID, &t.Amount, &t.Ledger, &t.Code, &t.AgentCode, &t.Reference)
		transfers = append(transfers, t)
	}

	if len(transfers) == 0 {
		return
	}

	corePayload, _ := json.Marshal(transfers)
	url := fmt.Sprintf("%s/api/v1/transfers", s.TBCoreURL)
	resp, err := http.Post(url, "application/json", bytes.NewReader(corePayload))
	if err != nil {
		log.Printf("[edge] core unreachable: %v — transfers remain pending", err)
		return
	}
	defer resp.Body.Close()

	if resp.StatusCode < 300 {
		for _, t := range transfers {
			pgDB.Exec(`UPDATE edge_transfers SET sync_status='synced', synced_at=NOW() WHERE id=$1`, t.ID)
		}
		pgDB.Exec(`UPDATE edge_sync_state SET value = (SELECT COUNT(*) FROM edge_transfers WHERE sync_status='synced')::TEXT, updated_at=NOW() WHERE key='synced_count'`)
		pgDB.Exec(`UPDATE edge_sync_state SET value = (SELECT COUNT(*) FROM edge_transfers WHERE sync_status='pending')::TEXT, updated_at=NOW() WHERE key='pending_count'`)
		log.Printf("[edge] Synced %d transfers to core", len(transfers))
	} else {
		for _, t := range transfers {
			pgDB.Exec(`UPDATE edge_transfers SET sync_status='failed' WHERE id=$1`, t.ID)
		}
		pgDB.Exec(`UPDATE edge_sync_state SET value = (SELECT COUNT(*) FROM edge_transfers WHERE sync_status='failed')::TEXT, updated_at=NOW() WHERE key='failed_count'`)
		log.Printf("[edge] Core rejected %d transfers (status=%d)", len(transfers), resp.StatusCode)
	}
}

func (s *Service) healthHandler(w http.ResponseWriter, r *http.Request) {
	var pending, synced, failed string
	if pgDB != nil {
		pgDB.QueryRow(`SELECT value FROM edge_sync_state WHERE key='pending_count'`).Scan(&pending)
		pgDB.QueryRow(`SELECT value FROM edge_sync_state WHERE key='synced_count'`).Scan(&synced)
		pgDB.QueryRow(`SELECT value FROM edge_sync_state WHERE key='failed_count'`).Scan(&failed)
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"status":      "healthy",
		"service":     s.Name,
		"version":     s.Version,
		"uptime":      time.Since(s.StartTime).String(),
		"persistence": "postgresql",
		"sync": map[string]string{
			"pending": pending,
			"synced":  synced,
			"failed":  failed,
		},
	})
}

func (s *Service) syncStatusHandler(w http.ResponseWriter, r *http.Request) {
	var pending, synced, failed int
	if pgDB != nil {
		pgDB.QueryRow(`SELECT COUNT(*) FROM edge_transfers WHERE sync_status='pending'`).Scan(&pending)
		pgDB.QueryRow(`SELECT COUNT(*) FROM edge_transfers WHERE sync_status='synced'`).Scan(&synced)
		pgDB.QueryRow(`SELECT COUNT(*) FROM edge_transfers WHERE sync_status='failed'`).Scan(&failed)
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"pending":  pending,
		"synced":   synced,
		"failed":   failed,
		"postgres": "connected",
	})
}

func (s *Service) triggerSyncHandler(w http.ResponseWriter, r *http.Request) {
	s.syncToCore(r.Context())
	json.NewEncoder(w).Encode(map[string]string{"status": "sync_triggered"})
}

func (s *Service) retryFailedHandler(w http.ResponseWriter, r *http.Request) {
	if pgDB != nil {
		pgDB.Exec(`UPDATE edge_transfers SET sync_status='pending' WHERE sync_status='failed'`)
	}
	json.NewEncoder(w).Encode(map[string]string{"status": "failed_requeued"})
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

func main() {
	initDB()

	tbCoreURL := os.Getenv("TB_CORE_URL")
	if tbCoreURL == "" {
		tbCoreURL = "http://tigerbeetle-core:8080"
	}

	svc := &Service{
		Name:      "tigerbeetle-edge",
		Version:   "2.0.0",
		StartTime: time.Now(),
		TBCoreURL: tbCoreURL,
	}

	shutdownTracer := initTracer("tigerbeetle-edge", "2.0.0")
	defer func() {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		_ = shutdownTracer(ctx)
	}()

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	go func() {
		ticker := time.NewTicker(10 * time.Second)
		defer ticker.Stop()
		for {
			select {
			case <-ctx.Done():
				return
			case <-ticker.C:
				svc.syncToCore(ctx)
			}
		}
	}()

	router := mux.NewRouter()
	router.HandleFunc("/health", svc.healthHandler).Methods("GET")
	router.HandleFunc("/transfers", svc.commitTransferHandler).Methods("POST")
	router.HandleFunc("/sync/status", svc.syncStatusHandler).Methods("GET")
	router.HandleFunc("/sync/trigger", svc.triggerSyncHandler).Methods("POST")
	router.HandleFunc("/sync/retry", svc.retryFailedHandler).Methods("POST")

	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	log.Printf("Starting TigerBeetle Edge v2.0.0 on :%s (offline-first, PostgreSQL-backed)", port)
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
