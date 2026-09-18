package main

import (
	"context"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"log"
	"math"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
	tb "github.com/tigerbeetle/tigerbeetle-go"
	tbtypes "github.com/tigerbeetle/tigerbeetle-go/pkg/types"
)

// SettlementBatchProcessor — Processes end-of-day settlement batches
// Aggregates agent transactions, calculates net positions, generates settlement files

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

type ledgerRow struct {
	id              int64
	transactionID   string
	agentID         string
	transactionType string
	grossAmount     int64 // minor units (kobo)
	grossFee        int64
	agentCommission int64
}

var (
	batches   = make(map[string]*SettlementBatch)
	batchesMu sync.RWMutex

	dbPool   *pgxpool.Pool
	tbClient tb.Client
)

// settlementBatchID is DETERMINISTIC per settlement date + 6-hour window
// (e.g. "batch-20250101-w2"). A fresh random/sequential ID per run would
// defeat TigerBeetle dedup: the transfer ID "stl:<batch>:<agent>" must be
// stable across re-runs so a retried batch reuses the same TB transfer IDs
// and TigerBeetle rejects the duplicates instead of double-paying agents.
func settlementBatchID(t time.Time) string {
	window := t.Hour() / 6
	return fmt.Sprintf("batch-%s-w%d", t.Format("20060102"), window)
}

// stringToUint128 converts a string ID to a deterministic tbtypes.Uint128.
func stringToUint128(s string) tbtypes.Uint128 {
	var result tbtypes.Uint128
	b := []byte(s)
	if len(b) > 16 {
		b = b[:16]
	}
	copy(result[:], b)
	return result
}

// claimUnsettledRows atomically claims unsettled billing ledger rows for this
// batch inside a single DB transaction: SELECT ... FOR UPDATE SKIP LOCKED (so
// concurrent processors never see the same rows), then a claiming UPDATE that
// flips the rows to 'processing' with this batch ID. Rows already 'settled'
// (posted by an earlier run) are never re-claimed, so re-runs skip
// already-posted agents.
func claimUnsettledRows(ctx context.Context, batchID string) ([]ledgerRow, error) {
	tx, err := dbPool.Begin(ctx)
	if err != nil {
		return nil, fmt.Errorf("begin claim transaction: %w", err)
	}
	defer tx.Rollback(ctx)

	rows, err := tx.Query(ctx, `
		SELECT id, transaction_id, agent_id, transaction_type,
		       gross_amount, gross_fee, agent_commission
		FROM platform_billing_ledger
		WHERE settlement_status = 'pending'
		ORDER BY id
		LIMIT 10000
		FOR UPDATE SKIP LOCKED`)
	if err != nil {
		return nil, fmt.Errorf("query unsettled ledger rows: %w", err)
	}

	var out []ledgerRow
	for rows.Next() {
		var r ledgerRow
		if err := rows.Scan(&r.id, &r.transactionID, &r.agentID, &r.transactionType,
			&r.grossAmount, &r.grossFee, &r.agentCommission); err != nil {
			rows.Close()
			return nil, fmt.Errorf("scan ledger row: %w", err)
		}
		out = append(out, r)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return nil, err
	}
	if len(out) == 0 {
		return out, tx.Commit(ctx)
	}

	rowIDs := make([]int64, 0, len(out))
	for _, r := range out {
		rowIDs = append(rowIDs, r.id)
	}
	// Claiming UPDATE: guarded on settlement_status='pending' so a row claimed
	// by a racing processor between SELECT and UPDATE is not stolen.
	cmd, err := tx.Exec(ctx, `
		UPDATE platform_billing_ledger
		SET settlement_status = 'processing', settlement_batch_id = $1
		WHERE id = ANY($2) AND settlement_status = 'pending'`,
		batchID, rowIDs)
	if err != nil {
		return nil, fmt.Errorf("claim ledger rows: %w", err)
	}
	if cmd.RowsAffected() != int64(len(out)) {
		return nil, fmt.Errorf("claim race: claimed %d of %d selected rows — aborting batch", cmd.RowsAffected(), len(out))
	}
	return out, tx.Commit(ctx)
}

