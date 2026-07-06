// persistence.go — SQLite persistence layer for go-ledger-sync.
//
// Ensures all ledger entries, account balances, settlement batches,
// reconciliation results, and transaction lifecycles survive restarts.
// Uses WAL mode for concurrent read/write performance.

package main

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"os"

	_ "github.com/mattn/go-sqlite3"
)

// PersistenceDB wraps the SQLite connection for ledger persistence.
type PersistenceDB struct {
	conn *sql.DB
}

// OpenPersistence opens (or creates) the SQLite database and initializes tables.
func OpenPersistence(path string) (*PersistenceDB, error) {
	conn, err := sql.Open("sqlite3", path+"?_journal_mode=WAL&_busy_timeout=5000&_synchronous=NORMAL")
	if err != nil {
		return nil, fmt.Errorf("open sqlite: %w", err)
	}

	db := &PersistenceDB{conn: conn}
	if err := db.migrate(); err != nil {
		conn.Close()
		return nil, fmt.Errorf("migrate: %w", err)
	}

	log.Printf("[persist] SQLite opened at %s (WAL mode)", path)
	return db, nil
}

func (db *PersistenceDB) migrate() error {
	queries := []string{
		`CREATE TABLE IF NOT EXISTS ledger_entries (
			id TEXT PRIMARY KEY,
			debit_account_id TEXT NOT NULL,
			credit_account_id TEXT NOT NULL,
			amount INTEGER NOT NULL,
			currency TEXT NOT NULL DEFAULT 'NGN',
			ledger_code INTEGER NOT NULL DEFAULT 0,
			transfer_code INTEGER NOT NULL DEFAULT 0,
			pending INTEGER NOT NULL DEFAULT 0,
			timestamp INTEGER NOT NULL,
			metadata TEXT DEFAULT '{}'
		)`,
		`CREATE TABLE IF NOT EXISTS account_balances (
			account_id TEXT PRIMARY KEY,
			debits_posted INTEGER NOT NULL DEFAULT 0,
			credits_posted INTEGER NOT NULL DEFAULT 0,
			debits_pending INTEGER NOT NULL DEFAULT 0,
			credits_pending INTEGER NOT NULL DEFAULT 0,
			balance INTEGER NOT NULL DEFAULT 0,
			currency TEXT NOT NULL DEFAULT 'NGN',
			last_updated INTEGER NOT NULL
		)`,
		`CREATE TABLE IF NOT EXISTS settlement_batches (
			id TEXT PRIMARY KEY,
			status TEXT NOT NULL DEFAULT 'pending',
			total_amount INTEGER NOT NULL DEFAULT 0,
			transfer_count INTEGER NOT NULL DEFAULT 0,
			transfers_json TEXT DEFAULT '[]',
			created_at INTEGER NOT NULL,
			settled_at INTEGER DEFAULT 0
		)`,
		`CREATE TABLE IF NOT EXISTS reconciliation_results (
			id TEXT PRIMARY KEY,
			status TEXT NOT NULL,
			matched_count INTEGER NOT NULL DEFAULT 0,
			unmatched_count INTEGER NOT NULL DEFAULT 0,
			discrepancy_amount INTEGER NOT NULL DEFAULT 0,
			timestamp INTEGER NOT NULL
		)`,
		`CREATE TABLE IF NOT EXISTS transaction_lifecycles (
			transaction_id TEXT PRIMARY KEY,
			current_state TEXT NOT NULL,
			previous_state TEXT NOT NULL DEFAULT '',
			transitions_json TEXT DEFAULT '[]'
		)`,
		`CREATE INDEX IF NOT EXISTS idx_entries_debit ON ledger_entries(debit_account_id)`,
		`CREATE INDEX IF NOT EXISTS idx_entries_credit ON ledger_entries(credit_account_id)`,
		`CREATE INDEX IF NOT EXISTS idx_entries_ts ON ledger_entries(timestamp)`,
		`CREATE INDEX IF NOT EXISTS idx_settlements_status ON settlement_batches(status)`,
	}
	for _, q := range queries {
		if _, err := db.conn.Exec(q); err != nil {
			return fmt.Errorf("exec %q: %w", q[:40], err)
		}
	}
	return nil
}

// Close closes the database connection.
func (db *PersistenceDB) Close() error {
	return db.conn.Close()
}

// ── Ledger Entry Persistence ─────────────────────────────────────────────────

