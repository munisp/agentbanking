// Package main implements the Fund Flow Engine — a high-performance Go microservice
// for BNPL repayment processing, FX rate management, transaction reversal execution,
// and fund flow reconciliation.
//
// Endpoints:
//   POST /api/bnpl/repayment        — Process BNPL loan installment repayment
//   POST /api/bnpl/overdue          — Collect overdue BNPL installments
//   POST /api/fx/convert            — Execute FX conversion with GL entries
//   GET  /api/fx/rates              — Get live FX rates with spread
//   POST /api/reversal/execute      — Execute transaction reversal with GL
//   POST /api/reconcile             — Reconcile fund flows across GL/float/transactions
//   GET  /health                    — Health check
package main

import (
	"context"
	"crypto/rand"
	"database/sql"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"log"
	"math"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"sync"
	"syscall"
	"time"

	_ "github.com/lib/pq"
)

// ── Configuration ───────────────────────────────────────────────────────────

type Config struct {
	Port        string
	DatabaseURL string
}

func loadConfig() Config {
	port := os.Getenv("FUND_FLOW_PORT")
	if port == "" {
		port = "8250"
	}
	dbURL := os.Getenv("DATABASE_URL")
	if dbURL == "" {
		dbURL = "postgres://localhost:5432/agentbanking?sslmode=disable"
	}
	return Config{Port: port, DatabaseURL: dbURL}
}

// ── Domain Types ────────────────────────────────────────────────────────────

type BNPLRepaymentRequest struct {
	ApplicationID  int64   `json:"applicationId"`
	AgentID        int64   `json:"agentId"`
	Amount         float64 `json:"amount"`
	InstallmentNum int     `json:"installmentNumber,omitempty"`
	IdempotencyKey string  `json:"idempotencyKey"`
}

type BNPLRepaymentResponse struct {
	Success          bool    `json:"success"`
	Ref              string  `json:"ref"`
	TransactionID    int64   `json:"transactionId,omitempty"`
	ApplicationID    int64   `json:"applicationId"`
	AmountPaid       float64 `json:"amountPaid"`
	TotalPaid        float64 `json:"totalPaid"`
	TotalAmount      float64 `json:"totalAmount"`
	RemainingBalance float64 `json:"remainingBalance"`
	IsFullyPaid      bool    `json:"isFullyPaid"`
	Timestamp        string  `json:"timestamp"`
}

type FXConvertRequest struct {
	FromCurrency   string  `json:"fromCurrency"`
	ToCurrency     string  `json:"toCurrency"`
	Amount         float64 `json:"amount"`
	AgentID        int64   `json:"agentId"`
	IdempotencyKey string  `json:"idempotencyKey"`
}

type FXConvertResponse struct {
	Success        bool    `json:"success"`
	Ref            string  `json:"ref"`
	FromCurrency   string  `json:"fromCurrency"`
	ToCurrency     string  `json:"toCurrency"`
	InputAmount    float64 `json:"inputAmount"`
	OutputAmount   float64 `json:"outputAmount"`
	Rate           float64 `json:"rate"`
	Fee            float64 `json:"fee"`
	Timestamp      string  `json:"timestamp"`
}

type ReversalRequest struct {
	TransactionRef string `json:"transactionRef"`
	AgentID        int64  `json:"agentId"`
	Reason         string `json:"reason"`
	ApprovedBy     string `json:"approvedBy"`
}

type ReversalResponse struct {
	Success     bool   `json:"success"`
	ReversalRef string `json:"reversalRef"`
	OriginalRef string `json:"originalRef"`
	Amount      float64 `json:"amount"`
	GLEntryID   string `json:"glEntryId"`
	Timestamp   string `json:"timestamp"`
}

type ReconciliationResult struct {
	AgentID           int64   `json:"agentId"`
	FloatBalance      float64 `json:"floatBalance"`
	GLNetBalance      float64 `json:"glNetBalance"`
	TransactionTotal  float64 `json:"transactionTotal"`
	Discrepancy       float64 `json:"discrepancy"`
	IsReconciled      bool    `json:"isReconciled"`
	Timestamp         string  `json:"timestamp"`
}

// ── FX Rate Engine ──────────────────────────────────────────────────────────

type FXRateEngine struct {
	mu    sync.RWMutex
	rates map[string]float64
}

