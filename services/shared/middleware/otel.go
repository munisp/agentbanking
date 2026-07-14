// Package middleware provides shared production middleware for all 54agent Go services.
// Includes: OpenTelemetry tracing, rate limiting, mTLS, and graceful shutdown helpers.
package middleware

import (
	"context"
	"crypto/tls"
	"crypto/x509"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracehttp"
	"go.opentelemetry.io/otel/propagation"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.26.0"
	"go.opentelemetry.io/otel/trace"
	"golang.org/x/time/rate"
)

// ─── OpenTelemetry ────────────────────────────────────────────────────────────

// InitTracer initialises the OpenTelemetry SDK and returns a shutdown function.
// OTEL_EXPORTER_OTLP_ENDPOINT defaults to http://otel-collector:4318.
func InitTracer(serviceName, serviceVersion string) (func(context.Context) error, error) {
	endpoint := os.Getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
	if endpoint == "" {
		endpoint = "http://otel-collector:4318"
	}

	exporter, err := otlptracehttp.New(
		context.Background(),
		otlptracehttp.WithEndpoint(endpoint),
		otlptracehttp.WithInsecure(),
	)
	if err != nil {
		return nil, fmt.Errorf("create OTLP exporter: %w", err)
	}

	res, err := resource.New(context.Background(),
		resource.WithAttributes(
			semconv.ServiceName(serviceName),
			semconv.ServiceVersion(serviceVersion),
			attribute.String("deployment.environment", os.Getenv("ENVIRONMENT")),
		),
	)
	if err != nil {
		return nil, fmt.Errorf("create OTel resource: %w", err)
	}

	tp := sdktrace.NewTracerProvider(
		sdktrace.WithBatcher(exporter),
		sdktrace.WithResource(res),
		sdktrace.WithSampler(sdktrace.ParentBased(sdktrace.TraceIDRatioBased(1.0))),
	)
	otel.SetTracerProvider(tp)
	otel.SetTextMapPropagator(propagation.NewCompositeTextMapPropagator(
		propagation.TraceContext{},
		propagation.Baggage{},
	))

	return tp.Shutdown, nil
}

// Tracer returns a named tracer from the global provider.
func Tracer(name string) trace.Tracer {
	return otel.Tracer(name)
}

// OTelHTTPMiddleware injects trace context into every incoming HTTP request.
func OTelHTTPMiddleware(serviceName string) func(http.Handler) http.Handler {
	tracer := otel.Tracer(serviceName)
	propagator := otel.GetTextMapPropagator()

	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			ctx := propagator.Extract(r.Context(), propagation.HeaderCarrier(r.Header))
			ctx, span := tracer.Start(ctx, r.Method+" "+r.URL.Path,
				trace.WithAttributes(
					semconv.HTTPRequestMethodKey.String(r.Method),
					semconv.URLPath(r.URL.Path),
					semconv.ServerAddress(r.Host),
				),
			)
			defer span.End()

			rw := &responseWriter{ResponseWriter: w, statusCode: http.StatusOK}
			next.ServeHTTP(rw, r.WithContext(ctx))

			span.SetAttributes(semconv.HTTPResponseStatusCode(rw.statusCode))
		})
	}
}

type responseWriter struct {
	http.ResponseWriter
	statusCode int
}

func (rw *responseWriter) WriteHeader(code int) {
	rw.statusCode = code
	rw.ResponseWriter.WriteHeader(code)
}

// ─── Rate Limiting ────────────────────────────────────────────────────────────

// RateLimiter wraps golang.org/x/time/rate for per-IP rate limiting.
type RateLimiter struct {
	limiter *rate.Limiter
}

// NewRateLimiter creates a token-bucket limiter: r requests/second, burst b.
func NewRateLimiter(r rate.Limit, b int) *RateLimiter {
	return &RateLimiter{limiter: rate.NewLimiter(r, b)}
}

// HTTPMiddleware returns an HTTP middleware that enforces the rate limit.
func (rl *RateLimiter) HTTPMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if !rl.limiter.Allow() {
			http.Error(w, `{"error":"rate limit exceeded"}`, http.StatusTooManyRequests)
			return
		}
		next.ServeHTTP(w, r)
	})
}

// ─── mTLS ─────────────────────────────────────────────────────────────────────

// MTLSConfig builds a *tls.Config for mutual TLS.
// Reads cert/key/ca from MTLS_CERT_FILE, MTLS_KEY_FILE, MTLS_CA_FILE env vars
// (or the provided defaults).
func MTLSConfig(certFile, keyFile, caFile string) (*tls.Config, error) {
	if v := os.Getenv("MTLS_CERT_FILE"); v != "" {
		certFile = v
	}
	if v := os.Getenv("MTLS_KEY_FILE"); v != "" {
		keyFile = v
	}
	if v := os.Getenv("MTLS_CA_FILE"); v != "" {
		caFile = v
	}

	cert, err := tls.LoadX509KeyPair(certFile, keyFile)
	if err != nil {
		return nil, fmt.Errorf("load cert/key: %w", err)
	}

	caCert, err := os.ReadFile(caFile)
	if err != nil {
		return nil, fmt.Errorf("read CA cert: %w", err)
	}

	caPool := x509.NewCertPool()
	if !caPool.AppendCertsFromPEM(caCert) {
		return nil, fmt.Errorf("parse CA cert")
	}

	return &tls.Config{
		Certificates: []tls.Certificate{cert},
		ClientCAs:    caPool,
		ClientAuth:   tls.RequireAndVerifyClientCert,
		MinVersion:   tls.VersionTLS13,
	}, nil
}

// MTLSClientConfig builds a *tls.Config for outbound mTLS connections.
func MTLSClientConfig(certFile, keyFile, caFile string) (*tls.Config, error) {
	cfg, err := MTLSConfig(certFile, keyFile, caFile)
	if err != nil {
		return nil, err
	}
	cfg.ClientAuth = tls.NoClientCert // client mode: no inbound cert required
	return cfg, nil
}

// ─── Graceful Shutdown ────────────────────────────────────────────────────────

// GracefulShutdown blocks until SIGTERM or SIGINT is received, then calls
// the provided shutdown function with a 30-second timeout.
func GracefulShutdown(serviceName string, shutdown func(ctx context.Context) error) {
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	sig := <-quit
	log.Printf("[%s] received signal %s — shutting down gracefully", serviceName, sig)

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	if err := shutdown(ctx); err != nil {
		log.Printf("[%s] shutdown error: %v", serviceName, err)
	} else {
		log.Printf("[%s] shutdown complete", serviceName)
	}
}

// GracefulHTTPShutdown wraps an *http.Server for graceful shutdown.
func GracefulHTTPShutdown(serviceName string, srv *http.Server, extraShutdown ...func(context.Context) error) {
	GracefulShutdown(serviceName, func(ctx context.Context) error {
		for _, fn := range extraShutdown {
			if err := fn(ctx); err != nil {
				log.Printf("[%s] extra shutdown error: %v", serviceName, err)
			}
		}
		return srv.Shutdown(ctx)
	})
}
