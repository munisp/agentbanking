// dual-write-service v2.0
// Gap 1: Compensating transactions written to outbox (not direct UPDATE)
// Gap 2: Deterministic TigerBeetle transfer IDs via SHA-256(idempotency_key)
package main

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"syscall"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"github.com/redis/go-redis/v9"
	"go.uber.org/zap"
)

type Config struct {
	Port            string
	PostgresDSN     string
	RedisAddr       string
	RedisPassword   string
	TigerBeetleURL  string
	LockTTL         time.Duration
	BalanceCacheTTL time.Duration
	MaxRetries      int
	RequestTimeout  time.Duration
}

func loadConfig() Config {
	return Config{
		Port:            getEnv("PORT", "8091"),
		PostgresDSN:     getEnv("DATABASE_URL", "postgres://remitflow:remitflow@postgres:5432/remitflow?sslmode=require"),
		RedisAddr:       getEnv("REDIS_ADDR", "redis:6379"),
		RedisPassword:   getEnv("REDIS_PASSWORD", ""),
		TigerBeetleURL:  getEnv("TIGERBEETLE_HTTP_URL", "http://tigerbeetle-core:8090"),
		LockTTL:         30 * time.Second,
		BalanceCacheTTL: 30 * time.Second,
		MaxRetries:      3,
		RequestTimeout:  10 * time.Second,
	}
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

type AccountCreateRequest struct {
	UserID      string `json:"user_id" binding:"required"`
	Currency    string `json:"currency" binding:"required"`
	AccountType string `json:"account_type" binding:"required"`
	Ledger      uint32 `json:"ledger"`
}

type TransferRequest struct {
	IdempotencyKey  string                 `json:"idempotency_key" binding:"required"`
	DebitAccountID  string                 `json:"debit_account_id" binding:"required"`
	CreditAccountID string                 `json:"credit_account_id" binding:"required"`
	Amount          int64                  `json:"amount" binding:"required,min=1"`
	Currency        string                 `json:"currency" binding:"required"`
	TransferType    string                 `json:"transfer_type" binding:"required"`
	UserID          string                 `json:"user_id" binding:"required"`
	Description     string                 `json:"description"`
	Metadata        map[string]interface{} `json:"metadata"`
}

type DualWriteResult struct {
	PostgresID    string    `json:"postgres_id"`
	TigerBeetleID string    `json:"tigerbeetle_id"`
	Status        string    `json:"status"`
	DebitBalance  int64     `json:"debit_balance_after"`
	CreditBalance int64     `json:"credit_balance_after"`
	ProcessedAt   time.Time `json:"processed_at"`
	Idempotent    bool      `json:"idempotent,omitempty"`
}

type TigerBeetleTransfer struct {
	ID              string `json:"id"`
	DebitAccountID  string `json:"debit_account_id"`
	CreditAccountID string `json:"credit_account_id"`
	Amount          int64  `json:"amount"`
	Ledger          uint32 `json:"ledger"`
	Code            uint16 `json:"code"`
	Flags           uint16 `json:"flags"`
	UserData128     string `json:"user_data_128,omitempty"`
}

type TigerBeetleAccount struct {
	ID          string `json:"id"`
	Ledger      uint32 `json:"ledger"`
	Code        uint16 `json:"code"`
	Flags       uint16 `json:"flags"`
	UserData128 string `json:"user_data_128,omitempty"`
}

type OutboxEventType string

const (
	OutboxEventAccountCreated     OutboxEventType = "account.created"
	OutboxEventTransferCompleted  OutboxEventType = "transfer.completed"
	OutboxEventCompensateAccount  OutboxEventType = "compensate.account.failed"
	OutboxEventCompensateTransfer OutboxEventType = "compensate.transfer.failed"
	OutboxEventCommitFailed       OutboxEventType = "compensate.commit.failed"
)

var (
	dualWriteTotal = prometheus.NewCounterVec(prometheus.CounterOpts{
		Name: "remitflow_dual_write_total",
		Help: "Total dual-write operations by type and status",
	}, []string{"type", "status"})
	dualWriteDuration = prometheus.NewHistogramVec(prometheus.HistogramOpts{
		Name:    "remitflow_dual_write_duration_seconds",
		Buckets: prometheus.DefBuckets,
	}, []string{"type"})
	compensatingTransactions = prometheus.NewCounter(prometheus.CounterOpts{
		Name: "remitflow_compensating_transactions_total",
		Help: "Compensating transactions enqueued to outbox",
	})
	cacheHits = prometheus.NewCounterVec(prometheus.CounterOpts{
		Name: "remitflow_balance_cache_hits_total",
	}, []string{"result"})
	outboxEnqueued = prometheus.NewCounterVec(prometheus.CounterOpts{
		Name: "remitflow_outbox_enqueued_total",
	}, []string{"event_type"})
)

func init() {
	prometheus.MustRegister(dualWriteTotal, dualWriteDuration, compensatingTransactions, cacheHits, outboxEnqueued)
}

// Gap 2: deterministicTransferID — SHA-256(prefix || idempotency_key) → uint64 hex.
// Provides a second idempotency layer independent of Redis.
// prefix: 0x01=main, 0x02=fee, 0x03=reversal
func deterministicTransferID(idempotencyKey string, prefix byte) string {
	h := sha256.New()
	h.Write([]byte{prefix})
	h.Write([]byte(idempotencyKey))
	digest := h.Sum(nil)
	id := binary.BigEndian.Uint64(digest[:8])
	return fmt.Sprintf("%016x", id)
}

func deterministicAccountID(userID, currency string) string {
	h := sha256.New()
	h.Write([]byte("account:" + userID + ":" + currency))
	return hex.EncodeToString(h.Sum(nil)[:16])
}

func ledgerForCurrency(currency string) uint32 {
	m := map[string]uint32{
		"NGN": 1, "USD": 2, "GBP": 3, "EUR": 4,
		"GHS": 5, "KES": 6, "ZAR": 7, "XOF": 8,
		"XAF": 9, "UGX": 10, "TZS": 11, "ETB": 12,
		"CNY": 13, "INR": 14,
	}
	if id, ok := m[currency]; ok {
		return id
	}
	return 99
}

func transferCodeForType(t string) uint16 {
	m := map[string]uint16{
		"remittance": 1001, "fee": 1002, "fx": 1003,
		"reversal": 1004, "escrow": 1005, "settlement": 1006, "refund": 1007,
	}
	if c, ok := m[t]; ok {
		return c
	}
	return 1000
}

type DualWriteService struct {
	cfg    Config
	db     *pgxpool.Pool
	redis  *redis.Client
	logger *zap.Logger
}

func NewDualWriteService(cfg Config, db *pgxpool.Pool, rdb *redis.Client, logger *zap.Logger) *DualWriteService {
	return &DualWriteService{cfg: cfg, db: db, redis: rdb, logger: logger}
}

func (s *DualWriteService) EnsureSchema(ctx context.Context) error {
	_, err := s.db.Exec(ctx, `
		CREATE TABLE IF NOT EXISTS outbox (
			id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
			event_type    TEXT NOT NULL,
			payload       JSONB NOT NULL,
			status        TEXT NOT NULL DEFAULT 'pending',
			retry_count   INTEGER NOT NULL DEFAULT 0,
			created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
			processed_at  TIMESTAMPTZ,
			error_message TEXT
		);
		CREATE INDEX IF NOT EXISTS idx_outbox_status_created ON outbox (status, created_at)
			WHERE status IN ('pending','failed');
		CREATE TABLE IF NOT EXISTS outbox_dead_letter (
			id UUID PRIMARY KEY, event_type TEXT NOT NULL,
			payload JSONB NOT NULL, retry_count INTEGER NOT NULL,
			last_error TEXT, created_at TIMESTAMPTZ NOT NULL,
			moved_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
		);
		CREATE TABLE IF NOT EXISTS balance_snapshots (
			id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
			wallet_id UUID NOT NULL, balance BIGINT NOT NULL,
			currency TEXT NOT NULL, snapshot_source TEXT NOT NULL DEFAULT 'tigerbeetle',
			snapshotted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
		);
		CREATE INDEX IF NOT EXISTS idx_balance_snapshots_wallet
			ON balance_snapshots (wallet_id, snapshotted_at DESC);
		CREATE TABLE IF NOT EXISTS balance_reconciliation_log (
			id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
			wallet_id UUID NOT NULL, currency TEXT NOT NULL,
			postgres_balance BIGINT NOT NULL, tigerbeetle_balance BIGINT NOT NULL,
			discrepancy BIGINT NOT NULL, discrepancy_pct NUMERIC(10,4),
			severity TEXT NOT NULL, reconciled_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
		);
	`)
	return err
}

// Gap 1: enqueueOutboxEventTx writes an event WITHIN an existing PG transaction.
// The outbox write is co-located with the business state change — both commit or both roll back.
func (s *DualWriteService) enqueueOutboxEventTx(ctx context.Context, tx pgx.Tx, eventType OutboxEventType, payload map[string]interface{}) error {
	b, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("marshal outbox payload: %w", err)
	}
	_, err = tx.Exec(ctx, `INSERT INTO outbox (event_type, payload) VALUES ($1, $2)`, string(eventType), b)
	if err != nil {
		return fmt.Errorf("enqueue outbox %s: %w", eventType, err)
	}
	outboxEnqueued.WithLabelValues(string(eventType)).Inc()
	return nil
}

