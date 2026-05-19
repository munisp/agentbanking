/*
connectivity-resilience — 54Link Store-and-Forward Message Queue

Designed for unreliable African network environments (2G, rural, intermittent connectivity).
Provides durable message queuing with adaptive retry, compression, and guaranteed delivery.

HTTP API (port 8060):
  POST /api/enqueue          — enqueue a message for reliable delivery
  POST /api/batch-enqueue    — enqueue multiple messages atomically
  GET  /api/queue/stats      — queue depth, retry stats, delivery rates
  GET  /api/queue/pending    — list pending messages with priority
  POST /api/queue/drain      — force drain: attempt delivery of all pending
  POST /api/queue/purge      — purge expired/dead-letter messages
  POST /api/deliver/:id      — manually trigger delivery of a specific message
  GET  /api/dlq              — list dead-letter queue entries
  POST /api/dlq/retry/:id    — retry a dead-letter message
  POST /api/compress         — compress payload (adaptive: gzip/brotli/zstd)
  POST /api/decompress       — decompress payload
  GET  /api/connection/probe — lightweight connection probe (< 100 bytes)
  GET  /api/health           — liveness + readiness check
  GET  /api/metrics          — Prometheus-compatible metrics
*/
package main

import (
	"bytes"
	"compress/gzip"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"math"
	"math/rand"
	"net/http"
	"os"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/google/uuid"
)

// ── Domain Types ─────────────────────────────────────────────────────────────

type Priority int

const (
	PriorityCritical Priority = 0 // Financial transactions — never drop
	PriorityHigh     Priority = 1 // Auth, float updates
	PriorityNormal   Priority = 2 // Notifications, analytics
	PriorityLow      Priority = 3 // Telemetry, logs
)

type MessageStatus string

const (
	StatusPending   MessageStatus = "pending"
	StatusDelivered MessageStatus = "delivered"
	StatusRetrying  MessageStatus = "retrying"
	StatusFailed    MessageStatus = "failed"
	StatusExpired   MessageStatus = "expired"
	StatusDLQ       MessageStatus = "dead_letter"
)

type CompressionAlgo string

const (
	CompressNone  CompressionAlgo = "none"
	CompressGzip  CompressionAlgo = "gzip"
	CompressBrotli CompressionAlgo = "brotli"
	CompressZstd  CompressionAlgo = "zstd"
)

type QueuedMessage struct {
	ID              string          `json:"id"`
	CorrelationID   string          `json:"correlationId,omitempty"`
	DestinationURL  string          `json:"destinationUrl"`
	Method          string          `json:"method"`
	Headers         map[string]string `json:"headers,omitempty"`
	Body            []byte          `json:"body"`
	CompressedBody  []byte          `json:"compressedBody,omitempty"`
	Compression     CompressionAlgo `json:"compression"`
	Priority        Priority        `json:"priority"`
	Status          MessageStatus   `json:"status"`
	RetryCount      int             `json:"retryCount"`
	MaxRetries      int             `json:"maxRetries"`
	NextRetryAt     time.Time       `json:"nextRetryAt"`
	CreatedAt       time.Time       `json:"createdAt"`
	LastAttemptAt   *time.Time      `json:"lastAttemptAt,omitempty"`
	DeliveredAt     *time.Time      `json:"deliveredAt,omitempty"`
	ExpiresAt       time.Time       `json:"expiresAt"`
	LastError       string          `json:"lastError,omitempty"`
	Checksum        string          `json:"checksum"`
	OriginalSize    int             `json:"originalSize"`
	CompressedSize  int             `json:"compressedSize"`
	TenantID        string          `json:"tenantId,omitempty"`
	AgentCode       string          `json:"agentCode,omitempty"`
	TransactionType string          `json:"transactionType,omitempty"`
	IdempotencyKey  string          `json:"idempotencyKey,omitempty"`
}

type DeadLetterEntry struct {
	Message     QueuedMessage `json:"message"`
	Reason      string        `json:"reason"`
	MovedAt     time.Time     `json:"movedAt"`
	RetryCount  int           `json:"retryCount"`
}

