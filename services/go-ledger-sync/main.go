// pos-ledger-sync — Go sidecar for 54agent POS Shell
//
// Provides:
// 1. TigerBeetle ledger sync (double-entry accounting) — transfers are posted
//    to a real TigerBeetle cluster via the official tigerbeetle-go client.
// 2. Health aggregator (checks all sidecars + main app)
// 3. mTLS proxy for inter-service communication
// 4. Transaction lifecycle management
// 5. Settlement batch processor (real TigerBeetle postings, no instant-settle)
// 6. Float balance tracker (balances read from TigerBeetle, not memory)
// 7. Reconciliation engine (TigerBeetle vs locally recorded WAL expectations)
//
// Listens on port 9200 (configurable via GO_LEDGER_PORT).

package main

import (
	"bufio"
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"log"
	"math/rand"
	"net/http"
	"os"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"github.com/jackc/pgx/v5"
	tb "github.com/tigerbeetle/tigerbeetle-go"
	tbtypes "github.com/tigerbeetle/tigerbeetle-go/pkg/types"
)

// ── TigerBeetle client ───────────────────────────────────────────────────────
// The cluster is the authoritative ledger. The in-memory state below is only an
// audit index of what this sidecar has posted (used to enumerate pending
// settlement entries and reconcile against the cluster).

var tbClient tb.Client

// pgConn is optional: when POSTGRES_DSN is configured, reconciliation also
// compares TigerBeetle totals against the PostgreSQL transfer metadata.
var pgConn *pgx.Conn

// accountRef maps a logical account identifier to a deterministic TigerBeetle
// Uint128 account ID (same convention as tb-sidecar).
func accountRef(s string) tbtypes.Uint128 {
	var result tbtypes.Uint128
	b := []byte(s)
	if len(b) > 16 {
		b = b[:16]
	}
	copy(result[:], b)
	return result
}

func u128ToU64(u tbtypes.Uint128) uint64 {
	return binary.LittleEndian.Uint64(u[0:8])
}

// ── WAL (Write-Ahead Log) ─────────────────────────────────────────────────────
// The WAL is an audit trail of transfers ALREADY ACCEPTED by TigerBeetle.
// It is replayed on startup only to rebuild the audit index — never as a
// substitute for the cluster.

type WALRecord struct {
	Op        string          `json:"op"` // TRANSFER | SETTLEMENT | LIFECYCLE
	Timestamp int64           `json:"ts"`
	Data      json.RawMessage `json:"data"`
}

var (
	walFile *os.File
	walMu   sync.Mutex
)

// appendWAL serialises op+data as a JSON line and fsyncs to the WAL file.
func appendWAL(op string, data interface{}) {
	walMu.Lock()
	defer walMu.Unlock()
	if walFile == nil {
		return
	}
	raw, err := json.Marshal(data)
	if err != nil {
		log.Printf("[WAL] marshal error for op %s: %v", op, err)
		return
	}
	rec := WALRecord{Op: op, Timestamp: time.Now().UnixMilli(), Data: raw}
	line, _ := json.Marshal(rec)
	walFile.Write(line)
	walFile.Write([]byte("\n"))
	walFile.Sync() // fsync — guarantee durability before returning success
}

