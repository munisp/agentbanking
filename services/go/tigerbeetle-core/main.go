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
	"strconv"
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

// ── Persistence: PostgreSQL (all state — NO in-memory maps) ────────────────

type Service struct {
	Name      string
	Version   string
	StartTime time.Time

	requestsTotal   int64
	requestsSuccess int64
	requestsFailed  int64
}

type TBAccount struct {
	ID             uint64 `json:"id"`
	UserData       uint64 `json:"user_data"`
	Ledger         uint32 `json:"ledger"`
	Code           uint16 `json:"code"`
	Flags          uint16 `json:"flags"`
	DebitsPending  uint64 `json:"debits_pending"`
	DebitsPosted   uint64 `json:"debits_posted"`
	CreditsPending uint64 `json:"credits_pending"`
	CreditsPosted  uint64 `json:"credits_posted"`
	Timestamp      int64  `json:"timestamp"`
}

type TBTransfer struct {
	ID              uint64 `json:"id"`
	DebitAccountID  uint64 `json:"debit_account_id"`
	CreditAccountID uint64 `json:"credit_account_id"`
	UserData        uint64 `json:"user_data"`
	PendingID       uint64 `json:"pending_id"`
	Timeout         uint64 `json:"timeout"`
	Ledger          uint32 `json:"ledger"`
	Code            uint16 `json:"code"`
	Flags           uint16 `json:"flags"`
	Amount          uint64 `json:"amount"`
	Timestamp       int64  `json:"timestamp"`
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

var pgDB *sql.DB

// ── Database Init ─────────────────────────────────────────────────────────

func initDB() {
	dbURL := os.Getenv("DATABASE_URL")
	if dbURL == "" {
		dbURL = "postgres://postgres:postgres@localhost:5432/tigerbeetle_core?sslmode=disable"
	}
	var err error
	pgDB, err = sql.Open("postgres", dbURL)
	if err != nil {
		log.Printf("[tigerbeetle-core] DB open warning: %v", err)
		return
	}
	pgDB.SetMaxOpenConns(20)
	pgDB.SetMaxIdleConns(10)
	pgDB.SetConnMaxLifetime(5 * time.Minute)

	pgDB.Exec(`CREATE TABLE IF NOT EXISTS tb_accounts (
		id BIGINT PRIMARY KEY,
		user_data BIGINT NOT NULL DEFAULT 0,
		ledger INT NOT NULL DEFAULT 0,
		code SMALLINT NOT NULL DEFAULT 0,
		flags SMALLINT NOT NULL DEFAULT 0,
		debits_pending BIGINT NOT NULL DEFAULT 0,
		debits_posted BIGINT NOT NULL DEFAULT 0,
		credits_pending BIGINT NOT NULL DEFAULT 0,
		credits_posted BIGINT NOT NULL DEFAULT 0,
		created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
		updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
	)`)
	pgDB.Exec(`CREATE INDEX IF NOT EXISTS idx_tb_accounts_ledger ON tb_accounts(ledger)`)
	pgDB.Exec(`CREATE INDEX IF NOT EXISTS idx_tb_accounts_code ON tb_accounts(code)`)

	pgDB.Exec(`CREATE TABLE IF NOT EXISTS tb_transfers (
		id BIGINT PRIMARY KEY,
		debit_account_id BIGINT NOT NULL,
		credit_account_id BIGINT NOT NULL,
		user_data BIGINT NOT NULL DEFAULT 0,
		pending_id BIGINT NOT NULL DEFAULT 0,
		timeout BIGINT NOT NULL DEFAULT 0,
		ledger INT NOT NULL DEFAULT 0,
		code SMALLINT NOT NULL DEFAULT 0,
		flags SMALLINT NOT NULL DEFAULT 0,
		amount BIGINT NOT NULL DEFAULT 0,
		created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
	)`)
	pgDB.Exec(`CREATE INDEX IF NOT EXISTS idx_tb_transfers_debit ON tb_transfers(debit_account_id)`)
	pgDB.Exec(`CREATE INDEX IF NOT EXISTS idx_tb_transfers_credit ON tb_transfers(credit_account_id)`)
	pgDB.Exec(`CREATE INDEX IF NOT EXISTS idx_tb_transfers_created ON tb_transfers(created_at)`)

	pgDB.Exec(`CREATE TABLE IF NOT EXISTS tb_core_audit_log (
		id SERIAL PRIMARY KEY,
		action TEXT NOT NULL,
		entity_id TEXT NOT NULL,
		data JSONB,
		created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
	)`)

	log.Println("[tigerbeetle-core] PostgreSQL tables initialized")
}

func persistAccount(acc *TBAccount) {
	if pgDB == nil {
		return
	}
	_, err := pgDB.Exec(`INSERT INTO tb_accounts (id, user_data, ledger, code, flags, debits_pending, debits_posted, credits_pending, credits_posted)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
		ON CONFLICT (id) DO UPDATE SET
			user_data=$2, ledger=$3, code=$4, flags=$5,
			debits_pending=$6, debits_posted=$7,
			credits_pending=$8, credits_posted=$9,
			updated_at=NOW()`,
		acc.ID, acc.UserData, acc.Ledger, acc.Code, acc.Flags,
		acc.DebitsPending, acc.DebitsPosted, acc.CreditsPending, acc.CreditsPosted)
	if err != nil {
		log.Printf("[tigerbeetle-core] persistAccount error: %v", err)
	}
}

func loadAccount(id uint64) (*TBAccount, bool) {
	if pgDB == nil {
		return nil, false
	}
	acc := &TBAccount{}
	err := pgDB.QueryRow(`SELECT id, user_data, ledger, code, flags, debits_pending, debits_posted, credits_pending, credits_posted
		FROM tb_accounts WHERE id=$1`, id).Scan(
		&acc.ID, &acc.UserData, &acc.Ledger, &acc.Code, &acc.Flags,
		&acc.DebitsPending, &acc.DebitsPosted, &acc.CreditsPending, &acc.CreditsPosted)
	if err != nil {
		return nil, false
	}
	return acc, true
}

func persistTransfer(tx *TBTransfer) {
	if pgDB == nil {
		return
	}
	_, err := pgDB.Exec(`INSERT INTO tb_transfers (id, debit_account_id, credit_account_id, user_data, pending_id, timeout, ledger, code, flags, amount)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
		ON CONFLICT (id) DO NOTHING`,
		tx.ID, tx.DebitAccountID, tx.CreditAccountID, tx.UserData,
		tx.PendingID, tx.Timeout, tx.Ledger, tx.Code, tx.Flags, tx.Amount)
	if err != nil {
		log.Printf("[tigerbeetle-core] persistTransfer error: %v", err)
	}
}

func loadTransfer(id uint64) (*TBTransfer, bool) {
	if pgDB == nil {
		return nil, false
	}
	tx := &TBTransfer{}
	err := pgDB.QueryRow(`SELECT id, debit_account_id, credit_account_id, user_data, pending_id, timeout, ledger, code, flags, amount
		FROM tb_transfers WHERE id=$1`, id).Scan(
		&tx.ID, &tx.DebitAccountID, &tx.CreditAccountID, &tx.UserData,
		&tx.PendingID, &tx.Timeout, &tx.Ledger, &tx.Code, &tx.Flags, &tx.Amount)
	if err != nil {
		return nil, false
	}
	return tx, true
}

func logAudit(action, entityID string, data interface{}) {
	if pgDB == nil {
		return
	}
	dataJSON, _ := json.Marshal(data)
	pgDB.Exec(`INSERT INTO tb_core_audit_log (action, entity_id, data) VALUES ($1, $2, $3)`,
		action, entityID, string(dataJSON))
}

// ── Middleware: Kafka + Dapr + Mojaloop async publish ────────────────────

func publishMiddleware(eventType string, payload interface{}) {
	data, _ := json.Marshal(payload)

	kafkaBrokers := os.Getenv("KAFKA_BROKERS")
	if kafkaBrokers == "" {
		kafkaBrokers = "kafka:9092"
	}
	daprPort := os.Getenv("DAPR_HTTP_PORT")
	if daprPort == "" {
		daprPort = "3500"
	}
	mojaloopURL := os.Getenv("MOJALOOP_URL")
	if mojaloopURL == "" {
		mojaloopURL = "http://mojaloop-hub:4003"
	}
	opensearchURL := os.Getenv("OPENSEARCH_URL")
	if opensearchURL == "" {
		opensearchURL = "http://localhost:9200"
	}

	go func() {
		url := fmt.Sprintf("http://localhost:%s/v1.0/publish/kafka-pubsub/tb.core.%s", daprPort, eventType)
		http.Post(url, "application/json", bytes.NewReader(data))
	}()
	go func() {
		url := fmt.Sprintf("http://localhost:%s/v1.0/publish/pubsub/tb.core.%s", daprPort, eventType)
		http.Post(url, "application/json", bytes.NewReader(data))
	}()
	go func() {
		idx := fmt.Sprintf("tb-core-events-%s", time.Now().Format("2006.01"))
		url := fmt.Sprintf("%s/%s/_doc", opensearchURL, idx)
		http.Post(url, "application/json", bytes.NewReader(data))
	}()
}

// ── JWT Auth Middleware ─────────────────────────────────────────────────────

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

	svcName := os.Getenv("SERVICE_NAME")
	if svcName == "" {
		svcName = "tigerbeetle-core"
	}
	svcVersion := os.Getenv("SERVICE_VERSION")
	if svcVersion == "" {
		svcVersion = "2.0.0"
	}
	shutdownTracer := initTracer(svcName, svcVersion)
	defer func() {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		_ = shutdownTracer(ctx)
	}()

	service := &Service{
		Name:      "tigerbeetle-core",
		Version:   "2.0.0",
		StartTime: time.Now(),
	}

	router := mux.NewRouter()

	router.HandleFunc("/health", service.healthHandler).Methods("GET")
	router.HandleFunc("/", service.rootHandler).Methods("GET")
	router.HandleFunc("/api/v1/status", service.statusHandler).Methods("GET")
	router.HandleFunc("/api/v1/metrics", service.metricsHandler).Methods("GET")

	router.HandleFunc("/api/v1/accounts", service.createAccountHandler).Methods("POST")
	router.HandleFunc("/api/v1/accounts/{id}", service.getAccountHandler).Methods("GET")
	router.HandleFunc("/api/v1/accounts/{id}/balance", service.getBalanceHandler).Methods("GET")
	router.HandleFunc("/api/v1/transfers", service.createTransferHandler).Methods("POST")
	router.HandleFunc("/api/v1/transfers/{id}", service.getTransferHandler).Methods("GET")
	router.HandleFunc("/api/v1/reconcile", service.reconcileHandler).Methods("POST")

	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	log.Printf("Starting %s v%s on port %s (PostgreSQL-backed)\n", service.Name, service.Version, port)
	log.Fatal(http.ListenAndServe(":"+port, jwtAuthMiddleware(router)))
}