// markAgentRowsSettled flips one agent's claimed rows to 'settled' immediately
// after that agent's TigerBeetle transfer commits, so a mid-batch failure
// leaves per-row state consistent: posted agents are 'settled', unposted
// agents are reverted to 'pending' by revertUnpostedRows.
func markAgentRowsSettled(ctx context.Context, batchID string, rowIDs []int64) error {
	_, err := dbPool.Exec(ctx, `
		UPDATE platform_billing_ledger
		SET settlement_status = 'settled', settled_at = NOW()
		WHERE id = ANY($1) AND settlement_batch_id = $2 AND settlement_status = 'processing'`,
		rowIDs, batchID)
	if err != nil {
		return fmt.Errorf("mark agent rows settled: %w", err)
	}
	return nil
}

// revertUnpostedRows returns this batch's still-'processing' rows to 'pending'
// so a later re-run retries exactly the agents that were never posted.
func revertUnpostedRows(ctx context.Context, batchID string) {
	if _, err := dbPool.Exec(ctx, `
		UPDATE platform_billing_ledger
		SET settlement_status = 'pending', settlement_batch_id = NULL
		WHERE settlement_batch_id = $1 AND settlement_status = 'processing'`,
		batchID); err != nil {
		log.Printf("[settlement-batch-processor] failed to revert unposted rows for batch %s: %v", batchID, err)
	}
}

// ensureTBAccount creates a settlement account in TigerBeetle, tolerating EXISTS.
func ensureTBAccount(id tbtypes.Uint128, code uint16) error {
	results, err := tbClient.CreateAccounts([]tbtypes.Account{
		{ID: id, Ledger: 1, Code: code, Flags: 0},
	})
	if err != nil {
		return fmt.Errorf("tigerbeetle CreateAccounts: %w", err)
	}
	for _, res := range results {
		if !strings.Contains(fmt.Sprintf("%v", res.Result), "EXISTS") {
			return fmt.Errorf("tigerbeetle account creation rejected: result=%v index=%d", res.Result, res.Index)
		}
	}
	return nil
}

// postSettlementTransfer posts the real per-agent net settlement transfer.
func postSettlementTransfer(batchID, agentID string, amountKobo int64) error {
	if amountKobo <= 0 {
		return fmt.Errorf("non-positive settlement amount %d for agent %s", amountKobo, agentID)
	}
	transferID := stringToUint128(fmt.Sprintf("stl:%s:%s", batchID, agentID))
	platformAcct := stringToUint128("settle:platform")
	agentAcct := stringToUint128("settle:" + agentID)

	if err := ensureTBAccount(platformAcct, 3001); err != nil {
		return err
	}
	if err := ensureTBAccount(agentAcct, 3002); err != nil {
		return err
	}

	results, err := tbClient.CreateTransfers([]tbtypes.Transfer{
		{
			ID:              transferID,
			DebitAccountID:  platformAcct,
			CreditAccountID: agentAcct,
			Amount:          tbtypes.ToUint128(uint64(amountKobo)),
			Ledger:          1,
			Code:            2,
			Flags:           0,
		},
	})
	if err != nil {
		return fmt.Errorf("tigerbeetle CreateTransfers: %w", err)
	}
	if len(results) > 0 {
		// The transfer ID is deterministic (stl:<batch>:<agent>), so EXISTS on
		// a re-run means this agent was ALREADY posted by an earlier attempt —
		// treat as success (dedup), never as a second payment.
		if strings.Contains(fmt.Sprintf("%v", results[0].Result), "EXISTS") {
			log.Printf("[TigerBeetle] settlement transfer %s already exists (dedup) — agent %s already posted",
				hex.EncodeToString(transferID[:]), agentID)
			return nil
		}
		return fmt.Errorf("tigerbeetle settlement transfer rejected: result=%v index=%d", results[0].Result, results[0].Index)
	}
	log.Printf("[TigerBeetle] settlement transfer %s committed (%d kobo -> agent %s)",
		hex.EncodeToString(transferID[:]), amountKobo, agentID)
	return nil
}

