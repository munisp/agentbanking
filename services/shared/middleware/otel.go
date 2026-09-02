// Package middleware provides shared production middleware for all 54agent Go services.
// Includes: OpenTelemetry tracing + metrics, tenant context propagation,
// rate limiting, mTLS, and graceful shutdown helpers.
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
	"go.opentelemetry.io/otel/baggage"
	"go.opentelemetry.io/otel/exporters/otlp/otlpmetric/otlpmetrichttp"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracehttp"
	"go.opentelemetry.io/otel/propagation"
	sdkmetric "go.opentelemetry.io/otel/sdk/metric"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.26.0"
	"go.opentelemetry.io/otel/trace"
	"golang.org/x/time/rate"
)

// ─── OpenTelemetry ────────────────────────────────────────────────────────────

const defaultOTLPEndpoint = "http://otel-collector:4318"

// otelEndpoint returns OTEL_EXPORTER_OTLP_ENDPOINT or the in-cluster default.
func otelEndpoint() string {
	endpoint := os.Getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
	if endpoint == "" {
		endpoint = defaultOTLPEndpoint
	}
	return endpoint
}

// otelResource builds the shared OTel resource (service name/version +
// deployment environment) used by both the trace and meter providers.
func otelResource(serviceName, serviceVersion string) (*resource.Resource, error) {
	return resource.New(context.Background(),
		resource.WithAttributes(
			semconv.ServiceName(serviceName),
			semconv.ServiceVersion(serviceVersion),
			attribute.String("deployment.environment", os.Getenv("ENVIRONMENT")),
		),
	)
}

// InitTracer initialises the OpenTelemetry SDK and returns a shutdown function.
// OTEL_EXPORTER_OTLP_ENDPOINT defaults to http://otel-collector:4318.
func InitTracer(serviceName, serviceVersion string) (func(context.Context) error, error) {
	endpoint := otelEndpoint()

	exporter, err := otlptracehttp.New(
		context.Background(),
		otlptracehttp.WithEndpoint(endpoint),
		otlptracehttp.WithInsecure(),
	)
	if err != nil {
		return nil, fmt.Errorf("create OTLP exporter: %w", err)
	}

	res, err := otelResource(serviceName, serviceVersion)
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

// InitTelemetry initialises BOTH the trace provider (identical to InitTracer)
// and a metric MeterProvider exporting via OTLP/HTTP to the same endpoint
// (OTEL_EXPORTER_OTLP_ENDPOINT, default http://otel-collector:4318, insecure),
// with a 30-second PeriodicReader. Resource attributes match the traces.
// The returned shutdown function shuts down both providers.
func InitTelemetry(serviceName, serviceVersion string) (func(context.Context) error, error) {
	shutdownTraces, err := InitTracer(serviceName, serviceVersion)
	if err != nil {
		return nil, err
	}

	metricExporter, err := otlpmetrichttp.New(
		context.Background(),
		otlpmetrichttp.WithEndpoint(otelEndpoint()),
		otlpmetrichttp.WithInsecure(),
	)
	if err != nil {
		return shutdownTraces, fmt.Errorf("create OTLP metric exporter: %w", err)
	}

	res, err := otelResource(serviceName, serviceVersion)
	if err != nil {
		return shutdownTraces, fmt.Errorf("create OTel resource: %w", err)
	}

	mp := sdkmetric.NewMeterProvider(
		sdkmetric.WithReader(sdkmetric.NewPeriodicReader(
			metricExporter,
			sdkmetric.WithInterval(30*time.Second),
		)),
		sdkmetric.WithResource(res),
	)
	otel.SetMeterProvider(mp)

	return func(ctx context.Context) error {
		traceErr := shutdownTraces(ctx)
		metricErr := mp.Shutdown(ctx)
		if traceErr != nil {
			return traceErr
		}
		return metricErr
	}, nil
}

// Tracer returns a named tracer from the global provider.
func Tracer(name string) trace.Tracer {
	return otel.Tracer(name)
}

// ─── Tenant context ───────────────────────────────────────────────────────────

// tenantIDBaggageKey is the W3C baggage key carrying the tenant id across
// service boundaries (shared contract with the TypeScript api-server).
const tenantIDBaggageKey = "tenant.id"

// TenantIDUnknown is used when no tenant id is present on the request/context.
const TenantIDUnknown = "unknown"

// TenantIDFromRequest extracts the tenant id from the X-Tenant-ID header,
// defaulting to "unknown" when absent.
func TenantIDFromRequest(r *http.Request) string {
	if tenantID := r.Header.Get("X-Tenant-ID"); tenantID != "" {
		return tenantID
	}
	return TenantIDUnknown
}

// ContextWithTenant returns a context carrying tenant.id as OTel baggage.
// On baggage encoding failure the original context is returned unchanged.
func ContextWithTenant(ctx context.Context, tenantID string) context.Context {
	member, err := baggage.NewMember(tenantIDBaggageKey, tenantID)
	if err != nil {
		return ctx
	}
	bag, err := baggage.New(member)
	if err != nil {
		return ctx
	}
	return baggage.ContextWithBaggage(ctx, bag)
}

// TenantIDFromContext returns the tenant.id baggage value on the context,
// or "unknown" when absent.
func TenantIDFromContext(ctx context.Context) string {
	if member := baggage.FromContext(ctx).Member(tenantIDBaggageKey); member.Value() != "" {
		return member.Value()
	}
	return TenantIDUnknown
}

// OTelHTTPMiddleware injects trace context into every incoming HTTP request.
// It also propagates tenant context: the X-Tenant-ID header is stamped as a
// tenant.id span attribute and stored as tenant.id baggage on the request
// context (default "unknown").
func OTelHTTPMiddleware(serviceName string) func(http.Handler) http.Handler {
	tracer := otel.Tracer(serviceName)
	propagator := otel.GetTextMapPropagator()

	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			ctx := propagator.Extract(r.Context(), propagation.HeaderCarrier(r.Header))
			tenantID := TenantIDFromRequest(r)
			ctx = ContextWithTenant(ctx, tenantID)
			ctx, span := tracer.Start(ctx, r.Method+" "+r.URL.Path,
				trace.WithAttributes(
					semconv.HTTPRequestMethodKey.String(r.Method),
					semconv.URLPath(r.URL.Path),
					semconv.ServerAddress(r.Host),
					attribute.String(tenantIDBaggageKey, tenantID),
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