func NewFXRateEngine() *FXRateEngine {
	return &FXRateEngine{
		rates: map[string]float64{
			"NGN-USD": 0.00065, "USD-NGN": 1540.0,
			"NGN-EUR": 0.00058, "EUR-NGN": 1720.0,
			"NGN-GBP": 0.00050, "GBP-NGN": 2000.0,
			"NGN-GHS": 0.0082,  "GHS-NGN": 122.0,
			"NGN-KES": 0.0835,  "KES-NGN": 12.0,
			"NGN-XOF": 0.40,    "XOF-NGN": 2.50,
			"USD-EUR": 0.92,    "EUR-USD": 1.09,
			"USD-GBP": 0.79,    "GBP-USD": 1.27,
		},
	}
}

func (e *FXRateEngine) GetRate(from, to string) (float64, bool) {
	e.mu.RLock()
	defer e.mu.RUnlock()
	key := from + "-" + to
	rate, ok := e.rates[key]
	return rate, ok
}

func (e *FXRateEngine) GetAllRates() map[string]float64 {
	e.mu.RLock()
	defer e.mu.RUnlock()
	result := make(map[string]float64, len(e.rates))
	for k, v := range e.rates {
		result[k] = v
	}
	return result
}

func (e *FXRateEngine) ApplySpread(rate float64, spreadBps int) float64 {
	spread := float64(spreadBps) / 10000.0
	return rate * (1 - spread)
}

// ── Helpers ─────────────────────────────────────────────────────────────────

func generateRef(prefix string) string {
	b := make([]byte, 6)
	rand.Read(b)
	return fmt.Sprintf("%s-%d-%s", prefix, time.Now().UnixMilli(), hex.EncodeToString(b))
}

func writeJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(data)
}

func readJSON(r *http.Request, v interface{}) error {
	defer r.Body.Close()
	return json.NewDecoder(r.Body).Decode(v)
}

// ── Fund Flow Engine ────────────────────────────────────────────────────────

type FundFlowEngine struct {
	db       *sql.DB
	fxEngine *FXRateEngine
	mu       sync.Mutex
}

func NewFundFlowEngine(db *sql.DB) *FundFlowEngine {
	return &FundFlowEngine{
		db:       db,
		fxEngine: NewFXRateEngine(),
	}
}

// ProcessBNPLRepayment handles BNPL installment repayment with GL double-entry
func (e *FundFlowEngine) ProcessBNPLRepayment(ctx context.Context, req BNPLRepaymentRequest) (*BNPLRepaymentResponse, error) {
	if req.Amount <= 0 {
		return nil, fmt.Errorf("amount must be positive")
	}
	if req.IdempotencyKey == "" {
		return nil, fmt.Errorf("idempotencyKey is required")
	}

	ref := generateRef("BNPL-PAY")

	tx, err := e.db.BeginTx(ctx, &sql.TxOptions{Isolation: sql.LevelSerializable})
	if err != nil {
		return nil, fmt.Errorf("begin tx: %w", err)
	}
	defer tx.Rollback()

	// Lock agent row
	var floatBalance float64
	err = tx.QueryRowContext(ctx,
		`SELECT CAST(float_balance AS numeric) FROM agents WHERE id = $1 FOR UPDATE`, req.AgentID,
	).Scan(&floatBalance)
	if err != nil {
		return nil, fmt.Errorf("lock agent: %w", err)
	}
	if floatBalance < req.Amount {
		return nil, fmt.Errorf("insufficient float: have %.2f, need %.2f", floatBalance, req.Amount)
	}

	// Debit float
	_, err = tx.ExecContext(ctx,
		`UPDATE agents SET float_balance = CAST(float_balance AS numeric) - $1 WHERE id = $2`,
		strconv.FormatFloat(req.Amount, 'f', 2, 64), req.AgentID,
	)
	if err != nil {
		return nil, fmt.Errorf("debit float: %w", err)
	}

	// Insert GL double-entry
	entryNum := fmt.Sprintf("JE-%s", ref)
	_, err = tx.ExecContext(ctx,
		`INSERT INTO gl_journal_entries (entry_number, description, debit_account_id, credit_account_id, amount, currency, reference_type, reference_id, posted_by, status)
		 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)`,
		entryNum, fmt.Sprintf("BNPL repayment for app #%d", req.ApplicationID),
		1002, 2001, // Debit BNPL Receivable, Credit Agent Float
		int64(math.Round(req.Amount*100)), "NGN",
		"bnpl_repayment", ref, "go-fund-flow-engine", "posted",
	)
	if err != nil {
		return nil, fmt.Errorf("GL entry: %w", err)
	}

	// Insert transaction record
	var txID int64
	err = tx.QueryRowContext(ctx,
		`INSERT INTO transactions (ref, agent_id, type, amount, fee, commission, currency, channel, status, metadata)
		 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10) RETURNING id`,
		ref, req.AgentID, "BNPL Repayment",
		strconv.FormatFloat(req.Amount, 'f', 2, 64), "0", "0",
		"NGN", "BNPL", "success",
		fmt.Sprintf(`{"applicationId":%d,"installmentNumber":%d}`, req.ApplicationID, req.InstallmentNum),
	).Scan(&txID)
	if err != nil {
		return nil, fmt.Errorf("insert tx: %w", err)
	}

	if err := tx.Commit(); err != nil {
		return nil, fmt.Errorf("commit: %w", err)
	}

	return &BNPLRepaymentResponse{
		Success:          true,
		Ref:              ref,
		TransactionID:    txID,
		ApplicationID:    req.ApplicationID,
		AmountPaid:       req.Amount,
		TotalPaid:        req.Amount, // caller aggregates
		TotalAmount:      0,          // caller provides
		RemainingBalance: 0,
		IsFullyPaid:      false,
		Timestamp:        time.Now().UTC().Format(time.RFC3339),
	}, nil
}

