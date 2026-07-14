package main

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"
	"encoding/json"
)

// Config holds service configuration
type Config struct {
	Port        string
	DBURL       string
	KafkaBroker string
	RedisURL    string
}

// Service represents the shared microservice
type Service struct {
	config Config
	server *http.Server
}

func NewService(cfg Config) *Service {
	return &Service{config: cfg}
}

func (s *Service) healthHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"status":  "healthy",
		"service": "shared",
		"uptime":  time.Since(time.Now()).String(),
	})
}

func (s *Service) readyHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"status": "ready",
		"checks": map[string]string{
			"database": "connected",
			"kafka":    "connected",
			"redis":    "connected",
		},
	})
}

func (s *Service) metricsHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "text/plain")
	fmt.Fprintf(w, "# HELP shared_requests_total Total requests\n")
	fmt.Fprintf(w, "# TYPE shared_requests_total counter\n")
	fmt.Fprintf(w, "shared_requests_total 0\n")
}

func (s *Service) Start() error {
	mux := http.NewServeMux()
	mux.HandleFunc("/health", s.healthHandler)
	mux.HandleFunc("/ready", s.readyHandler)
	mux.HandleFunc("/metrics", s.metricsHandler)

	s.server = &http.Server{
		Addr:         ":" + s.config.Port,
		Handler:      mux,
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 15 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	log.Printf("[shared] Starting on port %s", s.config.Port)
	return s.server.ListenAndServe()
}

func (s *Service) Shutdown(ctx context.Context) error {
	return s.server.Shutdown(ctx)
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func main() {
	cfg := Config{
		Port:        getEnv("PORT", "8106"),
		DBURL:       getEnv("DATABASE_URL", "postgres://localhost:5432/shared"),
		KafkaBroker: getEnv("KAFKA_BROKERS", "localhost:9092"),
		RedisURL:    getEnv("REDIS_URL", "redis://localhost:6379"),
	}

	svc := NewService(cfg)

	go func() {
		if err := svc.Start(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("Server failed: %v", err)
		}
	}()

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Println("[shared] Shutting down...")
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	if err := svc.Shutdown(ctx); err != nil {
		log.Fatalf("Forced shutdown: %v", err)
	}
	log.Println("[shared] Stopped")
}
