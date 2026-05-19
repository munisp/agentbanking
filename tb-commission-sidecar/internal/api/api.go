// Package api provides HTTP endpoints for the TigerBeetle commission sidecar.
// Handles commission credits, settlement transfers, and refund reversals.
package api

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"

	"github.com/54link/tb-commission-sidecar/internal/ledger"
)

type Server struct {
	ledger *ledger.Ledger
	mux    *http.ServeMux
}

func New(l *ledger.Ledger) *Server {
	s := &Server{ledger: l, mux: http.NewServeMux()}
	s.routes()
	return s
}

func (s *Server) routes() {
	s.mux.HandleFunc("/health", s.handleHealth)
	s.mux.HandleFunc("/commission/credit", s.handleCommissionCredit)
	s.mux.HandleFunc("/settlement/transfer", s.handleSettlementTransfer)
	s.mux.HandleFunc("/refund/reversal", s.handleRefundReversal)
	s.mux.HandleFunc("/balance/", s.handleGetBalance)
	s.mux.HandleFunc("/stats", s.handleStats)
	s.mux.HandleFunc("/unsynced", s.handleUnsynced)
}

func (s *Server) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	s.mux.ServeHTTP(w, r)
}

type transferRequest struct {
	DebitAccount  string                 `json:"debit_account"`
	CreditAccount string                 `json:"credit_account"`
	Amount        int64                  `json:"amount"`
	Ledger        int                    `json:"ledger"`
	Code          int                    `json:"code"`
	Reference     string                 `json:"reference"`
	Metadata      map[string]interface{} `json:"metadata,omitempty"`
}

func (s *Server) handleHealth(w http.ResponseWriter, r *http.Request) {
	stats, _ := s.ledger.Stats()
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"status":  "healthy",
		"service": "tb-commission-sidecar",
		"version": "1.0.0",
		"stats":   stats,
	})
}

func (s *Server) handleCommissionCredit(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", 405)
		return
	}
	var req transferRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, err.Error(), 400)
		return
	}
	meta, _ := json.Marshal(req.Metadata)
	t := &ledger.Transfer{
		DebitAccount:  req.DebitAccount,
		CreditAccount: req.CreditAccount,
		Amount:        req.Amount,
		Ledger:        req.Ledger,
		Code:          req.Code,
		Reference:     req.Reference,
		TransferType:  ledger.CommissionDirect,
		Metadata:      meta,
	}
	if req.Code == 302 {
		t.TransferType = ledger.CommissionHierarchySplit
	}
	id, err := s.ledger.CreateTransfer(t)
	if err != nil {
		log.Printf("[Commission] Transfer failed: %v", err)
		http.Error(w, err.Error(), 500)
		return
	}
	log.Printf("[Commission] Transfer %d: %s -> %s (%d kobo)", id, req.DebitAccount, req.CreditAccount, req.Amount)
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"transferId": fmt.Sprintf("TB-COMM-%d", id),
		"syncStatus": "pending_tb_sync",
	})
}

func (s *Server) handleSettlementTransfer(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", 405)
		return
	}
	var req transferRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, err.Error(), 400)
		return
	}
	meta, _ := json.Marshal(req.Metadata)
	id, err := s.ledger.CreateTransfer(&ledger.Transfer{
		DebitAccount:  req.DebitAccount,
		CreditAccount: req.CreditAccount,
		Amount:        req.Amount,
		Ledger:        req.Ledger,
		Code:          req.Code,
		Reference:     req.Reference,
		TransferType:  ledger.SettlementTransfer,
		Metadata:      meta,
	})
	if err != nil {
		http.Error(w, err.Error(), 500)
		return
	}
	log.Printf("[Settlement] Transfer %d: %s -> %s (%d kobo)", id, req.DebitAccount, req.CreditAccount, req.Amount)
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{"transferId": fmt.Sprintf("TB-SETTLE-%d", id)})
}

func (s *Server) handleRefundReversal(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", 405)
		return
	}
	var req transferRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, err.Error(), 400)
		return
	}
	meta, _ := json.Marshal(req.Metadata)
	id, err := s.ledger.CreateTransfer(&ledger.Transfer{
		DebitAccount:  req.DebitAccount,
		CreditAccount: req.CreditAccount,
		Amount:        req.Amount,
		Ledger:        req.Ledger,
		Code:          req.Code,
		Reference:     req.Reference,
		TransferType:  ledger.RefundReversal,
		Metadata:      meta,
	})
	if err != nil {
		http.Error(w, err.Error(), 500)
		return
	}
	log.Printf("[Refund] Reversal %d: %s -> %s (%d kobo)", id, req.DebitAccount, req.CreditAccount, req.Amount)
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{"transferId": fmt.Sprintf("TB-REFUND-%d", id)})
}

func (s *Server) handleGetBalance(w http.ResponseWriter, r *http.Request) {
	account := r.URL.Path[len("/balance/"):]
	if account == "" {
		http.Error(w, "account required", 400)
		return
	}
	balance, err := s.ledger.GetBalance(account)
	if err != nil {
		http.Error(w, err.Error(), 500)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{"account": account, "balance": balance})
}

func (s *Server) handleStats(w http.ResponseWriter, r *http.Request) {
	stats, err := s.ledger.Stats()
	if err != nil {
		http.Error(w, err.Error(), 500)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(stats)
}

func (s *Server) handleUnsynced(w http.ResponseWriter, r *http.Request) {
	transfers, err := s.ledger.GetUnsyncedTransfers(100)
	if err != nil {
		http.Error(w, err.Error(), 500)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{"transfers": transfers, "count": len(transfers)})
}
