// Package ledger implements a SQLite-backed double-entry ledger
// for commission, settlement, and refund operations.
// Bridges Node.js application to TigerBeetle with offline-first durability.
package ledger

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"sync"
	"time"

	_ "github.com/mattn/go-sqlite3"
)

type TransferType int

const (
	CommissionDirect        TransferType = 1
	CommissionHierarchySplit TransferType = 2
	SettlementTransfer      TransferType = 3
	RefundReversal          TransferType = 4
	CommissionClawback      TransferType = 5
)

type Transfer struct {
	ID            int64           `json:"id"`
	DebitAccount  string          `json:"debit_account"`
	CreditAccount string          `json:"credit_account"`
	Amount        int64           `json:"amount"`
	Ledger        int             `json:"ledger"`
	Code          int             `json:"code"`
	Reference     string          `json:"reference"`
	TransferType  TransferType    `json:"transfer_type"`
	Metadata      json.RawMessage `json:"metadata,omitempty"`
	SyncedToTB    bool            `json:"synced_to_tb"`
	TBTransferID  string          `json:"tb_transfer_id,omitempty"`
	CreatedAt     time.Time       `json:"created_at"`
}

type Ledger struct {
	db *sql.DB
	mu sync.RWMutex
}

func New(dbPath string) (*Ledger, error) {
	db, err := sql.Open("sqlite3", dbPath+"?_journal_mode=WAL&_synchronous=NORMAL&_busy_timeout=5000")
	if err != nil {
		return nil, fmt.Errorf("open db: %w", err)
	}
	if err := migrate(db); err != nil {
		return nil, fmt.Errorf("migrate: %w", err)
	}
	return &Ledger{db: db}, nil
}

func migrate(db *sql.DB) error {
	_, err := db.Exec(`
		CREATE TABLE IF NOT EXISTS transfers (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			debit_account TEXT NOT NULL,
			credit_account TEXT NOT NULL,
			amount INTEGER NOT NULL CHECK(amount > 0),
			ledger INTEGER NOT NULL,
			code INTEGER NOT NULL,
			reference TEXT NOT NULL,
			transfer_type INTEGER NOT NULL,
			metadata TEXT,
			synced_to_tb BOOLEAN DEFAULT FALSE,
			tb_transfer_id TEXT,
			created_at DATETIME DEFAULT CURRENT_TIMESTAMP
		);
		CREATE INDEX IF NOT EXISTS idx_transfers_reference ON transfers(reference);
		CREATE INDEX IF NOT EXISTS idx_transfers_debit ON transfers(debit_account);
		CREATE INDEX IF NOT EXISTS idx_transfers_credit ON transfers(credit_account);
		CREATE INDEX IF NOT EXISTS idx_transfers_synced ON transfers(synced_to_tb);
		CREATE INDEX IF NOT EXISTS idx_transfers_type ON transfers(transfer_type);

		CREATE TABLE IF NOT EXISTS account_balances (
			account_id TEXT PRIMARY KEY,
			debit_total INTEGER DEFAULT 0,
			credit_total INTEGER DEFAULT 0,
			updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
		);
	`)
	return err
}

func (l *Ledger) CreateTransfer(t *Transfer) (int64, error) {
	l.mu.Lock()
	defer l.mu.Unlock()

	tx, err := l.db.Begin()
	if err != nil {
		return 0, err
	}
	defer tx.Rollback()

	res, err := tx.Exec(`
		INSERT INTO transfers (debit_account, credit_account, amount, ledger, code, reference, transfer_type, metadata)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
		t.DebitAccount, t.CreditAccount, t.Amount, t.Ledger, t.Code, t.Reference, t.TransferType, string(t.Metadata))
	if err != nil {
		return 0, err
	}

	id, _ := res.LastInsertId()

	_, err = tx.Exec(`
		INSERT INTO account_balances (account_id, debit_total, updated_at)
		VALUES (?, ?, CURRENT_TIMESTAMP)
		ON CONFLICT(account_id) DO UPDATE SET debit_total = debit_total + ?, updated_at = CURRENT_TIMESTAMP`,
		t.DebitAccount, t.Amount, t.Amount)
	if err != nil {
		return 0, err
	}

	_, err = tx.Exec(`
		INSERT INTO account_balances (account_id, credit_total, updated_at)
		VALUES (?, ?, CURRENT_TIMESTAMP)
		ON CONFLICT(account_id) DO UPDATE SET credit_total = credit_total + ?, updated_at = CURRENT_TIMESTAMP`,
		t.CreditAccount, t.Amount, t.Amount)
	if err != nil {
		return 0, err
	}

	return id, tx.Commit()
}

func (l *Ledger) GetBalance(accountID string) (int64, error) {
	l.mu.RLock()
	defer l.mu.RUnlock()

	var debit, credit int64
	err := l.db.QueryRow(`SELECT COALESCE(debit_total,0), COALESCE(credit_total,0) FROM account_balances WHERE account_id = ?`, accountID).Scan(&debit, &credit)
	if err == sql.ErrNoRows {
		return 0, nil
	}
	return credit - debit, err
}

func (l *Ledger) GetUnsyncedTransfers(limit int) ([]Transfer, error) {
	l.mu.RLock()
	defer l.mu.RUnlock()

	rows, err := l.db.Query(`SELECT id, debit_account, credit_account, amount, ledger, code, reference, transfer_type, COALESCE(metadata,'{}'), synced_to_tb, COALESCE(tb_transfer_id,''), created_at FROM transfers WHERE synced_to_tb = FALSE ORDER BY id ASC LIMIT ?`, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var transfers []Transfer
	for rows.Next() {
		var t Transfer
		var meta string
		if err := rows.Scan(&t.ID, &t.DebitAccount, &t.CreditAccount, &t.Amount, &t.Ledger, &t.Code, &t.Reference, &t.TransferType, &meta, &t.SyncedToTB, &t.TBTransferID, &t.CreatedAt); err != nil {
			return nil, err
		}
		t.Metadata = json.RawMessage(meta)
		transfers = append(transfers, t)
	}
	return transfers, nil
}

func (l *Ledger) MarkSynced(id int64, tbTransferID string) error {
	l.mu.Lock()
	defer l.mu.Unlock()
	_, err := l.db.Exec(`UPDATE transfers SET synced_to_tb = TRUE, tb_transfer_id = ? WHERE id = ?`, tbTransferID, id)
	return err
}

func (l *Ledger) Stats() (map[string]interface{}, error) {
	l.mu.RLock()
	defer l.mu.RUnlock()

	stats := map[string]interface{}{}
	var total, synced int64
	l.db.QueryRow(`SELECT COUNT(*) FROM transfers`).Scan(&total)
	l.db.QueryRow(`SELECT COUNT(*) FROM transfers WHERE synced_to_tb = TRUE`).Scan(&synced)
	stats["total_transfers"] = total
	stats["synced"] = synced
	stats["unsynced"] = total - synced

	var accounts int64
	l.db.QueryRow(`SELECT COUNT(*) FROM account_balances`).Scan(&accounts)
	stats["accounts"] = accounts

	return stats, nil
}

func (l *Ledger) Close() error {
	return l.db.Close()
}