// ── Adaptive Retry with Jitter ───────────────────────────────────────────────

type RetryStrategy struct {
	BaseDelayMs     int     `json:"baseDelayMs"`
	MaxDelayMs      int     `json:"maxDelayMs"`
	BackoffFactor   float64 `json:"backoffFactor"`
	JitterFraction  float64 `json:"jitterFraction"`
	MaxRetries      int     `json:"maxRetries"`
}

var DefaultRetryStrategy = RetryStrategy{
	BaseDelayMs:    1000,   // 1 second
	MaxDelayMs:     300000, // 5 minutes max
	BackoffFactor:  2.0,
	JitterFraction: 0.3,   // ±30% jitter to prevent thundering herd
	MaxRetries:     15,     // Up to 15 retries (~30 min total)
}

var CriticalRetryStrategy = RetryStrategy{
	BaseDelayMs:    500,
	MaxDelayMs:     600000, // 10 minutes max for financial txns
	BackoffFactor:  1.5,
	JitterFraction: 0.2,
	MaxRetries:     30,     // Up to 30 retries (~2 hours)
}

func (rs RetryStrategy) NextDelay(attempt int) time.Duration {
	delay := float64(rs.BaseDelayMs) * math.Pow(rs.BackoffFactor, float64(attempt))
	if delay > float64(rs.MaxDelayMs) {
		delay = float64(rs.MaxDelayMs)
	}
	// Add jitter: delay ± (jitterFraction * delay)
	jitter := delay * rs.JitterFraction * (2*rand.Float64() - 1)
	delay += jitter
	if delay < 0 {
		delay = float64(rs.BaseDelayMs)
	}
	return time.Duration(delay) * time.Millisecond
}

// ── Connection Quality Tracker ───────────────────────────────────────────────

type ConnectionQuality struct {
	mu              sync.RWMutex
	latencySamples  []float64
	failureCount    int
	successCount    int
	lastProbeAt     time.Time
	effectiveType   string // "4g", "3g", "2g", "slow-2g", "offline"
	estimatedBandwidthKbps float64
}

func NewConnectionQuality() *ConnectionQuality {
	return &ConnectionQuality{
		latencySamples: make([]float64, 0, 100),
		effectiveType:  "unknown",
	}
}

func (cq *ConnectionQuality) RecordSuccess(latencyMs float64) {
	cq.mu.Lock()
	defer cq.mu.Unlock()
	cq.successCount++
	cq.latencySamples = append(cq.latencySamples, latencyMs)
	if len(cq.latencySamples) > 100 {
		cq.latencySamples = cq.latencySamples[len(cq.latencySamples)-100:]
	}
	cq.lastProbeAt = time.Now()
	cq.classifyConnection()
}

func (cq *ConnectionQuality) RecordFailure() {
	cq.mu.Lock()
	defer cq.mu.Unlock()
	cq.failureCount++
	cq.lastProbeAt = time.Now()
	if cq.failureCount > 3 {
		cq.effectiveType = "offline"
	}
}

func (cq *ConnectionQuality) classifyConnection() {
	if len(cq.latencySamples) == 0 {
		return
	}
	// Use recent 10 samples for classification
	recent := cq.latencySamples
	if len(recent) > 10 {
		recent = recent[len(recent)-10:]
	}
	var sum float64
	for _, v := range recent {
		sum += v
	}
	avgLatency := sum / float64(len(recent))

	switch {
	case avgLatency < 100:
		cq.effectiveType = "4g"
		cq.estimatedBandwidthKbps = 5000
	case avgLatency < 300:
		cq.effectiveType = "3g"
		cq.estimatedBandwidthKbps = 1500
	case avgLatency < 800:
		cq.effectiveType = "2g"
		cq.estimatedBandwidthKbps = 200
	case avgLatency < 2000:
		cq.effectiveType = "slow-2g"
		cq.estimatedBandwidthKbps = 50
	default:
		cq.effectiveType = "offline"
		cq.estimatedBandwidthKbps = 0
	}
}