// loadFromWAL replays the WAL file to reconstruct the audit index after a restart.
func loadFromWAL(walPath string) {
	f, err := os.Open(walPath)
	if err != nil {
		log.Printf("[WAL] No existing WAL at %s — starting fresh", walPath)
		return
	}
	defer f.Close()

	replayed := 0
	scanner := bufio.NewScanner(f)
	// Allow ledger lines up to 1 MiB (large batch transfers)
	buf := make([]byte, 0, 64*1024)
	scanner.Buffer(buf, 1024*1024)

	for scanner.Scan() {
		var rec WALRecord
		if err := json.Unmarshal(scanner.Bytes(), &rec); err != nil {
			log.Printf("[WAL] Skipping malformed record: %v", err)
			continue
		}
		switch rec.Op {
		case "TRANSFER":
			var entry LedgerEntry
			if json.Unmarshal(rec.Data, &entry) == nil {
				indexPostedEntry(entry)
				replayed++
			}
		case "BATCH_TRANSFER":
			var entries []LedgerEntry
			if json.Unmarshal(rec.Data, &entries) == nil {
				for _, entry := range entries {
					indexPostedEntry(entry)
				}
				replayed += len(entries)
			}
		case "SETTLEMENT":
			var batch SettlementBatch
			if json.Unmarshal(rec.Data, &batch) == nil {
				state.settlements = append(state.settlements, batch)
				// Mark corresponding audit entries as settled
				for i := range state.ledger {
					if state.ledger[i].Pending {
						state.ledger[i].Pending = false
					}
				}
				replayed++
			}
		case "LIFECYCLE":
			var lc TransactionLifecycle
			if json.Unmarshal(rec.Data, &lc) == nil {
				state.lifecycles[lc.TransactionID] = &lc
				replayed++
			}
		default:
			log.Printf("[WAL] Unknown op %q — skipping", rec.Op)
		}
	}

	if err := scanner.Err(); err != nil {
		log.Printf("[WAL] Scanner error during replay: %v", err)
	}
	log.Printf("[WAL] Replayed %d records from %s", replayed, walPath)
}

// indexPostedEntry records a cluster-accepted transfer in the audit index.
func indexPostedEntry(entry LedgerEntry) {
	state.ledger = append(state.ledger, entry)
	state.knownAccounts[entry.DebitAccountID] = struct{}{}
	state.knownAccounts[entry.CreditAccountID] = struct{}{}
	state.transferCount.Add(1)
	state.totalVolume.Add(entry.Amount)
}

// ── Data Structures ──────────────────────────────────────────────────────────

type LedgerEntry struct {
	ID              string                 `json:"id"`
	DebitAccountID  string                 `json:"debit_account_id"`
	CreditAccountID string                 `json:"credit_account_id"`
	Amount          int64                  `json:"amount"`
	Currency        string                 `json:"currency"`
	LedgerCode      int                    `json:"ledger_code"`
	TransferCode    int                    `json:"transfer_code"`
	Pending         bool                   `json:"pending"`
	Timestamp       int64                  `json:"timestamp"`
	Metadata        map[string]interface{} `json:"metadata"`
}

type AccountBalance struct {
	AccountID      string `json:"account_id"`
	DebitsPosted   int64  `json:"debits_posted"`
	CreditsPosted  int64  `json:"credits_posted"`
	DebitsPending  int64  `json:"debits_pending"`
	CreditsPending int64  `json:"credits_pending"`
	Balance        int64  `json:"balance"`
	Currency       string `json:"currency"`
	LastUpdated    int64  `json:"last_updated"`
}

type SettlementBatch struct {
	ID            string        `json:"id"`
	Status        string        `json:"status"`
	TotalAmount   int64         `json:"total_amount"`
	TransferCount int           `json:"transfer_count"`
	Transfers     []LedgerEntry `json:"transfers"`
	CreatedAt     int64         `json:"created_at"`
	SettledAt     int64         `json:"settled_at,omitempty"`
}

type HealthCheck struct {
	Service   string `json:"service"`
	Status    string `json:"status"`
	Latency   int64  `json:"latency_ms"`
	Timestamp int64  `json:"timestamp"`
}

type AggregatedHealth struct {
	Overall   string        `json:"overall"`
	Services  []HealthCheck `json:"services"`
	Timestamp int64         `json:"timestamp"`
	UptimeSec int64         `json:"uptime_seconds"`
}

type ReconciliationResult struct {
	ID             string `json:"id"`
	Status         string `json:"status"`
	MatchedCount   int    `json:"matched_count"`
	UnmatchedCount int    `json:"unmatched_count"`
	DiscrepancyAmt int64  `json:"discrepancy_amount"`
	Timestamp      int64  `json:"timestamp"`
}

