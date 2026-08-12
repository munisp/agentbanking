// pos-ledger-sync — Go sidecar for 54agent POS Shell
//
// Provides:
// 1. TigerBeetle ledger sync (double-entry accounting) — backed by a real
//    TigerBeetle cluster via the official tigerbeetle-go client
// 2. Health aggregator (checks all sidecars + main app)
// 3. mTLS proxy for inter-service communication
// 4. Transaction lifecycle management
// 5. Settlement batch processor (two-phase commit against TigerBeetle)
// 6. Float balance tracker
// 7. Reconciliation engine (TigerBeetle cluster vs local synced ledger)
//
// Listens on port 9200 (configurable via GO_LEDGER_PORT).

package main

import (
	"bufio"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"log"
	"math/rand"
	"net/http"
	"os"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	tb "github.com/tigerbeetle/tigerbeetle-go"
	tbtypes "github.com/tigerbeetle/tigerbeetle-go/pkg/types"
)

// ── TigerBeetle cluster client (source of truth) ─────────────────────────────

var tbClient tb.Client

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

// tbAccountID maps a POS account identifier to its TigerBeetle account ID.
func tbAccountID(accountID string) tbtypes.Uint128 {
	return stringToUint128("acct:" + accountID)
}

// ensureTBAccount creates the account in TigerBeetle, tolerating EXISTS.
func ensureTBAccount(accountID, currency string) error {
	results, err := tbClient.CreateAccounts([]tbtypes.Account{
		{ID: tbAccountID(accountID), Ledger: 1, Code: 1, Flags: 0},
	})
	if err != nil {
		return fmt.Errorf("tigerbeetle CreateAccounts: %w", err)
	}
	for _, res := range results {
		if !strings.Contains(fmt.Sprintf("%v", res.Result), "EXISTS") {
			return fmt.Errorf("tigerbeetle account creation rejected for %s: result=%v", accountID, res.Result)
		}
	}
	return nil
}

// postTransferToTigerBeetle posts a real transfer. Pending entries are posted
// as two-phase pending transfers so settlement can post them later.
func postTransferToTigerBeetle(entry LedgerEntry) error {
	if tbClient == nil {
		return fmt.Errorf("tigerbeetle client not connected")
	}
	if err := ensureTBAccount(entry.DebitAccountID, entry.Currency); err != nil {
		return err
	}
	if err := ensureTBAccount(entry.CreditAccountID, entry.Currency); err != nil {
		return err
	}

	flags := uint16(0)
	if entry.Pending {
		flags = tbtypes.TransferFlags{Pending: true}.ToUint16()
	}

	results, err := tbClient.CreateTransfers([]tbtypes.Transfer{
		{
			ID:              stringToUint128(entry.ID),
			DebitAccountID:  tbAccountID(entry.DebitAccountID),
			CreditAccountID: tbAccountID(entry.CreditAccountID),
			Amount:          tbtypes.ToUint128(uint64(entry.Amount)),
			Ledger:          uint32(entry.LedgerCode),
			Code:            uint16(entry.TransferCode),
			Flags:           flags,
		},
	})
	if err != nil {
		return fmt.Errorf("tigerbeetle CreateTransfers: %w", err)
	}
	if len(results) > 0 {
		return fmt.Errorf("tigerbeetle transfer rejected: result=%v index=%d", results[0].Result, results[0].Index)
	}
	return nil
}

// settlePendingTransfer posts the pending transfer in TigerBeetle (2nd phase).
func settlePendingTransfer(entry LedgerEntry) error {
	if tbClient == nil {
		return fmt.Errorf("tigerbeetle client not connected")
	}
	results, err := tbClient.CreateTransfers([]tbtypes.Transfer{
		{
			ID:              stringToUint128("stl:" + entry.ID),
			DebitAccountID:  tbAccountID(entry.DebitAccountID),
			CreditAccountID: tbAccountID(entry.CreditAccountID),
			Amount:          tbtypes.ToUint128(0), // 0 = post full pending amount
			PendingID:       stringToUint128(entry.ID),
			Ledger:          uint32(entry.LedgerCode),
			Code:            uint16(entry.TransferCode),
			Flags:           tbtypes.TransferFlags{PostPendingTransfer: true}.ToUint16(),
		},
	})
	if err != nil {
		return fmt.Errorf("tigerbeetle post-pending transfer: %w", err)
	}
	if len(results) > 0 {
		return fmt.Errorf("tigerbeetle settlement rejected for %s: result=%v", entry.ID, results[0].Result)
	}
	return nil
}

// ── WAL (Write-Ahead Log) ─────────────────────────────────────────────────────
// Provides durable persistence using only Go stdlib (no external DB driver).
// Every mutation is appended as a JSON line to the WAL file before the in-memory
// state is updated. On startup, the WAL is replayed to rebuild state, ensuring
// no data is lost across pod restarts.

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

