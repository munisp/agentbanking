package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"time"

	"github.com/google/uuid"
)

// --- Configuration (loaded from environment) ---
var (
	npciBaseURL    = os.Getenv("NPCI_API_BASE_URL")
	pspMerchantID  = os.Getenv("PSP_MERCHANT_ID")
	pspAPIKey      = os.Getenv("PSP_API_KEY")
	pspAPISecret   = os.Getenv("PSP_API_SECRET")
	simulationMode = os.Getenv("UPI_SIMULATION_MODE") == "true"
	environment    = os.Getenv("ENVIRONMENT")
)

// npciConfigured reports whether a real NPCI switch integration is configured.
func npciConfigured() bool {
	return npciBaseURL != "" && pspMerchantID != "" && pspAPIKey != "" && pspAPISecret != ""
}

// --- Data Structures ---

type PaymentRequest struct {
	TransactionID   string  `json:"transactionId"`
	PayeeVPA        string  `json:"payeeVpa"`
	PayerVPA        string  `json:"payerVpa"`
	Amount          float64 `json:"amount"`
	TransactionNote string  `json:"transactionNote"`
}

type PaymentResponse struct {
	Status        string `json:"status"`
	TransactionID string `json:"transactionId"`
	NPCITransID   string `json:"npciTransactionId,omitempty"`
	Message       string `json:"message"`
}

type StatusRequest struct {
	OriginalTransactionID string `json:"originalTransactionId"`
}

type StatusResponse struct {
	Status        string  `json:"status"`
	TransactionID string  `json:"transactionId"`
	Amount        float64 `json:"amount"`
	Timestamp     string  `json:"timestamp"`
}

// --- UPI Service Logic ---

// generateSignature creates a signature for the request body as required by NPCI
func generateSignature(requestBody []byte, timestamp string) string {
	payload := fmt.Sprintf("%s|%s", string(requestBody), timestamp)
	hash := sha256.Sum256([]byte(payload + pspAPISecret))
	return hex.EncodeToString(hash[:])
}

func writeJSONError(w http.ResponseWriter, status int, message string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	if err := json.NewEncoder(w).Encode(map[string]string{"status": "ERROR", "message": message}); err != nil {
		log.Printf("Error encoding error response: %v", err)
	}
}

// handlePaymentRequest processes an incoming payment request
func handlePaymentRequest(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		w.WriteHeader(http.StatusMethodNotAllowed)
		return
	}

	var req PaymentRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		log.Printf("Error decoding payment request: %v", err)
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	log.Printf("Received payment request: %+v", req)

	if simulationMode {
		// Simulated NPCI interaction — only reachable when UPI_SIMULATION_MODE=true
		// and ENVIRONMENT != production (enforced in main).
		npciTransID := uuid.New().String()
		log.Printf("WARNING: simulating NPCI transaction with ID: %s (UPI_SIMULATION_MODE)", npciTransID)

		time.Sleep(2 * time.Second) // Simulate network latency

		resp := PaymentResponse{
			Status:        "SIMULATED_SUCCESS",
			TransactionID: req.TransactionID,
			NPCITransID:   npciTransID,
			Message:       "SIMULATED payment response (UPI_SIMULATION_MODE) — not a real NPCI authorization",
		}

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		if err := json.NewEncoder(w).Encode(resp); err != nil {
			log.Printf("Error encoding payment response: %v", err)
		}
		return
	}

	if !npciConfigured() {
		log.Printf("Refusing payment %s: NPCI switch not configured", req.TransactionID)
		writeJSONError(w, http.StatusServiceUnavailable,
			"NPCI switch is not configured (set NPCI_API_BASE_URL, PSP_MERCHANT_ID, PSP_API_KEY, PSP_API_SECRET); refusing to fabricate a payment response")
		return
	}

	// A certified NPCI/PSP switch integration is required to submit real payments.
	// Fail loud rather than fabricate a transaction id or success status.
	log.Printf("Refusing payment %s: real NPCI submission not implemented", req.TransactionID)
	writeJSONError(w, http.StatusNotImplemented,
		"NPCI payment submission is not implemented for the configured switch; refusing to fabricate a transaction id")
}

// handleStatusRequest processes a request to check the status of a transaction
func handleStatusRequest(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		w.WriteHeader(http.StatusMethodNotAllowed)
		return
	}

	var req StatusRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		log.Printf("Error decoding status request: %v", err)
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	log.Printf("Received status request for transaction: %s", req.OriginalTransactionID)

	if simulationMode {
		log.Printf("WARNING: simulating NPCI status check for transaction: %s (UPI_SIMULATION_MODE)", req.OriginalTransactionID)

		time.Sleep(1 * time.Second)

		resp := StatusResponse{
			Status:        "SIMULATED_SUCCESS",
			TransactionID: req.OriginalTransactionID,
			Amount:        150.75, // Simulated amount (UPI_SIMULATION_MODE)
			Timestamp:     time.Now().UTC().Format(time.RFC3339),
		}

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		if err := json.NewEncoder(w).Encode(resp); err != nil {
			log.Printf("Error encoding status response: %v", err)
		}
		return
	}

	if !npciConfigured() {
		log.Printf("Refusing status check %s: NPCI switch not configured", req.OriginalTransactionID)
		writeJSONError(w, http.StatusServiceUnavailable,
			"NPCI switch is not configured; refusing to fabricate a transaction status")
		return
	}

	log.Printf("Refusing status check %s: real NPCI status query not implemented", req.OriginalTransactionID)
	writeJSONError(w, http.StatusNotImplemented,
		"NPCI status query is not implemented for the configured switch; refusing to fabricate a transaction status")
}

// healthCheck provides a simple health check endpoint
func healthCheck(w http.ResponseWriter, r *http.Request) {
	resp := map[string]string{"status": "UP"}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(resp)
}

// --- Main Server ---

func main() {
	log.Println("--- Starting UPI Connector Service ---")

	if simulationMode && environment == "production" {
		log.Fatal("UPI_SIMULATION_MODE=true is forbidden when ENVIRONMENT=production")
	}
	if simulationMode {
		log.Println("WARNING: running with SIMULATED NPCI responses (non-production only)")
	} else if !npciConfigured() {
		log.Println("WARNING: NPCI switch not configured; /upi/payment and /upi/status will return 503")
	}

	http.HandleFunc("/upi/payment", handlePaymentRequest)
	http.HandleFunc("/upi/status", handleStatusRequest)
	http.HandleFunc("/health", healthCheck)

	port := ":5005"
	log.Printf("Server listening on port %s", port)

	if err := http.ListenAndServe(port, nil); err != nil {
		log.Fatalf("Failed to start server: %v", err)
	}
}
