// Package api exposes the TigerBeetle sidecar as an HTTP service.
// The POS Node.js server calls this API to submit double-entry transfers
// before writing to PostgreSQL.
package api

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"time"

	"github.com/54link/tb-sidecar/internal/ledger"
	"github.com/54link/tb-sidecar/internal/sync"
	"github.com/google/uuid"
)

// Server is the HTTP API server.
type Server struct {
	db     *ledger.DB
	engine *sync.Engine
	mux    *http.ServeMux
}

// New creates a new API server.
func New(db *ledger.DB, engine *sync.Engine) *Server {
	s := &Server{db: db, engine: engine, mux: http.NewServeMux()}
	s.routes()
	return s
}

// ServeHTTP implements http.Handler.
func (s *Server) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	s.mux.ServeHTTP(w, r)
}

func (s *Server) routes() {
	s.mux.HandleFunc("/health",                  s.handleHealth)
	s.mux.HandleFunc("/sync/status",             s.handleSyncStatus)
	s.mux.HandleFunc("/accounts",                s.handleCreateAccount)
	s.mux.HandleFunc("/accounts/",               s.handleGetAccount)
	s.mux.HandleFunc("/transfers",               s.handleCreateTransfer)
	s.mux.HandleFunc("/transfers/",              s.handleGetTransfer)
	s.mux.HandleFunc("/agent/",                  s.handleAgentBalance)
}

// ─── handlers ───────────────────────────────────────────────────────────────

func (s *Server) handleHealth(w http.ResponseWriter, r *http.Request) {
	jsonOK(w, map[string]string{
		"status":  "ok",
		"service": "tb-sidecar",
		"time":    time.Now().UTC().Format(time.RFC3339),
	})
}

func (s *Server) handleSyncStatus(w http.ResponseWriter, r *http.Request) {
	jsonOK(w, s.engine.SyncStatus())
}

// POST /accounts
func (s *Server) handleCreateAccount(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	var req struct {
		ID        string `json:"id"`
		AgentCode string `json:"agentCode"`
		Ledger    uint32 `json:"ledger"`
		Code      uint16 `json:"code"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		jsonErr(w, "invalid request body", http.StatusBadRequest)
		return
	}
	if req.ID == "" {
		req.ID = uuid.New().String()
	}
	acc := ledger.Account{
		ID:        req.ID,
		AgentCode: req.AgentCode,
		Ledger:    req.Ledger,
		Code:      req.Code,
	}
	if err := s.db.CreateAccount(acc); err != nil {
		jsonErr(w, err.Error(), http.StatusInternalServerError)
		return
	}
	jsonOK(w, map[string]string{"id": req.ID, "status": "created"})
}

// GET /accounts/{id}
func (s *Server) handleGetAccount(w http.ResponseWriter, r *http.Request) {
	id := r.URL.Path[len("/accounts/"):]
	if id == "" {
		jsonErr(w, "account id required", http.StatusBadRequest)
		return
	}
	acc, err := s.db.GetAccount(id)
	if err != nil {
		jsonErr(w, err.Error(), http.StatusInternalServerError)
		return
	}
	if acc == nil {
		jsonErr(w, "account not found", http.StatusNotFound)
		return
	}
	jsonOK(w, acc)
}

// POST /transfers
func (s *Server) handleCreateTransfer(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	var req struct {
		ID              string `json:"id"`
		DebitAccountID  string `json:"debitAccountId"`
		CreditAccountID string `json:"creditAccountId"`
		Amount          int64  `json:"amount"` // kobo
		Ledger          uint32 `json:"ledger"`
		Code            uint16 `json:"code"`
		Ref             string `json:"ref"`
		TxType          string `json:"txType"`
		AgentCode       string `json:"agentCode"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		jsonErr(w, "invalid request body", http.StatusBadRequest)
		return
	}
	if req.DebitAccountID == "" || req.CreditAccountID == "" {
		jsonErr(w, "debitAccountId and creditAccountId are required", http.StatusBadRequest)
		return
	}
	if req.Amount <= 0 {
		jsonErr(w, "amount must be positive (in kobo)", http.StatusBadRequest)
		return
	}
	if req.ID == "" {
		req.ID = uuid.New().String()
	}
	if req.Ledger == 0 {
		req.Ledger = ledger.LedgerAgentAccounts
	}
	if req.Code == 0 {
		req.Code = ledger.CodeAgentFloat
	}

	t := ledger.Transfer{
		ID:              req.ID,
		DebitAccountID:  req.DebitAccountID,
		CreditAccountID: req.CreditAccountID,
		Amount:          req.Amount,
		Ledger:          req.Ledger,
		Code:            req.Code,
		Ref:             req.Ref,
		TxType:          req.TxType,
		AgentCode:       req.AgentCode,
	}

	if err := s.db.CreateTransfer(t); err != nil {
		log.Printf("[api] CreateTransfer error: %v", err)
		jsonErr(w, err.Error(), http.StatusUnprocessableEntity)
		return
	}

	jsonOK(w, map[string]interface{}{
		"id":         req.ID,
		"status":     "committed",
		"syncStatus": "pending",
		"amount":     req.Amount,
	})
}

// GET /transfers/{id}
func (s *Server) handleGetTransfer(w http.ResponseWriter, r *http.Request) {
	id := r.URL.Path[len("/transfers/"):]
	if id == "" {
		jsonErr(w, "transfer id required", http.StatusBadRequest)
		return
	}
	t, err := s.db.GetTransfer(id)
	if err != nil {
		jsonErr(w, err.Error(), http.StatusInternalServerError)
		return
	}
	if t == nil {
		jsonErr(w, "transfer not found", http.StatusNotFound)
		return
	}
	jsonOK(w, t)
}

// GET /agent/{agentCode}/balance
func (s *Server) handleAgentBalance(w http.ResponseWriter, r *http.Request) {
	// Path: /agent/{agentCode}/balance
	path := r.URL.Path[len("/agent/"):]
	parts := splitPath(path)
	if len(parts) < 2 || parts[1] != "balance" {
		jsonErr(w, "use /agent/{agentCode}/balance", http.StatusBadRequest)
		return
	}
	agentCode := parts[0]
	// Agent float account ID is derived as "float-{agentCode}"
	accountID := fmt.Sprintf("float-%s", agentCode)
	balance, err := s.db.GetBalance(accountID)
	if err != nil {
		jsonErr(w, err.Error(), http.StatusNotFound)
		return
	}
	jsonOK(w, map[string]interface{}{
		"agentCode":  agentCode,
		"balanceKobo": balance,
		"balanceNGN": float64(balance) / 100.0,
	})
}

// ─── helpers ────────────────────────────────────────────────────────────────

func jsonOK(w http.ResponseWriter, v interface{}) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(v) //nolint:errcheck
}

func jsonErr(w http.ResponseWriter, msg string, code int) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	json.NewEncoder(w).Encode(map[string]string{"error": msg}) //nolint:errcheck
}

func splitPath(path string) []string {
	var parts []string
	for _, p := range []string{} {
		_ = p
	}
	start := 0
	for i := 0; i < len(path); i++ {
		if path[i] == '/' {
			if i > start {
				parts = append(parts, path[start:i])
			}
			start = i + 1
		}
	}
	if start < len(path) {
		parts = append(parts, path[start:])
	}
	return parts
}