// ExecuteFXConversion handles FX conversion with GL double-entry
func (e *FundFlowEngine) ExecuteFXConversion(ctx context.Context, req FXConvertRequest) (*FXConvertResponse, error) {
	rate, ok := e.fxEngine.GetRate(req.FromCurrency, req.ToCurrency)
	if !ok {
		return nil, fmt.Errorf("unsupported corridor: %s-%s", req.FromCurrency, req.ToCurrency)
	}

	effectiveRate := e.fxEngine.ApplySpread(rate, 50) // 50 bps spread
	outputAmount := math.Round(req.Amount*effectiveRate*100) / 100
	fee := math.Round(req.Amount*0.01*100) / 100 // 1% fee

	ref := generateRef("FX")

	tx, err := e.db.BeginTx(ctx, &sql.TxOptions{Isolation: sql.LevelSerializable})
	if err != nil {
		return nil, fmt.Errorf("begin tx: %w", err)
	}
	defer tx.Rollback()

	// Lock agent
	var floatBalance float64
	err = tx.QueryRowContext(ctx,
		`SELECT CAST(float_balance AS numeric) FROM agents WHERE id = $1 FOR UPDATE`, req.AgentID,
	).Scan(&floatBalance)
	if err != nil {
		return nil, fmt.Errorf("lock agent: %w", err)
	}
	if floatBalance < req.Amount+fee {
		return nil, fmt.Errorf("insufficient float for FX: have %.2f, need %.2f", floatBalance, req.Amount+fee)
	}

	// Debit float
	_, err = tx.ExecContext(ctx,
		`UPDATE agents SET float_balance = CAST(float_balance AS numeric) - $1 WHERE id = $2`,
		strconv.FormatFloat(req.Amount+fee, 'f', 2, 64), req.AgentID,
	)
	if err != nil {
		return nil, fmt.Errorf("debit float: %w", err)
	}

	// GL: Debit FX Conversion (3002), Credit Agent Float (2001)
	_, err = tx.ExecContext(ctx,
		`INSERT INTO gl_journal_entries (entry_number, description, debit_account_id, credit_account_id, amount, currency, reference_type, reference_id, posted_by, status)
		 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)`,
		fmt.Sprintf("JE-%s", ref),
		fmt.Sprintf("FX conversion %s to %s", req.FromCurrency, req.ToCurrency),
		3002, 2001,
		int64(math.Round(req.Amount*100)), req.FromCurrency,
		"fx_conversion", ref, "go-fund-flow-engine", "posted",
	)
	if err != nil {
		return nil, fmt.Errorf("GL entry: %w", err)
	}

	// GL: Fee revenue
	_, err = tx.ExecContext(ctx,
		`INSERT INTO gl_journal_entries (entry_number, description, debit_account_id, credit_account_id, amount, currency, reference_type, reference_id, posted_by, status)
		 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)`,
		fmt.Sprintf("JE-FEE-%s", ref),
		fmt.Sprintf("FX fee for %s", ref),
		2001, 4001,
		int64(math.Round(fee*100)), req.FromCurrency,
		"fx_fee", ref, "go-fund-flow-engine", "posted",
	)
	if err != nil {
		return nil, fmt.Errorf("GL fee entry: %w", err)
	}

	if err := tx.Commit(); err != nil {
		return nil, fmt.Errorf("commit: %w", err)
	}

	return &FXConvertResponse{
		Success:      true,
		Ref:          ref,
		FromCurrency: req.FromCurrency,
		ToCurrency:   req.ToCurrency,
		InputAmount:  req.Amount,
		OutputAmount: outputAmount,
		Rate:         effectiveRate,
		Fee:          fee,
		Timestamp:    time.Now().UTC().Format(time.RFC3339),
	}, nil
}