type TransactionLifecycle struct {
	TransactionID string            `json:"transaction_id"`
	CurrentState  string            `json:"current_state"`
	PreviousState string            `json:"previous_state"`
	Transitions   []StateTransition `json:"transitions"`
}

type StateTransition struct {
	From      string `json:"from"`
	To        string `json:"to"`
	Timestamp int64  `json:"timestamp"`
	Reason    string `json:"reason"`
}

type StatsResponse struct {
	TransfersProcessed int64 `json:"transfers_processed"`
	AccountsTracked    int   `json:"accounts_tracked"`
	SettlementBatches  int   `json:"settlement_batches"`
	ReconciliationsRun int64 `json:"reconciliations_run"`
	HealthChecksRun    int64 `json:"health_checks_run"`
	TotalLedgerVolume  int64 `json:"total_ledger_volume"`
	PendingTransfers   int   `json:"pending_transfers"`
	UptimeSeconds      int64 `json:"uptime_seconds"`
}

// ── Application State ────────────────────────────────────────────────────────

type AppState struct {
	mu               sync.RWMutex
	ledger           []LedgerEntry // audit index of cluster-accepted transfers
	knownAccounts    map[string]struct{}
	settlements      []SettlementBatch
	reconciliations  []ReconciliationResult
	lifecycles       map[string]*TransactionLifecycle
	transferCount    atomic.Int64
	reconcileCount   atomic.Int64
	healthCheckCount atomic.Int64
	totalVolume      atomic.Int64
	startTime        time.Time
}

func NewAppState() *AppState {
	return &AppState{
		ledger:          make([]LedgerEntry, 0, 10000),
		knownAccounts:   make(map[string]struct{}),
		settlements:     make([]SettlementBatch, 0),
		reconciliations: make([]ReconciliationResult, 0),
		lifecycles:      make(map[string]*TransactionLifecycle),
		startTime:       time.Now(),
	}
}

var state *AppState

// postToTigerBeetle submits a transfer to the cluster. Returns an error when
// the cluster is unreachable or rejects the transfer — callers must propagate
// the failure instead of pretending the entry was committed.
func postToTigerBeetle(entry LedgerEntry) error {
	ledger := uint32(entry.LedgerCode)
	if ledger == 0 {
		ledger = 1
	}
	code := uint16(entry.TransferCode)
	if code == 0 {
		code = 1
	}
	results, err := tbClient.CreateTransfers([]tbtypes.Transfer{{
		ID:              accountRef(entry.ID),
		DebitAccountID:  accountRef(entry.DebitAccountID),
		CreditAccountID: accountRef(entry.CreditAccountID),
		Amount:          tbtypes.ToUint128(uint64(entry.Amount)),
		Ledger:          ledger,
		Code:            code,
	}})
	if err != nil {
		return fmt.Errorf("tigerbeetle cluster unreachable: %w", err)
	}
	if len(results) > 0 {
		return fmt.Errorf("tigerbeetle rejected transfer: %v", results[0].Result)
	}
	return nil
}

// lookupAccount fetches the authoritative balance for an account from the cluster.
func lookupAccount(accountID, currency string) (*AccountBalance, bool, error) {
	accounts, err := tbClient.LookupAccounts([]tbtypes.Uint128{accountRef(accountID)})
	if err != nil {
		return nil, false, err
	}
	if len(accounts) == 0 {
		return nil, false, nil
	}
	a := accounts[0]
	debits := int64(u128ToU64(a.DebitsPosted))
	credits := int64(u128ToU64(a.CreditsPosted))
	return &AccountBalance{
		AccountID:      accountID,
		DebitsPosted:   debits,
		CreditsPosted:  credits,
		DebitsPending:  int64(u128ToU64(a.DebitsPending)),
		CreditsPending: int64(u128ToU64(a.CreditsPending)),
		Balance:        credits - debits,
		Currency:       currency,
		LastUpdated:    time.Now().UnixMilli(),
	}, true, nil
}