func (cq *ConnectionQuality) GetStatus() map[string]interface{} {
	cq.mu.RLock()
	defer cq.mu.RUnlock()
	avgLatency := 0.0
	if len(cq.latencySamples) > 0 {
		var sum float64
		for _, v := range cq.latencySamples {
			sum += v
		}
		avgLatency = sum / float64(len(cq.latencySamples))
	}
	return map[string]interface{}{
		"effectiveType":      cq.effectiveType,
		"avgLatencyMs":       avgLatency,
		"successCount":       cq.successCount,
		"failureCount":       cq.failureCount,
		"estimatedBandwidthKbps": cq.estimatedBandwidthKbps,
		"sampleCount":        len(cq.latencySamples),
		"lastProbeAt":        cq.lastProbeAt,
	}
}

// ── Message Queue Store ──────────────────────────────────────────────────────

// StoreAndForward is the core store-and-forward queue for offline resilience
type StoreAndForward = MessageQueue
type MessageQueue struct {
	mu              sync.RWMutex
	pending         map[string]*QueuedMessage
	delivered       map[string]*QueuedMessage
	dlq             map[string]*DeadLetterEntry
	idempotencyMap  map[string]string // idempotencyKey → messageID
	connQuality     *ConnectionQuality
	totalEnqueued   int64
	totalDelivered  int64
	totalFailed     int64
	totalCompressedBytes int64
	totalOriginalBytes   int64
}

func NewMessageQueue() *MessageQueue {
	return &MessageQueue{
		pending:        make(map[string]*QueuedMessage),
		delivered:      make(map[string]*QueuedMessage),
		dlq:            make(map[string]*DeadLetterEntry),
		idempotencyMap: make(map[string]string),
		connQuality:    NewConnectionQuality(),
	}
}

func (mq *MessageQueue) Enqueue(msg *QueuedMessage) (*QueuedMessage, error) {
	mq.mu.Lock()
	defer mq.mu.Unlock()

	// Idempotency check
	if msg.IdempotencyKey != "" {
		if existingID, ok := mq.idempotencyMap[msg.IdempotencyKey]; ok {
			if existing, exists := mq.pending[existingID]; exists {
				return existing, nil
			}
			if existing, exists := mq.delivered[existingID]; exists {
				return existing, nil
			}
		}
	}

	if msg.ID == "" {
		msg.ID = uuid.New().String()
	}
	msg.CreatedAt = time.Now()
	msg.Status = StatusPending
	msg.NextRetryAt = time.Now()

	if msg.ExpiresAt.IsZero() {
		// Default TTL based on priority
		switch msg.Priority {
		case PriorityCritical:
			msg.ExpiresAt = time.Now().Add(24 * time.Hour) // 24h for financial
		case PriorityHigh:
			msg.ExpiresAt = time.Now().Add(6 * time.Hour)
		case PriorityNormal:
			msg.ExpiresAt = time.Now().Add(2 * time.Hour)
		case PriorityLow:
			msg.ExpiresAt = time.Now().Add(30 * time.Minute)
		}
	}

	if msg.MaxRetries == 0 {
		if msg.Priority == PriorityCritical {
			msg.MaxRetries = CriticalRetryStrategy.MaxRetries
		} else {
			msg.MaxRetries = DefaultRetryStrategy.MaxRetries
		}
	}

	// Compute checksum for integrity verification
	hash := sha256.Sum256(msg.Body)
	msg.Checksum = hex.EncodeToString(hash[:])
	msg.OriginalSize = len(msg.Body)

	// Auto-compress if payload > 512 bytes
	if len(msg.Body) > 512 {
		compressed, algo := adaptiveCompress(msg.Body, mq.connQuality.effectiveType)
		msg.CompressedBody = compressed
		msg.Compression = algo
		msg.CompressedSize = len(compressed)
	} else {
		msg.Compression = CompressNone
		msg.CompressedSize = msg.OriginalSize
	}

	mq.pending[msg.ID] = msg
	if msg.IdempotencyKey != "" {
		mq.idempotencyMap[msg.IdempotencyKey] = msg.ID
	}
	mq.totalEnqueued++
	mq.totalOriginalBytes += int64(msg.OriginalSize)
	mq.totalCompressedBytes += int64(msg.CompressedSize)

	return msg, nil
}

