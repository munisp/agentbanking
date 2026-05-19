// Carrier Signal Monitor — Go microservice
// Polls and tracks signal strength across available carriers (Safaricom, MTN, Airtel, Glo, 9mobile)
// Provides real-time carrier ranking, signal history, and auto-switch recommendations
//
// Endpoints:
//   GET  /carriers            — List all monitored carriers with current signal
//   GET  /carriers/:name      — Get detailed signal info for a specific carrier
//   GET  /ranking             — Get carriers ranked by signal quality
//   POST /report              — Report signal measurement from a device
//   GET  /history/:carrier    — Get signal history for a carrier
//   GET  /recommendation      — Get auto-switch recommendation
//   POST /switch              — Record a carrier switch event
//   GET  /switch-history      — Get carrier switch history
//   GET  /health              — Health check

package main

import (
	"fmt"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"log"
	"math"
	"net/http"
	"sort"
	"strings"
	"sync"
	"time"
)

// ── Types ────────────────────────────────────────────────────────────────────

type CarrierInfo struct {
	Name          string  `json:"name"`
	MccMnc       string  `json:"mccMnc"`
	Country       string  `json:"country"`
	Technology    string  `json:"technology"`
	SignalDbm     float64 `json:"signalDbm"`
	SignalBars    int     `json:"signalBars"`
	LatencyMs     float64 `json:"latencyMs"`
	BandwidthKbps float64 `json:"bandwidthKbps"`
	PacketLossPct float64 `json:"packetLossPct"`
	QualityScore  float64 `json:"qualityScore"`
	Available     bool    `json:"available"`
	LastUpdated   int64   `json:"lastUpdated"`
	SampleCount   int     `json:"sampleCount"`
}

type SignalReport struct {
	Carrier       string  `json:"carrier"`
	AgentCode     string  `json:"agentCode"`
	Region        string  `json:"region"`
	SignalDbm     float64 `json:"signalDbm"`
	LatencyMs     float64 `json:"latencyMs"`
	BandwidthKbps float64 `json:"bandwidthKbps"`
	PacketLossPct float64 `json:"packetLossPct"`
	Technology    string  `json:"technology"`
	Timestamp     int64   `json:"timestamp"`
}

type SignalHistoryPoint struct {
	Timestamp     int64   `json:"timestamp"`
	SignalDbm     float64 `json:"signalDbm"`
	LatencyMs     float64 `json:"latencyMs"`
	BandwidthKbps float64 `json:"bandwidthKbps"`
	QualityScore  float64 `json:"qualityScore"`
	AgentCode     string  `json:"agentCode"`
	Region        string  `json:"region"`
}

type SwitchEvent struct {
	ID            string `json:"id"`
	FromCarrier   string `json:"fromCarrier"`
	ToCarrier     string `json:"toCarrier"`
	AgentCode     string `json:"agentCode"`
	Reason        string `json:"reason"`
	Timestamp     int64  `json:"timestamp"`
	AutoTriggered bool   `json:"autoTriggered"`
}

type SwitchRecommendation struct {
	ShouldSwitch  bool    `json:"shouldSwitch"`
	CurrentCarrier string `json:"currentCarrier"`
	BestCarrier   string  `json:"bestCarrier"`
	CurrentScore  float64 `json:"currentScore"`
	BestScore     float64 `json:"bestScore"`
	Improvement   float64 `json:"improvement"`
	Reason        string  `json:"reason"`
}

// ── Data Store ───────────────────────────────────────────────────────────────

var (
	carriers      = make(map[string]*CarrierInfo)
	signalHistory = make(map[string][]SignalHistoryPoint) // carrier -> history
	switchHistory []SwitchEvent
	mu            sync.RWMutex
	maxHistory    = 10000
)

func init() {
	// Initialize known African carriers
	knownCarriers := []struct {
		name    string
		mccMnc  string
		country string
	}{
		{"Safaricom", "639-02", "KE"},
		{"MTN", "621-30", "NG"},
		{"Airtel", "621-20", "NG"},
		{"Glo", "621-50", "NG"},
		{"9mobile", "621-60", "NG"},
		{"MTN_GH", "620-01", "GH"},
		{"Vodafone_GH", "620-02", "GH"},
		{"Orange_SN", "608-01", "SN"},
		{"MTN_ZA", "655-10", "ZA"},
		{"Vodacom_ZA", "655-01", "ZA"},
	}
	for _, c := range knownCarriers {
		carriers[c.name] = &CarrierInfo{
			Name:      c.name,
			MccMnc:    c.mccMnc,
			Country:   c.country,
			Available: true,
			SignalDbm: -75,
			SignalBars: 3,
			QualityScore: 50,
		}
	}
}