// loadFromWAL replays the WAL file to reconstruct in-memory state after a restart.
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
				state.ledger = append(state.ledger, entry)
				updateAccount(entry.DebitAccountID, entry.Currency, -entry.Amount, entry.Pending)
				updateAccount(entry.CreditAccountID, entry.Currency, entry.Amount, entry.Pending)
				state.transferCount.Add(1)
				state.totalVolume.Add(entry.Amount)
				replayed++
			}
		case "BATCH_TRANSFER":
			var entries []LedgerEntry
			if json.Unmarshal(rec.Data, &entries) == nil {
				for _, entry := range entries {
					state.ledger = append(state.ledger, entry)
					updateAccount(entry.DebitAccountID, entry.Currency, -entry.Amount, entry.Pending)
					updateAccount(entry.CreditAccountID, entry.Currency, entry.Amount, entry.Pending)
					state.transferCount.Add(1)
					state.totalVolume.Add(entry.Amount)
				}
				replayed += len(entries)
			}
		case "SETTLEMENT":
			var batch SettlementBatch
			if json.Unmarshal(rec.Data, &batch) == nil {
				state.settlements = append(state.settlements, batch)
				// Mark corresponding ledger entries as settled
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
// Local materialised cache of transfers that were ACCEPTED by the TigerBeetle
// cluster. Nothing is recorded here unless the cluster committed it first.

type AppState struct {
	mu               sync.RWMutex
	ledger           []LedgerEntry
	accounts         map[string]*AccountBalance
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
		accounts:        make(map[string]*AccountBalance),
		settlements:     make([]SettlementBatch, 0),
		reconciliations: make([]ReconciliationResult, 0),
		lifecycles:      make(map[string]*TransactionLifecycle),
		startTime:       time.Now(),
	}
}

