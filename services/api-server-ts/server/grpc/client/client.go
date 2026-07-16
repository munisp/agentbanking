package grpcclient

// Production gRPC client with retries, circuit breaker, and connection pooling

import (
	"context"
	"fmt"
	"log"
	"sync"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/keepalive"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

type CircuitState int

const (
	CircuitClosed CircuitState = iota
	CircuitOpen
	CircuitHalfOpen
)

type CircuitBreaker struct {
	mu              sync.Mutex
	state           CircuitState
	failures        int
	threshold       int
	lastFailure     time.Time
	resetTimeout    time.Duration
}

func NewCircuitBreaker(threshold int, resetTimeout time.Duration) *CircuitBreaker {
	return &CircuitBreaker{
		state:        CircuitClosed,
		threshold:    threshold,
		resetTimeout: resetTimeout,
	}
}

func (cb *CircuitBreaker) Allow() bool {
	cb.mu.Lock()
	defer cb.mu.Unlock()

	switch cb.state {
	case CircuitClosed:
		return true
	case CircuitOpen:
		if time.Since(cb.lastFailure) > cb.resetTimeout {
			cb.state = CircuitHalfOpen
			return true
		}
		return false
	case CircuitHalfOpen:
		return true
	}
	return false
}

func (cb *CircuitBreaker) RecordSuccess() {
	cb.mu.Lock()
	defer cb.mu.Unlock()
	cb.failures = 0
	cb.state = CircuitClosed
}

func (cb *CircuitBreaker) RecordFailure() {
	cb.mu.Lock()
	defer cb.mu.Unlock()
	cb.failures++
	cb.lastFailure = time.Now()
	if cb.failures >= cb.threshold {
		cb.state = CircuitOpen
	}
}

// ServiceConnection manages a gRPC connection with circuit breaker and retries
type ServiceConnection struct {
	conn    *grpc.ClientConn
	cb      *CircuitBreaker
	target  string
	mu      sync.Mutex
}

var (
	connections = make(map[string]*ServiceConnection)
	connMu      sync.Mutex
)

// GetConnection returns a pooled gRPC connection with circuit breaker
func GetConnection(target string) (*grpc.ClientConn, error) {
	connMu.Lock()
	defer connMu.Unlock()

	if sc, ok := connections[target]; ok {
		if !sc.cb.Allow() {
			return nil, fmt.Errorf("circuit breaker open for %s", target)
		}
		return sc.conn, nil
	}

	conn, err := grpc.Dial(target,
		grpc.WithTransportCredentials(insecure.NewCredentials()), // Use mTLS in production
		grpc.WithKeepaliveParams(keepalive.ClientParameters{
			Time:                10 * time.Second,
			Timeout:             3 * time.Second,
			PermitWithoutStream: true,
		}),
		grpc.WithDefaultCallOptions(
			grpc.MaxCallRecvMsgSize(16 * 1024 * 1024),
			grpc.MaxCallSendMsgSize(16 * 1024 * 1024),
		),
	)
	if err != nil {
		return nil, fmt.Errorf("failed to connect to %s: %w", target, err)
	}

	connections[target] = &ServiceConnection{
		conn:   conn,
		cb:     NewCircuitBreaker(5, 30*time.Second),
		target: target,
	}

	return conn, nil
}

// CallWithRetry executes a gRPC call with retries and circuit breaker
func CallWithRetry(ctx context.Context, target string, maxRetries int, fn func(*grpc.ClientConn) error) error {
	var lastErr error
	for attempt := 0; attempt <= maxRetries; attempt++ {
		conn, err := GetConnection(target)
		if err != nil {
			lastErr = err
			continue
		}

		err = fn(conn)
		if err == nil {
			connMu.Lock()
			if sc, ok := connections[target]; ok {
				sc.cb.RecordSuccess()
			}
			connMu.Unlock()
			return nil
		}

		lastErr = err
		st, ok := status.FromError(err)
		if ok && (st.Code() == codes.Unavailable || st.Code() == codes.DeadlineExceeded) {
			connMu.Lock()
			if sc, ok := connections[target]; ok {
				sc.cb.RecordFailure()
			}
			connMu.Unlock()

			if attempt < maxRetries {
				backoff := time.Duration(1<<uint(attempt)) * 100 * time.Millisecond
				time.Sleep(backoff)
			}
			continue
		}

		return err // Non-retryable error
	}

	return fmt.Errorf("all %d retries failed for %s: %w", maxRetries+1, target, lastErr)
}

// CloseAll closes all pooled connections (call on shutdown)
func CloseAll() {
	connMu.Lock()
	defer connMu.Unlock()
	for target, sc := range connections {
		if err := sc.conn.Close(); err != nil {
			log.Printf("[gRPC] Error closing connection to %s: %v", target, err)
		}
	}
	connections = make(map[string]*ServiceConnection)
}
