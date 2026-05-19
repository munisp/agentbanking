// Package ledger provides a SQLite-backed double-entry bookkeeping engine
// for the 54Link POS terminal. It operates fully offline and queues transfers
// for upstream sync to the TigerBeetle Zig cluster when connectivity resumes.
package ledger

import (
	"database/sql"
	"fmt"
	"time"

	_ "github.com/mattn/go-sqlite3"
)

// DB is the SQLite connection handle shared across the sidecar.
type DB struct {
	conn *sql.DB
}

// Account represents a double-entry ledger account.
type Account struct {
	ID             string    `json:"id"`
	AgentCode      string    `json:"agentCode"`
	Ledger         uint32    `json:"ledger"`
	Code           uint16    `json:"code"`
	DebitsPosted   int64     `json:"debitsPosted"`
	CreditsPosted  int64     `json:"creditsPosted"`
	DebitsPending  int64     `json:"debitsPending"`
	CreditsPending int64     `json:"creditsPending"`
	CreatedAt      time.Time `json:"createdAt"`
}

// Transfer represents a double-entry transfer between two accounts.
type Transfer struct {
	ID              string    `json:"id"`
	DebitAccountID  string    `json:"debitAccountId"`
	CreditAccountID string    `json:"creditAccountId"`
	Amount          int64     `json:"amount"`    // in kobo (smallest NGN unit)
	Ledger          uint32    `json:"ledger"`
	Code            uint16    `json:"code"`
	Ref             string    `json:"ref"`
	TxType          string    `json:"txType"`
	AgentCode       string    `json:"agentCode"`
	Pending         bool      `json:"pending"`
	CreatedAt       time.Time `json:"createdAt"`
	SyncedAt        *time.Time `json:"syncedAt,omitempty"`
	SyncStatus      string    `json:"syncStatus"` // "pending" | "synced" | "failed"
}

// Nigerian banking ledger codes (mirrors Zig implementation)
const (
	LedgerCustomerDeposits  uint32 = 1000
	LedgerAgentAccounts     uint32 = 2000
	LedgerBankReserves      uint32 = 3000
	LedgerFeeIncome         uint32 = 4000
	LedgerOperationalExpenses uint32 = 5000
	LedgerRegulatoryReserves uint32 = 6000
)

// Account codes
const (
	CodeSavingsAccount  uint16 = 100
	CodeCurrentAccount  uint16 = 200
	CodeAgentFloat      uint16 = 300
	CodeTransactionFee  uint16 = 400
	CodeCBNReserve      uint16 = 500
	CodeInterchangeFee  uint16 = 600
)

// Open opens (or creates) the SQLite database at the given path and applies schema.
func Open(path string) (*DB, error) {
	conn, err := sql.Open("sqlite3", path+"?_journal_mode=WAL&_synchronous=NORMAL&_foreign_keys=ON")
	if err != nil {
		return nil, fmt.Errorf("open sqlite: %w", err)
	}
	db := &DB{conn: conn}
	if err := db.migrate(); err != nil {
		return nil, fmt.Errorf("migrate: %w", err)
	}
	return db, nil
}

// Close closes the SQLite connection.
func (db *DB) Close() error {
	return db.conn.Close()
}

// migrate applies the schema DDL idempotently.
func (db *DB) migrate() error {
	_, err := db.conn.Exec(`
		CREATE TABLE IF NOT EXISTS accounts (
			id              TEXT PRIMARY KEY,
			agent_code      TEXT NOT NULL,
			ledger          INTEGER NOT NULL,
			code            INTEGER NOT NULL,
			debits_posted   INTEGER NOT NULL DEFAULT 0,
			credits_posted  INTEGER NOT NULL DEFAULT 0,
			debits_pending  INTEGER NOT NULL DEFAULT 0,
			credits_pending INTEGER NOT NULL DEFAULT 0,
			created_at      TEXT NOT NULL DEFAULT (datetime('now'))
		);

		CREATE TABLE IF NOT EXISTS transfers (
			id                TEXT PRIMARY KEY,
			debit_account_id  TEXT NOT NULL,
			credit_account_id TEXT NOT NULL,
			amount            INTEGER NOT NULL,
			ledger            INTEGER NOT NULL,
			code              INTEGER NOT NULL,
			ref               TEXT NOT NULL DEFAULT '',
			tx_type           TEXT NOT NULL DEFAULT '',
			agent_code        TEXT NOT NULL DEFAULT '',
			pending           INTEGER NOT NULL DEFAULT 0,
			created_at        TEXT NOT NULL DEFAULT (datetime('now')),
			synced_at         TEXT,
			sync_status       TEXT NOT NULL DEFAULT 'pending'
		);

		CREATE INDEX IF NOT EXISTS idx_transfers_sync_status ON transfers(sync_status);
		CREATE INDEX IF NOT EXISTS idx_transfers_agent_code  ON transfers(agent_code);
		CREATE INDEX IF NOT EXISTS idx_accounts_agent_code   ON accounts(agent_code);
	`)
	return err
}

