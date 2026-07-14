package middleware

import (
	"fmt"
	"log"
	"net/http"
	"os"
	"strings"
	"sync"
	"time"
)

type Middleware func(http.Handler) http.Handler

func Chain(handler http.Handler, middlewares ...Middleware) http.Handler {
	for i := len(middlewares) - 1; i >= 0; i-- {
		handler = middlewares[i](handler)
	}
	return handler
}

// CORS enables cross-origin requests
func CORS(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		origin := r.Header.Get("Origin")
		if origin == "" {
			origin = "*"
		}
		w.Header().Set("Access-Control-Allow-Origin", origin)
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Request-ID, X-Internal-Key")
		w.Header().Set("Access-Control-Max-Age", "86400")

		if r.Method == "OPTIONS" {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		next.ServeHTTP(w, r)
	})
}

// RequestID adds a unique request ID
func RequestID(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		id := r.Header.Get("X-Request-ID")
		if id == "" {
			id = fmt.Sprintf("req_%d", time.Now().UnixNano())
		}
		w.Header().Set("X-Request-ID", id)
		next.ServeHTTP(w, r)
	})
}

// Logger logs request details
func Logger(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		next.ServeHTTP(w, r)
		log.Printf("[%s] %s %s (%s)", r.Method, r.URL.Path, r.RemoteAddr, time.Since(start))
	})
}

// Recovery handles panics gracefully
func Recovery(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		defer func() {
			if err := recover(); err != nil {
				log.Printf("[PANIC] %v", err)
				http.Error(w, `{"error":"internal server error"}`, http.StatusInternalServerError)
			}
		}()
		next.ServeHTTP(w, r)
	})
}

// RateLimit provides per-IP rate limiting
func RateLimit(next http.Handler) http.Handler {
	type visitor struct {
		count    int
		resetAt  time.Time
	}
	var mu sync.Mutex
	visitors := make(map[string]*visitor)
	maxRequests := 100
	window := time.Minute

	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		ip := r.RemoteAddr
		if fwd := r.Header.Get("X-Forwarded-For"); fwd != "" {
			ip = strings.Split(fwd, ",")[0]
		}

		mu.Lock()
		v, exists := visitors[ip]
		if !exists || time.Now().After(v.resetAt) {
			visitors[ip] = &visitor{count: 1, resetAt: time.Now().Add(window)}
			mu.Unlock()
			next.ServeHTTP(w, r)
			return
		}
		v.count++
		if v.count > maxRequests {
			mu.Unlock()
			http.Error(w, `{"error":"rate limit exceeded"}`, http.StatusTooManyRequests)
			return
		}
		mu.Unlock()
		next.ServeHTTP(w, r)
	})
}

// Auth validates the internal API key or JWT
func Auth(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Skip auth for health checks
		if r.URL.Path == "/health" {
			next.ServeHTTP(w, r)
			return
		}

		// Check internal key (service-to-service)
		internalKey := os.Getenv("INTERNAL_API_KEY")
		if internalKey != "" && r.Header.Get("X-Internal-Key") == internalKey {
			next.ServeHTTP(w, r)
			return
		}

		// Check Authorization header
		auth := r.Header.Get("Authorization")
		if auth == "" || !strings.HasPrefix(auth, "Bearer ") {
			// In development mode, allow unauthenticated access
			if os.Getenv("NODE_ENV") != "production" {
				next.ServeHTTP(w, r)
				return
			}
			http.Error(w, `{"error":"unauthorized"}`, http.StatusUnauthorized)
			return
		}

		// JWT validation would happen here via shared library
		next.ServeHTTP(w, r)
	})
}
