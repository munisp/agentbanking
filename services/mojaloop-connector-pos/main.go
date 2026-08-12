package main

import (
	"syscall"
	"os/signal"
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"log"
	"net/http"
	"os"
	"strconv"
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

// Mojaloop hub connection (FSPIOP). Simulation mode is only honoured outside
// production; MOJALOOP_SIMULATION_MODE=true + ENVIRONMENT=production is fatal.
var (
	hubURL         = os.Getenv("MOJALOOP_HUB_URL")
	fspID          = os.Getenv("MOJALOOP_FSP_ID")
	simulationMode = os.Getenv("MOJALOOP_SIMULATION_MODE") == "true"
	environment    = os.Getenv("ENVIRONMENT")
)

func hubConfigured() bool {
	return hubURL != "" && fspID != ""
}

func writeJSONError(w http.ResponseWriter, status int, message string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	if err := json.NewEncoder(w).Encode(map[string]string{"status": "error", "message": message}); err != nil {
		log.Printf("Error encoding error response: %v", err)
	}
}

// proxyToHub forwards a request to the Mojaloop hub (FSPIOP API) and relays
// the hub's response verbatim. Any hub failure maps to 502/503 — never to
// fabricated quotes, transfers, or settlement data.
func proxyToHub(w http.ResponseWriter, method, path string, body []byte, contentType, destination string) {
	if !hubConfigured() {
		writeJSONError(w, http.StatusServiceUnavailable,
			"mojaloop hub not configured: set MOJALOOP_HUB_URL and MOJALOOP_FSP_ID")
		return
	}

	req, err := http.NewRequest(method, hubURL+path, bytes.NewReader(body))
	if err != nil {
		writeJSONError(w, http.StatusInternalServerError, err.Error())
		return
	}
	if contentType != "" {
		req.Header.Set("Content-Type", contentType)
		req.Header.Set("Accept", contentType)
	}
	req.Header.Set("FSPIOP-Source", fspID)
	if destination != "" {
		req.Header.Set("FSPIOP-Destination", destination)
	}
	req.Header.Set("Date", time.Now().UTC().Format(http.TimeFormat))

	client := &http.Client{Timeout: 15 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		writeJSONError(w, http.StatusServiceUnavailable, "mojaloop hub unreachable: "+err.Error())
		return
	}
	defer resp.Body.Close()
	respBody, _ := ioutil.ReadAll(resp.Body)

	if resp.StatusCode >= 400 {
		writeJSONError(w, http.StatusBadGateway,
			fmt.Sprintf("mojaloop hub returned HTTP %d: %s", resp.StatusCode, string(respBody)))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(resp.StatusCode)
	if len(respBody) > 0 {
		if _, err := w.Write(respBody); err != nil {
			log.Printf("Error writing hub response: %v", err)
		}
	}
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

	if simulationMode {
		// Simulated quote — only reachable when MOJALOOP_SIMULATION_MODE=true
		// and ENVIRONMENT != production (enforced in main).
		log.Println("WARNING: returning simulated quote (MOJALOOP_SIMULATION_MODE)")
		fee := req.Amount * 0.01
		if fee < 10 {
			fee = 10
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"quoteId":        fmt.Sprintf("SIM-QUO-%d", time.Now().UnixNano()),
			"transferAmount": req.Amount,
			"payeeFee":       fee,
			"currency":       req.Currency,
			"expiresAt":      time.Now().Add(15 * time.Minute).Format(time.RFC3339),
			"simulated":      true,
		})
		return
	}

	// Real FSPIOP quote request to the hub. The hub answers asynchronously
	// (PUT /quotes/{quoteId} callback) and returns 202 Accepted here.
	quoteID := fmt.Sprintf("QUO-%d", time.Now().UnixNano())
	fspiopQuote := map[string]interface{}{
		"quoteId":       quoteID,
		"transactionId": quoteID,
		"payer": map[string]interface{}{
			"partyIdInfo": map[string]string{
				"partyIdType":     "MSISDN",
				"partyIdentifier": req.PayerID,
				"fspId":           req.PayerFSP,
			},
		},
		"payee": map[string]interface{}{
			"partyIdInfo": map[string]string{
				"partyIdType":     "MSISDN",
				"partyIdentifier": req.PayeeID,
				"fspId":           req.PayeeFSP,
			},
		},
		"amountType": "SEND",
		"amount": map[string]string{
			"amount":   strconv.FormatFloat(req.Amount, 'f', 2, 64),
			"currency": req.Currency,
		},
		"transactionType": map[string]string{
			"scenario":      "TRANSFER",
			"initiator":     "PAYER",
			"initiatorType": "CONSUMER",
		},
		"note": req.Note,
	}
	body, err := json.Marshal(fspiopQuote)
	if err != nil {
		writeJSONError(w, http.StatusInternalServerError, err.Error())
		return
	}
	proxyToHub(w, http.MethodPost, "/quotes", body,
		"application/vnd.interoperability.quotes+json;version=1.0", req.PayeeFSP)
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

	if simulationMode {
		// Simulated transfer — only reachable when MOJALOOP_SIMULATION_MODE=true
		// and ENVIRONMENT != production (enforced in main).
		log.Println("WARNING: returning simulated transfer (MOJALOOP_SIMULATION_MODE)")
		result := TransferResult{
			TransferID:    fmt.Sprintf("SIM-TRF-%d", time.Now().UnixNano()),
			Status:        "SIMULATED_COMMITTED",
			Amount:        req.Amount,
			Currency:      req.Currency,
			CompletedAt:   time.Now(),
			SettlementID:  fmt.Sprintf("SIM-SET-%d", time.Now().UnixMilli()),
			ILPCondition:  "SIMULATED-CONDITION",
			ILPFulfilment: "SIMULATED-FULFILMENT",
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(result)
		return
	}

	// A real FSPIOP transfer requires a valid ILP condition obtained from a hub
	// quote (and fulfilment delivered via the hub callback). This connector
	// must not fabricate COMMITTED transfers, settlement IDs, or ILP crypto.
	log.Printf("Refusing transfer of %v %s: no real FSPIOP transfer flow available", req.Amount, req.Currency)
	writeJSONError(w, http.StatusNotImplemented,
		"transfer initiation requires the FSPIOP quote/transfer flow with a real ILP condition from the hub; local fabrication of COMMITTED transfers and settlement IDs has been removed")
}

func participantsHandler(w http.ResponseWriter, r *http.Request) {
	if simulationMode {
		log.Println("WARNING: returning simulated participant list (MOJALOOP_SIMULATION_MODE)")
		participants := []map[string]string{
			{"fspId": "OPAY", "name": "OPay", "status": "active"},
			{"fspId": "PALMPAY", "name": "PalmPay", "status": "active"},
			{"fspId": "MONIEPOINT", "name": "Moniepoint", "status": "active"},
			{"fspId": "KUDA", "name": "Kuda", "status": "active"},
			{"fspId": "PAGA", "name": "Paga", "status": "active"},
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{"participants": participants, "simulated": true})
		return
	}

	// Real participant list from the hub's participant registry.
	proxyToHub(w, http.MethodGet, "/participants", nil,
		"application/vnd.interoperability.participants+json;version=1.0", "")
}

func main() {
	if simulationMode && environment == "production" {
		log.Fatal("MOJALOOP_SIMULATION_MODE=true is forbidden when ENVIRONMENT=production")
	}
	if simulationMode {
		log.Println("WARNING: running with SIMULATED mojaloop responses (non-production only)")
	} else if !hubConfigured() {
		log.Println("WARNING: mojaloop hub not configured; /api/v1/quotes and /api/v1/participants will return 503")
	}

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

// --- Production: Graceful Shutdown ---
func setupGracefulShutdown(srv *http.Server) {
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		sig := <-quit
		log.Printf("[shutdown] Received signal %s, shutting down gracefully...", sig)
		ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
		defer cancel()
		if err := srv.Shutdown(ctx); err != nil {
			log.Printf("[shutdown] Server forced to shutdown: %v", err)
		}
		log.Println("[shutdown] Server exited")
	}()
}