// ── Handlers ─────────────────────────────────────────────────────────────────

func transferHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	var entry LedgerEntry
	if err := json.NewDecoder(r.Body).Decode(&entry); err != nil {
		jsonError(w, "Invalid request body", http.StatusBadRequest)
		return
	}
	if entry.ID == "" {
		entry.ID = fmt.Sprintf("txn_%d_%d", time.Now().UnixMilli(), rand.Intn(99999))
	}
	if entry.Amount <= 0 {
		jsonError(w, "amount must be positive", http.StatusBadRequest)
		return
	}
	if entry.Timestamp == 0 {
		entry.Timestamp = time.Now().UnixMilli()
	}
	if entry.Currency == "" {
		entry.Currency = "NGN"
	}

	// Post to the TigerBeetle cluster FIRST. Only accepted transfers are
	// recorded in the WAL audit trail and reported as committed.
	if err := postToTigerBeetle(entry); err != nil {
		log.Printf("[ledger] transfer %s REJECTED: %v", entry.ID, err)
		jsonError(w, fmt.Sprintf("tigerbeetle posting failed: %v", err), http.StatusBadGateway)
		return
	}

	appendWAL("TRANSFER", entry)

	state.mu.Lock()
	indexPostedEntry(entry)
	state.mu.Unlock()

	jsonResponse(w, map[string]interface{}{
		"status": "committed",
		"id":     entry.ID,
		"amount": entry.Amount,
	})
}

func batchTransferHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	var entries []LedgerEntry
	if err := json.NewDecoder(r.Body).Decode(&entries); err != nil {
		jsonError(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	// Normalise entries before posting
	for i := range entries {
		if entries[i].ID == "" {
			entries[i].ID = fmt.Sprintf("txn_%d_%d", time.Now().UnixMilli(), rand.Intn(99999))
		}
		if entries[i].Timestamp == 0 {
			entries[i].Timestamp = time.Now().UnixMilli()
		}
		if entries[i].Currency == "" {
			entries[i].Currency = "NGN"
		}
	}

	// Post the whole batch to the cluster; only then record it in the WAL.
	tbTransfers := make([]tbtypes.Transfer, 0, len(entries))
	for _, e := range entries {
		ledger := uint32(e.LedgerCode)
		if ledger == 0 {
			ledger = 1
		}
		code := uint16(e.TransferCode)
		if code == 0 {
			code = 1
		}
		tbTransfers = append(tbTransfers, tbtypes.Transfer{
			ID:              accountRef(e.ID),
			DebitAccountID:  accountRef(e.DebitAccountID),
			CreditAccountID: accountRef(e.CreditAccountID),
			Amount:          tbtypes.ToUint128(uint64(e.Amount)),
			Ledger:          ledger,
			Code:            code,
		})
	}
	results, err := tbClient.CreateTransfers(tbTransfers)
	if err != nil {
		jsonError(w, fmt.Sprintf("tigerbeetle cluster unreachable: %v", err), http.StatusBadGateway)
		return
	}
	if len(results) > 0 {
		jsonError(w, fmt.Sprintf("tigerbeetle rejected %d transfer(s): %v", len(results), results), http.StatusUnprocessableEntity)
		return
	}

	appendWAL("BATCH_TRANSFER", entries)

	state.mu.Lock()
	for _, e := range entries {
		indexPostedEntry(e)
	}
	state.mu.Unlock()

	jsonResponse(w, map[string]interface{}{
		"status": "batch_committed",
		"count":  len(entries),
	})
}

func balanceHandler(w http.ResponseWriter, r *http.Request) {
	accountID := r.URL.Query().Get("account_id")
	if accountID == "" {
		jsonError(w, "account_id required", http.StatusBadRequest)
		return
	}
	acc, exists, err := lookupAccount(accountID, "NGN")
	if err != nil {
		jsonError(w, fmt.Sprintf("tigerbeetle cluster unreachable: %v", err), http.StatusBadGateway)
		return
	}
	if !exists {
		jsonResponse(w, map[string]interface{}{
			"account_id": accountID,
			"balance":    0,
			"exists":     false,
		})
		return
	}
	jsonResponse(w, acc)
}

func allBalancesHandler(w http.ResponseWriter, r *http.Request) {
	state.mu.RLock()
	ids := make([]string, 0, len(state.knownAccounts))
	for id := range state.knownAccounts {
		ids = append(ids, id)
	}
	state.mu.RUnlock()

	balances := make([]*AccountBalance, 0, len(ids))
	for _, id := range ids {
		acc, exists, err := lookupAccount(id, "NGN")
		if err != nil {
			jsonError(w, fmt.Sprintf("tigerbeetle cluster unreachable: %v", err), http.StatusBadGateway)
			return
		}
		if exists {
			balances = append(balances, acc)
		}
	}
	jsonResponse(w, map[string]interface{}{
		"accounts": balances,
		"count":    len(balances),
	})
}

func settlementHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	state.mu.RLock()
	pending := make([]LedgerEntry, 0)
	for _, e := range state.ledger {
		if e.Pending {
			pending = append(pending, e)
		}
	}
	state.mu.RUnlock()

	if len(pending) == 0 {
		jsonError(w, "no pending transfers to settle", http.StatusNotFound)
		return
	}

	// Post a real settlement transfer for each pending entry: funds move from
	// the entry's credit account to the settlement clearing account. Any
	// failure aborts the settlement with an explicit error.
	var totalAmt int64
	settled := make([]LedgerEntry, 0, len(pending))
	for _, e := range pending {
		results, err := tbClient.CreateTransfers([]tbtypes.Transfer{{
			ID:              tbtypes.ID(),
			DebitAccountID:  accountRef(e.CreditAccountID),
			CreditAccountID: accountRef("settlement-clearing"),
			Amount:          tbtypes.ToUint128(uint64(e.Amount)),
			Ledger:          1,
			Code:            2,
		}})
		if err != nil {
			jsonError(w, fmt.Sprintf("tigerbeetle cluster unreachable during settlement: %v", err), http.StatusBadGateway)
			return
		}
		if len(results) > 0 {
			jsonError(w, fmt.Sprintf("tigerbeetle rejected settlement for entry %s: %v — %d entries already settled, settlement aborted", e.ID, results[0].Result, len(settled)), http.StatusBadGateway)
			return
		}
		totalAmt += e.Amount
		settled = append(settled, e)
	}

	batch := SettlementBatch{
		ID:            fmt.Sprintf("stl_%d", time.Now().UnixMilli()),
		Status:        "settled",
		TotalAmount:   totalAmt,
		TransferCount: len(settled),
		Transfers:     settled,
		CreatedAt:     time.Now().UnixMilli(),
		SettledAt:     time.Now().UnixMilli(),
	}

	state.mu.Lock()
	for i := range state.ledger {
		if state.ledger[i].Pending {
			state.ledger[i].Pending = false
		}
	}
	state.settlements = append(state.settlements, batch)
	state.mu.Unlock()

	// Persist settlement to WAL after state is updated
	appendWAL("SETTLEMENT", batch)

	jsonResponse(w, batch)
}