// CreateAccount creates a new account if it does not already exist.
func (db *DB) CreateAccount(a Account) error {
	_, err := db.conn.Exec(`
		INSERT OR IGNORE INTO accounts (id, agent_code, ledger, code, created_at)
		VALUES (?, ?, ?, ?, ?)`,
		a.ID, a.AgentCode, a.Ledger, a.Code, time.Now().UTC().Format(time.RFC3339),
	)
	return err
}

// GetAccount retrieves an account by ID.
func (db *DB) GetAccount(id string) (*Account, error) {
	row := db.conn.QueryRow(`
		SELECT id, agent_code, ledger, code,
		       debits_posted, credits_posted, debits_pending, credits_pending, created_at
		FROM accounts WHERE id = ?`, id)
	var a Account
	var createdAt string
	err := row.Scan(&a.ID, &a.AgentCode, &a.Ledger, &a.Code,
		&a.DebitsPosted, &a.CreditsPosted, &a.DebitsPending, &a.CreditsPending, &createdAt)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	a.CreatedAt, _ = time.Parse(time.RFC3339, createdAt)
	return &a, nil
}

// GetBalance returns the net balance of an account (credits_posted - debits_posted) in kobo.
func (db *DB) GetBalance(accountID string) (int64, error) {
	var debits, credits int64
	err := db.conn.QueryRow(
		`SELECT debits_posted, credits_posted FROM accounts WHERE id = ?`, accountID,
	).Scan(&debits, &credits)
	if err == sql.ErrNoRows {
		return 0, fmt.Errorf("account not found: %s", accountID)
	}
	return credits - debits, err
}

// CreateTransfer processes a double-entry transfer atomically.
// It validates both accounts exist, checks balance constraints, and updates
// the account balances and the transfers table in a single SQLite transaction.
func (db *DB) CreateTransfer(t Transfer) error {
	tx, err := db.conn.Begin()
	if err != nil {
		return fmt.Errorf("begin tx: %w", err)
	}
	defer tx.Rollback() //nolint:errcheck

	// Lock and read debit account
	var debitDebits, debitCredits int64
	err = tx.QueryRow(
		`SELECT debits_posted, credits_posted FROM accounts WHERE id = ?`, t.DebitAccountID,
	).Scan(&debitDebits, &debitCredits)
	if err == sql.ErrNoRows {
		return fmt.Errorf("debit account not found: %s", t.DebitAccountID)
	}
	if err != nil {
		return err
	}

	// Lock and read credit account
	var creditDebits, creditCredits int64
	err = tx.QueryRow(
		`SELECT debits_posted, credits_posted FROM accounts WHERE id = ?`, t.CreditAccountID,
	).Scan(&creditDebits, &creditCredits)
	if err == sql.ErrNoRows {
		return fmt.Errorf("credit account not found: %s", t.CreditAccountID)
	}
	if err != nil {
		return err
	}

	// Balance check: debit account must have sufficient credits (float)
	debitBalance := debitCredits - debitDebits
	if debitBalance < t.Amount {
		return fmt.Errorf("insufficient balance: have %d kobo, need %d kobo", debitBalance, t.Amount)
	}

	now := time.Now().UTC().Format(time.RFC3339)

	// Update debit account
	_, err = tx.Exec(
		`UPDATE accounts SET debits_posted = debits_posted + ? WHERE id = ?`,
		t.Amount, t.DebitAccountID,
	)
	if err != nil {
		return fmt.Errorf("update debit account: %w", err)
	}

	// Update credit account
	_, err = tx.Exec(
		`UPDATE accounts SET credits_posted = credits_posted + ? WHERE id = ?`,
		t.Amount, t.CreditAccountID,
	)
	if err != nil {
		return fmt.Errorf("update credit account: %w", err)
	}

	// Insert transfer record
	_, err = tx.Exec(`
		INSERT INTO transfers (id, debit_account_id, credit_account_id, amount, ledger, code,
		                       ref, tx_type, agent_code, pending, created_at, sync_status)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')`,
		t.ID, t.DebitAccountID, t.CreditAccountID, t.Amount,
		t.Ledger, t.Code, t.Ref, t.TxType, t.AgentCode,
		boolToInt(t.Pending), now,
	)
	if err != nil {
		return fmt.Errorf("insert transfer: %w", err)
	}

	return tx.Commit()
}

