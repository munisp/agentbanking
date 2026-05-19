// Resilience Proxy — Sprint 76
// Connection pooling, circuit breaking, retry with backoff for African networks
// WebSocket fallback to SSE/long-polling, adaptive bandwidth detection
package main

import (
	"encoding/json"
	"log"
	"math"
	"net/http"
	"os"
	"sync"
	"time"
)

const (
	ServiceName    = "resilience-proxy"
	ServiceVersion = "1.0.0"
	DefaultPort    = "9105"
)

type ConnectionMode string
const (
	ModeWebSocket   ConnectionMode = "websocket"
	ModeSSE         ConnectionMode = "sse"
	ModeLongPoll    ConnectionMode = "long-poll"
	ModeOffline     ConnectionMode = "offline"
)

type BandwidthTier string
const (
	TierHigh   BandwidthTier = "high"    // >2Mbps
	TierMedium BandwidthTier = "medium"  // 500kbps-2Mbps
	TierLow    BandwidthTier = "low"     // 100-500kbps
	TierMinimal BandwidthTier = "minimal" // <100kbps
)

type AgentConnection struct {
	AgentID       string         `json:"agentId"`
	Mode          ConnectionMode `json:"mode"`
	BandwidthTier BandwidthTier  `json:"bandwidthTier"`
	BandwidthKbps float64        `json:"bandwidthKbps"`
	LatencyMs     float64        `json:"latencyMs"`
	JitterMs      float64        `json:"jitterMs"`
	PacketLoss    float64        `json:"packetLossPct"`
	LastSeen      int64          `json:"lastSeen"`
	Reconnects    int            `json:"reconnects"`
	QueuedMsgs    int            `json:"queuedMsgs"`
	Region        string         `json:"region"`
	Carrier       string         `json:"carrier"`
}

type ResilienceConfig struct {
	WebSocketTimeout    int     `json:"wsTimeoutMs"`
	SSERetryInterval    int     `json:"sseRetryMs"`
	LongPollInterval    int     `json:"longPollMs"`
	MaxReconnectAttempts int    `json:"maxReconnects"`
	BackoffMultiplier   float64 `json:"backoffMultiplier"`
	MaxBackoffMs        int     `json:"maxBackoffMs"`
	OfflineQueueMax     int     `json:"offlineQueueMax"`
	CompressionEnabled  bool    `json:"compressionEnabled"`
	AdaptiveBandwidth   bool    `json:"adaptiveBandwidth"`
}

type ResilienceProxy struct {
	mu          sync.RWMutex
	connections map[string]*AgentConnection
	config      ResilienceConfig
	metrics     ProxyMetrics
}

type ProxyMetrics struct {
	TotalConnections   int64 `json:"totalConnections"`
	ActiveWebSocket    int   `json:"activeWebSocket"`
	ActiveSSE          int   `json:"activeSSE"`
	ActiveLongPoll     int   `json:"activeLongPoll"`
	OfflineAgents      int   `json:"offlineAgents"`
	TotalReconnects    int64 `json:"totalReconnects"`
	TotalMsgQueued     int64 `json:"totalMsgQueued"`
	TotalMsgDelivered  int64 `json:"totalMsgDelivered"`
	AvgLatencyMs       float64 `json:"avgLatencyMs"`
	AvgBandwidthKbps   float64 `json:"avgBandwidthKbps"`
}

func NewResilienceProxy() *ResilienceProxy {
	return &ResilienceProxy{
		connections: make(map[string]*AgentConnection),
		config: ResilienceConfig{
			WebSocketTimeout: 30000, SSERetryInterval: 5000, LongPollInterval: 10000,
			MaxReconnectAttempts: 10, BackoffMultiplier: 1.5, MaxBackoffMs: 60000,
			OfflineQueueMax: 500, CompressionEnabled: true, AdaptiveBandwidth: true,
		},
	}
}

func (p *ResilienceProxy) DetermineMode(bw, latency, jitter, loss float64) ConnectionMode {
	if bw < 50 || loss > 30 { return ModeOffline }
	if bw < 100 || loss > 15 || latency > 800 { return ModeLongPoll }
	if bw < 500 || loss > 5 || latency > 400 { return ModeSSE }
	return ModeWebSocket
}

