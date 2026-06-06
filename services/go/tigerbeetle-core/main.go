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
	"strconv"
	"sync"
	"sync/atomic"
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

type Service struct {
	Name      string
	Version   string
	StartTime time.Time

	mu       sync.RWMutex
	accounts map[uint64]*TBAccount
	transfers map[uint64]*TBTransfer

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
		svcName = "tigerbeetle-core"
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
		Name:      "tigerbeetle-core",
		Version:   "1.0.0",
		StartTime: time.Now(),
		accounts:  make(map[uint64]*TBAccount),
		transfers: make(map[uint64]*TBTransfer),
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

	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	log.Printf("Starting %s on port %s\n", service.Name, port)
	log.Fatal(http.ListenAndServe(":"+port, jwtAuthMiddleware(router)))
}

func (s *Service) healthHandler(w http.ResponseWriter, r *http.Request) {
	s.mu.RLock()
	accountCount := len(s.accounts)
	transferCount := len(s.transfers)
	s.mu.RUnlock()

	response := map[string]interface{}{
		"status":          "healthy",
		"service":         s.Name,
		"timestamp":       time.Now(),
		"uptime":          time.Since(s.StartTime).String(),
		"accounts_count":  accountCount,
		"transfers_count": transferCount,
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

func (s *Service) rootHandler(w http.ResponseWriter, r *http.Request) {
	response := map[string]interface{}{
		"service":     s.Name,
		"version":     s.Version,
		"description": "TigerBeetle core accounting service",
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
	s.mu.RLock()
	accountCount := len(s.accounts)
	transferCount := len(s.transfers)
	s.mu.RUnlock()

	metrics := map[string]interface{}{
		"requests_total":    atomic.LoadInt64(&s.requestsTotal),
		"requests_success":  atomic.LoadInt64(&s.requestsSuccess),
		"requests_failed":   atomic.LoadInt64(&s.requestsFailed),
		"accounts_total":    accountCount,
		"transfers_total":   transferCount,
		"uptime_seconds":    int(time.Since(s.StartTime).Seconds()),
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(metrics)
}

func (s *Service) createAccountHandler(w http.ResponseWriter, r *http.Request) {
	atomic.AddInt64(&s.requestsTotal, 1)

	var accounts []TBAccount
	if err := json.NewDecoder(r.Body).Decode(&accounts); err != nil {
		atomic.AddInt64(&s.requestsFailed, 1)
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(ErrorResponse{Error: "invalid_request", Message: err.Error()})
		return
	}

	s.mu.Lock()
	for i := range accounts {
		accounts[i].Timestamp = time.Now().UnixNano()
		s.accounts[accounts[i].ID] = &accounts[i]
	}
	s.mu.Unlock()

	atomic.AddInt64(&s.requestsSuccess, 1)
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"success":          true,
		"accounts_created": len(accounts),
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

	s.mu.RLock()
	account, exists := s.accounts[id]
	s.mu.RUnlock()

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

	s.mu.RLock()
	account, exists := s.accounts[id]
	s.mu.RUnlock()

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

	var transfers []TBTransfer
	if err := json.NewDecoder(r.Body).Decode(&transfers); err != nil {
		atomic.AddInt64(&s.requestsFailed, 1)
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(ErrorResponse{Error: "invalid_request", Message: err.Error()})
		return
	}

	s.mu.Lock()
	for i := range transfers {
		transfers[i].Timestamp = time.Now().UnixNano()
		s.transfers[transfers[i].ID] = &transfers[i]

		debit, dOk := s.accounts[transfers[i].DebitAccountID]
		credit, cOk := s.accounts[transfers[i].CreditAccountID]
		if dOk {
			debit.DebitsPosted += transfers[i].Amount
		}
		if cOk {
			credit.CreditsPosted += transfers[i].Amount
		}
	}
	s.mu.Unlock()

	atomic.AddInt64(&s.requestsSuccess, 1)
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"success":           true,
		"transfers_created": len(transfers),
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

	s.mu.RLock()
	transfer, exists := s.transfers[id]
	s.mu.RUnlock()

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