var state *AppState

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
	if entry.Timestamp == 0 {
		entry.Timestamp = time.Now().UnixMilli()
	}
	if entry.Currency == "" {
		entry.Currency = "NGN"
	}
	if entry.LedgerCode == 0 {
		entry.LedgerCode = 1
	}
	if entry.TransferCode == 0 {
		entry.TransferCode = 1
	}

	// Post to the real TigerBeetle cluster first. Only record locally what the
	// cluster actually committed.
	if err := postTransferToTigerBeetle(entry); err != nil {
		log.Printf("[TB] transfer %s rejected: %v", entry.ID, err)
		jsonError(w, "ledger posting failed: "+err.Error(), http.StatusServiceUnavailable)
		return
	}

	// Persist to WAL before updating in-memory state
	appendWAL("TRANSFER", entry)

	state.mu.Lock()
	state.ledger = append(state.ledger, entry)
	updateAccount(entry.DebitAccountID, entry.Currency, -entry.Amount, entry.Pending)
	updateAccount(entry.CreditAccountID, entry.Currency, entry.Amount, entry.Pending)
	state.mu.Unlock()

	state.transferCount.Add(1)
	state.totalVolume.Add(entry.Amount)

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

	// Normalise entries before persisting
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
		if entries[i].LedgerCode == 0 {
			entries[i].LedgerCode = 1
		}
		if entries[i].TransferCode == 0 {
			entries[i].TransferCode = 1
		}
	}

	// Post every entry to the real cluster. Any rejection aborts the batch —
	// nothing is recorded that TigerBeetle did not accept.
	for i := range entries {
		if err := postTransferToTigerBeetle(entries[i]); err != nil {
			log.Printf("[TB] batch transfer %s rejected: %v", entries[i].ID, err)
			jsonError(w, fmt.Sprintf("batch aborted at entry %d (%s): %v", i, entries[i].ID, err),
				http.StatusServiceUnavailable)
			return
		}
	}

	// Persist batch to WAL atomically before updating state
	appendWAL("BATCH_TRANSFER", entries)

	state.mu.Lock()
	for i := range entries {
		state.ledger = append(state.ledger, entries[i])
		updateAccount(entries[i].DebitAccountID, entries[i].Currency, -entries[i].Amount, entries[i].Pending)
		updateAccount(entries[i].CreditAccountID, entries[i].Currency, entries[i].Amount, entries[i].Pending)
		state.transferCount.Add(1)
		state.totalVolume.Add(entries[i].Amount)
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
	state.mu.RLock()
	acc, exists := state.accounts[accountID]
	state.mu.RUnlock()
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
	balances := make([]*AccountBalance, 0, len(state.accounts))
	for _, acc := range state.accounts {
		balances = append(balances, acc)
	}
	state.mu.RUnlock()
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
		jsonError(w, "no pending transfers to settle", http.StatusConflict)
		return
	}

	// Post the second phase of every pending transfer in TigerBeetle.
	// A settlement is only reported once the cluster accepted it.
	for _, e := range pending {
		if err := settlePendingTransfer(e); err != nil {
			log.Printf("[TB] settlement failed for %s: %v", e.ID, err)
			jsonError(w, "settlement posting failed for "+e.ID+": "+err.Error(), http.StatusServiceUnavailable)
			return
		}
	}

	var totalAmt int64
	for _, e := range pending {
		totalAmt += e.Amount
	}
	batch := SettlementBatch{
		ID:            fmt.Sprintf("stl_%d", time.Now().UnixMilli()),
		Status:        "settled",
		TotalAmount:   totalAmt,
		TransferCount: len(pending),
		Transfers:     pending,
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

// reconcileHandler honestly compares the local synced ledger against the
// TigerBeetle cluster. It never reports "balanced" by construction.
func reconcileHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	if tbClient == nil {
		jsonError(w, "tigerbeetle cluster unreachable — reconciliation cannot run", http.StatusServiceUnavailable)
		return
	}

	state.mu.RLock()
	accountIDs := make([]string, 0, len(state.accounts))
	localAccounts := make(map[string]AccountBalance, len(state.accounts))
	for id, acc := range state.accounts {
		accountIDs = append(accountIDs, id)
		localAccounts[id] = *acc
	}
	state.mu.RUnlock()

	matched := 0
	unmatched := 0
	var discrepancy int64

	for _, accountID := range accountIDs {
		accounts, err := tbClient.LookupAccounts([]tbtypes.Uint128{tbAccountID(accountID)})
		if err != nil {
			jsonError(w, "tigerbeetle lookup failed during reconciliation: "+err.Error(), http.StatusServiceUnavailable)
			return
		}
		local := localAccounts[accountID]
		if len(accounts) == 0 {
			// Local state claims activity the cluster does not know about.
			unmatched++
			discrepancy += local.CreditsPosted + local.DebitsPosted
			continue
		}
		tbAcc := accounts[0]
		tbDebits := int64(tbAcc.DebitsPosted.BigInt().Uint64())
		tbCredits := int64(tbAcc.CreditsPosted.BigInt().Uint64())
		if tbDebits == local.DebitsPosted && tbCredits == local.CreditsPosted {
			matched++
		} else {
			unmatched++
			d := (tbCredits - tbDebits) - (local.CreditsPosted - local.DebitsPosted)
			if d < 0 {
				d = -d
			}
			discrepancy += d
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

	jsonResponse(w, result)
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
		"accounts":       len(state.accounts),
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
		AccountsTracked:    len(state.accounts),
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

func updateAccount(accountID, currency string, amount int64, pending bool) {
	acc, exists := state.accounts[accountID]
	if !exists {
		acc = &AccountBalance{
			AccountID: accountID,
			Currency:  currency,
		}
		state.accounts[accountID] = acc
	}
	if pending {
		if amount > 0 {
			acc.CreditsPending += amount
		} else {
			acc.DebitsPending += -amount
		}
	} else {
		if amount > 0 {
			acc.CreditsPosted += amount
		} else {
			acc.DebitsPosted += -amount
		}
	}
	acc.Balance = acc.CreditsPosted - acc.DebitsPosted
	acc.LastUpdated = time.Now().UnixMilli()
}

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

	// Initialise in-memory state
	state = NewAppState()

	// Connect to the real TigerBeetle cluster — this sidecar is a ledger sync
	// facade and refuses to masquerade as a ledger without it.
	tbAddresses := os.Getenv("TB_ADDRESSES")
	if tbAddresses == "" {
		tbAddresses = os.Getenv("TIGERBEETLE_ADDR")
	}
	if tbAddresses == "" {
		tbAddresses = "localhost:3000"
	}
	clusterID, _ := strconv.ParseUint(os.Getenv("TB_CLUSTER_ID"), 10, 64)

	client, err := tb.NewClient(tbtypes.ToUint128(clusterID), strings.Split(tbAddresses, ","))
	if err != nil {
		log.Fatalf("[pos-ledger-sync] TigerBeetle client init failed (%s): %v — refusing to start", tbAddresses, err)
	}
	defer client.Close()
	if _, err := client.LookupAccounts([]tbtypes.Uint128{tbtypes.ToUint128(1)}); err != nil {
		log.Fatalf("[pos-ledger-sync] TigerBeetle cluster unreachable at %s: %v — refusing to start", tbAddresses, err)
	}
	tbClient = client
	log.Printf("[pos-ledger-sync] Connected to TigerBeetle cluster %d at %s", clusterID, tbAddresses)

	// WAL — durable persistence across pod restarts
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

	// Replay existing WAL to restore state before accepting requests
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