func generateID() string {
	b := make([]byte, 6)
	rand.Read(b)
	return "SW-" + hex.EncodeToString(b)
}

func signalToBar(dbm float64) int {
	if dbm >= -50 { return 5 }
	if dbm >= -65 { return 4 }
	if dbm >= -80 { return 3 }
	if dbm >= -95 { return 2 }
	if dbm >= -110 { return 1 }
	return 0
}

func computeQuality(signal, latency, bandwidth, loss float64) float64 {
	sigScore := math.Max(0, math.Min(100, (signal+120)*(100.0/70.0)))
	latScore := math.Max(0, math.Min(100, 100-latency/10))
	bwScore := math.Max(0, math.Min(100, bandwidth/100))
	lossScore := math.Max(0, math.Min(100, 100-loss*10))
	return sigScore*0.25 + latScore*0.30 + bwScore*0.25 + lossScore*0.20
}

// ── Handlers ─────────────────────────────────────────────────────────────────

func handleListCarriers(w http.ResponseWriter, r *http.Request) {
	mu.RLock()
	defer mu.RUnlock()

	list := make([]*CarrierInfo, 0, len(carriers))
	for _, c := range carriers {
		list = append(list, c)
	}
	sort.Slice(list, func(i, j int) bool { return list[i].QualityScore > list[j].QualityScore })

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(list)
}