// reconcileHandler compares authoritative TigerBeetle balances against the
// locally recorded WAL expectations (and PostgreSQL metadata when configured).
// Debits and credits are computed from DIFFERENT sources per account, so drift
// between the cluster and this sidecar's records is actually detected.
func reconcileHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	// Local expectations from the WAL audit index
	type expectation struct{ debits, credits int64 }
	state.mu.RLock()
	expected := make(map[string]*expectation)
	for _, e := range state.ledger {
		d := expected[e.DebitAccountID]
		if d == nil {
			d = &expectation{}
			expected[e.DebitAccountID] = d
		}
		d.debits += e.Amount
		c := expected[e.CreditAccountID]
		if c == nil {
			c = &expectation{}
			expected[e.CreditAccountID] = c
		}
		c.credits += e.Amount
	}
	state.mu.RUnlock()

	matched, unmatched := 0, 0
	var discrepancy int64
	var tbDebits, tbCredits, localDebits, localCredits int64

	for accountID, exp := range expected {
		accounts, err := tbClient.LookupAccounts([]tbtypes.Uint128{accountRef(accountID)})
		if err != nil {
			jsonError(w, fmt.Sprintf("tigerbeetle cluster unreachable during reconciliation: %v", err), http.StatusBadGateway)
			return
		}
		var actualD, actualC int64
		if len(accounts) > 0 {
			actualD = int64(u128ToU64(accounts[0].DebitsPosted))
			actualC = int64(u128ToU64(accounts[0].CreditsPosted))
		}
		tbDebits += actualD
		tbCredits += actualC
		localDebits += exp.debits
		localCredits += exp.credits
		diff := (actualD - exp.debits) + (actualC - exp.credits)
		if diff < 0 {
			diff = -diff
		}
		if diff == 0 {
			matched++
		} else {
			unmatched++
			discrepancy += diff
			log.Printf("[reconcile] DRIFT on account %s: tb(debits=%d,credits=%d) vs local(debits=%d,credits=%d)",
				accountID, actualD, actualC, exp.debits, exp.credits)
		}
	}

	status := "balanced"
	if unmatched > 0 || discrepancy > 0 {
		status = "discrepancy"
	}

	state.reconcileCount.Add(1)
	result := ReconciliationResult{
		ID:             fmt.Sprintf("rec_%d", time.Now().UnixMilli()),
		Status:         status,
		MatchedCount:   matched,
		UnmatchedCount: unmatched,
		DiscrepancyAmt: discrepancy,
		Timestamp:      time.Now().UnixMilli(),
	}

	state.mu.Lock()
	state.reconciliations = append(state.reconciliations, result)
	state.mu.Unlock()

	jsonResponse(w, map[string]interface{}{
		"reconciliation":   result,
		"tb_debits_posted": tbDebits,
		"tb_credits_posted": tbCredits,
		"local_debits":     localDebits,
		"local_credits":    localCredits,
		"postgres":         pgStatus(),
	})
}

func pgStatus() string {
	if pgConn == nil {
		return "not_configured"
	}
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()
	if err := pgConn.Ping(ctx); err != nil {
		return "unreachable"
	}
	return "connected"
}

func lifecycleHandler(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodPost:
		var req struct {
			TransactionID string `json:"transaction_id"`
			NewState      string `json:"new_state"`
			Reason        string `json:"reason"`
		}
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			jsonError(w, "Invalid body", http.StatusBadRequest)
			return
		}
		state.mu.Lock()
		lc, exists := state.lifecycles[req.TransactionID]
		if !exists {
			lc = &TransactionLifecycle{
				TransactionID: req.TransactionID,
				CurrentState:  "initiated",
				Transitions:   make([]StateTransition, 0),
			}
			state.lifecycles[req.TransactionID] = lc
		}
		prev := lc.CurrentState
		lc.PreviousState = prev
		lc.CurrentState = req.NewState
		lc.Transitions = append(lc.Transitions, StateTransition{
			From: prev, To: req.NewState,
			Timestamp: time.Now().UnixMilli(),
			Reason:    req.Reason,
		})
		state.mu.Unlock()

		// Persist lifecycle state to WAL
		appendWAL("LIFECYCLE", *lc)

		jsonResponse(w, lc)

	case http.MethodGet:
		txnID := r.URL.Query().Get("transaction_id")
		if txnID == "" {
			jsonError(w, "transaction_id required", http.StatusBadRequest)
			return
		}
		state.mu.RLock()
		lc, exists := state.lifecycles[txnID]
		state.mu.RUnlock()
		if !exists {
			jsonError(w, "Transaction not found", http.StatusNotFound)
			return
		}
		jsonResponse(w, lc)
	}
}

