package main

import (
	"syscall"
	"os/signal"
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"net/http/httputil"
	"net/url"
	"os"
	"sync"
	"time"
)

// State represents circuit breaker states
type State int

const (
	StateClosed   State = iota // Normal operation — requests pass through
	StateOpen                  // Circuit tripped — requests fail fast
	StateHalfOpen              // Testing recovery — limited requests allowed
)

func (s State) String() string {
	switch s {
	case StateClosed:
		return "closed"
	case StateOpen:
		return "open"
	case StateHalfOpen:
		return "half-open"
	default:
		return "unknown"
	}
}

// CircuitBreaker implements the circuit breaker pattern per upstream service
type CircuitBreaker struct {
	mu              sync.RWMutex
	state           State
	failureCount    int
	successCount    int
	lastFailure     time.Time
	lastStateChange time.Time
	totalRequests   int64
	totalFailures   int64
	totalSuccesses  int64

	// Configuration
	FailureThreshold   int           `json:"failure_threshold"`
	SuccessThreshold   int           `json:"success_threshold"`
	OpenTimeout        time.Duration `json:"open_timeout"`
	HalfOpenMaxReqs    int           `json:"half_open_max_requests"`
	RequestTimeout     time.Duration `json:"request_timeout"`
}

// ServiceConfig holds upstream service configuration
type ServiceConfig struct {
	ID             string `json:"id"`
	Name           string `json:"name"`
	UpstreamURL    string `json:"upstream_url"`
	HealthEndpoint string `json:"health_endpoint"`
	Breaker        *CircuitBreaker
}

// ProxyManager manages circuit breakers for all registered upstream services
type ProxyManager struct {
	mu       sync.RWMutex
	services map[string]*ServiceConfig
}

var (
	manager *ProxyManager
	port    string
)

func init() {
	port = os.Getenv("CIRCUIT_BREAKER_PORT")
	if port == "" {
		port = "8141"
	}

	manager = &ProxyManager{
		services: make(map[string]*ServiceConfig),
	}

	// Register known platform services with their circuit breaker configs
	knownUpstreams := []ServiceConfig{
		{ID: "biometric-orchestrator", Name: "Biometric Orchestrator", UpstreamURL: envOr("BIOMETRIC_ORCHESTRATOR_URL", "http://localhost:8046"), HealthEndpoint: "/health"},
		{ID: "deepface-service", Name: "DeepFace Service", UpstreamURL: envOr("DEEPFACE_SERVICE_URL", "http://localhost:8133"), HealthEndpoint: "/health"},
		{ID: "kyb-engine", Name: "KYB Engine", UpstreamURL: envOr("KYB_ENGINE_URL", "http://localhost:8130"), HealthEndpoint: "/health"},
		{ID: "kyb-risk-engine", Name: "KYB Risk Engine", UpstreamURL: envOr("KYB_RISK_ENGINE_URL", "http://localhost:8131"), HealthEndpoint: "/health"},
		{ID: "kyb-analytics", Name: "KYB Analytics", UpstreamURL: envOr("KYB_ANALYTICS_URL", "http://localhost:8132"), HealthEndpoint: "/health"},
		{ID: "liveness-service", Name: "Liveness Detection", UpstreamURL: envOr("LIVENESS_SERVICE_URL", "http://localhost:8041"), HealthEndpoint: "/health"},
		{ID: "face-matching", Name: "Face Matching", UpstreamURL: envOr("FACE_MATCHING_URL", "http://localhost:8042"), HealthEndpoint: "/health"},
		{ID: "deepfake-detection", Name: "Deepfake Detection", UpstreamURL: envOr("DEEPFAKE_SERVICE_URL", "http://localhost:8043"), HealthEndpoint: "/health"},
		{ID: "ocr-service", Name: "OCR Service", UpstreamURL: envOr("OCR_SERVICE_URL", "http://localhost:8044"), HealthEndpoint: "/health"},
		{ID: "settlement-service", Name: "Settlement Service", UpstreamURL: envOr("SETTLEMENT_SERVICE_URL", "http://localhost:8050"), HealthEndpoint: "/health"},
		{ID: "fraud-engine", Name: "Fraud Engine", UpstreamURL: envOr("FRAUD_ENGINE_URL", "http://localhost:8060"), HealthEndpoint: "/health"},
		{ID: "notification-service", Name: "Notification Service", UpstreamURL: envOr("NOTIFICATION_SERVICE_URL", "http://localhost:8070"), HealthEndpoint: "/health"},
		{ID: "payment-gateway", Name: "Payment Gateway", UpstreamURL: envOr("PAYMENT_GATEWAY_URL", "http://localhost:8080"), HealthEndpoint: "/health"},
	}

	for i := range knownUpstreams {
		knownUpstreams[i].Breaker = &CircuitBreaker{
			state:            StateClosed,
			lastStateChange:  time.Now(),
			FailureThreshold: 5,
			SuccessThreshold: 3,
			OpenTimeout:      30 * time.Second,
			HalfOpenMaxReqs:  3,
			RequestTimeout:   10 * time.Second,
		}
		manager.services[knownUpstreams[i].ID] = &knownUpstreams[i]
	}
}