func (p *ResilienceProxy) DetermineTier(bw float64) BandwidthTier {
	switch {
	case bw >= 2000: return TierHigh
	case bw >= 500: return TierMedium
	case bw >= 100: return TierLow
	default: return TierMinimal
	}
}

func (p *ResilienceProxy) CalculateBackoff(attempt int) int {
	backoff := float64(1000) * math.Pow(p.config.BackoffMultiplier, float64(attempt))
	if backoff > float64(p.config.MaxBackoffMs) { backoff = float64(p.config.MaxBackoffMs) }
	return int(backoff)
}

func (p *ResilienceProxy) RegisterConnection(agentID, region, carrier string, bw, latency, jitter, loss float64) *AgentConnection {
	mode := p.DetermineMode(bw, latency, jitter, loss)
	tier := p.DetermineTier(bw)
	conn := &AgentConnection{
		AgentID: agentID, Mode: mode, BandwidthTier: tier, BandwidthKbps: bw,
		LatencyMs: latency, JitterMs: jitter, PacketLoss: loss,
		LastSeen: time.Now().UnixMilli(), Region: region, Carrier: carrier,
	}
	p.mu.Lock()
	if existing, ok := p.connections[agentID]; ok {
		conn.Reconnects = existing.Reconnects + 1
		conn.QueuedMsgs = existing.QueuedMsgs
	}
	p.connections[agentID] = conn
	p.metrics.TotalConnections++
	p.mu.Unlock()
	return conn
}

func (p *ResilienceProxy) GetMetrics() ProxyMetrics {
	p.mu.RLock()
	defer p.mu.RUnlock()
	m := p.metrics
	totalLat, totalBW := 0.0, 0.0
	for _, c := range p.connections {
		switch c.Mode {
		case ModeWebSocket: m.ActiveWebSocket++
		case ModeSSE: m.ActiveSSE++
		case ModeLongPoll: m.ActiveLongPoll++
		case ModeOffline: m.OfflineAgents++
		}
		totalLat += c.LatencyMs
		totalBW += c.BandwidthKbps
	}
	n := float64(len(p.connections))
	if n > 0 { m.AvgLatencyMs = totalLat / n; m.AvgBandwidthKbps = totalBW / n }
	return m
}

func main() {
	proxy := NewResilienceProxy()
	mux := http.NewServeMux()

	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(map[string]interface{}{
			"service": ServiceName, "version": ServiceVersion, "status": "healthy",
			"connections": len(proxy.connections),
		})
	})

	mux.HandleFunc("/api/resilience/connect", func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			AgentID string  `json:"agentId"`
			Region  string  `json:"region"`
			Carrier string  `json:"carrier"`
			BW      float64 `json:"bandwidthKbps"`
			Latency float64 `json:"latencyMs"`
			Jitter  float64 `json:"jitterMs"`
			Loss    float64 `json:"packetLossPct"`
		}
		json.NewDecoder(r.Body).Decode(&req)
		conn := proxy.RegisterConnection(req.AgentID, req.Region, req.Carrier, req.BW, req.Latency, req.Jitter, req.Loss)
		json.NewEncoder(w).Encode(conn)
	})

	mux.HandleFunc("/api/resilience/metrics", func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(proxy.GetMetrics())
	})

	mux.HandleFunc("/api/resilience/config", func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodGet {
			json.NewEncoder(w).Encode(proxy.config)
		} else {
			json.NewDecoder(r.Body).Decode(&proxy.config)
			json.NewEncoder(w).Encode(proxy.config)
		}
	})

	mux.HandleFunc("/api/resilience/backoff", func(w http.ResponseWriter, r *http.Request) {
		attempts := []int{0, 1, 2, 3, 4, 5, 6, 7, 8, 9}
		backoffs := make([]map[string]int, len(attempts))
		for i, a := range attempts {
			backoffs[i] = map[string]int{"attempt": a, "backoffMs": proxy.CalculateBackoff(a)}
		}
		json.NewEncoder(w).Encode(backoffs)
	})

	port := getEnv("PORT", DefaultPort)
	log.Printf("[%s] v%s listening on :%s", ServiceName, ServiceVersion, port)
	log.Fatal(http.ListenAndServe(":"+port, mux))
}

func getEnv(key, def string) string {
	if v := os.Getenv(key); v != "" { return v }
	return def
}