// enqueueOutboxEventDirect uses a standalone connection for commit-failed compensations.
func (s *DualWriteService) enqueueOutboxEventDirect(ctx context.Context, eventType OutboxEventType, payload map[string]interface{}) error {
	b, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("marshal outbox payload: %w", err)
	}
	_, err = s.db.Exec(ctx, `INSERT INTO outbox (event_type, payload) VALUES ($1, $2)`, string(eventType), b)
	if err != nil {
		return fmt.Errorf("enqueue outbox %s: %w", eventType, err)
	}
	outboxEnqueued.WithLabelValues(string(eventType)).Inc()
	return nil
}

func (s *DualWriteService) CreateAccount(ctx context.Context, req AccountCreateRequest) (*DualWriteResult, error) {
	timer := prometheus.NewTimer(dualWriteDuration.WithLabelValues("create_account"))
	defer timer.ObserveDuration()

	tbAccountID := deterministicAccountID(req.UserID, req.Currency) // Gap 2
	accountID := uuid.New().String()
	ledger := req.Ledger
	if ledger == 0 {
		ledger = ledgerForCurrency(req.Currency)
	}

	lockKey := fmt.Sprintf("lock:account:create:%s:%s", req.UserID, req.Currency)
	locked, err := s.redis.SetNX(ctx, lockKey, accountID, s.cfg.LockTTL).Result()
	if err != nil || !locked {
		dualWriteTotal.WithLabelValues("create_account", "lock_failed").Inc()
		return nil, fmt.Errorf("could not acquire lock for account creation")
	}
	defer s.redis.Del(ctx, lockKey)

	tx, err := s.db.Begin(ctx)
	if err != nil {
		return nil, fmt.Errorf("begin tx: %w", err)
	}
	defer tx.Rollback(ctx)

	_, err = tx.Exec(ctx, `
		INSERT INTO wallets (id, user_id, currency, account_type, tigerbeetle_account_id, status, created_at, updated_at)
		VALUES ($1,$2,$3,$4,$5,'pending',NOW(),NOW())
		ON CONFLICT (user_id, currency) DO NOTHING
	`, accountID, req.UserID, req.Currency, req.AccountType, tbAccountID)
	if err != nil {
		dualWriteTotal.WithLabelValues("create_account", "postgres_failed").Inc()
		return nil, fmt.Errorf("postgres account creation failed: %w", err)
	}

	tbAccount := TigerBeetleAccount{ID: tbAccountID, Ledger: ledger, Code: 1, Flags: 0, UserData128: req.UserID}
	if err := s.tigerbeetleCreateAccount(ctx, tbAccount); err != nil {
		// Gap 1: compensation event written WITHIN the same PG transaction
		comp := map[string]interface{}{
			"account_id": accountID, "tb_account_id": tbAccountID,
			"user_id": req.UserID, "currency": req.Currency,
			"reason": err.Error(), "ts": time.Now().UTC().Format(time.RFC3339),
		}
		if oErr := s.enqueueOutboxEventTx(ctx, tx, OutboxEventCompensateAccount, comp); oErr != nil {
			s.logger.Error("Failed to enqueue compensation", zap.String("account_id", accountID), zap.Error(oErr))
		}
		tx.Commit(ctx) // commit so compensation is durable
		compensatingTransactions.Inc()
		dualWriteTotal.WithLabelValues("create_account", "tigerbeetle_failed").Inc()
		return nil, fmt.Errorf("tigerbeetle account creation failed (compensation enqueued): %w", err)
	}

	success := map[string]interface{}{
		"event_type": string(OutboxEventAccountCreated), "account_id": accountID,
		"tigerbeetle_id": tbAccountID, "user_id": req.UserID,
		"currency": req.Currency, "ledger": ledger, "ts": time.Now().UTC().Format(time.RFC3339),
	}
	_ = s.enqueueOutboxEventTx(ctx, tx, OutboxEventAccountCreated, success)

	_, err = tx.Exec(ctx, `UPDATE wallets SET status='active', updated_at=NOW() WHERE id=$1`, accountID)
	if err != nil {
		comp := map[string]interface{}{
			"account_id": accountID, "tb_account_id": tbAccountID,
			"user_id": req.UserID, "reason": "pg_commit_failed:" + err.Error(),
			"ts": time.Now().UTC().Format(time.RFC3339),
		}
		bgCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		if oErr := s.enqueueOutboxEventDirect(bgCtx, OutboxEventCommitFailed, comp); oErr != nil {
			s.logger.Error("CRITICAL: commit+outbox both failed", zap.String("account_id", accountID), zap.Error(oErr))
		}
		dualWriteTotal.WithLabelValues("create_account", "commit_failed").Inc()
		return nil, fmt.Errorf("2PC commit failed (compensation enqueued): %w", err)
	}

	if err := tx.Commit(ctx); err != nil {
		return nil, fmt.Errorf("tx commit failed: %w", err)
	}

	ev, _ := json.Marshal(map[string]interface{}{
		"event_type": "account.created", "account_id": accountID,
		"tigerbeetle_id": tbAccountID, "user_id": req.UserID,
		"currency": req.Currency, "ts": time.Now().UTC().Format(time.RFC3339),
	})
	s.redis.Publish(ctx, "remitflow:account:events", ev)
	dualWriteTotal.WithLabelValues("create_account", "success").Inc()
	s.logger.Info("Account dual-write OK", zap.String("account_id", accountID), zap.String("tb_id", tbAccountID))

	return &DualWriteResult{PostgresID: accountID, TigerBeetleID: tbAccountID, Status: "active", ProcessedAt: time.Now().UTC()}, nil
}

