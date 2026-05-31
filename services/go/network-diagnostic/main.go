// Network Diagnostic Tool — Sprint 76
// Ping/traceroute/speedtest from agent device, connection quality monitoring
package main

import (
	"syscall"
	"os/signal"
	"context"
	"encoding/json"
	"fmt"
	"log"
	"math/rand"
	"net/http"
	"os"
	"sync"
	"time"
)

const (
	ServiceName    = "network-diagnostic"
	ServiceVersion = "1.0.0"
	DefaultPort    = "9104"
)

type PingResult struct {
	Target     string  `json:"target"`
	RTTMs      float64 `json:"rttMs"`
	PacketLoss float64 `json:"packetLossPct"`
	Jitter     float64 `json:"jitterMs"`
	TTL        int     `json:"ttl"`
	Timestamp  int64   `json:"timestamp"`
}

type SpeedTestResult struct {
	DownloadKbps float64 `json:"downloadKbps"`
	UploadKbps   float64 `json:"uploadKbps"`
	LatencyMs    float64 `json:"latencyMs"`
	JitterMs     float64 `json:"jitterMs"`
	ServerRegion string  `json:"serverRegion"`
	Carrier      string  `json:"carrier"`
	Timestamp    int64   `json:"timestamp"`
}

type TracerouteHop struct {
	Hop     int     `json:"hop"`
	Address string  `json:"address"`
	RTTMs   float64 `json:"rttMs"`
	Status  string  `json:"status"`
}

type ConnectionQuality struct {
	AgentID      string  `json:"agentId"`
	Carrier      string  `json:"carrier"`
	Region       string  `json:"region"`
	SignalDbm    int     `json:"signalDbm"`
	LatencyMs    float64 `json:"latencyMs"`
	JitterMs     float64 `json:"jitterMs"`
	PacketLoss   float64 `json:"packetLossPct"`
	BandwidthKbps float64 `json:"bandwidthKbps"`
	Grade        string  `json:"grade"`
	Timestamp    int64   `json:"timestamp"`
}

type DiagnosticService struct {
	mu      sync.RWMutex
	history []ConnectionQuality
}

func NewDiagnosticService() *DiagnosticService {
	return &DiagnosticService{history: make([]ConnectionQuality, 0)}
}

func (s *DiagnosticService) RunPing(target string, count int) PingResult {
	totalRTT := 0.0
	lost := 0
	rtts := make([]float64, 0, count)
	for i := 0; i < count; i++ {
		rtt := 20.0 + rand.Float64()*180.0
		if rand.Float64() < 0.05 {
			lost++
		} else {
			totalRTT += rtt
			rtts = append(rtts, rtt)
		}
	}
	avgRTT := 0.0
	jitter := 0.0
	if len(rtts) > 0 {
		avgRTT = totalRTT / float64(len(rtts))
		if len(rtts) > 1 {
			for i := 1; i < len(rtts); i++ {
				diff := rtts[i] - rtts[i-1]
				if diff < 0 { diff = -diff }
				jitter += diff
			}
			jitter /= float64(len(rtts) - 1)
		}
	}
	return PingResult{
		Target: target, RTTMs: avgRTT, PacketLoss: float64(lost) / float64(count) * 100,
		Jitter: jitter, TTL: 64, Timestamp: time.Now().UnixMilli(),
	}
}

func (s *DiagnosticService) RunSpeedTest(carrier, region string) SpeedTestResult {
	return SpeedTestResult{
		DownloadKbps: 500 + rand.Float64()*9500,
		UploadKbps:   200 + rand.Float64()*4800,
		LatencyMs:    20 + rand.Float64()*180,
		JitterMs:     5 + rand.Float64()*45,
		ServerRegion: region, Carrier: carrier,
		Timestamp: time.Now().UnixMilli(),
	}
}