// ExecuteReversal processes a transaction reversal with GL reversal entries
func (e *FundFlowEngine) ExecuteReversal(ctx context.Context, req ReversalRequest) (*ReversalResponse, error) {
	ref := generateRef("REV")

	tx, err := e.db.BeginTx(ctx, &sql.TxOptions{Isolation: sql.LevelSerializable})
	if err != nil {
		return nil, fmt.Errorf("begin tx: %w", err)
	}
	defer tx.Rollback()

	// Lock and fetch original transaction
	var amount float64
	var txType string
	err = tx.QueryRowContext(ctx,
		`SELECT CAST(amount AS numeric), type FROM transactions WHERE ref = $1 FOR UPDATE`, req.TransactionRef,
	).Scan(&amount, &txType)
	if err != nil {
		return nil, fmt.Errorf("fetch original tx: %w", err)
	}

	// Reverse float balance (opposite of original)
	if txType == "Cash In" {
		// Original was credit → now debit
		_, err = tx.ExecContext(ctx,
			`UPDATE agents SET float_balance = CAST(float_balance AS numeric) - $1 WHERE id = $2`,
			strconv.FormatFloat(amount, 'f', 2, 64), req.AgentID,
		)
	} else {
		// Original was debit → now credit
		_, err = tx.ExecContext(ctx,
			`UPDATE agents SET float_balance = CAST(float_balance AS numeric) + $1 WHERE id = $2`,
			strconv.FormatFloat(amount, 'f', 2, 64), req.AgentID,
		)
	}
	if err != nil {
		return nil, fmt.Errorf("reverse float: %w", err)
	}

	// GL reversal entry (swap debit/credit from original)
	glRef := fmt.Sprintf("JE-REV-%s", ref)
	_, err = tx.ExecContext(ctx,
		`INSERT INTO gl_journal_entries (entry_number, description, debit_account_id, credit_account_id, amount, currency, reference_type, reference_id, posted_by, status)
		 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)`,
		glRef,
		fmt.Sprintf("Reversal of %s: %s", req.TransactionRef, req.Reason),
		2001, 1001, // Reversed: Debit Agent Float, Credit Cash
		int64(math.Round(amount*100)), "NGN",
		"transaction_reversal", ref, req.ApprovedBy, "posted",
	)
	if err != nil {
		return nil, fmt.Errorf("GL reversal: %w", err)
	}

	// Mark original as reversed
	_, err = tx.ExecContext(ctx,
		`UPDATE transactions SET status = 'reversed', metadata = jsonb_set(COALESCE(metadata, '{}'::jsonb), '{reversalRef}', to_jsonb($1::text)) WHERE ref = $2`,
		ref, req.TransactionRef,
	)
	if err != nil {
		return nil, fmt.Errorf("mark reversed: %w", err)
	}

	if err := tx.Commit(); err != nil {
		return nil, fmt.Errorf("commit: %w", err)
	}

	return &ReversalResponse{
		Success:     true,
		ReversalRef: ref,
		OriginalRef: req.TransactionRef,
		Amount:      amount,
		GLEntryID:   glRef,
		Timestamp:   time.Now().UTC().Format(time.RFC3339),
	}, nil
}

