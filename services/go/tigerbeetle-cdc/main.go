// Package main implements the TigerBeetle CDC (Change Data Capture) service.
//
// Polls PostgreSQL tables (tb_accounts, tb_transfers, tb_transfer_metadata)
// for new or changed rows and publishes change events to Kafka via Dapr.
// Ensures that any writes that bypass the Go/Rust/Python middleware are
// still synced to the event pipeline (Kafka → OpenSearch → Lakehouse).
//
// Persistence: PostgreSQL (zero in-memory state)
// Polling interval: configurable via CDC_POLL_INTERVAL (default: 5s)
package main

import (
	"bytes"
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"sync/atomic"
	"syscall"
	"time"

	_ "github.com/lib/pq"
	"github.com/gorilla/mux"
)

type CDCConfig struct {
	Port          string
	DatabaseURL   string
	DaprHTTPPort  string
	PollInterval  time.Duration
	BatchSize     int
	OpenSearchURL string
}

type CDCEvent struct {
	Table     string                 `json:"table"`
	Operation string                 `json:"operation"`
	Key       string                 `json:"key"`
	Data      map[string]interface{} `json:"data"`
	Timestamp string                 `json:"timestamp"`
}

var (
	pgDB           *sql.DB
	eventsEmitted  int64
	pollCycles     int64
	errorsTotal    int64
	lastPollTime   time.Time
)

func loadConfig() CDCConfig {
	interval := 5 * time.Second
	if v := os.Getenv("CDC_POLL_INTERVAL"); v != "" {
		if d, err := time.ParseDuration(v); err == nil {
			interval = d
		}
	}
	return CDCConfig{
		Port:          getEnv("PORT", "8090"),
		DatabaseURL:   getEnv("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/tigerbeetle_core?sslmode=disable"),
		DaprHTTPPort:  getEnv("DAPR_HTTP_PORT", "3500"),
		PollInterval:  interval,
		BatchSize:     500,
		OpenSearchURL: getEnv("OPENSEARCH_URL", "http://localhost:9200"),
	}
}

func getEnv(k, fallback string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return fallback
}

func initDB(cfg CDCConfig) {
	var err error
	pgDB, err = sql.Open("postgres", cfg.DatabaseURL)
	if err != nil {
		log.Printf("[cdc] DB warning: %v", err)
		return
	}
	pgDB.SetMaxOpenConns(10)
	pgDB.SetMaxIdleConns(5)
	pgDB.SetConnMaxLifetime(5 * time.Minute)

	// CDC watermark table — tracks the last-seen timestamp per source table
	pgDB.Exec(`CREATE TABLE IF NOT EXISTS cdc_watermarks (
		table_name TEXT PRIMARY KEY,
		last_processed_at TIMESTAMPTZ NOT NULL DEFAULT '1970-01-01',
		events_emitted BIGINT NOT NULL DEFAULT 0,
		updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
	)`)
	// Initialize watermarks for known tables
	for _, t := range []string{"tb_accounts", "tb_transfers", "tb_transfer_metadata", "edge_transfers", "billing_ledger_entries"} {
		pgDB.Exec(`INSERT INTO cdc_watermarks (table_name) VALUES ($1) ON CONFLICT DO NOTHING`, t)
	}

	pgDB.Exec(`CREATE TABLE IF NOT EXISTS cdc_event_log (
		id SERIAL PRIMARY KEY,
		source_table TEXT NOT NULL,
		source_key TEXT NOT NULL,
		operation TEXT NOT NULL,
		published BOOLEAN NOT NULL DEFAULT false,
		created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
	)`)
	pgDB.Exec(`CREATE INDEX IF NOT EXISTS idx_cdc_log_created ON cdc_event_log(created_at)`)
	pgDB.Exec(`CREATE INDEX IF NOT EXISTS idx_cdc_log_published ON cdc_event_log(published)`)

	log.Println("[cdc] PostgreSQL CDC tables initialized")
}

// ── CDC Polling ──────────────────────────────────────────────────────────────

func pollTable(ctx context.Context, cfg CDCConfig, tableName, keyCol, tsCol string) {
	if pgDB == nil {
		return
	}

	var watermark time.Time
	pgDB.QueryRow(`SELECT last_processed_at FROM cdc_watermarks WHERE table_name=$1`, tableName).Scan(&watermark)

	query := fmt.Sprintf(`SELECT * FROM %s WHERE %s > $1 ORDER BY %s LIMIT $2`, tableName, tsCol, tsCol)
	rows, err := pgDB.QueryContext(ctx, query, watermark, cfg.BatchSize)
	if err != nil {
		log.Printf("[cdc] poll %s error: %v", tableName, err)
		return
	}
	defer rows.Close()

	cols, _ := rows.Columns()
	var maxTS time.Time
	var count int

	for rows.Next() {
		vals := make([]interface{}, len(cols))
		ptrs := make([]interface{}, len(cols))
		for i := range vals {
			ptrs[i] = &vals[i]
		}
		rows.Scan(ptrs...)

		data := make(map[string]interface{})
		var key string
		for i, col := range cols {
			data[col] = vals[i]
			if col == keyCol {
				key = fmt.Sprintf("%v", vals[i])
			}
			if col == tsCol {
				if t, ok := vals[i].(time.Time); ok && t.After(maxTS) {
					maxTS = t
				}
			}
		}

		event := CDCEvent{
			Table:     tableName,
			Operation: "upsert",
			Key:       key,
			Data:      data,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
		}

		publishCDCEvent(cfg, event)
		logCDCEvent(tableName, key, "upsert")
		count++
	}

	if count > 0 && !maxTS.IsZero() {
		pgDB.Exec(`UPDATE cdc_watermarks SET last_processed_at=$2, events_emitted=events_emitted+$3, updated_at=NOW() WHERE table_name=$1`,
			tableName, maxTS, count)
		atomic.AddInt64(&eventsEmitted, int64(count))
		log.Printf("[cdc] Emitted %d events from %s", count, tableName)
	}
}

