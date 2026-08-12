package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"math"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"sync"
	"syscall"
	"time"

	"github.com/jackc/pgx/v5"
	tb "github.com/tigerbeetle/tigerbeetle-go"
	tbtypes "github.com/tigerbeetle/tigerbeetle-go/pkg/types"
)

// SettlementBatchProcessor — Processes end-of-day settlement batches
// Aggregates agent transactions from PostgreSQL, posts net settlement transfers
// to the TigerBeetle cluster, and marks transactions settled. There is no
// fabricated batch data: batches are built only from real unsettled rows.

type SettlementBatch struct {
	BatchID       string            `json:"batch_id"`
	Status        string            `json:"status"` // pending, processing, completed, failed
	CreatedAt     time.Time         `json:"created_at"`
	CompletedAt   *time.Time        `json:"completed_at,omitempty"`
	AgentCount    int               `json:"agent_count"`
	TotalVolume   float64           `json:"total_volume"`
	TotalFees     float64           `json:"total_fees"`
	TotalComm     float64           `json:"total_commission"`
	NetSettlement float64           `json:"net_settlement"`
	Entries       []SettlementEntry `json:"entries"`
}

type SettlementEntry struct {
	AgentID       string  `json:"agent_id"`
	AgentCode     string  `json:"agent_code"`
	TxCount       int     `json:"tx_count"`
	CashInVolume  float64 `json:"cash_in_volume"`
	CashOutVolume float64 `json:"cash_out_volume"`
	TransferVol   float64 `json:"transfer_volume"`
	FeesCollected float64 `json:"fees_collected"`
	Commission    float64 `json:"commission"`
	NetPosition   float64 `json:"net_position"`
	SettlementAmt float64 `json:"settlement_amount"`
}

var (
	batches   = make(map[string]*SettlementBatch)
	batchesMu sync.RWMutex
	batchSeq  int

	db      *pgx.Conn
	tbClient tb.Client
)

func generateBatchID() string {
	batchSeq++
	return fmt.Sprintf("BATCH-%s-%04d", time.Now().Format("20060102"), batchSeq)
}

func round2(v float64) float64 { return math.Round(v*100) / 100 }

// accountRef maps a logical ledger account identifier to a deterministic
// TigerBeetle Uint128 account ID (same convention as tb-sidecar).
func accountRef(s string) tbtypes.Uint128 {
	var result tbtypes.Uint128
	b := []byte(s)
	if len(b) > 16 {
		b = b[:16]
	}
	copy(result[:], b)
	return result
}

func writeJSONError(w http.ResponseWriter, code int, payload map[string]interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	json.NewEncoder(w).Encode(payload)
}