// GetPendingSyncTransfers returns all transfers not yet synced to the Zig cluster.
func (db *DB) GetPendingSyncTransfers(limit int) ([]Transfer, error) {
	rows, err := db.conn.Query(`
		SELECT id, debit_account_id, credit_account_id, amount, ledger, code,
		       ref, tx_type, agent_code, pending, created_at, synced_at, sync_status
		FROM transfers WHERE sync_status = 'pending'
		ORDER BY created_at ASC LIMIT ?`, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	return scanTransfers(rows)
}

// MarkSynced marks a transfer as successfully synced to the Zig cluster.
func (db *DB) MarkSynced(id string) error {
	now := time.Now().UTC().Format(time.RFC3339)
	_, err := db.conn.Exec(
		`UPDATE transfers SET sync_status = 'synced', synced_at = ? WHERE id = ?`, now, id,
	)
	return err
}

// MarkSyncFailed marks a transfer as failed to sync (will be retried).
func (db *DB) MarkSyncFailed(id string) error {
	_, err := db.conn.Exec(
		`UPDATE transfers SET sync_status = 'failed' WHERE id = ?`, id,
	)
	return err
}

// ResetFailedForRetry resets failed transfers back to pending for retry.
func (db *DB) ResetFailedForRetry() error {
	_, err := db.conn.Exec(
		`UPDATE transfers SET sync_status = 'pending' WHERE sync_status = 'failed'`,
	)
	return err
}

// GetTransfer retrieves a single transfer by ID.
func (db *DB) GetTransfer(id string) (*Transfer, error) {
	rows, err := db.conn.Query(
		`SELECT id, debit_account_id, credit_account_id, amount, ledger, code,
		        ref, tx_type, agent_code, pending, created_at, synced_at, sync_status
		 FROM transfers WHERE id = ?`, id)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	transfers, err := scanTransfers(rows)
	if err != nil || len(transfers) == 0 {
		return nil, err
	}
	return &transfers[0], nil
}

// SyncStats returns counts of pending/synced/failed transfers.
func (db *DB) SyncStats() (pending, synced, failed int64, err error) {
	row := db.conn.QueryRow(`
		SELECT
			SUM(CASE WHEN sync_status='pending' THEN 1 ELSE 0 END),
			SUM(CASE WHEN sync_status='synced'  THEN 1 ELSE 0 END),
			SUM(CASE WHEN sync_status='failed'  THEN 1 ELSE 0 END)
		FROM transfers`)
	err = row.Scan(&pending, &synced, &failed)
	return
}

// ─── helpers ────────────────────────────────────────────────────────────────

func boolToInt(b bool) int {
	if b {
		return 1
	}
	return 0
}

func scanTransfers(rows *sql.Rows) ([]Transfer, error) {
	var out []Transfer
	for rows.Next() {
		var t Transfer
		var createdAt string
		var syncedAt sql.NullString
		var pending int
		err := rows.Scan(
			&t.ID, &t.DebitAccountID, &t.CreditAccountID, &t.Amount,
			&t.Ledger, &t.Code, &t.Ref, &t.TxType, &t.AgentCode,
			&pending, &createdAt, &syncedAt, &t.SyncStatus,
		)
		if err != nil {
			return nil, err
		}
		t.Pending = pending == 1
		t.CreatedAt, _ = time.Parse(time.RFC3339, createdAt)
		if syncedAt.Valid {
			ts, _ := time.Parse(time.RFC3339, syncedAt.String)
			t.SyncedAt = &ts
		}
		out = append(out, t)
	}
	return out, rows.Err()
}