// persistBatch upserts the durable batch record in Postgres (settlement_batches,
// migration 0055) so batch state survives process restarts — the in-memory map
// alone lost all batch history on restart and made re-runs invisible.
func persistBatch(ctx context.Context, batch *SettlementBatch, errMsg *string) {
	entriesJSON, merr := json.Marshal(batch.Entries)
	if merr != nil {
		log.Printf("[settlement-batch-processor] marshal batch entries: %v", merr)
		return
	}
	_, err := dbPool.Exec(ctx, `
		INSERT INTO settlement_batches
			(batch_id, status, agent_count, total_volume, total_fees, total_commission,
			 net_settlement, entries, error, created_at, completed_at)
		VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
		ON CONFLICT (batch_id) DO UPDATE SET
			status = EXCLUDED.status,
			agent_count = EXCLUDED.agent_count,
			total_volume = EXCLUDED.total_volume,
			total_fees = EXCLUDED.total_fees,
			total_commission = EXCLUDED.total_commission,
			net_settlement = EXCLUDED.net_settlement,
			entries = EXCLUDED.entries,
			error = EXCLUDED.error,
			completed_at = EXCLUDED.completed_at`,
		batch.BatchID, batch.Status, batch.AgentCount, batch.TotalVolume,
		batch.TotalFees, batch.TotalComm, batch.NetSettlement,
		string(entriesJSON), errMsg, batch.CreatedAt, batch.CompletedAt)
	if err != nil {
		log.Printf("[settlement-batch-processor] persist batch %s failed: %v", batch.BatchID, err)
	}
}