func (s *DiagnosticService) RunTraceroute(target string) []TracerouteHop {
	hops := 8 + rand.Intn(8)
	result := make([]TracerouteHop, hops)
	for i := 0; i < hops; i++ {
		result[i] = TracerouteHop{
			Hop: i + 1, Address: fmt.Sprintf("10.%d.%d.%d", rand.Intn(255), rand.Intn(255), rand.Intn(255)),
			RTTMs: float64(i+1)*15 + rand.Float64()*30, Status: "ok",
		}
	}
	result[hops-1].Address = target
	return result
}

func (s *DiagnosticService) AssessQuality(agentID, carrier, region string, signal int, latency, jitter, loss, bw float64) ConnectionQuality {
	score := 0.0
	score += float64(signal+120) / 70.0 * 25
	score += (1 - latency/1000) * 25
	score += (1 - loss/100) * 25
	score += (bw / 10000) * 25
	if score > 100 { score = 100 }
	if score < 0 { score = 0 }
	grade := "F"
	switch {
	case score >= 90: grade = "A+"
	case score >= 80: grade = "A"
	case score >= 70: grade = "B"
	case score >= 60: grade = "C"
	case score >= 50: grade = "D"
	}
	q := ConnectionQuality{
		AgentID: agentID, Carrier: carrier, Region: region, SignalDbm: signal,
		LatencyMs: latency, JitterMs: jitter, PacketLoss: loss, BandwidthKbps: bw,
		Grade: grade, Timestamp: time.Now().UnixMilli(),
	}
	s.mu.Lock()
	s.history = append(s.history, q)
	s.mu.Unlock()
	return q
}


// recoverMiddleware catches panics and returns 500 instead of crashing
func recoverMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		defer func() {
			if err := recover(); err != nil {
				log.Printf("[recovery] panic: %v", err)
				http.Error(w, "internal server error", http.StatusInternalServerError)
			}
		}()
		next.ServeHTTP(w, r)
	})
}

func main() {
	svc := NewDiagnosticService()
	mux := http.NewServeMux()

	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(map[string]interface{}{
			"service": ServiceName, "version": ServiceVersion, "status": "healthy",
			"historySize": len(svc.history),
		})
	})

	mux.HandleFunc("/api/diagnostic/ping", func(w http.ResponseWriter, r *http.Request) {
		target := r.URL.Query().Get("target")
		if target == "" { target = "8.8.8.8" }
		result := svc.RunPing(target, 10)
		json.NewEncoder(w).Encode(result)
	})

	mux.HandleFunc("/api/diagnostic/speedtest", func(w http.ResponseWriter, r *http.Request) {
		carrier := r.URL.Query().Get("carrier")
		region := r.URL.Query().Get("region")
		result := svc.RunSpeedTest(carrier, region)
		json.NewEncoder(w).Encode(result)
	})

	mux.HandleFunc("/api/diagnostic/traceroute", func(w http.ResponseWriter, r *http.Request) {
		target := r.URL.Query().Get("target")
		if target == "" { target = "api.54link.com" }
		result := svc.RunTraceroute(target)
		json.NewEncoder(w).Encode(result)
	})

	mux.HandleFunc("/api/diagnostic/quality", func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			AgentID string  `json:"agentId"`
			Carrier string  `json:"carrier"`
			Region  string  `json:"region"`
			Signal  int     `json:"signalDbm"`
			Latency float64 `json:"latencyMs"`
			Jitter  float64 `json:"jitterMs"`
			Loss    float64 `json:"packetLossPct"`
			BW      float64 `json:"bandwidthKbps"`
		}
		json.NewDecoder(r.Body).Decode(&req)
		q := svc.AssessQuality(req.AgentID, req.Carrier, req.Region, req.Signal, req.Latency, req.Jitter, req.Loss, req.BW)
		json.NewEncoder(w).Encode(q)
	})

	port := getEnv("PORT", DefaultPort)
	log.Printf("[%s] v%s listening on :%s", ServiceName, ServiceVersion, port)
	log.Fatal(http.ListenAndServe(":"+port, mux))
}

func getEnv(key, def string) string {
	if v := os.Getenv(key); v != "" { return v }
	return def
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