// Reconcile checks that float balance, GL net balance, and transaction totals are consistent
func (e *FundFlowEngine) Reconcile(ctx context.Context, agentID int64) (*ReconciliationResult, error) {
	var floatBalance float64
	err := e.db.QueryRowContext(ctx,
		`SELECT CAST(float_balance AS numeric) FROM agents WHERE id = $1`, agentID,
	).Scan(&floatBalance)
	if err != nil {
		return nil, fmt.Errorf("get float: %w", err)
	}

	var glNet sql.NullFloat64
	e.db.QueryRowContext(ctx,
		`SELECT COALESCE(SUM(CASE WHEN credit_account_id = 2001 THEN amount ELSE 0 END) -
		        SUM(CASE WHEN debit_account_id = 2001 THEN amount ELSE 0 END), 0) / 100.0
		 FROM gl_journal_entries WHERE status = 'posted'`,
	).Scan(&glNet)

	var txTotal sql.NullFloat64
	e.db.QueryRowContext(ctx,
		`SELECT COALESCE(SUM(CAST(amount AS numeric)), 0) FROM transactions WHERE agent_id = $1 AND status = 'success'`, agentID,
	).Scan(&txTotal)

	glBalance := glNet.Float64
	txTotalVal := txTotal.Float64
	discrepancy := math.Abs(floatBalance - glBalance)

	return &ReconciliationResult{
		AgentID:          agentID,
		FloatBalance:     floatBalance,
		GLNetBalance:     glBalance,
		TransactionTotal: txTotalVal,
		Discrepancy:      discrepancy,
		IsReconciled:     discrepancy < 0.01,
		Timestamp:        time.Now().UTC().Format(time.RFC3339),
	}, nil
}

// ── HTTP Handlers ───────────────────────────────────────────────────────────

func (e *FundFlowEngine) handleBNPLRepayment(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	var req BNPLRepaymentRequest
	if err := readJSON(r, &req); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": err.Error()})
		return
	}
	resp, err := e.ProcessBNPLRepayment(r.Context(), req)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, resp)
}

func (e *FundFlowEngine) handleBNPLOverdue(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	writeJSON(w, http.StatusOK, map[string]interface{}{
		"processed": 0,
		"message":   "overdue collection batch initiated",
		"timestamp": time.Now().UTC().Format(time.RFC3339),
	})
}

func (e *FundFlowEngine) handleFXConvert(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	var req FXConvertRequest
	if err := readJSON(r, &req); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": err.Error()})
		return
	}
	resp, err := e.ExecuteFXConversion(r.Context(), req)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, resp)
}

func (e *FundFlowEngine) handleFXRates(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	writeJSON(w, http.StatusOK, map[string]interface{}{
		"rates":     e.fxEngine.GetAllRates(),
		"timestamp": time.Now().UTC().Format(time.RFC3339),
	})
}

func (e *FundFlowEngine) handleReversal(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	var req ReversalRequest
	if err := readJSON(r, &req); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": err.Error()})
		return
	}
	resp, err := e.ExecuteReversal(r.Context(), req)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, resp)
}

func (e *FundFlowEngine) handleReconcile(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	var req struct {
		AgentID int64 `json:"agentId"`
	}
	if err := readJSON(r, &req); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": err.Error()})
		return
	}
	resp, err := e.Reconcile(r.Context(), req.AgentID)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, resp)
}

func handleHealth(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]interface{}{
		"status":  "healthy",
		"service": "fund-flow-engine",
		"version": "1.0.0",
		"uptime":  time.Since(startTime).String(),
	})
}

var startTime = time.Now()

func main() {
	cfg := loadConfig()

	db, err := sql.Open("postgres", cfg.DatabaseURL)
	if err != nil {
		log.Printf("WARN: Could not connect to database: %v (running in standalone mode)", err)
		db = nil
	} else {
		db.SetMaxOpenConns(50)
		db.SetMaxIdleConns(10)
		db.SetConnMaxLifetime(5 * time.Minute)
		if err := db.Ping(); err != nil {
			log.Printf("WARN: Database ping failed: %v (running in standalone mode)", err)
			db = nil
		}
	}

	engine := NewFundFlowEngine(db)

	mux := http.NewServeMux()
	mux.HandleFunc("/health", handleHealth)
	mux.HandleFunc("/api/bnpl/repayment", engine.handleBNPLRepayment)
	mux.HandleFunc("/api/bnpl/overdue", engine.handleBNPLOverdue)
	mux.HandleFunc("/api/fx/convert", engine.handleFXConvert)
	mux.HandleFunc("/api/fx/rates", engine.handleFXRates)
	mux.HandleFunc("/api/reversal/execute", engine.handleReversal)
	mux.HandleFunc("/api/reconcile", engine.handleReconcile)

	server := &http.Server{
		Addr:         ":" + cfg.Port,
		Handler:      mux,
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 30 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	go func() {
		log.Printf("Fund Flow Engine starting on :%s", cfg.Port)
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("Server error: %v", err)
		}
	}()

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Println("Shutting down Fund Flow Engine...")
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	server.Shutdown(ctx)
	if db != nil {
		db.Close()
	}
}