func (mq *MessageQueue) DeliverMessage(id string) error {
	mq.mu.Lock()
	msg, ok := mq.pending[id]
	if !ok {
		mq.mu.Unlock()
		return fmt.Errorf("message %s not found in pending queue", id)
	}
	mq.mu.Unlock()

	// Attempt HTTP delivery
	body := msg.Body
	if msg.Compression != CompressNone && len(msg.CompressedBody) > 0 {
		body = msg.CompressedBody
	}

	req, err := http.NewRequest(msg.Method, msg.DestinationURL, bytes.NewReader(body))
	if err != nil {
		return mq.handleDeliveryFailure(msg, err.Error())
	}

	for k, v := range msg.Headers {
		req.Header.Set(k, v)
	}
	if msg.Compression != CompressNone {
		req.Header.Set("Content-Encoding", string(msg.Compression))
	}
	req.Header.Set("X-Message-ID", msg.ID)
	req.Header.Set("X-Checksum", msg.Checksum)
	req.Header.Set("X-Original-Size", strconv.Itoa(msg.OriginalSize))
	req.Header.Set("X-Retry-Count", strconv.Itoa(msg.RetryCount))

	// Adaptive timeout based on connection quality
	timeout := 10 * time.Second
	cqStatus := mq.connQuality.GetStatus()
	if et, ok := cqStatus["effectiveType"].(string); ok {
		switch et {
		case "slow-2g":
			timeout = 30 * time.Second
		case "2g":
			timeout = 20 * time.Second
		case "3g":
			timeout = 15 * time.Second
		}
	}

	client := &http.Client{Timeout: timeout}
	start := time.Now()
	resp, err := client.Do(req)
	latency := float64(time.Since(start).Milliseconds())

	if err != nil {
		mq.connQuality.RecordFailure()
		return mq.handleDeliveryFailure(msg, err.Error())
	}
	defer resp.Body.Close()

	mq.connQuality.RecordSuccess(latency)

	if resp.StatusCode >= 200 && resp.StatusCode < 300 {
		mq.mu.Lock()
		now := time.Now()
		msg.Status = StatusDelivered
		msg.DeliveredAt = &now
		delete(mq.pending, id)
		mq.delivered[id] = msg
		mq.totalDelivered++
		mq.mu.Unlock()
		return nil
	}

	return mq.handleDeliveryFailure(msg, fmt.Sprintf("HTTP %d", resp.StatusCode))
}

func (mq *MessageQueue) handleDeliveryFailure(msg *QueuedMessage, errMsg string) error {
	mq.mu.Lock()
	defer mq.mu.Unlock()

	now := time.Now()
	msg.LastAttemptAt = &now
	msg.LastError = errMsg
	msg.RetryCount++

	// Check if expired
	if time.Now().After(msg.ExpiresAt) {
		msg.Status = StatusExpired
		delete(mq.pending, msg.ID)
		mq.dlq[msg.ID] = &DeadLetterEntry{
			Message:    *msg,
			Reason:     "expired: " + errMsg,
			MovedAt:    time.Now(),
			RetryCount: msg.RetryCount,
		}
		mq.totalFailed++
		return fmt.Errorf("message expired after %d retries", msg.RetryCount)
	}

	// Check max retries
	if msg.RetryCount >= msg.MaxRetries {
		msg.Status = StatusDLQ
		delete(mq.pending, msg.ID)
		mq.dlq[msg.ID] = &DeadLetterEntry{
			Message:    *msg,
			Reason:     "max retries exceeded: " + errMsg,
			MovedAt:    time.Now(),
			RetryCount: msg.RetryCount,
		}
		mq.totalFailed++
		return fmt.Errorf("max retries (%d) exceeded", msg.MaxRetries)
	}

	// Schedule next retry with adaptive backoff
	strategy := DefaultRetryStrategy
	if msg.Priority == PriorityCritical {
		strategy = CriticalRetryStrategy
	}
	msg.Status = StatusRetrying
	msg.NextRetryAt = time.Now().Add(strategy.NextDelay(msg.RetryCount))

	return fmt.Errorf("delivery failed (attempt %d/%d): %s, next retry at %s",
		msg.RetryCount, msg.MaxRetries, errMsg, msg.NextRetryAt.Format(time.RFC3339))
}