// SaveEntry persists a ledger entry atomically.
func (db *PersistenceDB) SaveEntry(entry LedgerEntry) error {
	metaJSON, _ := json.Marshal(entry.Metadata)
	pending := 0
	if entry.Pending {
		pending = 1
	}
	_, err := db.conn.Exec(
		`INSERT OR REPLACE INTO ledger_entries (id, debit_account_id, credit_account_id, amount, currency, ledger_code, transfer_code, pending, timestamp, metadata)
		 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		entry.ID, entry.DebitAccountID, entry.CreditAccountID, entry.Amount,
		entry.Currency, entry.LedgerCode, entry.TransferCode, pending, entry.Timestamp, string(metaJSON),
	)
	return err
}

// LoadEntries loads all ledger entries from the database.
func (db *PersistenceDB) LoadEntries() ([]LedgerEntry, error) {
	rows, err := db.conn.Query(`SELECT id, debit_account_id, credit_account_id, amount, currency, ledger_code, transfer_code, pending, timestamp, metadata FROM ledger_entries ORDER BY timestamp`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var entries []LedgerEntry
	for rows.Next() {
		var e LedgerEntry
		var metaStr string
		var pendingInt int
		if err := rows.Scan(&e.ID, &e.DebitAccountID, &e.CreditAccountID, &e.Amount, &e.Currency, &e.LedgerCode, &e.TransferCode, &pendingInt, &e.Timestamp, &metaStr); err != nil {
			return nil, err
		}
		e.Pending = pendingInt != 0
		json.Unmarshal([]byte(metaStr), &e.Metadata)
		entries = append(entries, e)
	}
	return entries, nil
}

// ── Account Balance Persistence ──────────────────────────────────────────────

// SaveBalance persists an account balance.
func (db *PersistenceDB) SaveBalance(bal AccountBalance) error {
	_, err := db.conn.Exec(
		`INSERT OR REPLACE INTO account_balances (account_id, debits_posted, credits_posted, debits_pending, credits_pending, balance, currency, last_updated)
		 VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
		bal.AccountID, bal.DebitsPosted, bal.CreditsPosted, bal.DebitsPending, bal.CreditsPending, bal.Balance, bal.Currency, bal.LastUpdated,
	)
	return err
}

// LoadBalances loads all account balances from the database.
func (db *PersistenceDB) LoadBalances() (map[string]*AccountBalance, error) {
	rows, err := db.conn.Query(`SELECT account_id, debits_posted, credits_posted, debits_pending, credits_pending, balance, currency, last_updated FROM account_balances`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	balances := make(map[string]*AccountBalance)
	for rows.Next() {
		var b AccountBalance
		if err := rows.Scan(&b.AccountID, &b.DebitsPosted, &b.CreditsPosted, &b.DebitsPending, &b.CreditsPending, &b.Balance, &b.Currency, &b.LastUpdated); err != nil {
			return nil, err
		}
		balances[b.AccountID] = &b
	}
	return balances, nil
}

// ── Settlement Batch Persistence ─────────────────────────────────────────────

// SaveSettlement persists a settlement batch.
func (db *PersistenceDB) SaveSettlement(batch SettlementBatch) error {
	txJSON, _ := json.Marshal(batch.Transfers)
	_, err := db.conn.Exec(
		`INSERT OR REPLACE INTO settlement_batches (id, status, total_amount, transfer_count, transfers_json, created_at, settled_at)
		 VALUES (?, ?, ?, ?, ?, ?, ?)`,
		batch.ID, batch.Status, batch.TotalAmount, batch.TransferCount, string(txJSON), batch.CreatedAt, batch.SettledAt,
	)
	return err
}

// LoadSettlements loads all settlement batches from the database.
func (db *PersistenceDB) LoadSettlements() ([]SettlementBatch, error) {
	rows, err := db.conn.Query(`SELECT id, status, total_amount, transfer_count, transfers_json, created_at, settled_at FROM settlement_batches ORDER BY created_at`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var batches []SettlementBatch
	for rows.Next() {
		var b SettlementBatch
		var txJSON string
		if err := rows.Scan(&b.ID, &b.Status, &b.TotalAmount, &b.TransferCount, &txJSON, &b.CreatedAt, &b.SettledAt); err != nil {
			return nil, err
		}
		json.Unmarshal([]byte(txJSON), &b.Transfers)
		batches = append(batches, b)
	}
	return batches, nil
}

// ── Lifecycle Persistence ────────────────────────────────────────────────────

// SaveLifecycle persists a transaction lifecycle.
func (db *PersistenceDB) SaveLifecycle(lc TransactionLifecycle) error {
	transJSON, _ := json.Marshal(lc.Transitions)
	_, err := db.conn.Exec(
		`INSERT OR REPLACE INTO transaction_lifecycles (transaction_id, current_state, previous_state, transitions_json)
		 VALUES (?, ?, ?, ?)`,
		lc.TransactionID, lc.CurrentState, lc.PreviousState, string(transJSON),
	)
	return err
}

// ── State Hydration ──────────────────────────────────────────────────────────

// HydrateState loads all persisted data into the in-memory AppState.
func HydrateState(db *PersistenceDB, state *AppState) error {
	entries, err := db.LoadEntries()
	if err != nil {
		return fmt.Errorf("load entries: %w", err)
	}
	state.ledger = entries
	state.transferCount.Store(int64(len(entries)))
	log.Printf("[persist] Hydrated %d ledger entries", len(entries))

	balances, err := db.LoadBalances()
	if err != nil {
		return fmt.Errorf("load balances: %w", err)
	}
	state.accounts = balances
	log.Printf("[persist] Hydrated %d account balances", len(balances))

	settlements, err := db.LoadSettlements()
	if err != nil {
		return fmt.Errorf("load settlements: %w", err)
	}
	state.settlements = settlements
	log.Printf("[persist] Hydrated %d settlement batches", len(settlements))

	// Calculate total volume from entries
	var totalVol int64
	for _, e := range entries {
		totalVol += e.Amount
	}
	state.totalVolume.Store(totalVol)

	return nil
}

// GetDBPath returns the persistence database path from env or default.
func GetDBPath() string {
	path := os.Getenv("GO_LEDGER_DB_PATH")
	if path == "" {
		path = "/tmp/go-ledger-sync.db"
	}
	return path
}