func (s *DualWriteService) Transfer(ctx context.Context, req TransferRequest) (*DualWriteResult, error) {
	timer := prometheus.NewTimer(dualWriteDuration.WithLabelValues("transfer"))
	defer timer.ObserveDuration()

	iKey := fmt.Sprintf("idempotency:transfer:%s", req.IdempotencyKey)
	if existing, err := s.redis.Get(ctx, iKey).Result(); err == nil && existing != "" {
		var cached DualWriteResult
		if json.Unmarshal([]byte(existing), &cached) == nil {
			cached.Idempotent = true
			dualWriteTotal.WithLabelValues("transfer", "idempotent").Inc()
			return &cached, nil
		}
	}

	lockKey := fmt.Sprintf("lock:transfer:%s:%s", req.DebitAccountID, req.CreditAccountID)
	locked, err := s.redis.SetNX(ctx, lockKey, req.IdempotencyKey, s.cfg.LockTTL).Result()
	if err != nil || !locked {
		dualWriteTotal.WithLabelValues("transfer", "lock_failed").Inc()
		return nil, fmt.Errorf("transfer lock unavailable")
	}
	defer s.redis.Del(ctx, lockKey)

	var debitTBID, creditTBID string
	if err := s.db.QueryRow(ctx, `SELECT tigerbeetle_account_id FROM wallets WHERE id=$1 AND status='active'`, req.DebitAccountID).Scan(&debitTBID); err != nil {
		return nil, fmt.Errorf("debit account not found: %w", err)
	}
	if err := s.db.QueryRow(ctx, `SELECT tigerbeetle_account_id FROM wallets WHERE id=$1 AND status='active'`, req.CreditAccountID).Scan(&creditTBID); err != nil {
		return nil, fmt.Errorf("credit account not found: %w", err)
	}

	transferID := uuid.New().String()
	tbTransferID := deterministicTransferID(req.IdempotencyKey, 0x01) // Gap 2
	ledger := ledgerForCurrency(req.Currency)
	code := transferCodeForType(req.TransferType)

	tx, err := s.db.Begin(ctx)
	if err != nil {
		return nil, fmt.Errorf("begin tx: %w", err)
	}
	defer tx.Rollback(ctx)

	metaJSON, _ := json.Marshal(req.Metadata)
	_, err = tx.Exec(ctx, `
		INSERT INTO transactions (id,idempotency_key,debit_account_id,credit_account_id,
			amount,currency,transfer_type,user_id,description,metadata,tigerbeetle_transfer_id,status,created_at,updated_at)
		VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,'pending',NOW(),NOW())
		ON CONFLICT (idempotency_key) DO NOTHING
	`, transferID, req.IdempotencyKey, req.DebitAccountID, req.CreditAccountID,
		req.Amount, req.Currency, req.TransferType, req.UserID, req.Description, metaJSON, tbTransferID)
	if err != nil {
		dualWriteTotal.WithLabelValues("transfer", "postgres_failed").Inc()
		return nil, fmt.Errorf("postgres insert failed: %w", err)
	}

	tbTransfer := TigerBeetleTransfer{
		ID: tbTransferID, DebitAccountID: debitTBID, CreditAccountID: creditTBID,
		Amount: req.Amount, Ledger: ledger, Code: code, Flags: 0, UserData128: req.UserID,
	}
	if err := s.tigerbeetleCreateTransfer(ctx, tbTransfer); err != nil {
		// Gap 1: compensation event written WITHIN the same PG transaction
		comp := map[string]interface{}{
			"transfer_id": transferID, "tb_transfer_id": tbTransferID,
			"debit_account": req.DebitAccountID, "credit_account": req.CreditAccountID,
			"amount": req.Amount, "currency": req.Currency,
			"reason": err.Error(), "ts": time.Now().UTC().Format(time.RFC3339),
		}
		if oErr := s.enqueueOutboxEventTx(ctx, tx, OutboxEventCompensateTransfer, comp); oErr != nil {
			s.logger.Error("Failed to enqueue transfer compensation", zap.String("transfer_id", transferID), zap.Error(oErr))
		}
		tx.Commit(ctx)
		compensatingTransactions.Inc()
		dualWriteTotal.WithLabelValues("transfer", "tigerbeetle_failed").Inc()
		return nil, fmt.Errorf("tigerbeetle transfer failed (compensation enqueued): %w", err)
	}

	success := map[string]interface{}{
		"event_type": string(OutboxEventTransferCompleted), "transfer_id": transferID,
		"tb_transfer_id": tbTransferID, "debit_account": req.DebitAccountID,
		"credit_account": req.CreditAccountID, "amount": req.Amount,
		"currency": req.Currency, "user_id": req.UserID, "ts": time.Now().UTC().Format(time.RFC3339),
	}
	_ = s.enqueueOutboxEventTx(ctx, tx, OutboxEventTransferCompleted, success)

	_, err = tx.Exec(ctx, `UPDATE transactions SET status='completed', processed_at=NOW(), updated_at=NOW() WHERE id=$1`, transferID)
	if err != nil {
		comp := map[string]interface{}{
			"transfer_id": transferID, "tb_transfer_id": tbTransferID,
			"amount": req.Amount, "currency": req.Currency,
			"reason": "pg_commit_failed:" + err.Error(), "ts": time.Now().UTC().Format(time.RFC3339),
		}
		bgCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		if oErr := s.enqueueOutboxEventDirect(bgCtx, OutboxEventCommitFailed, comp); oErr != nil {
			s.logger.Error("CRITICAL: commit+outbox both failed", zap.String("transfer_id", transferID), zap.Error(oErr))
		}
		dualWriteTotal.WithLabelValues("transfer", "commit_failed").Inc()
		return nil, fmt.Errorf("2PC commit failed (compensation enqueued): %w", err)
	}

	if err := tx.Commit(ctx); err != nil {
		return nil, fmt.Errorf("tx commit failed: %w", err)
	}

	s.redis.Del(ctx, fmt.Sprintf("balance:%s", req.DebitAccountID), fmt.Sprintf("balance:%s", req.CreditAccountID))
	debitBal := s.getBalanceWithCache(ctx, req.DebitAccountID, debitTBID)
	creditBal := s.getBalanceWithCache(ctx, req.CreditAccountID, creditTBID)

	result := &DualWriteResult{
		PostgresID: transferID, TigerBeetleID: tbTransferID,
		Status: "completed", DebitBalance: debitBal, CreditBalance: creditBal,
		ProcessedAt: time.Now().UTC(),
	}
	resultJSON, _ := json.Marshal(result)
	s.redis.Set(ctx, iKey, resultJSON, 24*time.Hour)

	ev, _ := json.Marshal(map[string]interface{}{
		"event_type": "transfer.completed", "transfer_id": transferID,
		"tb_transfer_id": tbTransferID, "debit_account": req.DebitAccountID,
		"credit_account": req.CreditAccountID, "amount": req.Amount,
		"currency": req.Currency, "user_id": req.UserID,
		"debit_balance": debitBal, "credit_balance": creditBal,
		"ts": time.Now().UTC().Format(time.RFC3339),
	})
	s.redis.Publish(ctx, "remitflow:transfer:events", ev)
	dualWriteTotal.WithLabelValues("transfer", "success").Inc()
	s.logger.Info("Transfer dual-write OK", zap.String("transfer_id", transferID), zap.Int64("amount", req.Amount))
	return result, nil
}