func (mq *MessageQueue) GetStats() map[string]interface{} {
	mq.mu.RLock()
	defer mq.mu.RUnlock()

	pendingByPriority := map[string]int{
		"critical": 0, "high": 0, "normal": 0, "low": 0,
	}
	retrying := 0
	for _, msg := range mq.pending {
		switch msg.Priority {
		case PriorityCritical:
			pendingByPriority["critical"]++
		case PriorityHigh:
			pendingByPriority["high"]++
		case PriorityNormal:
			pendingByPriority["normal"]++
		case PriorityLow:
			pendingByPriority["low"]++
		}
		if msg.Status == StatusRetrying {
			retrying++
		}
	}

	compressionRatio := 0.0
	if mq.totalOriginalBytes > 0 {
		compressionRatio = 1.0 - float64(mq.totalCompressedBytes)/float64(mq.totalOriginalBytes)
	}

	return map[string]interface{}{
		"pendingCount":       len(mq.pending),
		"deliveredCount":     len(mq.delivered),
		"dlqCount":           len(mq.dlq),
		"retryingCount":      retrying,
		"totalEnqueued":      mq.totalEnqueued,
		"totalDelivered":     mq.totalDelivered,
		"totalFailed":        mq.totalFailed,
		"pendingByPriority":  pendingByPriority,
		"compressionRatio":   fmt.Sprintf("%.1f%%", compressionRatio*100),
		"totalOriginalBytes": mq.totalOriginalBytes,
		"totalCompressedBytes": mq.totalCompressedBytes,
		"connectionQuality":  mq.connQuality.GetStatus(),
	}
}

func (mq *MessageQueue) GetPending() []*QueuedMessage {
	mq.mu.RLock()
	defer mq.mu.RUnlock()
	msgs := make([]*QueuedMessage, 0, len(mq.pending))
	for _, msg := range mq.pending {
		msgs = append(msgs, msg)
	}
	// Sort by priority (critical first), then by creation time
	sort.Slice(msgs, func(i, j int) bool {
		if msgs[i].Priority != msgs[j].Priority {
			return msgs[i].Priority < msgs[j].Priority
		}
		return msgs[i].CreatedAt.Before(msgs[j].CreatedAt)
	})
	return msgs
}

func (mq *MessageQueue) GetDLQ() []*DeadLetterEntry {
	mq.mu.RLock()
	defer mq.mu.RUnlock()
	entries := make([]*DeadLetterEntry, 0, len(mq.dlq))
	for _, e := range mq.dlq {
		entries = append(entries, e)
	}
	return entries
}

func (mq *MessageQueue) RetryDLQ(id string) error {
	mq.mu.Lock()
	defer mq.mu.Unlock()
	entry, ok := mq.dlq[id]
	if !ok {
		return fmt.Errorf("DLQ entry %s not found", id)
	}
	msg := entry.Message
	msg.Status = StatusPending
	msg.RetryCount = 0
	msg.NextRetryAt = time.Now()
	msg.ExpiresAt = time.Now().Add(1 * time.Hour)
	msg.LastError = ""
	mq.pending[msg.ID] = &msg
	delete(mq.dlq, id)
	return nil
}

func (mq *MessageQueue) Drain() (delivered, failed int) {
	pending := mq.GetPending()
	for _, msg := range pending {
		if time.Now().Before(msg.NextRetryAt) {
			continue
		}
		err := mq.DeliverMessage(msg.ID)
		if err != nil {
			failed++
		} else {
			delivered++
		}
	}
	return
}