func handleCreateBatch(w http.ResponseWriter, r *http.Request) {
	if r.Method != "POST" {
		http.Error(w, `{"error":"method not allowed"}`, 405)
		return
	}
	ctx := r.Context()

	// Query real unsettled transactions from PostgreSQL — no fabricated agents.
	rows, err := db.Query(ctx, `
		SELECT agent_id, COUNT(*)::int, COALESCE(SUM(amount),0)::float8,
		       COALESCE(SUM(fee),0)::float8, COALESCE(SUM(commission),0)::float8
		FROM transactions
		WHERE settled = FALSE AND status = 'success'
		GROUP BY agent_id
		ORDER BY agent_id`)
	if err != nil {
		log.Printf("[batch] failed to query unsettled transactions: %v", err)
		writeJSONError(w, http.StatusServiceUnavailable, map[string]interface{}{
			"error": "postgres_unavailable", "detail": err.Error(),
		})
		return
	}

	type agentAgg struct {
		agentID    string
		txCount    int
		volume     float64
		fees       float64
		commission float64
	}
	var aggs []agentAgg
	for rows.Next() {
		var a agentAgg
		if err := rows.Scan(&a.agentID, &a.txCount, &a.volume, &a.fees, &a.commission); err != nil {
			rows.Close()
			writeJSONError(w, http.StatusInternalServerError, map[string]interface{}{
				"error": "postgres_scan_failed", "detail": err.Error(),
			})
			return
		}
		aggs = append(aggs, a)
	}
	rows.Close()

	if len(aggs) == 0 {
		writeJSONError(w, http.StatusNotFound, map[string]interface{}{
			"error":  "no_eligible_transactions",
			"detail": "zero unsettled transactions eligible for batch settlement",
		})
		return
	}

	batch := &SettlementBatch{
		BatchID:   generateBatchID(),
		Status:    "processing",
		CreatedAt: time.Now(),
	}

	var failedAgents []string
	for _, a := range aggs {
		settleAmt := a.volume - a.commission
		entry := SettlementEntry{
			AgentID:       a.agentID,
			AgentCode:     a.agentID,
			TxCount:       a.txCount,
			FeesCollected: round2(a.fees),
			Commission:    round2(a.commission),
			NetPosition:   round2(a.volume),
			SettlementAmt: round2(settleAmt),
		}

		// Post the real net-settlement transfer to the TigerBeetle cluster:
		// platform settlement pool → agent settlement account.
		amountKobo := uint64(math.Round(settleAmt * 100))
		if amountKobo > 0 {
			results, tbErr := tbClient.CreateTransfers([]tbtypes.Transfer{{
				ID:              tbtypes.ID(),
				DebitAccountID:  accountRef("platform-settlement-pool"),
				CreditAccountID: accountRef("agent:" + a.agentID),
				Amount:          tbtypes.ToUint128(amountKobo),
				Ledger:          1,
				Code:            1,
			}})
			if tbErr != nil {
				log.Printf("[batch] TigerBeetle unreachable for agent %s: %v", a.agentID, tbErr)
				failedAgents = append(failedAgents, a.agentID)
				continue
			}
			if len(results) > 0 {
				log.Printf("[batch] TigerBeetle rejected settlement for agent %s: %v", a.agentID, results[0].Result)
				failedAgents = append(failedAgents, a.agentID)
				continue
			}
		}

		batch.Entries = append(batch.Entries, entry)
		batch.TotalVolume += a.volume
		batch.TotalFees += a.fees
		batch.TotalComm += a.commission
	}

	if len(batch.Entries) == 0 {
		batch.Status = "failed"
		writeJSONError(w, http.StatusBadGateway, map[string]interface{}{
			"error":         "ledger_posting_failed",
			"detail":        "TigerBeetle settlement posting failed for every eligible agent",
			"failed_agents": failedAgents,
			"batch_id":      batch.BatchID,
		})
		return
	}

	// Mark the settled transactions in Postgres for the agents whose ledger
	// transfers were actually accepted.
	settledAgents := make([]string, 0, len(batch.Entries))
	for _, e := range batch.Entries {
		settledAgents = append(settledAgents, e.AgentID)
	}
	if _, err := db.Exec(ctx, `
		UPDATE transactions
		SET settled = TRUE, settlement_batch_id = $1
		WHERE settled = FALSE AND status = 'success' AND agent_id = ANY($2)`,
		batch.BatchID, settledAgents); err != nil {
		log.Printf("[batch] failed to mark transactions settled: %v", err)
		writeJSONError(w, http.StatusBadGateway, map[string]interface{}{
			"error":    "settlement_mark_failed",
			"detail":   fmt.Sprintf("ledger transfers posted for %d agents but Postgres update failed: %v", len(settledAgents), err),
			"batch_id": batch.BatchID,
		})
		return
	}

	batch.AgentCount = len(batch.Entries)
	batch.NetSettlement = round2(batch.TotalVolume - batch.TotalComm)
	batch.TotalVolume = round2(batch.TotalVolume)
	batch.TotalFees = round2(batch.TotalFees)
	batch.TotalComm = round2(batch.TotalComm)
	now := time.Now()
	batch.CompletedAt = &now
	batch.Status = "completed"

	entriesJSON, _ := json.Marshal(batch.Entries)
	if _, err := db.Exec(ctx, `
		INSERT INTO settlement_batches
		(batch_id, status, agent_count, total_volume, total_fees, total_commission,
		 net_settlement, entries, created_at, completed_at)
		VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)`,
		batch.BatchID, batch.Status, batch.AgentCount, batch.TotalVolume,
		batch.TotalFees, batch.TotalComm, batch.NetSettlement, string(entriesJSON),
		batch.CreatedAt, batch.CompletedAt); err != nil {
		log.Printf("[batch] failed to persist batch %s: %v", batch.BatchID, err)
		writeJSONError(w, http.StatusBadGateway, map[string]interface{}{
			"error":    "batch_persist_failed",
			"detail":   fmt.Sprintf("settlement posted and marked but batch record persist failed: %v", err),
			"batch_id": batch.BatchID,
		})
		return
	}

	batchesMu.Lock()
	batches[batch.BatchID] = batch
	batchesMu.Unlock()

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"batch":         batch,
		"failed_agents": failedAgents,
	})
}