func handleCreateBatch(w http.ResponseWriter, r *http.Request) {
	if r.Method != "POST" {
		http.Error(w, `{"error":"method not allowed"}`, 405)
		return
	}
	ctx := r.Context()

	// Deterministic batch ID for this settlement date + window: re-runs of the
	// same window reuse the same ID, so TB transfer IDs (stl:<batch>:<agent>)
	// dedupe cross-run instead of double-paying agents.
	batchID := settlementBatchID(time.Now())

	// Step 1: atomically claim real unsettled transactions for this batch
	// (FOR UPDATE SKIP LOCKED + claiming UPDATE). Fail loudly when there are none.
	rows, err := claimUnsettledRows(ctx, batchID)
	if err != nil {
		log.Printf("[settlement-batch-processor] failed to claim unsettled rows: %v", err)
		http.Error(w, fmt.Sprintf(`{"error":%q}`, "failed to claim unsettled transactions: "+err.Error()), 500)
		return
	}
	if len(rows) == 0 {
		http.Error(w, `{"error":"no eligible unsettled transactions"}`, 422)
		return
	}

	batchesMu.Lock()
	batch := &SettlementBatch{
		BatchID:   batchID,
		Status:    "processing",
		CreatedAt: time.Now(),
	}
	batches[batch.BatchID] = batch
	batchesMu.Unlock()

	// Step 2: aggregate real rows per agent.
	type agentAgg struct {
		txCount    int
		cashIn     float64
		cashOut    float64
		transfer   float64
		fees       float64
		commission float64
		rowIDs     []int64
	}
	agents := map[string]*agentAgg{}
	order := []string{}
	for _, row := range rows {
		agg, ok := agents[row.agentID]
		if !ok {
			agg = &agentAgg{}
			agents[row.agentID] = agg
			order = append(order, row.agentID)
		}
		amountNGN := float64(row.grossAmount) / 100.0
		switch row.transactionType {
		case "cash_in":
			agg.cashIn += amountNGN
		case "cash_out":
			agg.cashOut += amountNGN
		default:
			agg.transfer += amountNGN
		}
		agg.fees += float64(row.grossFee) / 100.0
		agg.commission += float64(row.agentCommission) / 100.0
		agg.txCount++
		agg.rowIDs = append(agg.rowIDs, row.id)
	}

	for _, agentID := range order {
		agg := agents[agentID]
		entry := SettlementEntry{
			AgentID:       agentID,
			AgentCode:     agentID,
			TxCount:       agg.txCount,
			CashInVolume:  math.Round(agg.cashIn*100) / 100,
			CashOutVolume: math.Round(agg.cashOut*100) / 100,
			TransferVol:   math.Round(agg.transfer*100) / 100,
			FeesCollected: math.Round(agg.fees*100) / 100,
			Commission:    math.Round(agg.commission*100) / 100,
			NetPosition:   math.Round((agg.cashIn-agg.cashOut)*100) / 100,
			SettlementAmt: math.Round((agg.cashIn-agg.cashOut-agg.commission)*100) / 100,
		}
		batch.Entries = append(batch.Entries, entry)
		batch.TotalVolume += agg.cashIn + agg.cashOut + agg.transfer
		batch.TotalFees += agg.fees
		batch.TotalComm += agg.commission
	}
	batch.AgentCount = len(batch.Entries)
	batch.NetSettlement = math.Round((batch.TotalVolume-batch.TotalFees)*100) / 100
	batch.TotalVolume = math.Round(batch.TotalVolume*100) / 100
	batch.TotalFees = math.Round(batch.TotalFees*100) / 100
	batch.TotalComm = math.Round(batch.TotalComm*100) / 100

	// Persist the batch record (processing) before posting so batch state is
	// durable even if the process dies mid-loop.
	persistBatch(ctx, batch, nil)

	// Step 3: post the real per-agent settlement transfers to TigerBeetle.
	// Per-entry status: each agent's rows flip to 'settled' right after that
	// agent's transfer commits. On failure, unposted agents' rows revert to
	// 'pending' so a re-run retries exactly them — posted agents are skipped
	// (their rows are 'settled' and their deterministic TB transfer IDs dedupe).
	for _, entry := range batch.Entries {
		amountKobo := int64(math.Round(entry.SettlementAmt * 100))
		agg := agents[entry.AgentID]
		if amountKobo <= 0 {
			// Nothing payable to this agent — settle the claimed rows without a transfer.
			if err := markAgentRowsSettled(ctx, batch.BatchID, agg.rowIDs); err != nil {
				log.Printf("[settlement-batch-processor] batch %s settle-mark failed for agent %s: %v", batch.BatchID, entry.AgentID, err)
			}
			continue
		}
		if err := postSettlementTransfer(batch.BatchID, entry.AgentID, amountKobo); err != nil {
			revertUnpostedRows(ctx, batch.BatchID)
			batchesMu.Lock()
			batch.Status = "failed"
			batchesMu.Unlock()
			errMsg := "ledger settlement posting failed for agent " + entry.AgentID + ": " + err.Error()
			persistBatch(ctx, batch, &errMsg)
			log.Printf("[settlement-batch-processor] batch %s failed at agent %s: %v", batch.BatchID, entry.AgentID, err)
			http.Error(w, fmt.Sprintf(`{"error":%q,"batch_id":%q}`, errMsg, batch.BatchID), 500)
			return
		}
		if err := markAgentRowsSettled(ctx, batch.BatchID, agg.rowIDs); err != nil {
			// TB transfer is committed but rows not marked. Reverting this
			// agent's rows to 'pending' is SAFE (unlike the post-failure path,
			// here re-posting is deduped): a re-run re-claims them, the
			// deterministic TB transfer ID returns EXISTS (no double pay), and
			// the rows are then marked settled.
			revertUnpostedRows(ctx, batch.BatchID)
			batchesMu.Lock()
			batch.Status = "failed"
			batchesMu.Unlock()
			errMsg := "failed to mark ledger rows settled after posting for agent " + entry.AgentID + ": " + err.Error()
			persistBatch(ctx, batch, &errMsg)
			log.Printf("[settlement-batch-processor] batch %s settle-mark failed after TB posting for agent %s: %v", batch.BatchID, entry.AgentID, err)
			http.Error(w, fmt.Sprintf(`{"error":%q,"batch_id":%q}`, errMsg, batch.BatchID), 500)
			return
		}
	}

	now := time.Now()
	batchesMu.Lock()
	batch.CompletedAt = &now
	batch.Status = "completed"
	batchesMu.Unlock()
	persistBatch(ctx, batch, nil)

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(batch)
}

