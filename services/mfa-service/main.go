package main

import (
	"context"
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha1"
	"encoding/base32"
	"encoding/json"
	"fmt"
	"log/slog"
	"math/big"
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

const (
	serviceName    = "mfa-service"
	serviceVersion = "1.0.0"
	totpWindow     = 1  // ±1 time step tolerance
	totpStep       = 30 // seconds
)

// ── OTel ──────────────────────────────────────────────────────────────────────

func initTracer() func(context.Context) error {
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

// ── TOTP helpers ──────────────────────────────────────────────────────────────

func generateTOTPSecret() (string, error) {
	b := make([]byte, 20)
	if _, err := rand.Read(b); err != nil {
		return "", err
	}
	return base32.StdEncoding.EncodeToString(b), nil
}

func totpCode(secret string, t time.Time) (string, error) {
	key, err := base32.StdEncoding.DecodeString(secret)
	if err != nil {
		return "", err
	}
	counter := t.Unix() / totpStep
	msg := make([]byte, 8)
	for i := 7; i >= 0; i-- {
		msg[i] = byte(counter & 0xff)
		counter >>= 8
	}
	mac := hmac.New(sha1.New, key)
	mac.Write(msg)
	h := mac.Sum(nil)
	offset := h[len(h)-1] & 0x0f
	code := (int(h[offset])&0x7f)<<24 |
		int(h[offset+1])<<16 |
		int(h[offset+2])<<8 |
		int(h[offset+3])
	return fmt.Sprintf("%06d", code%1_000_000), nil
}

func verifyTOTP(secret, userCode string) bool {
	now := time.Now()
	for delta := -totpWindow; delta <= totpWindow; delta++ {
		t := now.Add(time.Duration(delta) * time.Duration(totpStep) * time.Second)
		expected, err := totpCode(secret, t)
		if err == nil && expected == userCode {
			return true
		}
	}
	return false
}

// generateBackupCodes returns 8 random 8-character alphanumeric backup codes.
func generateBackupCodes() ([]string, error) {
	const chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
	codes := make([]string, 8)
	for i := range codes {
		code := make([]byte, 8)
		for j := range code {
			n, err := rand.Int(rand.Reader, big.NewInt(int64(len(chars))))
			if err != nil {
				return nil, err
			}
			code[j] = chars[n.Int64()]
		}
		codes[i] = string(code)
	}
	return codes, nil
}

// ── Handlers ──────────────────────────────────────────────────────────────────

type mfaServer struct{}

func (s *mfaServer) healthHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{
		"status":  "ok",
		"service": serviceName,
		"version": serviceVersion,
	})
}

func (s *mfaServer) enrollHandler(w http.ResponseWriter, r *http.Request) {
	ctx, span := otel.Tracer(serviceName).Start(r.Context(), "mfa.enroll")
	defer span.End()
	_ = ctx

	secret, err := generateTOTPSecret()
	if err != nil {
		http.Error(w, `{"error":"failed to generate secret"}`, http.StatusInternalServerError)
		return
	}
	backupCodes, err := generateBackupCodes()
	if err != nil {
		http.Error(w, `{"error":"failed to generate backup codes"}`, http.StatusInternalServerError)
		return
	}
	issuer := os.Getenv("MFA_ISSUER")
	if issuer == "" {
		issuer = "54agent"
	}
	userID := r.URL.Query().Get("user_id")
	otpAuthURL := fmt.Sprintf("otpauth://totp/%s:%s?secret=%s&issuer=%s&algorithm=SHA1&digits=6&period=30",
		issuer, userID, secret, issuer)

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"secret":       secret,
		"otpauth_url":  otpAuthURL,
		"backup_codes": backupCodes,
	})
}

func (s *mfaServer) verifyHandler(w http.ResponseWriter, r *http.Request) {
	ctx, span := otel.Tracer(serviceName).Start(r.Context(), "mfa.verify")
	defer span.End()
	_ = ctx

	var req struct {
		Secret string `json:"secret"`
		Code   string `json:"code"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, `{"error":"invalid request body"}`, http.StatusBadRequest)
		return
	}
	valid := verifyTOTP(req.Secret, req.Code)
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]bool{"valid": valid})
}

// ── Rate limiting + OTel middleware ───────────────────────────────────────────

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

func otelMiddleware(next http.Handler) http.Handler {
	tracer := otel.Tracer(serviceName)
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		ctx, span := tracer.Start(r.Context(), r.Method+" "+r.URL.Path)
		defer span.End()
		next.ServeHTTP(w, r.WithContext(ctx))
	})
}

// ── Main ──────────────────────────────────────────────────────────────────────

func main() {
	// OTel
	shutdownTracer := initTracer()
	defer func() {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		_ = shutdownTracer(ctx)
	}()

	srv := &mfaServer{}
	router := mux.NewRouter()
	router.HandleFunc("/healthz", srv.healthHandler).Methods("GET")
	router.HandleFunc("/api/v1/mfa/enroll", srv.enrollHandler).Methods("POST")
	router.HandleFunc("/api/v1/mfa/verify", srv.verifyHandler).Methods("POST")

	// Middleware chain: OTel → rate limit → router
	chain := otelMiddleware(rateLimitMiddleware(200, 50, router))

	port := os.Getenv("PORT")
	if port == "" {
		port = "8086"
	}
	httpSrv := &http.Server{
		Addr:         ":" + port,
		Handler:      chain,
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 15 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	go func() {
		slog.Info("MFA service starting", "port", port)
		if err := httpSrv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			slog.Error("Server error", "err", err)
			os.Exit(1)
		}
	}()

	// Graceful shutdown
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGTERM, syscall.SIGINT)
	<-quit
	slog.Info("Shutting down MFA service...")
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	if err := httpSrv.Shutdown(ctx); err != nil {
		slog.Error("Shutdown error", "err", err)
	}
	slog.Info("MFA service stopped")
}