func (s *DualWriteService) getBalanceWithCache(ctx context.Context, walletID, tbAccountID string) int64 {
	cacheKey := fmt.Sprintf("balance:%s", walletID)
	if cached, err := s.redis.Get(ctx, cacheKey).Result(); err == nil {
		if bal, err := strconv.ParseInt(cached, 10, 64); err == nil {
			cacheHits.WithLabelValues("hit").Inc()
			return bal
		}
	}
	cacheHits.WithLabelValues("miss").Inc()
	bal := s.fetchBalanceFromTigerBeetle(ctx, tbAccountID)
	s.redis.Set(ctx, cacheKey, strconv.FormatInt(bal, 10), s.cfg.BalanceCacheTTL)
	return bal
}

func (s *DualWriteService) fetchBalanceFromTigerBeetle(ctx context.Context, tbAccountID string) int64 {
	url := fmt.Sprintf("%s/api/v1/accounts/%s", s.cfg.TigerBeetleURL, tbAccountID)
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return 0
	}
	resp, err := (&http.Client{Timeout: s.cfg.RequestTimeout}).Do(req)
	if err != nil || resp.StatusCode != http.StatusOK {
		return 0
	}
	defer resp.Body.Close()
	var r struct {
		CreditsPosted int64 `json:"credits_posted"`
		DebitsPosted  int64 `json:"debits_posted"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&r); err != nil {
		return 0
	}
	return r.CreditsPosted - r.DebitsPosted
}

func (s *DualWriteService) tigerbeetleCreateAccount(ctx context.Context, account TigerBeetleAccount) error {
	body, _ := json.Marshal(account)
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, fmt.Sprintf("%s/api/v1/accounts", s.cfg.TigerBeetleURL), bytes.NewReader(body))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")
	resp, err := (&http.Client{Timeout: s.cfg.RequestTimeout}).Do(req)
	if err != nil {
		return fmt.Errorf("tigerbeetle HTTP: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusCreated {
		b, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("tigerbeetle account failed (%d): %s", resp.StatusCode, b)
	}
	return nil
}

func (s *DualWriteService) tigerbeetleCreateTransfer(ctx context.Context, transfer TigerBeetleTransfer) error {
	body, _ := json.Marshal(transfer)
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, fmt.Sprintf("%s/api/v1/transfers", s.cfg.TigerBeetleURL), bytes.NewReader(body))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")
	resp, err := (&http.Client{Timeout: s.cfg.RequestTimeout}).Do(req)
	if err != nil {
		return fmt.Errorf("tigerbeetle HTTP: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusCreated {
		b, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("tigerbeetle transfer failed (%d): %s", resp.StatusCode, b)
	}
	return nil
}

type Server struct {
	svc    *DualWriteService
	router *gin.Engine
	logger *zap.Logger
}

func NewServer(svc *DualWriteService, logger *zap.Logger) *Server {
	gin.SetMode(gin.ReleaseMode)
	r := gin.New()
	r.Use(gin.Recovery())
	s := &Server{svc: svc, router: r, logger: logger}
	r.GET("/health", s.handleHealth)
	r.GET("/metrics", gin.WrapH(promhttp.Handler()))
	v1 := r.Group("/api/v1")
	v1.POST("/accounts", s.handleCreateAccount)
	v1.POST("/transfers", s.handleTransfer)
	v1.GET("/balances/:wallet_id", s.handleGetBalance)
	v1.GET("/outbox/stats", s.handleOutboxStats)
	return s
}

func (s *Server) handleHealth(c *gin.Context) {
	c.JSON(200, gin.H{"service": "dual-write-service", "version": "2.0.0",
		"fixes": []string{"gap1:outbox-compensation", "gap2:deterministic-tb-ids"}})
}

func (s *Server) handleCreateAccount(c *gin.Context) {
	var req AccountCreateRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(400, gin.H{"error": err.Error()})
		return
	}
	ctx, cancel := context.WithTimeout(c.Request.Context(), s.svc.cfg.RequestTimeout)
	defer cancel()
	result, err := s.svc.CreateAccount(ctx, req)
	if err != nil {
		c.JSON(500, gin.H{"error": err.Error()})
		return
	}
	c.JSON(201, result)
}

func (s *Server) handleTransfer(c *gin.Context) {
	var req TransferRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(400, gin.H{"error": err.Error()})
		return
	}
	ctx, cancel := context.WithTimeout(c.Request.Context(), s.svc.cfg.RequestTimeout)
	defer cancel()
	result, err := s.svc.Transfer(ctx, req)
	if err != nil {
		c.JSON(500, gin.H{"error": err.Error()})
		return
	}
	c.JSON(200, result)
}

func (s *Server) handleGetBalance(c *gin.Context) {
	walletID := c.Param("wallet_id")
	ctx, cancel := context.WithTimeout(c.Request.Context(), 5*time.Second)
	defer cancel()
	var tbAccountID string
	if err := s.svc.db.QueryRow(ctx, `SELECT tigerbeetle_account_id FROM wallets WHERE id=$1 AND status='active'`, walletID).Scan(&tbAccountID); err != nil {
		c.JSON(404, gin.H{"error": "wallet not found"})
		return
	}
	c.JSON(200, gin.H{"wallet_id": walletID, "balance": s.svc.getBalanceWithCache(ctx, walletID, tbAccountID), "source": "tigerbeetle"})
}

func (s *Server) handleOutboxStats(c *gin.Context) {
	ctx, cancel := context.WithTimeout(c.Request.Context(), 5*time.Second)
	defer cancel()
	var pending, processing, completed, failed, dl int
	s.svc.db.QueryRow(ctx, `
		SELECT COUNT(*) FILTER (WHERE status='pending'), COUNT(*) FILTER (WHERE status='processing'),
		COUNT(*) FILTER (WHERE status='completed' AND processed_at > NOW()-INTERVAL '1 hour'),
		COUNT(*) FILTER (WHERE status='failed'), COUNT(*) FILTER (WHERE status='dead_letter')
		FROM outbox`).Scan(&pending, &processing, &completed, &failed, &dl)
	c.JSON(200, gin.H{"pending": pending, "processing": processing, "completed_last_hour": completed, "failed": failed, "dead_letter": dl})
}

func main() {
	logger, _ := zap.NewProduction()
	defer logger.Sync()
	cfg := loadConfig()

	dbCtx, dbCancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer dbCancel()
	db, err := pgxpool.New(dbCtx, cfg.PostgresDSN)
	if err != nil {
		log.Fatalf("PostgreSQL connect failed: %v", err)
	}
	defer db.Close()
	if err := db.Ping(dbCtx); err != nil {
		log.Fatalf("PostgreSQL ping failed: %v", err)
	}

	rdb := redis.NewClient(&redis.Options{
		Addr: cfg.RedisAddr, Password: cfg.RedisPassword, DB: 0,
		DialTimeout: 5 * time.Second, ReadTimeout: 3 * time.Second,
		WriteTimeout: 3 * time.Second, PoolSize: 50, MinIdleConns: 10,
	})
	redisCtx, redisCancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer redisCancel()
	if err := rdb.Ping(redisCtx).Err(); err != nil {
		log.Fatalf("Redis ping failed: %v", err)
	}
	defer rdb.Close()

	svc := NewDualWriteService(cfg, db, rdb, logger)
	schemaCtx, schemaCancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer schemaCancel()
	if err := svc.EnsureSchema(schemaCtx); err != nil {
		logger.Warn("EnsureSchema warning", zap.Error(err))
	}

	srv := NewServer(svc, logger)
	httpServer := &http.Server{
		Addr: ":" + cfg.Port, Handler: srv.router,
		ReadTimeout: 15 * time.Second, WriteTimeout: 15 * time.Second, IdleTimeout: 60 * time.Second,
	}

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		logger.Info("Dual-Write Service v2.0 starting", zap.String("port", cfg.Port))
		if err := httpServer.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("Server failed: %v", err)
		}
	}()
	<-quit
	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer shutdownCancel()
	httpServer.Shutdown(shutdownCtx)
	logger.Info("Dual-Write Service stopped")
}