func handleGetCarrier(w http.ResponseWriter, r *http.Request) {
	name := strings.TrimPrefix(r.URL.Path, "/carriers/")
	if name == "" {
		handleListCarriers(w, r)
		return
	}

	mu.RLock()
	c, exists := carriers[name]
	mu.RUnlock()

	if !exists {
		http.Error(w, "Carrier not found", http.StatusNotFound)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(c)
}

func handleRanking(w http.ResponseWriter, r *http.Request) {
	mu.RLock()
	defer mu.RUnlock()

	type RankedCarrier struct {
		Rank int `json:"rank"`
		*CarrierInfo
	}

	list := make([]RankedCarrier, 0, len(carriers))
	for _, c := range carriers {
		if c.Available && c.SampleCount > 0 {
			list = append(list, RankedCarrier{CarrierInfo: c})
		}
	}
	sort.Slice(list, func(i, j int) bool { return list[i].QualityScore > list[j].QualityScore })
	for i := range list {
		list[i].Rank = i + 1
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(list)
}

func handleReport(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var report SignalReport
	if err := json.NewDecoder(r.Body).Decode(&report); err != nil {
		http.Error(w, "Invalid JSON", http.StatusBadRequest)
		return
	}

	if report.Carrier == "" {
		http.Error(w, "carrier is required", http.StatusBadRequest)
		return
	}
	if report.Timestamp == 0 {
		report.Timestamp = time.Now().UnixMilli()
	}

	mu.Lock()
	defer mu.Unlock()

	c, exists := carriers[report.Carrier]
	if !exists {
		c = &CarrierInfo{
			Name:      report.Carrier,
			Country:   "NG",
			Available: true,
		}
		carriers[report.Carrier] = c
	}

	// Exponential moving average for smooth updates
	alpha := 0.3
	if c.SampleCount == 0 {
		c.SignalDbm = report.SignalDbm
		c.LatencyMs = report.LatencyMs
		c.BandwidthKbps = report.BandwidthKbps
		c.PacketLossPct = report.PacketLossPct
	} else {
		c.SignalDbm = c.SignalDbm*(1-alpha) + report.SignalDbm*alpha
		c.LatencyMs = c.LatencyMs*(1-alpha) + report.LatencyMs*alpha
		c.BandwidthKbps = c.BandwidthKbps*(1-alpha) + report.BandwidthKbps*alpha
		c.PacketLossPct = c.PacketLossPct*(1-alpha) + report.PacketLossPct*alpha
	}
	c.SignalBars = signalToBar(c.SignalDbm)
	c.QualityScore = computeQuality(c.SignalDbm, c.LatencyMs, c.BandwidthKbps, c.PacketLossPct)
	c.Technology = report.Technology
	c.LastUpdated = report.Timestamp
	c.SampleCount++

	// Add to history
	histPoint := SignalHistoryPoint{
		Timestamp:     report.Timestamp,
		SignalDbm:     report.SignalDbm,
		LatencyMs:     report.LatencyMs,
		BandwidthKbps: report.BandwidthKbps,
		QualityScore:  c.QualityScore,
		AgentCode:     report.AgentCode,
		Region:        report.Region,
	}
	signalHistory[report.Carrier] = append(signalHistory[report.Carrier], histPoint)
	if len(signalHistory[report.Carrier]) > maxHistory {
		signalHistory[report.Carrier] = signalHistory[report.Carrier][len(signalHistory[report.Carrier])-maxHistory:]
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"carrier":      report.Carrier,
		"qualityScore": c.QualityScore,
		"signalBars":   c.SignalBars,
		"sampleCount":  c.SampleCount,
	})
}

func handleHistory(w http.ResponseWriter, r *http.Request) {
	carrier := strings.TrimPrefix(r.URL.Path, "/history/")
	if carrier == "" {
		http.Error(w, "Carrier name required", http.StatusBadRequest)
		return
	}

	mu.RLock()
	hist, exists := signalHistory[carrier]
	mu.RUnlock()

	if !exists {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode([]SignalHistoryPoint{})
		return
	}

	// Return last 100 points
	start := 0
	if len(hist) > 100 {
		start = len(hist) - 100
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(hist[start:])
}

func handleRecommendation(w http.ResponseWriter, r *http.Request) {
	currentCarrier := r.URL.Query().Get("current")
	if currentCarrier == "" {
		currentCarrier = "MTN" // default
	}

	mu.RLock()
	defer mu.RUnlock()

	current, exists := carriers[currentCarrier]
	if !exists {
		http.Error(w, "Current carrier not found", http.StatusNotFound)
		return
	}

	var best *CarrierInfo
	for _, c := range carriers {
		if c.Available && c.SampleCount > 0 {
			if best == nil || c.QualityScore > best.QualityScore {
				best = c
			}
		}
	}

	if best == nil {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(SwitchRecommendation{
			ShouldSwitch:   false,
			CurrentCarrier: currentCarrier,
			BestCarrier:    currentCarrier,
			CurrentScore:   current.QualityScore,
			BestScore:      current.QualityScore,
			Reason:         "No alternative carriers available",
		})
		return
	}

	improvement := best.QualityScore - current.QualityScore
	shouldSwitch := improvement > 15 // Switch if >15% improvement

	reason := "Current carrier is optimal"
	if shouldSwitch {
		reason = fmt.Sprintf("%s has %.1f%% better quality score than %s", best.Name, improvement, currentCarrier)
	} else if improvement > 5 {
		reason = fmt.Sprintf("%s is slightly better but not enough to warrant switching (%.1f%% improvement)", best.Name, improvement)
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(SwitchRecommendation{
		ShouldSwitch:   shouldSwitch,
		CurrentCarrier: currentCarrier,
		BestCarrier:    best.Name,
		CurrentScore:   current.QualityScore,
		BestScore:      best.QualityScore,
		Improvement:    improvement,
		Reason:         reason,
	})
}

func handleSwitch(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req struct {
		FromCarrier   string `json:"fromCarrier"`
		ToCarrier     string `json:"toCarrier"`
		AgentCode     string `json:"agentCode"`
		Reason        string `json:"reason"`
		AutoTriggered bool   `json:"autoTriggered"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid JSON", http.StatusBadRequest)
		return
	}

	event := SwitchEvent{
		ID:            generateID(),
		FromCarrier:   req.FromCarrier,
		ToCarrier:     req.ToCarrier,
		AgentCode:     req.AgentCode,
		Reason:        req.Reason,
		Timestamp:     time.Now().UnixMilli(),
		AutoTriggered: req.AutoTriggered,
	}

	mu.Lock()
	switchHistory = append(switchHistory, event)
	if len(switchHistory) > 1000 {
		switchHistory = switchHistory[len(switchHistory)-1000:]
	}
	mu.Unlock()

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(event)
}

func handleSwitchHistory(w http.ResponseWriter, r *http.Request) {
	mu.RLock()
	defer mu.RUnlock()

	start := 0
	if len(switchHistory) > 50 {
		start = len(switchHistory) - 50
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(switchHistory[start:])
}

func handleHealth(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"status":  "healthy",
		"service": "carrier-signal-monitor",
		"version": "1.0.0",
		"uptime":  time.Since(startTime).String(),
		"carriers": len(carriers),
	})
}

var startTime = time.Now()

func main() {
	mux := http.NewServeMux()
	mux.HandleFunc("/carriers/", handleGetCarrier)
	mux.HandleFunc("/carriers", handleListCarriers)
	mux.HandleFunc("/ranking", handleRanking)
	mux.HandleFunc("/report", handleReport)
	mux.HandleFunc("/history/", handleHistory)
	mux.HandleFunc("/recommendation", handleRecommendation)
	mux.HandleFunc("/switch", handleSwitch)
	mux.HandleFunc("/switch-history", handleSwitchHistory)
	mux.HandleFunc("/health", handleHealth)

	port := "8113"
	log.Printf("[carrier-signal-monitor] Starting on :%s", port)
	if err := http.ListenAndServe(":"+port, mux); err != nil {
		log.Fatalf("Server failed: %v", err)
	}
}