func envOr(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

// AllowRequest checks if a request should be allowed through the circuit breaker
func (cb *CircuitBreaker) AllowRequest() bool {
	cb.mu.Lock()
	defer cb.mu.Unlock()

	switch cb.state {
	case StateClosed:
		return true
	case StateOpen:
		if time.Since(cb.lastStateChange) > cb.OpenTimeout {
			cb.state = StateHalfOpen
			cb.successCount = 0
			cb.failureCount = 0
			cb.lastStateChange = time.Now()
			log.Printf("[circuit-breaker] Transitioning to HALF-OPEN")
			return true
		}
		return false
	case StateHalfOpen:
		return cb.successCount+cb.failureCount < cb.HalfOpenMaxReqs
	}
	return false
}

// RecordSuccess records a successful request
func (cb *CircuitBreaker) RecordSuccess() {
	cb.mu.Lock()
	defer cb.mu.Unlock()

	cb.totalSuccesses++
	cb.totalRequests++

	switch cb.state {
	case StateHalfOpen:
		cb.successCount++
		if cb.successCount >= cb.SuccessThreshold {
			cb.state = StateClosed
			cb.failureCount = 0
			cb.lastStateChange = time.Now()
			log.Printf("[circuit-breaker] Transitioning to CLOSED (recovered)")
		}
	case StateClosed:
		cb.failureCount = 0
	}
}

// RecordFailure records a failed request
func (cb *CircuitBreaker) RecordFailure() {
	cb.mu.Lock()
	defer cb.mu.Unlock()

	cb.totalFailures++
	cb.totalRequests++
	cb.failureCount++
	cb.lastFailure = time.Now()

	switch cb.state {
	case StateClosed:
		if cb.failureCount >= cb.FailureThreshold {
			cb.state = StateOpen
			cb.lastStateChange = time.Now()
			log.Printf("[circuit-breaker] Transitioning to OPEN (tripped after %d failures)", cb.failureCount)
		}
	case StateHalfOpen:
		cb.state = StateOpen
		cb.lastStateChange = time.Now()
		log.Printf("[circuit-breaker] Transitioning back to OPEN (half-open failure)")
	}
}

// Stats returns circuit breaker metrics
func (cb *CircuitBreaker) Stats() map[string]interface{} {
	cb.mu.RLock()
	defer cb.mu.RUnlock()

	return map[string]interface{}{
		"state":           cb.state.String(),
		"failure_count":   cb.failureCount,
		"success_count":   cb.successCount,
		"total_requests":  cb.totalRequests,
		"total_failures":  cb.totalFailures,
		"total_successes": cb.totalSuccesses,
		"last_failure":    cb.lastFailure,
		"last_state_change": cb.lastStateChange,
	}
}

func handleProxy(w http.ResponseWriter, r *http.Request) {
	serviceID := r.URL.Query().Get("service")
	if serviceID == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "service query param required"})
		return
	}

	manager.mu.RLock()
	svc, ok := manager.services[serviceID]
	manager.mu.RUnlock()

	if !ok {
		writeJSON(w, http.StatusNotFound, map[string]string{"error": "service not registered"})
		return
	}

	if !svc.Breaker.AllowRequest() {
		writeJSON(w, http.StatusServiceUnavailable, map[string]interface{}{
			"error":   "circuit breaker open",
			"service": serviceID,
			"state":   svc.Breaker.Stats()["state"],
			"retry_after_seconds": svc.Breaker.OpenTimeout.Seconds(),
		})
		return
	}

	upstream, err := url.Parse(svc.UpstreamURL)
	if err != nil {
		svc.Breaker.RecordFailure()
		writeJSON(w, http.StatusBadGateway, map[string]string{"error": "invalid upstream"})
		return
	}

	proxy := httputil.NewSingleHostReverseProxy(upstream)
	proxy.ErrorHandler = func(w http.ResponseWriter, r *http.Request, err error) {
		svc.Breaker.RecordFailure()
		log.Printf("[circuit-breaker] Upstream error for %s: %v", serviceID, err)
		writeJSON(w, http.StatusBadGateway, map[string]string{"error": fmt.Sprintf("upstream error: %v", err)})
	}

	originalDirector := proxy.Director
	proxy.Director = func(r *http.Request) {
		originalDirector(r)
		r.Header.Set("X-Circuit-Breaker", "active")
		r.Header.Set("X-Upstream-Service", serviceID)
	}

	proxy.ModifyResponse = func(resp *http.Response) error {
		if resp.StatusCode >= 500 {
			svc.Breaker.RecordFailure()
		} else {
			svc.Breaker.RecordSuccess()
		}
		return nil
	}

	proxy.ServeHTTP(w, r)
}

