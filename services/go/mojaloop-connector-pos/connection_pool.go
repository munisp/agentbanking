package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"strconv"
	"sync"
	"sync/atomic"
	"time"
)

// ── Connection Pool for Mojaloop Central Ledger ─────────────────────────────
// Mojaloop uses MySQL — this pool manages HTTP connections to the Central Ledger
// API, with circuit breaking, retry, and batch settlement support.

type MojaloopPool struct {
	clients     []*http.Client
	mu          sync.Mutex
	idx         atomic.Int64
	maxRetries  int
	baseURL     string
	cbFailures  atomic.Int64
	cbThreshold int64
	cbOpen      atomic.Bool
	cbOpenedAt  atomic.Int64
	cbTimeout   time.Duration
}

func NewMojaloopPool(size int, baseURL string) *MojaloopPool {
	threshold, _ := strconv.ParseInt(getPoolEnv("ML_CB_THRESHOLD", "5"), 10, 64)
	retries, _ := strconv.Atoi(getPoolEnv("ML_MAX_RETRIES", "3"))

	pool := &MojaloopPool{
		clients:     make([]*http.Client, size),
		maxRetries:  retries,
		baseURL:     baseURL,
		cbThreshold: threshold,
		cbTimeout:   30 * time.Second,
	}

	for i := 0; i < size; i++ {
		pool.clients[i] = &http.Client{
			Timeout: 15 * time.Second,
			Transport: &http.Transport{
				MaxIdleConns:        200,
				MaxIdleConnsPerHost: 100,
				MaxConnsPerHost:     200,
				IdleConnTimeout:     90 * time.Second,
				DisableCompression:  false,
				DisableKeepAlives:   false,
			},
		}
	}

	return pool
}

func (p *MojaloopPool) getClient() *http.Client {
	idx := p.idx.Add(1) % int64(len(p.clients))
	return p.clients[idx]
}

func (p *MojaloopPool) isCircuitOpen() bool {
	if !p.cbOpen.Load() {
		return false
	}
	if time.Now().UnixMilli()-p.cbOpenedAt.Load() > p.cbTimeout.Milliseconds() {
		p.cbOpen.Store(false)
		p.cbFailures.Store(0)
		return false
	}
	return true
}

func (p *MojaloopPool) recordSuccess() {
	p.cbFailures.Store(0)
	p.cbOpen.Store(false)
}

func (p *MojaloopPool) recordFailure() {
	failures := p.cbFailures.Add(1)
	if failures >= p.cbThreshold {
		p.cbOpen.Store(true)
		p.cbOpenedAt.Store(time.Now().UnixMilli())
		log.Printf("[MOJALOOP-POOL] Circuit breaker OPEN after %d failures", failures)
	}
}

func (p *MojaloopPool) Do(ctx context.Context, method, path string, body interface{}) (*http.Response, error) {
	if p.isCircuitOpen() {
		return nil, fmt.Errorf("circuit breaker open")
	}

	var lastErr error
	for attempt := 0; attempt <= p.maxRetries; attempt++ {
		if attempt > 0 {
			backoff := time.Duration(attempt*attempt) * 100 * time.Millisecond
			select {
			case <-ctx.Done():
				return nil, ctx.Err()
			case <-time.After(backoff):
			}
		}

		client := p.getClient()
		req, err := http.NewRequestWithContext(ctx, method, p.baseURL+path, nil)
		if err != nil {
			return nil, err
		}
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("Accept", "application/json")

		resp, err := client.Do(req)
		if err != nil {
			lastErr = err
			p.recordFailure()
			continue
		}

		if resp.StatusCode >= 500 {
			resp.Body.Close()
			lastErr = fmt.Errorf("server error: %d", resp.StatusCode)
			p.recordFailure()
			continue
		}

		p.recordSuccess()
		return resp, nil
	}

	return nil, fmt.Errorf("all %d retries exhausted: %w", p.maxRetries, lastErr)
}

// ── Batch Settlement Processor ──────────────────────────────────────────────

type BatchSettlement struct {
	pool        *MojaloopPool
	batchSize   int
	flushInterval time.Duration
	pending     []SettlementItem
	mu          sync.Mutex
	processed   atomic.Int64
}

type SettlementItem struct {
	SettlementID string  `json:"settlementId"`
	ParticipantID string `json:"participantId"`
	Amount       float64 `json:"amount"`
	Currency     string  `json:"currency"`
}

func NewBatchSettlement(pool *MojaloopPool) *BatchSettlement {
	batchSize, _ := strconv.Atoi(getPoolEnv("ML_SETTLEMENT_BATCH", "100"))

	bs := &BatchSettlement{
		pool:        pool,
		batchSize:   batchSize,
		flushInterval: 5 * time.Second,
		pending:     make([]SettlementItem, 0, batchSize),
	}

	go bs.periodicFlush()
	return bs
}

func (bs *BatchSettlement) Add(item SettlementItem) {
	bs.mu.Lock()
	bs.pending = append(bs.pending, item)
	shouldFlush := len(bs.pending) >= bs.batchSize
	var batch []SettlementItem
	if shouldFlush {
		batch = bs.pending
		bs.pending = make([]SettlementItem, 0, bs.batchSize)
	}
	bs.mu.Unlock()

	if shouldFlush {
		go bs.flush(batch)
	}
}

func (bs *BatchSettlement) periodicFlush() {
	ticker := time.NewTicker(bs.flushInterval)
	defer ticker.Stop()

	for range ticker.C {
		bs.mu.Lock()
		if len(bs.pending) > 0 {
			batch := bs.pending
			bs.pending = make([]SettlementItem, 0, bs.batchSize)
			bs.mu.Unlock()
			bs.flush(batch)
		} else {
			bs.mu.Unlock()
		}
	}
}

func (bs *BatchSettlement) flush(batch []SettlementItem) {
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	_, err := bs.pool.Do(ctx, "POST", "/v1/settlement/batch", batch)
	if err != nil {
		log.Printf("[SETTLEMENT] Batch of %d failed: %v", len(batch), err)
		return
	}

	bs.processed.Add(int64(len(batch)))
	log.Printf("[SETTLEMENT] Batch of %d processed (total: %d)", len(batch), bs.processed.Load())
}

// ── Pool Metrics Endpoint ───────────────────────────────────────────────────

type PoolMetrics struct {
	ConnectionPoolSize int   `json:"connection_pool_size"`
	CircuitBreakerOpen bool  `json:"circuit_breaker_open"`
	CircuitFailures    int64 `json:"circuit_failures"`
	SettlementsProcessed int64 `json:"settlements_processed"`
}

func poolMetricsHandler(pool *MojaloopPool, settlement *BatchSettlement) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		metrics := PoolMetrics{
			ConnectionPoolSize: len(pool.clients),
			CircuitBreakerOpen: pool.cbOpen.Load(),
			CircuitFailures:    pool.cbFailures.Load(),
			SettlementsProcessed: settlement.processed.Load(),
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(metrics)
	}
}

func getPoolEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
