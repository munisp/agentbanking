package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"time"
)

type TransferRequest struct {
	PayerFSP string  `json:"payerFsp"`
	PayeeFSP string  `json:"payeeFsp"`
	Amount   float64 `json:"amount"`
	Currency string  `json:"currency"`
	PayerID  string  `json:"payerId"`
	PayeeID  string  `json:"payeeId"`
	Note     string  `json:"note,omitempty"`
}

type TransferResult struct {
	TransferID    string    `json:"transferId"`
	Status        string    `json:"status"`
	Amount        float64   `json:"amount"`
	Currency      string    `json:"currency"`
	CompletedAt   time.Time `json:"completedAt"`
	SettlementID  string    `json:"settlementId"`
	ILPCondition  string    `json:"ilpCondition"`
	ILPFulfilment string    `json:"ilpFulfilment"`
}

func healthHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"status": "healthy", "service": "mojaloop-connector-pos"})
}

func quoteHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	var req TransferRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	fee := req.Amount * 0.01
	if fee < 10 {
		fee = 10
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"quoteId":        fmt.Sprintf("QUO-%d", time.Now().UnixNano()),
		"transferAmount": req.Amount,
		"payeeFee":       fee,
		"currency":       req.Currency,
		"expiresAt":      time.Now().Add(15 * time.Minute).Format(time.RFC3339),
	})
}

func transferHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	var req TransferRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	result := TransferResult{
		TransferID:    fmt.Sprintf("TRF-%d", time.Now().UnixNano()),
		Status:        "COMMITTED",
		Amount:        req.Amount,
		Currency:      req.Currency,
		CompletedAt:   time.Now(),
		SettlementID:  fmt.Sprintf("SET-%d", time.Now().UnixMilli()),
		ILPCondition:  "SHA-256 condition placeholder",
		ILPFulfilment: "SHA-256 fulfilment placeholder",
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(result)
}

func participantsHandler(w http.ResponseWriter, r *http.Request) {
	participants := []map[string]string{
		{"fspId": "OPAY", "name": "OPay", "status": "active"},
		{"fspId": "PALMPAY", "name": "PalmPay", "status": "active"},
		{"fspId": "MONIEPOINT", "name": "Moniepoint", "status": "active"},
		{"fspId": "KUDA", "name": "Kuda", "status": "active"},
		{"fspId": "PAGA", "name": "Paga", "status": "active"},
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{"participants": participants})
}

func main() {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8143"
	}

	http.HandleFunc("/health", healthHandler)
	http.HandleFunc("/api/v1/quotes", quoteHandler)
	http.HandleFunc("/api/v1/transfers", transferHandler)
	http.HandleFunc("/api/v1/participants", participantsHandler)

	log.Printf("Mojaloop Connector POS starting on port %s", port)
	log.Fatal(http.ListenAndServe(fmt.Sprintf(":%s", port), nil))
}