func publishCDCEvent(cfg CDCConfig, event CDCEvent) {
	data, _ := json.Marshal(event)

	// Kafka via Dapr
	go func() {
		url := fmt.Sprintf("http://localhost:%s/v1.0/publish/kafka-pubsub/tb.cdc.events", cfg.DaprHTTPPort)
		http.Post(url, "application/json", bytes.NewReader(data))
	}()

	// Dapr direct pub/sub
	go func() {
		url := fmt.Sprintf("http://localhost:%s/v1.0/publish/pubsub/tb.cdc.%s", cfg.DaprHTTPPort, event.Table)
		http.Post(url, "application/json", bytes.NewReader(data))
	}()

	// OpenSearch indexing
	go func() {
		idx := fmt.Sprintf("cdc-%s-%s", event.Table, time.Now().Format("2006.01"))
		url := fmt.Sprintf("%s/%s/_doc/%s_%s", cfg.OpenSearchURL, idx, event.Table, event.Key)
		req, _ := http.NewRequest("PUT", url, bytes.NewReader(data))
		req.Header.Set("Content-Type", "application/json")
		http.DefaultClient.Do(req)
	}()
}

func logCDCEvent(table, key, op string) {
	if pgDB != nil {
		pgDB.Exec(`INSERT INTO cdc_event_log (source_table, source_key, operation, published) VALUES ($1, $2, $3, true)`,
			table, key, op)
	}
}

func runPollCycle(ctx context.Context, cfg CDCConfig) {
	atomic.AddInt64(&pollCycles, 1)
	lastPollTime = time.Now()

	pollTable(ctx, cfg, "tb_accounts", "id", "updated_at")
	pollTable(ctx, cfg, "tb_transfers", "id", "created_at")
	pollTable(ctx, cfg, "tb_transfer_metadata", "id", "created_at")
	pollTable(ctx, cfg, "edge_transfers", "id", "created_at")
	pollTable(ctx, cfg, "billing_ledger_entries", "id", "processed_at")
}

// ── HTTP Handlers ────────────────────────────────────────────────────────────

func healthHandler(w http.ResponseWriter, r *http.Request) {
	dbOK := false
	if pgDB != nil {
		dbOK = pgDB.Ping() == nil
	}
	json.NewEncoder(w).Encode(map[string]interface{}{
		"status":         "healthy",
		"service":        "tigerbeetle-cdc",
		"version":        "1.0.0",
		"persistence":    "postgresql",
		"postgres":       dbOK,
		"events_emitted": atomic.LoadInt64(&eventsEmitted),
		"poll_cycles":    atomic.LoadInt64(&pollCycles),
		"errors":         atomic.LoadInt64(&errorsTotal),
	})
}

func watermarksHandler(w http.ResponseWriter, r *http.Request) {
	if pgDB == nil {
		w.WriteHeader(http.StatusServiceUnavailable)
		return
	}
	rows, err := pgDB.Query(`SELECT table_name, last_processed_at, events_emitted FROM cdc_watermarks ORDER BY table_name`)
	if err != nil {
		w.WriteHeader(http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	var watermarks []map[string]interface{}
	for rows.Next() {
		var table string
		var ts time.Time
		var count int64
		rows.Scan(&table, &ts, &count)
		watermarks = append(watermarks, map[string]interface{}{
			"table":             table,
			"last_processed_at": ts.Format(time.RFC3339),
			"events_emitted":    count,
		})
	}
	json.NewEncoder(w).Encode(watermarks)
}

func triggerHandler(w http.ResponseWriter, r *http.Request) {
	cfg := loadConfig()
	runPollCycle(r.Context(), cfg)
	json.NewEncoder(w).Encode(map[string]string{"status": "poll_triggered"})
}

func main() {
	cfg := loadConfig()
	initDB(cfg)

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Background CDC poller
	go func() {
		ticker := time.NewTicker(cfg.PollInterval)
		defer ticker.Stop()
		for {
			select {
			case <-ctx.Done():
				return
			case <-ticker.C:
				runPollCycle(ctx, cfg)
			}
		}
	}()

	router := mux.NewRouter()
	router.HandleFunc("/health", healthHandler).Methods("GET")
	router.HandleFunc("/watermarks", watermarksHandler).Methods("GET")
	router.HandleFunc("/trigger", triggerHandler).Methods("POST")

	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		<-sigCh
		log.Println("[cdc] Shutting down...")
		cancel()
	}()

	log.Printf("Starting TigerBeetle CDC v1.0.0 on :%s (poll=%s, batch=%d)", cfg.Port, cfg.PollInterval, cfg.BatchSize)
	log.Fatal(http.ListenAndServe(":"+cfg.Port, router))
}