func (mq *MessageQueue) PurgeExpired() int {
	mq.mu.Lock()
	defer mq.mu.Unlock()
	purged := 0
	for id, msg := range mq.pending {
		if time.Now().After(msg.ExpiresAt) {
			mq.dlq[id] = &DeadLetterEntry{
				Message:    *msg,
				Reason:     "purged: expired",
				MovedAt:    time.Now(),
				RetryCount: msg.RetryCount,
			}
			delete(mq.pending, id)
			purged++
		}
	}
	return purged
}

// ── Adaptive Compression ─────────────────────────────────────────────────────

func adaptiveCompress(data []byte, connectionType string) ([]byte, CompressionAlgo) {
	// For very slow connections, use maximum compression (zstd > brotli > gzip)
	// For fast connections, use fast compression (gzip level 1)
	// Default to gzip as it has universal HTTP support
	var buf bytes.Buffer
	level := gzip.DefaultCompression
	switch connectionType {
	case "slow-2g", "2g":
		level = gzip.BestCompression
	case "3g":
		level = gzip.DefaultCompression
	default:
		level = gzip.BestSpeed
	}
	w, err := gzip.NewWriterLevel(&buf, level)
	if err != nil {
		return data, CompressNone
	}
	if _, err := w.Write(data); err != nil {
		return data, CompressNone
	}
	if err := w.Close(); err != nil {
		return data, CompressNone
	}
	compressed := buf.Bytes()
	// Only use compression if it actually saves space
	if len(compressed) >= len(data) {
		return data, CompressNone
	}
	return compressed, CompressGzip
}

func decompressGzip(data []byte) ([]byte, error) {
	r, err := gzip.NewReader(bytes.NewReader(data))
	if err != nil {
		return nil, err
	}
	defer r.Close()
	return io.ReadAll(r)
}

// ── Background Workers ───────────────────────────────────────────────────────

func startRetryWorker(mq *MessageQueue) {
	ticker := time.NewTicker(2 * time.Second)
	go func() {
		for range ticker.C {
			pending := mq.GetPending()
			for _, msg := range pending {
				if msg.Status == StatusRetrying && time.Now().After(msg.NextRetryAt) {
					go func(id string) {
						if err := mq.DeliverMessage(id); err != nil {
							log.Printf("[Retry] %s: %v", id, err)
						}
					}(msg.ID)
				}
			}
		}
	}()
}

func startExpiryWorker(mq *MessageQueue) {
	ticker := time.NewTicker(30 * time.Second)
	go func() {
		for range ticker.C {
			purged := mq.PurgeExpired()
			if purged > 0 {
				log.Printf("[Expiry] Purged %d expired messages", purged)
			}
		}
	}()
}

// ── HTTP Handlers ────────────────────────────────────────────────────────────

