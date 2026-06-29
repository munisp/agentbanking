package middleware

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"strings"
	"sync"
	"time"
)

var serviceName = getEnv("SERVICE_NAME", "unknown-go-service")

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

type ErrorBody struct {
	Code    int    `json:"code"`
	Message string `json:"message"`
	TraceID string `json:"trace_id,omitempty"`
}

type ErrorResponse struct {
	Error ErrorBody `json:"error"`
}

func WriteError(w http.ResponseWriter, code int, msg string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	json.NewEncoder(w).Encode(ErrorResponse{Error: ErrorBody{Code: code, Message: msg}})
}

func CORSMiddleware(next http.Handler) http.Handler {
	origins := strings.Split(getEnv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:5174,http://localhost:3000"), ",")
	allowed := make(map[string]bool, len(origins))
	for _, o := range origins {
		allowed[strings.TrimSpace(o)] = true
	}
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		origin := r.Header.Get("Origin")
		if allowed[origin] {
			w.Header().Set("Access-Control-Allow-Origin", origin)
		}
		w.Header().Set("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,PATCH,OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Authorization,Content-Type,X-Request-ID,X-Trace-ID,Idempotency-Key")
		w.Header().Set("Access-Control-Expose-Headers", "X-Request-ID,X-Trace-ID,X-RateLimit-Remaining")
		w.Header().Set("Access-Control-Allow-Credentials", "true")
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		next.ServeHTTP(w, r)
	})
}

func SecurityHeaders(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Content-Type-Options", "nosniff")
		w.Header().Set("X-Frame-Options", "DENY")
		w.Header().Set("X-XSS-Protection", "1; mode=block")
		w.Header().Set("Referrer-Policy", "strict-origin-when-cross-origin")
		w.Header().Set("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
		w.Header().Set("Cache-Control", "no-store")
		next.ServeHTTP(w, r)
	})
}

func RequestID(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		reqID := r.Header.Get("X-Request-ID")
		if reqID == "" {
			reqID = fmt.Sprintf("%d", time.Now().UnixNano())
		}
		traceID := r.Header.Get("X-Trace-ID")
		if traceID == "" {
			traceID = fmt.Sprintf("%d", time.Now().UnixNano())
		}
		w.Header().Set("X-Request-ID", reqID)
		w.Header().Set("X-Trace-ID", traceID)
		w.Header().Set("X-Service", serviceName)
		next.ServeHTTP(w, r)
	})
}

type metrics struct {
	mu           sync.Mutex
	requestCount map[string]int64
	errorCount   map[string]int64
	latencySum   map[string]float64
	latencyCount map[string]int64
}

var globalMetrics = &metrics{
	requestCount: make(map[string]int64),
	errorCount:   make(map[string]int64),
	latencySum:   make(map[string]float64),
	latencyCount: make(map[string]int64),
}

func MetricsMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/metrics" || r.URL.Path == "/health" || r.URL.Path == "/health/live" || r.URL.Path == "/health/ready" {
			next.ServeHTTP(w, r)
			return
		}
		start := time.Now()
		rw := &statusWriter{ResponseWriter: w, status: 200}
		next.ServeHTTP(rw, r)
		dur := time.Since(start).Seconds()
		key := r.Method + " " + r.URL.Path
		globalMetrics.mu.Lock()
		globalMetrics.requestCount[key]++
		if rw.status >= 400 {
			globalMetrics.errorCount[key]++
		}
		globalMetrics.latencySum[key] += dur
		globalMetrics.latencyCount[key]++
		globalMetrics.mu.Unlock()
	})
}

type statusWriter struct {
	http.ResponseWriter
	status int
}

func (w *statusWriter) WriteHeader(code int) {
	w.status = code
	w.ResponseWriter.WriteHeader(code)
}

func MetricsHandler(w http.ResponseWriter, r *http.Request) {
	globalMetrics.mu.Lock()
	defer globalMetrics.mu.Unlock()
	w.Header().Set("Content-Type", "text/plain; charset=utf-8")
	fmt.Fprintf(w, "# HELP http_requests_total Total HTTP requests\n# TYPE http_requests_total counter\n")
	for key, cnt := range globalMetrics.requestCount {
		parts := strings.SplitN(key, " ", 2)
		if len(parts) == 2 {
			fmt.Fprintf(w, "http_requests_total{service=%q,method=%q,path=%q} %d\n", serviceName, parts[0], parts[1], cnt)
		}
	}
	fmt.Fprintf(w, "# HELP http_request_duration_seconds HTTP latency\n# TYPE http_request_duration_seconds summary\n")
	for key := range globalMetrics.latencySum {
		parts := strings.SplitN(key, " ", 2)
		if len(parts) == 2 {
			fmt.Fprintf(w, "http_request_duration_seconds_sum{service=%q,method=%q,path=%q} %.6f\n", serviceName, parts[0], parts[1], globalMetrics.latencySum[key])
			fmt.Fprintf(w, "http_request_duration_seconds_count{service=%q,method=%q,path=%q} %d\n", serviceName, parts[0], parts[1], globalMetrics.latencyCount[key])
		}
	}
}

func HealthLiveHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"status": "ok", "service": serviceName})
}

func HealthReadyHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{"status": "ready", "service": serviceName, "checks": map[string]string{}})
}

func Apply(handler http.Handler) http.Handler {
	handler = RequestID(handler)
	handler = MetricsMiddleware(handler)
	handler = SecurityHeaders(handler)
	handler = CORSMiddleware(handler)
	return handler
}

func RegisterHealthRoutes(mux *http.ServeMux) {
	mux.HandleFunc("/health/live", HealthLiveHandler)
	mux.HandleFunc("/health/ready", HealthReadyHandler)
	mux.HandleFunc("/health", HealthLiveHandler)
	mux.HandleFunc("/metrics", MetricsHandler)
}

func SetupLogging() {
	log.SetFlags(0)
	log.SetOutput(os.Stdout)
}
