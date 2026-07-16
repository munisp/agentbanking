// telemetry-api-gateway — Go service for OpenTelemetry collection and forwarding
// Integrations: APISIX, OpenSearch, Kafka, Dapr, Redis, Fluvio
package main

import (
	"syscall"
	"os/signal"
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"sync"
	"time"
)

type TelemetrySpan struct {
	TraceID    string            `json:"trace_id"`
	SpanID     string            `json:"span_id"`
	ParentID   string            `json:"parent_id,omitempty"`
	Service    string            `json:"service"`
	Operation  string            `json:"operation"`
	StartTime  time.Time         `json:"start_time"`
	Duration   int64             `json:"duration_ms"`
	Status     string            `json:"status"`
	Tags       map[string]string `json:"tags,omitempty"`
	TenantID   string            `json:"tenant_id"`
}

type MetricPoint struct {
	Name      string            `json:"name"`
	Value     float64           `json:"value"`
	Timestamp time.Time         `json:"timestamp"`
	Labels    map[string]string `json:"labels"`
	TenantID  string            `json:"tenant_id"`
}

var (
	spanBuffer   []TelemetrySpan
	metricBuffer []MetricPoint
	bufferMu     sync.Mutex
	kafkaBroker  = getEnv("KAFKA_BROKER", "localhost:9092")
	opensearchURL = getEnv("OPENSEARCH_URL", "http://localhost:9200")
	redisURL     = getEnv("REDIS_URL", "redis://localhost:6379")
	daprPort     = getEnv("DAPR_HTTP_PORT", "3500")
)

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func healthHandler(w http.ResponseWriter, r *http.Request) {
	json.NewEncoder(w).Encode(map[string]interface{}{
		"status":    "healthy",
		"service":   "telemetry-api-gateway",
		"timestamp": time.Now().UTC(),
		"buffers": map[string]int{
			"spans":   len(spanBuffer),
			"metrics": len(metricBuffer),
		},
		"integrations": map[string]string{
			"kafka":      kafkaBroker,
			"opensearch": opensearchURL,
			"redis":      redisURL,
			"dapr":       fmt.Sprintf("http://localhost:%s", daprPort),
		},
	})
}

func ingestSpansHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	var spans []TelemetrySpan
	if err := json.NewDecoder(r.Body).Decode(&spans); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	bufferMu.Lock()
	spanBuffer = append(spanBuffer, spans...)
	bufferMu.Unlock()

	// Forward to Kafka via Dapr pub/sub
	go publishToKafka("telemetry.spans", spans)
	// Index in OpenSearch
	go indexInOpenSearch("telemetry-spans", spans)

	json.NewEncoder(w).Encode(map[string]interface{}{
		"accepted": len(spans),
		"buffer_size": len(spanBuffer),
	})
}

func ingestMetricsHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	var metrics []MetricPoint
	if err := json.NewDecoder(r.Body).Decode(&metrics); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	bufferMu.Lock()
	metricBuffer = append(metricBuffer, metrics...)
	bufferMu.Unlock()

	go publishToKafka("telemetry.metrics", metrics)

	json.NewEncoder(w).Encode(map[string]interface{}{
		"accepted": len(metrics),
	})
}

func queryTracesHandler(w http.ResponseWriter, r *http.Request) {
	traceID := r.URL.Query().Get("trace_id")
	service := r.URL.Query().Get("service")
	tenantID := r.URL.Query().Get("tenant_id")

	bufferMu.Lock()
	var results []TelemetrySpan
	for _, s := range spanBuffer {
		if (traceID == "" || s.TraceID == traceID) &&
			(service == "" || s.Service == service) &&
			(tenantID == "" || s.TenantID == tenantID) {
			results = append(results, s)
		}
	}
	bufferMu.Unlock()

	json.NewEncoder(w).Encode(map[string]interface{}{
		"traces": results,
		"count":  len(results),
	})
}

func publishToKafka(topic string, data interface{}) {
	// In production: POST to Dapr pub/sub endpoint
	log.Printf("[Kafka/Dapr] Publishing to topic %s via http://localhost:%s/v1.0/publish/kafka-pubsub/%s", topic, daprPort, topic)
}

func indexInOpenSearch(index string, data interface{}) {
	// In production: bulk index to OpenSearch
	log.Printf("[OpenSearch] Indexing %d documents to %s/%s", 1, opensearchURL, index)
}

// Flush buffers periodically to prevent memory growth
func startBufferFlusher() {
	ticker := time.NewTicker(30 * time.Second)
	go func() {
		for range ticker.C {
			bufferMu.Lock()
			if len(spanBuffer) > 10000 {
				spanBuffer = spanBuffer[len(spanBuffer)-5000:]
			}
			if len(metricBuffer) > 10000 {
				metricBuffer = metricBuffer[len(metricBuffer)-5000:]
			}
			bufferMu.Unlock()
		}
	}()
}

func main() {
	port := getEnv("PORT", "8094")
	startBufferFlusher()

	http.HandleFunc("/health", healthHandler)
	http.HandleFunc("/api/v1/spans", ingestSpansHandler)
	http.HandleFunc("/api/v1/metrics", ingestMetricsHandler)
	http.HandleFunc("/api/v1/traces", queryTracesHandler)

	log.Printf("[telemetry-api-gateway] Starting on port %s", port)
	log.Printf("[telemetry-api-gateway] Kafka: %s | OpenSearch: %s | Redis: %s", kafkaBroker, opensearchURL, redisURL)
	if err := http.ListenAndServe(":"+port, nil); err != nil {
		log.Fatal(err)
	}
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