func handleListBatches(w http.ResponseWriter, r *http.Request) {
	// Durable batch records are the source of truth (survive restarts);
	// fall back to the in-memory cache if the query fails.
	rows, err := dbPool.Query(r.Context(), `
		SELECT batch_id, status, agent_count, total_volume, total_fees,
		       total_commission, net_settlement, entries, created_at, completed_at
		FROM settlement_batches
		ORDER BY created_at DESC
		LIMIT 200`)
	if err == nil {
		defer rows.Close()
		list := []*SettlementBatch{}
		for rows.Next() {
			var b SettlementBatch
			var entriesJSON []byte
			if err := rows.Scan(&b.BatchID, &b.Status, &b.AgentCount, &b.TotalVolume,
				&b.TotalFees, &b.TotalComm, &b.NetSettlement, &entriesJSON,
				&b.CreatedAt, &b.CompletedAt); err != nil {
				break
			}
			_ = json.Unmarshal(entriesJSON, &b.Entries)
			list = append(list, &b)
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{"batches": list, "count": len(list)})
		return
	}
	log.Printf("[settlement-batch-processor] list batches from DB failed, using in-memory cache: %v", err)
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
	batchesMu.RLock()
	defer batchesMu.RUnlock()
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{"status": "healthy", "service": "settlement-batch-processor", "batches_processed": len(batches)})
}

// handleReady is the readiness probe — distinct from /health: it fails with
// 503 unless the PostgreSQL pool answers a ping within 2 seconds.
func handleReady(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	if dbPool == nil {
		w.WriteHeader(http.StatusServiceUnavailable)
		json.NewEncoder(w).Encode(map[string]interface{}{"status": "not_ready", "database": "pool not initialized"})
		return
	}
	ctx, cancel := context.WithTimeout(r.Context(), 2*time.Second)
	defer cancel()
	if err := dbPool.Ping(ctx); err != nil {
		w.WriteHeader(http.StatusServiceUnavailable)
		json.NewEncoder(w).Encode(map[string]interface{}{"status": "not_ready", "database": err.Error()})
		return
	}
	json.NewEncoder(w).Encode(map[string]interface{}{"status": "ready", "service": "settlement-batch-processor"})
}

func main() {
	port := os.Getenv("PORT")
	if port == "" {
		port = "9211"
	}

	// Postgres is the source of unsettled transactions — refuse to start without it.
	dsn := os.Getenv("POSTGRES_URL")
	if dsn == "" {
		dsn = os.Getenv("DATABASE_URL")
	}
	if dsn == "" {
		log.Fatal("[settlement-batch-processor] POSTGRES_URL/DATABASE_URL not set — refusing to start")
	}
	pool, err := pgxpool.New(context.Background(), dsn)
	if err != nil {
		log.Fatalf("[settlement-batch-processor] postgres connect failed: %v", err)
	}
	if err := pool.Ping(context.Background()); err != nil {
		log.Fatalf("[settlement-batch-processor] postgres unreachable: %v", err)
	}
	dbPool = pool
	defer dbPool.Close()

	// TigerBeetle is the settlement ledger — refuse to start without it.
	clusterID, _ := strconv.ParseUint(os.Getenv("TIGERBEETLE_CLUSTER_ID"), 10, 64)
	tbAddr := os.Getenv("TIGERBEETLE_ADDR")
	if tbAddr == "" {
		tbAddr = "localhost:3000"
	}
	client, err := tb.NewClient(tbtypes.ToUint128(clusterID), []string{tbAddr})
	if err != nil {
		log.Fatalf("[settlement-batch-processor] tigerbeetle client init failed (%s): %v", tbAddr, err)
	}
	tbClient = client
	defer tbClient.Close()

	http.HandleFunc("/api/v1/batch/create", handleCreateBatch)
	http.HandleFunc("/api/v1/batch/list", handleListBatches)
	http.HandleFunc("/health", handleHealth)
	http.HandleFunc("/ready", handleReady)
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
