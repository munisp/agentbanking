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
	batchSeq  int

	dbPool   *pgxpool.Pool
	tbClient tb.Client
)

func generateBatchID() string {
	batchSeq++
	return fmt.Sprintf("BATCH-%s-%04d", time.Now().Format("20060102"), batchSeq)
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

// fetchUnsettledRows queries the real unsettled billing ledger rows from Postgres.
func fetchUnsettledRows(ctx context.Context) ([]ledgerRow, error) {
	rows, err := dbPool.Query(ctx, `
		SELECT id, transaction_id, agent_id, transaction_type,
		       gross_amount, gross_fee, agent_commission
		FROM platform_billing_ledger
		WHERE settlement_status = 'pending'
		ORDER BY id
		LIMIT 10000`)
	if err != nil {
		return nil, fmt.Errorf("query unsettled ledger rows: %w", err)
	}
	defer rows.Close()

	var out []ledgerRow
	for rows.Next() {
		var r ledgerRow
		if err := rows.Scan(&r.id, &r.transactionID, &r.agentID, &r.transactionType,
			&r.grossAmount, &r.grossFee, &r.agentCommission); err != nil {
			return nil, fmt.Errorf("scan ledger row: %w", err)
		}
		out = append(out, r)
	}
	return out, rows.Err()
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
		return fmt.Errorf("tigerbeetle settlement transfer rejected: result=%v index=%d", results[0].Result, results[0].Index)
	}
	log.Printf("[TigerBeetle] settlement transfer %s committed (%d kobo -> agent %s)",
		hex.EncodeToString(transferID[:]), amountKobo, agentID)
	return nil
}

func handleCreateBatch(w http.ResponseWriter, r *http.Request) {
	if r.Method != "POST" {
		http.Error(w, `{"error":"method not allowed"}`, 405)
		return
	}
	ctx := r.Context()

	// Step 1: fetch real unsettled transactions. Fail loudly when there are none.
	rows, err := fetchUnsettledRows(ctx)
	if err != nil {
		log.Printf("[settlement-batch-processor] failed to fetch unsettled rows: %v", err)
		http.Error(w, fmt.Sprintf(`{"error":%q}`, "failed to query unsettled transactions: "+err.Error()), 500)
		return
	}
	if len(rows) == 0 {
		http.Error(w, `{"error":"no eligible unsettled transactions"}`, 422)
		return
	}

	batchesMu.Lock()
	batch := &SettlementBatch{
		BatchID:   generateBatchID(),
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

	// Step 3: post the real per-agent settlement transfers to TigerBeetle.
	// Any failure marks the whole batch failed — never report a fabricated completion.
	for _, entry := range batch.Entries {
		amountKobo := int64(math.Round(entry.SettlementAmt * 100))
		if amountKobo <= 0 {
			continue // nothing payable to this agent
		}
		if err := postSettlementTransfer(batch.BatchID, entry.AgentID, amountKobo); err != nil {
			batchesMu.Lock()
			batch.Status = "failed"
			batchesMu.Unlock()
			log.Printf("[settlement-batch-processor] batch %s failed at agent %s: %v", batch.BatchID, entry.AgentID, err)
			http.Error(w, fmt.Sprintf(`{"error":%q,"batch_id":%q}`,
				"ledger settlement posting failed for agent "+entry.AgentID+": "+err.Error(), batch.BatchID), 500)
			return
		}
	}

	// Step 4: mark the source rows settled only after successful ledger postings.
	rowIDs := make([]int64, 0, len(rows))
	for _, row := range rows {
		rowIDs = append(rowIDs, row.id)
	}
	if _, err := dbPool.Exec(ctx, `
		UPDATE platform_billing_ledger
		SET settlement_status = 'settled', settlement_batch_id = $1, settled_at = NOW()
		WHERE id = ANY($2) AND settlement_status = 'pending'`,
		batch.BatchID, rowIDs); err != nil {
		batchesMu.Lock()
		batch.Status = "failed"
		batchesMu.Unlock()
		log.Printf("[settlement-batch-processor] batch %s ledger update failed after TB postings: %v", batch.BatchID, err)
		http.Error(w, fmt.Sprintf(`{"error":%q,"batch_id":%q}`,
			"failed to mark ledger rows settled after postings: "+err.Error(), batch.BatchID), 500)
		return
	}

	now := time.Now()
	batchesMu.Lock()
	batch.CompletedAt = &now
	batch.Status = "completed"
	batchesMu.Unlock()

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(batch)
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
	batchesMu.RLock()
	defer batchesMu.RUnlock()
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{"status": "healthy", "service": "settlement-batch-processor", "batches_processed": len(batches)})
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