func handleStatus(w http.ResponseWriter, r *http.Request) {
	manager.mu.RLock()
	defer manager.mu.RUnlock()

	statuses := make(map[string]interface{})
	for id, svc := range manager.services {
		statuses[id] = map[string]interface{}{
			"name":         svc.Name,
			"upstream_url": svc.UpstreamURL,
			"breaker":      svc.Breaker.Stats(),
		}
	}

	writeJSON(w, http.StatusOK, map[string]interface{}{
		"services": statuses,
		"count":    len(manager.services),
	})
}

func handleReset(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}

	serviceID := r.URL.Query().Get("service")
	if serviceID == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "service param required"})
		return
	}

	manager.mu.RLock()
	svc, ok := manager.services[serviceID]
	manager.mu.RUnlock()

	if !ok {
		writeJSON(w, http.StatusNotFound, map[string]string{"error": "service not found"})
		return
	}

	svc.Breaker.mu.Lock()
	svc.Breaker.state = StateClosed
	svc.Breaker.failureCount = 0
	svc.Breaker.successCount = 0
	svc.Breaker.lastStateChange = time.Now()
	svc.Breaker.mu.Unlock()

	writeJSON(w, http.StatusOK, map[string]string{"message": "circuit breaker reset", "service": serviceID})
}

func handleHealth(w http.ResponseWriter, r *http.Request) {
	manager.mu.RLock()
	openCount := 0
	for _, svc := range manager.services {
		svc.Breaker.mu.RLock()
		if svc.Breaker.state == StateOpen {
			openCount++
		}
		svc.Breaker.mu.RUnlock()
	}
	totalServices := len(manager.services)
	manager.mu.RUnlock()

	status := "healthy"
	if openCount > totalServices/2 {
		status = "degraded"
	}

	writeJSON(w, http.StatusOK, map[string]interface{}{
		"status":         status,
		"service":        "circuit-breaker-proxy",
		"version":        "1.0.0",
		"total_services": totalServices,
		"open_circuits":  openCount,
	})
}

func writeJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(data)
}

func main() {
	mux := http.NewServeMux()
	mux.HandleFunc("/proxy/", handleProxy)
	mux.HandleFunc("/status", handleStatus)
	mux.HandleFunc("/reset", handleReset)
	mux.HandleFunc("/health", handleHealth)

	log.Printf("Circuit Breaker Proxy running on :%s with %d upstream services", port, len(manager.services))
	log.Fatal(http.ListenAndServe(":"+port, mux))
}

// --- Production: Graceful Shutdown ---
func setupGracefulShutdown(srv *http.Server) {
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		sig := <-quit
		log.Printf("[shutdown] Received signal %s, shutting down gracefully...", sig)
		ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
		defer cancel()
		if err := srv.Shutdown(ctx); err != nil {
			log.Printf("[shutdown] Server forced to shutdown: %v", err)
		}
		log.Println("[shutdown] Server exited")
	}()
}
