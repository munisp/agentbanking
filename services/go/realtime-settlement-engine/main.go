package main

import (
	"context"
	"crypto/rand"
	"database/sql"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"

	_ "github.com/lib/pq"
)

type SettlementBatch struct {
	ID            string    `json:"id"`
	AgentID       int64     `json:"agent_id"`
	TotalAmount   float64   `json:"total_amount"`
	TxCount       int       `json:"tx_count"`
	Status        string    `json:"status"`
	SettledAt     *time.Time `json:"settled_at,omitempty"`
	CreatedAt     time.Time `json:"created_at"`
	CutoffTime    time.Time `json:"cutoff_time"`
	SettlementRef string    `json:"settlement_ref"`
}

type SettlementEngine struct {
	db            *sql.DB
	mu            sync.RWMutex
	pendingBatches map[string]*SettlementBatch
	cutoffHours   []int // Hours at which settlement runs (e.g., 6, 12, 18, 23)
}

func NewSettlementEngine(db *sql.DB) *SettlementEngine {
	return &SettlementEngine{
		db:             db,
		pendingBatches: make(map[string]*SettlementBatch),
		cutoffHours:    []int{6, 12, 18, 23},
	}
}

func generateRef() string {
	b := make([]byte, 8)
	rand.Read(b)
	return fmt.Sprintf("STL-%d-%s", time.Now().Unix(), hex.EncodeToString(b))
}

func (e *SettlementEngine) CreateBatch(agentID int64, totalAmount float64, txCount int) (*SettlementBatch, error) {
	batch := &SettlementBatch{
		ID:            generateRef(),
		AgentID:       agentID,
		TotalAmount:   totalAmount,
		TxCount:       txCount,
		Status:        "pending",
		CreatedAt:     time.Now(),
		CutoffTime:    e.nextCutoff(),
		SettlementRef: generateRef(),
	}

	query := `INSERT INTO settlement_batches (id, agent_id, total_amount, tx_count, status, cutoff_time, settlement_ref, created_at)
	           VALUES ($1, $2, $3, $4, $5, $6, $7, $8)`
	_, err := e.db.Exec(query, batch.ID, batch.AgentID, batch.TotalAmount, batch.TxCount, batch.Status, batch.CutoffTime, batch.SettlementRef, batch.CreatedAt)
	if err != nil {
		return nil, fmt.Errorf("failed to create batch: %w", err)
	}

	e.mu.Lock()
	e.pendingBatches[batch.ID] = batch
	e.mu.Unlock()

	return batch, nil
}

func (e *SettlementEngine) ProcessBatch(batchID string) error {
	e.mu.Lock()
	batch, ok := e.pendingBatches[batchID]
	if !ok {
		e.mu.Unlock()
		return fmt.Errorf("batch %s not found", batchID)
	}
	batch.Status = "processing"
	e.mu.Unlock()

	tx, err := e.db.Begin()
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer tx.Rollback()

	// Debit agent float account
	_, err = tx.Exec(`UPDATE agents SET float_balance = float_balance - $1 WHERE id = $2`, batch.TotalAmount, batch.AgentID)
	if err != nil {
		batch.Status = "failed"
		return fmt.Errorf("failed to debit agent: %w", err)
	}

	// Credit settlement account
	now := time.Now()
	batch.SettledAt = &now
	batch.Status = "settled"

	_, err = tx.Exec(`UPDATE settlement_batches SET status = $1, settled_at = $2 WHERE id = $3`, batch.Status, now, batch.ID)
	if err != nil {
		return fmt.Errorf("failed to update batch: %w", err)
	}

	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit: %w", err)
	}

	e.mu.Lock()
	delete(e.pendingBatches, batchID)
	e.mu.Unlock()

	log.Printf("Settlement batch %s processed: NGN %.2f (%d txs) for agent %d", batchID, batch.TotalAmount, batch.TxCount, batch.AgentID)
	return nil
}

func (e *SettlementEngine) RunSettlementCycle(ctx context.Context) {
	ticker := time.NewTicker(5 * time.Minute)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			now := time.Now()
			for _, cutoff := range e.cutoffHours {
				if now.Hour() == cutoff && now.Minute() < 5 {
					e.processAllPending()
				}
			}
		}
	}
}

func (e *SettlementEngine) processAllPending() {
	e.mu.RLock()
	ids := make([]string, 0, len(e.pendingBatches))
	for id := range e.pendingBatches {
		ids = append(ids, id)
	}
	e.mu.RUnlock()

	for _, id := range ids {
		if err := e.ProcessBatch(id); err != nil {
			log.Printf("Error processing batch %s: %v", id, err)
		}
	}
}

func (e *SettlementEngine) nextCutoff() time.Time {
	now := time.Now()
	for _, h := range e.cutoffHours {
		t := time.Date(now.Year(), now.Month(), now.Day(), h, 0, 0, 0, now.Location())
		if t.After(now) {
			return t
		}
	}
	tomorrow := now.AddDate(0, 0, 1)
	return time.Date(tomorrow.Year(), tomorrow.Month(), tomorrow.Day(), e.cutoffHours[0], 0, 0, 0, now.Location())
}

func (e *SettlementEngine) GetStats() map[string]interface{} {
	e.mu.RLock()
	defer e.mu.RUnlock()

	var totalAmount float64
	var totalTx int
	for _, b := range e.pendingBatches {
		totalAmount += b.TotalAmount
		totalTx += b.TxCount
	}

	return map[string]interface{}{
		"pending_batches": len(e.pendingBatches),
		"pending_amount":  totalAmount,
		"pending_tx_count": totalTx,
		"next_cutoff":     e.nextCutoff().Format(time.RFC3339),
	}
}

func main() {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8400"
	}
	dbURL := os.Getenv("DATABASE_URL")
	if dbURL == "" {
		dbURL = "postgres://localhost:5432/agentbanking?sslmode=disable"
	}

	db, err := sql.Open("postgres", dbURL)
	if err != nil {
		log.Fatalf("Failed to connect to database: %v", err)
	}
	defer db.Close()
	db.SetMaxOpenConns(25)
	db.SetMaxIdleConns(5)
	db.SetConnMaxLifetime(5 * time.Minute)

	engine := NewSettlementEngine(db)

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	go engine.RunSettlementCycle(ctx)

	mux := http.NewServeMux()

	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		if err := db.Ping(); err != nil {
			http.Error(w, "unhealthy", http.StatusServiceUnavailable)
			return
		}
		json.NewEncoder(w).Encode(map[string]string{"status": "healthy", "service": "realtime-settlement-engine"})
	})

	mux.HandleFunc("/api/v1/settlement/batch", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}
		var req struct {
			AgentID     int64   `json:"agent_id"`
			TotalAmount float64 `json:"total_amount"`
			TxCount     int     `json:"tx_count"`
		}
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			http.Error(w, "invalid request", http.StatusBadRequest)
			return
		}
		batch, err := engine.CreateBatch(req.AgentID, req.TotalAmount, req.TxCount)
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(batch)
	})

	mux.HandleFunc("/api/v1/settlement/stats", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(engine.GetStats())
	})

	mux.HandleFunc("/api/v1/settlement/process", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}
		engine.processAllPending()
		json.NewEncoder(w).Encode(map[string]string{"status": "processing"})
	})

	server := &http.Server{Addr: ":" + port, Handler: mux}

	go func() {
		log.Printf("Realtime Settlement Engine listening on :%s", port)
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("Server error: %v", err)
		}
	}()

	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
	<-sigCh
	log.Println("Shutting down settlement engine...")
	cancel()
	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer shutdownCancel()
	server.Shutdown(shutdownCtx)
}