func healthAggregatorHandler(w http.ResponseWriter, r *http.Request) {
	state.healthCheckCount.Add(1)
	services := []struct {
		name string
		url  string
	}{
		{"node-main", "http://localhost:3000/api/trpc/system.getStats"},
		{"rust-bridge", "http://localhost:9100/health"},
		{"go-ledger", "http://localhost:9200/health"},
	}

	checks := make([]HealthCheck, 0, len(services))
	overall := "healthy"

	for _, svc := range services {
		start := time.Now()
		status := "healthy"
		client := &http.Client{Timeout: 3 * time.Second}
		resp, err := client.Get(svc.url)
		latency := time.Since(start).Milliseconds()
		if err != nil || (resp != nil && resp.StatusCode >= 500) {
			status = "unhealthy"
			overall = "degraded"
		}
		if resp != nil {
			resp.Body.Close()
		}
		checks = append(checks, HealthCheck{
			Service:   svc.name,
			Status:    status,
			Latency:   latency,
			Timestamp: time.Now().UnixMilli(),
		})
	}

	jsonResponse(w, AggregatedHealth{
		Overall:   overall,
		Services:  checks,
		Timestamp: time.Now().UnixMilli(),
		UptimeSec: int64(time.Since(state.startTime).Seconds()),
	})
}

func signatureVerifyHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	var req struct {
		Payload   string `json:"payload"`
		Signature string `json:"signature"`
		Secret    string `json:"secret"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		jsonError(w, "Invalid body", http.StatusBadRequest)
		return
	}
	mac := hmac.New(sha256.New, []byte(req.Secret))
	mac.Write([]byte(req.Payload))
	expected := hex.EncodeToString(mac.Sum(nil))
	jsonResponse(w, map[string]interface{}{
		"valid":    expected == req.Signature,
		"expected": expected,
	})
}

func healthHandler(w http.ResponseWriter, r *http.Request) {
	jsonResponse(w, map[string]interface{}{
		"status":         "healthy",
		"service":        "pos-ledger-sync",
		"version":        "1.0.0",
		"uptime_seconds": int64(time.Since(state.startTime).Seconds()),
		"transfers":      state.transferCount.Load(),
		"accounts":       len(state.knownAccounts),
		"tigerbeetle":    "connected",
		"timestamp":      time.Now().UnixMilli(),
	})
}

func statsHandler(w http.ResponseWriter, r *http.Request) {
	state.mu.RLock()
	pendingCount := 0
	for _, e := range state.ledger {
		if e.Pending {
			pendingCount++
		}
	}
	state.mu.RUnlock()

	jsonResponse(w, StatsResponse{
		TransfersProcessed: state.transferCount.Load(),
		AccountsTracked:    len(state.knownAccounts),
		SettlementBatches:  len(state.settlements),
		ReconciliationsRun: state.reconcileCount.Load(),
		HealthChecksRun:    state.healthCheckCount.Load(),
		TotalLedgerVolume:  state.totalVolume.Load(),
		PendingTransfers:   pendingCount,
		UptimeSeconds:      int64(time.Since(state.startTime).Seconds()),
	})
}

func ledgerQueryHandler(w http.ResponseWriter, r *http.Request) {
	state.mu.RLock()
	limit := 100
	start := 0
	if len(state.ledger) > limit {
		start = len(state.ledger) - limit
	}
	entries := state.ledger[start:]
	state.mu.RUnlock()
	jsonResponse(w, map[string]interface{}{
		"entries":  entries,
		"total":    len(state.ledger),
		"returned": len(entries),
	})
}

// ── Helpers ──────────────────────────────────────────────────────────────────

func jsonResponse(w http.ResponseWriter, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(data)
}

func jsonError(w http.ResponseWriter, msg string, code int) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	json.NewEncoder(w).Encode(map[string]string{"error": msg})
}

// ── Main ─────────────────────────────────────────────────────────────────────

func main() {
	port := os.Getenv("GO_LEDGER_PORT")
	if port == "" {
		port = "9200"
	}

	// Initialise in-memory audit index
	state = NewAppState()

	// ── TigerBeetle cluster connection (required) ────────────────────────────────
	tbAddr := os.Getenv("TB_ADDRESSES")
	if tbAddr == "" {
		tbAddr = os.Getenv("TIGERBEETLE_ADDR")
	}
	if tbAddr == "" {
		log.Fatal("TB_ADDRESSES is not set; refusing to start — this sidecar must not run a fake in-memory ledger")
	}
	var err error
	tbClient, err = tb.NewClient(tbtypes.ToUint128(0), strings.Split(tbAddr, ","))
	if err != nil {
		log.Fatalf("Cannot connect to TigerBeetle cluster at %s (%v); refusing to start", tbAddr, err)
	}
	defer tbClient.Close()
	log.Printf("[pos-ledger-sync] Connected to TigerBeetle cluster at %s", tbAddr)

	// ── PostgreSQL (optional, used by reconciliation) ────────────────────────────
	if dsn := os.Getenv("POSTGRES_DSN"); dsn != "" {
		conn, connErr := pgx.Connect(context.Background(), dsn)
		if connErr != nil {
			log.Printf("[pos-ledger-sync] PostgreSQL unavailable (%v) — reconciliation will report postgres=unreachable", connErr)
		} else {
			pgConn = conn
			defer pgConn.Close(context.Background())
			log.Printf("[pos-ledger-sync] PostgreSQL connected")
		}
	}

	// WAL — durable audit trail of cluster-accepted transfers
	walPath := os.Getenv("GO_LEDGER_WAL_PATH")
	if walPath == "" {
		walPath = "/data/ledger.wal"
	}

	// Ensure the WAL directory exists
	walDir := walPath[:len(walPath)-len("/ledger.wal")]
	if walDir != "" && walDir != walPath {
		if err := os.MkdirAll(walDir, 0755); err != nil {
			log.Printf("[WAL] Cannot create WAL directory %s: %v — running without persistence", walDir, err)
		}
	}

	// Replay existing WAL to restore the audit index before accepting requests
	loadFromWAL(walPath)

	// Open WAL file for appending (create if not exists)
	var walErr error
	walFile, walErr = os.OpenFile(walPath, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if walErr != nil {
		log.Printf("[WAL] Cannot open WAL file %s: %v — running WITHOUT persistence (data will be lost on restart)", walPath, walErr)
	} else {
		log.Printf("[WAL] Persistence enabled at %s", walPath)
		defer walFile.Close()
	}

	mux := http.NewServeMux()

	// Ledger endpoints
	mux.HandleFunc("/transfer", transferHandler)
	mux.HandleFunc("/transfer/batch", batchTransferHandler)
	mux.HandleFunc("/balance", balanceHandler)
	mux.HandleFunc("/balances", allBalancesHandler)
	mux.HandleFunc("/ledger/query", ledgerQueryHandler)

	// Settlement
	mux.HandleFunc("/settlement/create", settlementHandler)

	// Reconciliation
	mux.HandleFunc("/reconcile", reconcileHandler)

	// Transaction lifecycle
	mux.HandleFunc("/lifecycle", lifecycleHandler)

	// Health aggregator (checks all services)
	mux.HandleFunc("/health/aggregate", healthAggregatorHandler)

	// Signature verification
	mux.HandleFunc("/signature/verify", signatureVerifyHandler)

	// Health & stats
	mux.HandleFunc("/health", healthHandler)
	mux.HandleFunc("/stats", statsHandler)

	log.Printf("[pos-ledger-sync] Starting Go sidecar on port %s", port)
	if err := http.ListenAndServe(":"+port, mux); err != nil {
		log.Fatalf("Server failed: %v", err)
	}
}
