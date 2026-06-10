package resilience

import (
	"context"
	cryptorand "crypto/rand"
	"encoding/binary"
	"fmt"
	"math"
	"net/http"
	"os"
	"strconv"
	"sync"
	"time"
)

func getEnvInt(key string, fallback int) int {
	if v := os.Getenv(key); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			return n
		}
	}
	return fallback
}

func getEnvFloat(key string, fallback float64) float64 {
	if v := os.Getenv(key); v != "" {
		if f, err := strconv.ParseFloat(v, 64); err == nil {
			return f
		}
	}
	return fallback
}

type CircuitState int

const (
	Closed CircuitState = iota
	Open
	HalfOpen
)

type CircuitBreaker struct {
	mu               sync.Mutex
	state            CircuitState
	failures         int
	successes        int
	failureThreshold int
	successThreshold int
	timeout          time.Duration
	lastFailure      time.Time
}

func NewCircuitBreaker() *CircuitBreaker {
	return &CircuitBreaker{
		state:            Closed,
		failureThreshold: getEnvInt("CB_FAILURE_THRESHOLD", 5),
		successThreshold: getEnvInt("CB_SUCCESS_THRESHOLD", 2),
		timeout:          time.Duration(getEnvInt("CB_TIMEOUT_SECONDS", 30)) * time.Second,
	}
}

func (cb *CircuitBreaker) Allow() bool {
	cb.mu.Lock()
	defer cb.mu.Unlock()
	switch cb.state {
	case Closed:
		return true
	case Open:
		if time.Since(cb.lastFailure) > cb.timeout {
			cb.state = HalfOpen
			cb.successes = 0
			return true
		}
		return false
	case HalfOpen:
		return true
	}
	return false
}

func (cb *CircuitBreaker) RecordSuccess() {
	cb.mu.Lock()
	defer cb.mu.Unlock()
	cb.failures = 0
	if cb.state == HalfOpen {
		cb.successes++
		if cb.successes >= cb.successThreshold {
			cb.state = Closed
		}
	}
}

func (cb *CircuitBreaker) RecordFailure() {
	cb.mu.Lock()
	defer cb.mu.Unlock()
	cb.failures++
	cb.lastFailure = time.Now()
	if cb.failures >= cb.failureThreshold {
		cb.state = Open
	}
}

func (cb *CircuitBreaker) State() CircuitState {
	cb.mu.Lock()
	defer cb.mu.Unlock()
	return cb.state
}

type RetryConfig struct {
	MaxRetries  int
	BackoffBase float64
	BackoffMax  float64
}

func DefaultRetryConfig() RetryConfig {
	return RetryConfig{
		MaxRetries:  getEnvInt("HTTP_RETRIES", 3),
		BackoffBase: getEnvFloat("HTTP_BACKOFF_BASE", 0.5),
		BackoffMax:  getEnvFloat("HTTP_BACKOFF_MAX", 30.0),
	}
}

func RetryDo(ctx context.Context, cfg RetryConfig, fn func() error) error {
	var lastErr error
	for attempt := 0; attempt <= cfg.MaxRetries; attempt++ {
		lastErr = fn()
		if lastErr == nil {
			return nil
		}
		if attempt < cfg.MaxRetries {
			delay := math.Min(cfg.BackoffBase*math.Pow(2, float64(attempt)), cfg.BackoffMax)
			var b [8]byte
			cryptorand.Read(b[:])
			jitter := delay * 0.1 * float64(binary.LittleEndian.Uint64(b[:])) / float64(^uint64(0))
			select {
			case <-ctx.Done():
				return ctx.Err()
			case <-time.After(time.Duration((delay + jitter) * float64(time.Second))):
			}
		}
	}
	return fmt.Errorf("exhausted %d retries: %w", cfg.MaxRetries, lastErr)
}

func ResilientClient() *http.Client {
	connectTimeout := time.Duration(getEnvInt("HTTP_CONNECT_TIMEOUT", 5)) * time.Second
	readTimeout := time.Duration(getEnvInt("HTTP_READ_TIMEOUT", 30)) * time.Second
	return &http.Client{
		Timeout: connectTimeout + readTimeout,
		Transport: &http.Transport{
			MaxIdleConns:        100,
			MaxIdleConnsPerHost: 10,
			IdleConnTimeout:     90 * time.Second,
		},
	}
}
