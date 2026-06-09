// Package bootstrap provides a one-call production bootstrap for all 54Link Go services.
// It wires together OpenTelemetry, rate limiting, mTLS, and graceful shutdown.
package bootstrap

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"os"
	"time"

	"github.com/54link/pos-shell/services/go/shared/middleware"
)

// Config holds service-level configuration.
type Config struct {
	// ServiceName is used in OTel traces and logs (e.g. "api-gateway").
	ServiceName string
	// ServiceVersion is the semver string (e.g. "1.0.0").
	ServiceVersion string
	// ListenAddr is the HTTP listen address (e.g. ":8080").
	// Defaults to ":8080" or $PORT if set.
	ListenAddr string
	// RateLimit is requests per second per instance (token bucket). Default: 500.
	RateLimit float64
	// RateBurst is the burst size. Default: 100.
	RateBurst int
	// MTLSEnabled enables mutual TLS. Reads MTLS_CERT_FILE, MTLS_KEY_FILE, MTLS_CA_FILE.
	MTLSEnabled bool
	// Handler is the root HTTP handler (typically a mux).
	Handler http.Handler
}

// Run starts the service with all production middleware applied and blocks until shutdown.
// Usage:
//
//	bootstrap.Run(bootstrap.Config{
//	    ServiceName: "api-gateway",
//	    ServiceVersion: "1.0.0",
//	    Handler: myMux,
//	})
func Run(cfg Config) {
	if cfg.ServiceName == "" {
		cfg.ServiceName = os.Getenv("SERVICE_NAME")
	}
	if cfg.ServiceVersion == "" {
		cfg.ServiceVersion = os.Getenv("SERVICE_VERSION")
		if cfg.ServiceVersion == "" {
			cfg.ServiceVersion = "1.0.0"
		}
	}
	if cfg.ListenAddr == "" {
		if port := os.Getenv("PORT"); port != "" {
			cfg.ListenAddr = ":" + port
		} else {
			cfg.ListenAddr = ":8080"
		}
	}
	if cfg.RateLimit == 0 {
		cfg.RateLimit = 500
	}
	if cfg.RateBurst == 0 {
		cfg.RateBurst = 100
	}

	// ── OpenTelemetry ──────────────────────────────────────────────────────────
	shutdownTracer, err := middleware.InitTracer(cfg.ServiceName, cfg.ServiceVersion)
	if err != nil {
		log.Printf("[%s] OTel init warning (non-fatal): %v", cfg.ServiceName, err)
	}

	// ── Middleware chain ───────────────────────────────────────────────────────
	// Order: OTel → Rate Limit → Handler
	rl := middleware.NewRateLimiter(middleware.RateLimit(cfg.RateLimit), cfg.RateBurst)
	chain := middleware.OTelHTTPMiddleware(cfg.ServiceName)(rl.HTTPMiddleware(cfg.Handler))

	// ── TLS configuration ──────────────────────────────────────────────────────
	srv := &http.Server{
		Addr:         cfg.ListenAddr,
		Handler:      chain,
		ReadTimeout:  30 * time.Second,
		WriteTimeout: 30 * time.Second,
		IdleTimeout:  120 * time.Second,
	}

	if cfg.MTLSEnabled {
		tlsCfg, tlsErr := middleware.MTLSConfig(
			os.Getenv("MTLS_CERT_FILE"),
			os.Getenv("MTLS_KEY_FILE"),
			os.Getenv("MTLS_CA_FILE"),
		)
		if tlsErr != nil {
			log.Printf("[%s] mTLS config warning (non-fatal): %v", cfg.ServiceName, tlsErr)
		} else {
			srv.TLSConfig = tlsCfg
		}
	}

	// ── Start server ───────────────────────────────────────────────────────────
	go func() {
		log.Printf("[%s] listening on %s (mTLS=%v)", cfg.ServiceName, cfg.ListenAddr, cfg.MTLSEnabled)
		var serveErr error
		if cfg.MTLSEnabled && srv.TLSConfig != nil {
			serveErr = srv.ListenAndServeTLS(
				os.Getenv("MTLS_CERT_FILE"),
				os.Getenv("MTLS_KEY_FILE"),
			)
		} else {
			serveErr = srv.ListenAndServe()
		}
		if serveErr != nil && serveErr != http.ErrServerClosed {
			log.Fatalf("[%s] server error: %v", cfg.ServiceName, serveErr)
		}
	}()

	// ── Graceful shutdown ──────────────────────────────────────────────────────
	middleware.GracefulHTTPShutdown(cfg.ServiceName, srv, func(ctx context.Context) error {
		if shutdownTracer != nil {
			return shutdownTracer(ctx)
		}
		return nil
	})
}

// HealthHandler returns a simple /healthz handler for Kubernetes probes.
func HealthHandler(serviceName, version string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprintf(w, `{"service":%q,"version":%q,"status":"ok"}`, serviceName, version)
	}
}
