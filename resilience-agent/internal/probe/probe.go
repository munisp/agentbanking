// Package probe measures round-trip latency to a target endpoint and
// classifies the result into four quality tiers appropriate for the
// Nigerian mobile-network environment.
package probe

import (
	"context"
	"net/http"
	"time"
)

// Quality represents the four connectivity tiers.
type Quality string

const (
	QualityExcellent Quality = "Excellent" // < 300 ms  — strong 4G / WiFi
	QualityGood      Quality = "Good"      // 300–800 ms — normal 3G/4G
	QualityPoor      Quality = "Poor"      // 800–2000 ms — edge / congested cell
	QualityOffline   Quality = "Offline"   // > 2000 ms or error
)

// Result holds a single probe measurement.
type Result struct {
	Quality   Quality       `json:"quality"`
	LatencyMs int64         `json:"latency_ms"`
	ProbeURL  string        `json:"probe_url"`
	Timestamp time.Time     `json:"timestamp"`
	Error     string        `json:"error,omitempty"`
}

var client = &http.Client{
	Timeout: 2500 * time.Millisecond,
	// Disable keep-alives so each probe opens a fresh TCP connection,
	// giving a true cold-path latency measurement.
	Transport: &http.Transport{DisableKeepAlives: true},
}

// Probe performs a single HEAD request to url and returns a Result.
func Probe(url string) Result {
	ctx, cancel := context.WithTimeout(context.Background(), 2500*time.Millisecond)
	defer cancel()

	req, err := http.NewRequestWithContext(ctx, http.MethodHead, url, nil)
	if err != nil {
		return Result{Quality: QualityOffline, Error: err.Error(), Timestamp: time.Now()}
	}

	start := time.Now()
	resp, err := client.Do(req)
	latency := time.Since(start).Milliseconds()

	if err != nil {
		return Result{
			Quality:   QualityOffline,
			LatencyMs: latency,
			ProbeURL:  url,
			Timestamp: time.Now(),
			Error:     err.Error(),
		}
	}
	resp.Body.Close()

	return Result{
		Quality:   classify(latency),
		LatencyMs: latency,
		ProbeURL:  url,
		Timestamp: time.Now(),
	}
}

func classify(ms int64) Quality {
	switch {
	case ms < 300:
		return QualityExcellent
	case ms < 800:
		return QualityGood
	case ms < 2000:
		return QualityPoor
	default:
		return QualityOffline
	}
}