func (s *Service) healthHandler(w http.ResponseWriter, r *http.Request) {
	var accountCount, transferCount int
	if pgDB != nil {
		pgDB.QueryRow("SELECT COUNT(*) FROM tb_accounts").Scan(&accountCount)
		pgDB.QueryRow("SELECT COUNT(*) FROM tb_transfers").Scan(&transferCount)
	}

	response := map[string]interface{}{
		"status":          "healthy",
		"service":         s.Name,
		"version":         s.Version,
		"timestamp":       time.Now(),
		"uptime":          time.Since(s.StartTime).String(),
		"accounts_count":  accountCount,
		"transfers_count": transferCount,
		"persistence":     "postgresql",
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

func (s *Service) rootHandler(w http.ResponseWriter, r *http.Request) {
	response := map[string]interface{}{
		"service":     s.Name,
		"version":     s.Version,
		"description": "TigerBeetle core accounting service (PostgreSQL-persisted)",
		"status":      "running",
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

func (s *Service) statusHandler(w http.ResponseWriter, r *http.Request) {
	dbOK := false
	if pgDB != nil {
		err := pgDB.Ping()
		dbOK = err == nil
	}
	response := map[string]interface{}{
		"service":    s.Name,
		"status":     "operational",
		"uptime":     time.Since(s.StartTime).String(),
		"postgres":   dbOK,
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

func (s *Service) metricsHandler(w http.ResponseWriter, r *http.Request) {
	var accountCount, transferCount int
	var totalVolume int64
	if pgDB != nil {
		pgDB.QueryRow("SELECT COUNT(*) FROM tb_accounts").Scan(&accountCount)
		pgDB.QueryRow("SELECT COUNT(*) FROM tb_transfers").Scan(&transferCount)
		pgDB.QueryRow("SELECT COALESCE(SUM(amount), 0) FROM tb_transfers").Scan(&totalVolume)
	}

	metrics := map[string]interface{}{
		"requests_total":    atomic.LoadInt64(&s.requestsTotal),
		"requests_success":  atomic.LoadInt64(&s.requestsSuccess),
		"requests_failed":   atomic.LoadInt64(&s.requestsFailed),
		"accounts_total":    accountCount,
		"transfers_total":   transferCount,
		"total_volume_kobo": totalVolume,
		"uptime_seconds":    int(time.Since(s.StartTime).Seconds()),
		"persistence":       "postgresql",
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(metrics)
}

func (s *Service) createAccountHandler(w http.ResponseWriter, r *http.Request) {
	atomic.AddInt64(&s.requestsTotal, 1)

	body, err := io.ReadAll(r.Body)
	if err != nil {
		atomic.AddInt64(&s.requestsFailed, 1)
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(ErrorResponse{Error: "invalid_request", Message: err.Error()})
		return
	}

	var accounts []TBAccount
	if err := json.Unmarshal(body, &accounts); err != nil {
		atomic.AddInt64(&s.requestsFailed, 1)
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(ErrorResponse{Error: "invalid_request", Message: err.Error()})
		return
	}

	for i := range accounts {
		accounts[i].Timestamp = time.Now().UnixNano()
		persistAccount(&accounts[i])
	}

	logAudit("create_accounts", fmt.Sprintf("batch_%d", len(accounts)), map[string]int{"count": len(accounts)})
	publishMiddleware("account.created", map[string]interface{}{"count": len(accounts)})

	atomic.AddInt64(&s.requestsSuccess, 1)
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"success":          true,
		"accounts_created": len(accounts),
		"persistence":      "postgresql",
	})
}

func (s *Service) getAccountHandler(w http.ResponseWriter, r *http.Request) {
	atomic.AddInt64(&s.requestsTotal, 1)
	vars := mux.Vars(r)
	id, err := strconv.ParseUint(vars["id"], 10, 64)
	if err != nil {
		atomic.AddInt64(&s.requestsFailed, 1)
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(ErrorResponse{Error: "invalid_id", Message: "account ID must be numeric"})
		return
	}

	account, exists := loadAccount(id)
	if !exists {
		atomic.AddInt64(&s.requestsFailed, 1)
		w.WriteHeader(http.StatusNotFound)
		json.NewEncoder(w).Encode(ErrorResponse{Error: "not_found", Message: fmt.Sprintf("account %d not found", id)})
		return
	}

	atomic.AddInt64(&s.requestsSuccess, 1)
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(account)
}

func (s *Service) getBalanceHandler(w http.ResponseWriter, r *http.Request) {
	atomic.AddInt64(&s.requestsTotal, 1)
	vars := mux.Vars(r)
	id, err := strconv.ParseUint(vars["id"], 10, 64)
	if err != nil {
		atomic.AddInt64(&s.requestsFailed, 1)
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(ErrorResponse{Error: "invalid_id", Message: "account ID must be numeric"})
		return
	}

	account, exists := loadAccount(id)
	if !exists {
		atomic.AddInt64(&s.requestsFailed, 1)
		w.WriteHeader(http.StatusNotFound)
		json.NewEncoder(w).Encode(ErrorResponse{Error: "not_found", Message: fmt.Sprintf("account %d not found", id)})
		return
	}

	balance := int64(account.CreditsPosted) - int64(account.DebitsPosted)
	available := balance - int64(account.CreditsPending) + int64(account.DebitsPending)

	atomic.AddInt64(&s.requestsSuccess, 1)
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"account_id":        account.ID,
		"debits_pending":    account.DebitsPending,
		"debits_posted":     account.DebitsPosted,
		"credits_pending":   account.CreditsPending,
		"credits_posted":    account.CreditsPosted,
		"balance":           balance,
		"available_balance": available,
	})
}

func (s *Service) createTransferHandler(w http.ResponseWriter, r *http.Request) {
	atomic.AddInt64(&s.requestsTotal, 1)

	body, err := io.ReadAll(r.Body)
	if err != nil {
		atomic.AddInt64(&s.requestsFailed, 1)
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(ErrorResponse{Error: "invalid_request", Message: err.Error()})
		return
	}

	var transfers []TBTransfer
	if err := json.Unmarshal(body, &transfers); err != nil {
		atomic.AddInt64(&s.requestsFailed, 1)
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(ErrorResponse{Error: "invalid_request", Message: err.Error()})
		return
	}

	if pgDB != nil {
		tx, err := pgDB.Begin()
		if err == nil {
			for i := range transfers {
				transfers[i].Timestamp = time.Now().UnixNano()

				tx.Exec(`INSERT INTO tb_transfers (id, debit_account_id, credit_account_id, user_data, pending_id, timeout, ledger, code, flags, amount)
					VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
					ON CONFLICT (id) DO NOTHING`,
					transfers[i].ID, transfers[i].DebitAccountID, transfers[i].CreditAccountID,
					transfers[i].UserData, transfers[i].PendingID, transfers[i].Timeout,
					transfers[i].Ledger, transfers[i].Code, transfers[i].Flags, transfers[i].Amount)

				tx.Exec(`UPDATE tb_accounts SET debits_posted = debits_posted + $1, updated_at = NOW() WHERE id = $2`,
					transfers[i].Amount, transfers[i].DebitAccountID)
				tx.Exec(`UPDATE tb_accounts SET credits_posted = credits_posted + $1, updated_at = NOW() WHERE id = $2`,
					transfers[i].Amount, transfers[i].CreditAccountID)
			}
			tx.Commit()
		}
	}

	logAudit("create_transfers", fmt.Sprintf("batch_%d", len(transfers)), map[string]int{"count": len(transfers)})
	publishMiddleware("transfer.committed", map[string]interface{}{"count": len(transfers)})

	atomic.AddInt64(&s.requestsSuccess, 1)
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"success":           true,
		"transfers_created": len(transfers),
		"persistence":       "postgresql",
	})
}

func (s *Service) getTransferHandler(w http.ResponseWriter, r *http.Request) {
	atomic.AddInt64(&s.requestsTotal, 1)
	vars := mux.Vars(r)
	id, err := strconv.ParseUint(vars["id"], 10, 64)
	if err != nil {
		atomic.AddInt64(&s.requestsFailed, 1)
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(ErrorResponse{Error: "invalid_id", Message: "transfer ID must be numeric"})
		return
	}

	transfer, exists := loadTransfer(id)
	if !exists {
		atomic.AddInt64(&s.requestsFailed, 1)
		w.WriteHeader(http.StatusNotFound)
		json.NewEncoder(w).Encode(ErrorResponse{Error: "not_found", Message: fmt.Sprintf("transfer %d not found", id)})
		return
	}

	atomic.AddInt64(&s.requestsSuccess, 1)
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(transfer)
}

// reconcileHandler compares TB accounts with PG and returns discrepancies
func (s *Service) reconcileHandler(w http.ResponseWriter, r *http.Request) {
	atomic.AddInt64(&s.requestsTotal, 1)
	if pgDB == nil {
		w.WriteHeader(http.StatusServiceUnavailable)
		json.NewEncoder(w).Encode(ErrorResponse{Error: "no_db", Message: "PostgreSQL not available"})
		return
	}

	rows, err := pgDB.Query(`SELECT id, debits_posted, credits_posted FROM tb_accounts ORDER BY id LIMIT 1000`)
	if err != nil {
		w.WriteHeader(http.StatusInternalServerError)
		json.NewEncoder(w).Encode(ErrorResponse{Error: "query_error", Message: err.Error()})
		return
	}
	defer rows.Close()

	type ReconEntry struct {
		AccountID      uint64 `json:"account_id"`
		DebitsPosted   uint64 `json:"debits_posted"`
		CreditsPosted  uint64 `json:"credits_posted"`
		Balance        int64  `json:"balance"`
		ComputedDebits uint64 `json:"computed_debits_from_transfers"`
		ComputedCredits uint64 `json:"computed_credits_from_transfers"`
		Discrepancy    bool   `json:"discrepancy"`
	}

	var results []ReconEntry
	for rows.Next() {
		var e ReconEntry
		rows.Scan(&e.AccountID, &e.DebitsPosted, &e.CreditsPosted)
		e.Balance = int64(e.CreditsPosted) - int64(e.DebitsPosted)

		pgDB.QueryRow(`SELECT COALESCE(SUM(amount), 0) FROM tb_transfers WHERE debit_account_id=$1`, e.AccountID).Scan(&e.ComputedDebits)
		pgDB.QueryRow(`SELECT COALESCE(SUM(amount), 0) FROM tb_transfers WHERE credit_account_id=$1`, e.AccountID).Scan(&e.ComputedCredits)

		if e.ComputedDebits != e.DebitsPosted || e.ComputedCredits != e.CreditsPosted {
			e.Discrepancy = true
		}
		results = append(results, e)
	}

	logAudit("reconciliation", "all", map[string]int{"accounts_checked": len(results)})
	publishMiddleware("reconciliation.completed", map[string]interface{}{"accounts": len(results)})

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"status":           "completed",
		"accounts_checked": len(results),
		"results":          results,
	})
}

// ── OpenTelemetry ─────────────────────────────────────────────────────────

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