func handleListBatches(w http.ResponseWriter, r *http.Request) {
	batchesMu.RLock()
	defer batchesMu.RUnlock()
	var list []*SettlementBatch
	for _, b := range batches {
		list = append(list, b)
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{"batches": list, "count": len(list)})
}

func handleHealth(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{"status": "healthy", "service": "settlement-batch-processor", "batches_processed": len(batches)})
}

func main() {
	port := os.Getenv("PORT")
	if port == "" {
		port = "9211"
	}

	ctx := context.Background()

	// Postgres is the source of unsettled transactions — refuse to start without it.
	dsn := os.Getenv("POSTGRES_URL")
	if dsn == "" {
		dsn = os.Getenv("DATABASE_URL")
	}
	if dsn == "" {
		log.Fatal("POSTGRES_URL (or DATABASE_URL) is required; refusing to start without the transactions source")
	}
	var err error
	db, err = pgx.Connect(ctx, dsn)
	if err != nil {
		log.Fatalf("Cannot connect to PostgreSQL (%v); refusing to start", err)
	}
	defer db.Close(ctx)

	if _, err := db.Exec(ctx, `
		CREATE TABLE IF NOT EXISTS settlement_batches (
			batch_id        TEXT PRIMARY KEY,
			status          TEXT NOT NULL,
			agent_count     INT NOT NULL,
			total_volume    DOUBLE PRECISION NOT NULL,
			total_fees      DOUBLE PRECISION NOT NULL,
			total_commission DOUBLE PRECISION NOT NULL,
			net_settlement  DOUBLE PRECISION NOT NULL,
			entries         JSONB NOT NULL DEFAULT '[]',
			created_at      TIMESTAMPTZ NOT NULL,
			completed_at    TIMESTAMPTZ
		)`); err != nil {
		log.Fatalf("Cannot ensure settlement_batches schema: %v", err)
	}

	// TigerBeetle is where settlement transfers are posted — refuse to start without it.
	tbAddr := os.Getenv("TB_ADDRESSES")
	if tbAddr == "" {
		tbAddr = os.Getenv("TIGERBEETLE_ADDR")
	}
	if tbAddr == "" {
		tbAddr = "tigerbeetle:3000"
	}
	tbClient, err = tb.NewClient(tbtypes.ToUint128(0), strings.Split(tbAddr, ","))
	if err != nil {
		log.Fatalf("Cannot connect to TigerBeetle cluster at %s (%v); refusing to start", tbAddr, err)
	}
	defer tbClient.Close()

	http.HandleFunc("/api/v1/batch/create", handleCreateBatch)
	http.HandleFunc("/api/v1/batch/list", handleListBatches)
	http.HandleFunc("/health", handleHealth)
	log.Printf("[settlement-batch-processor] Starting on :%s", port)
	log.Fatal(http.ListenAndServe(":"+port, nil))
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