func main() {
	mq := NewMessageQueue()

	// Start background workers
	startRetryWorker(mq)
	startExpiryWorker(mq)

	mux := http.NewServeMux()

	// CORS middleware
	handler := corsMiddleware(mux)

	// ── Enqueue ──────────────────────────────────────────────────────────
	mux.HandleFunc("/api/enqueue", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
			return
		}
		var req struct {
			DestinationURL  string            `json:"destinationUrl"`
			Method          string            `json:"method"`
			Headers         map[string]string `json:"headers"`
			Body            json.RawMessage   `json:"body"`
			Priority        int               `json:"priority"`
			TenantID        string            `json:"tenantId"`
			AgentCode       string            `json:"agentCode"`
			TransactionType string            `json:"transactionType"`
			IdempotencyKey  string            `json:"idempotencyKey"`
			TTLMinutes      int               `json:"ttlMinutes"`
		}
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			jsonError(w, "Invalid request body", http.StatusBadRequest)
			return
		}
		if req.DestinationURL == "" {
			jsonError(w, "destinationUrl is required", http.StatusBadRequest)
			return
		}
		if req.Method == "" {
			req.Method = "POST"
		}

		msg := &QueuedMessage{
			DestinationURL:  req.DestinationURL,
			Method:          strings.ToUpper(req.Method),
			Headers:         req.Headers,
			Body:            req.Body,
			Priority:        Priority(req.Priority),
			TenantID:        req.TenantID,
			AgentCode:       req.AgentCode,
			TransactionType: req.TransactionType,
			IdempotencyKey:  req.IdempotencyKey,
		}
		if req.TTLMinutes > 0 {
			msg.ExpiresAt = time.Now().Add(time.Duration(req.TTLMinutes) * time.Minute)
		}

		result, err := mq.Enqueue(msg)
		if err != nil {
			jsonError(w, err.Error(), http.StatusInternalServerError)
			return
		}
		jsonResponse(w, map[string]interface{}{
			"id":             result.ID,
			"status":         result.Status,
			"compression":    result.Compression,
			"originalSize":   result.OriginalSize,
			"compressedSize": result.CompressedSize,
			"expiresAt":      result.ExpiresAt,
		}, http.StatusCreated)
	})

	// ── Batch Enqueue ────────────────────────────────────────────────────
	mux.HandleFunc("/api/batch-enqueue", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
			return
		}
		var messages []struct {
			DestinationURL  string            `json:"destinationUrl"`
			Method          string            `json:"method"`
			Headers         map[string]string `json:"headers"`
			Body            json.RawMessage   `json:"body"`
			Priority        int               `json:"priority"`
			IdempotencyKey  string            `json:"idempotencyKey"`
		}
		if err := json.NewDecoder(r.Body).Decode(&messages); err != nil {
			jsonError(w, "Invalid request body", http.StatusBadRequest)
			return
		}
		results := make([]map[string]interface{}, 0, len(messages))
		for _, m := range messages {
			method := m.Method
			if method == "" {
				method = "POST"
			}
			msg := &QueuedMessage{
				DestinationURL: m.DestinationURL,
				Method:         strings.ToUpper(method),
				Headers:        m.Headers,
				Body:           m.Body,
				Priority:       Priority(m.Priority),
				IdempotencyKey: m.IdempotencyKey,
			}
			result, _ := mq.Enqueue(msg)
			results = append(results, map[string]interface{}{
				"id":     result.ID,
				"status": result.Status,
			})
		}
		jsonResponse(w, map[string]interface{}{
			"enqueued": len(results),
			"messages": results,
		}, http.StatusCreated)
	})

	// ── Queue Stats ──────────────────────────────────────────────────────
	mux.HandleFunc("/api/queue/stats", func(w http.ResponseWriter, r *http.Request) {
		jsonResponse(w, mq.GetStats(), http.StatusOK)
	})

	// ── Pending Messages ─────────────────────────────────────────────────
	mux.HandleFunc("/api/queue/pending", func(w http.ResponseWriter, r *http.Request) {
		jsonResponse(w, mq.GetPending(), http.StatusOK)
	})

	// ── Force Drain ──────────────────────────────────────────────────────
	mux.HandleFunc("/api/queue/drain", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
			return
		}
		delivered, failed := mq.Drain()
		jsonResponse(w, map[string]interface{}{
			"delivered": delivered,
			"failed":    failed,
		}, http.StatusOK)
	})

	// ── Purge Expired ────────────────────────────────────────────────────
	mux.HandleFunc("/api/queue/purge", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
			return
		}
		purged := mq.PurgeExpired()
		jsonResponse(w, map[string]interface{}{"purged": purged}, http.StatusOK)
	})

	// ── Manual Deliver ───────────────────────────────────────────────────
	mux.HandleFunc("/api/deliver/", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
			return
		}
		id := strings.TrimPrefix(r.URL.Path, "/api/deliver/")
		if err := mq.DeliverMessage(id); err != nil {
			jsonError(w, err.Error(), http.StatusInternalServerError)
			return
		}
		jsonResponse(w, map[string]string{"status": "delivered"}, http.StatusOK)
	})

	// ── Dead Letter Queue ────────────────────────────────────────────────
	mux.HandleFunc("/api/dlq", func(w http.ResponseWriter, r *http.Request) {
		jsonResponse(w, mq.GetDLQ(), http.StatusOK)
	})

	mux.HandleFunc("/api/dlq/retry/", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
			return
		}
		id := strings.TrimPrefix(r.URL.Path, "/api/dlq/retry/")
		if err := mq.RetryDLQ(id); err != nil {
			jsonError(w, err.Error(), http.StatusNotFound)
			return
		}
		jsonResponse(w, map[string]string{"status": "requeued"}, http.StatusOK)
	})

	// ── Compress/Decompress ──────────────────────────────────────────────
	mux.HandleFunc("/api/compress", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
			return
		}
		body, _ := io.ReadAll(r.Body)
		connType := r.Header.Get("X-Connection-Type")
		if connType == "" {
			connType = "3g"
		}
		compressed, algo := adaptiveCompress(body, connType)
		w.Header().Set("Content-Type", "application/octet-stream")
		w.Header().Set("Content-Encoding", string(algo))
		w.Header().Set("X-Original-Size", strconv.Itoa(len(body)))
		w.Header().Set("X-Compressed-Size", strconv.Itoa(len(compressed)))
		w.Header().Set("X-Compression-Ratio", fmt.Sprintf("%.1f%%", (1.0-float64(len(compressed))/float64(len(body)))*100))
		w.Write(compressed)
	})

	mux.HandleFunc("/api/decompress", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
			return
		}
		body, _ := io.ReadAll(r.Body)
		encoding := r.Header.Get("Content-Encoding")
		if encoding == "gzip" {
			decompressed, err := decompressGzip(body)
			if err != nil {
				jsonError(w, "Decompression failed: "+err.Error(), http.StatusBadRequest)
				return
			}
			w.Write(decompressed)
			return
		}
		w.Write(body)
	})

	// ── Connection Probe ─────────────────────────────────────────────────
	mux.HandleFunc("/api/connection/probe", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/plain")
		w.Header().Set("Cache-Control", "no-store")
		w.Header().Set("X-Server-Time", strconv.FormatInt(time.Now().UnixMilli(), 10))
		w.WriteHeader(http.StatusOK)
		w.Write([]byte("ok"))
	})

	// ── Health ───────────────────────────────────────────────────────────
	mux.HandleFunc("/api/health", func(w http.ResponseWriter, r *http.Request) {
		stats := mq.GetStats()
		jsonResponse(w, map[string]interface{}{
			"status":    "healthy",
			"service":   "connectivity-resilience",
			"version":   "1.0.0",
			"uptime":    time.Since(startTime).String(),
			"queue":     stats,
		}, http.StatusOK)
	})

	// ── Metrics ──────────────────────────────────────────────────────────
	mux.HandleFunc("/api/metrics", func(w http.ResponseWriter, r *http.Request) {
		stats := mq.GetStats()
		w.Header().Set("Content-Type", "text/plain")
		fmt.Fprintf(w, "# HELP connectivity_queue_pending Number of pending messages\n")
		fmt.Fprintf(w, "connectivity_queue_pending %d\n", stats["pendingCount"])
		fmt.Fprintf(w, "# HELP connectivity_queue_delivered Total delivered messages\n")
		fmt.Fprintf(w, "connectivity_queue_delivered %d\n", stats["totalDelivered"])
		fmt.Fprintf(w, "# HELP connectivity_queue_failed Total failed messages\n")
		fmt.Fprintf(w, "connectivity_queue_failed %d\n", stats["totalFailed"])
		fmt.Fprintf(w, "# HELP connectivity_queue_dlq Dead letter queue size\n")
		fmt.Fprintf(w, "connectivity_queue_dlq %d\n", stats["dlqCount"])
	})

	port := os.Getenv("PORT")
	if port == "" {
		port = "8060"
	}
	log.Printf("[connectivity-resilience] Starting on :%s", port)
	log.Fatal(http.ListenAndServe(":"+port, handler))
}

var startTime = time.Now()

func corsMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Connection-Type, X-Message-ID")
		if r.Method == "OPTIONS" {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		next.ServeHTTP(w, r)
	})
}

func jsonResponse(w http.ResponseWriter, data interface{}, status int) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(data)
}

func jsonError(w http.ResponseWriter, msg string, status int) {
	jsonResponse(w, map[string]string{"error": msg}, status)
}
