package main

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"log"
	"net/http"
	"time"

	"github.com/google/uuid"
)

// --- Configuration ---
// In a real application, these would be loaded from a secure config service
const (
	NPCI_API_BASE_URL = "https://api.npci.org/upi/v1" // This is a placeholder URL
	PSP_MERCHANT_ID   = "YOUR_MERCHANT_ID"
	PSP_API_KEY       = "YOUR_API_KEY"
	PSP_API_SECRET    = "YOUR_API_SECRET"
)

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
	Status        string `json:"status"`
	TransactionID string `json:"transactionId"`
	Amount        float64 `json:"amount"`
	Timestamp     string `json:"timestamp"`
}

// --- UPI Service Logic ---

// generateSignature creates a signature for the request body as required by NPCI
func generateSignature(requestBody []byte, timestamp string) string {
	payload := fmt.Sprintf("%s|%s", string(requestBody), timestamp)
	hash := sha256.Sum256([]byte(payload + PSP_API_SECRET))
	return hex.EncodeToString(hash[:])
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

	// --- Mock NPCI Interaction ---
	// In a real implementation, this section would make a signed HTTP request to the NPCI API.
	// We are mocking the response for this demonstration.
	npciTransID := uuid.New().String()
	log.Printf("Simulating NPCI transaction with ID: %s", npciTransID)

	time.Sleep(2 * time.Second) // Simulate network latency

	// --- Send Response ---
	resp := PaymentResponse{
		Status:        "SUCCESS",
		TransactionID: req.TransactionID,
		NPCITransID:   npciTransID,
		Message:       "Payment processed successfully",
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	if err := json.NewEncoder(w).Encode(resp); err != nil {
		log.Printf("Error encoding payment response: %v", err)
	}
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

	// --- Mock NPCI Status Check ---
	// Again, this would be a real API call in a production system.
	log.Printf("Simulating NPCI status check for transaction: %s", req.OriginalTransactionID)

	time.Sleep(1 * time.Second)

	// --- Send Response ---
	resp := StatusResponse{
		Status:        "SUCCESS",
		TransactionID: req.OriginalTransactionID,
		Amount:        150.75, // Mocked amount
		Timestamp:     time.Now().UTC().Format(time.RFC3339),
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	if err := json.NewEncoder(w).Encode(resp); err != nil {
		log.Printf("Error encoding status response: %v", err)
	}
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

	// In a real system, you would use a more robust router like Gorilla Mux or Chi
	http.HandleFunc("/upi/payment", handlePaymentRequest)
	http.HandleFunc("/upi/status", handleStatusRequest)
	http.HandleFunc("/health", healthCheck)

	port := ":5005"
	log.Printf("Server listening on port %s", port)

	// Example of how to call the service:
	// curl -X POST -H "Content-Type: application/json" -d '{"transactionId": "TXN12345", "payeeVpa": "merchant@psp", "payerVpa": "customer@psp", "amount": 150.75, "transactionNote": "Test payment"}' http://localhost:5005/upi/payment
	// curl -X POST -H "Content-Type: application/json" -d '{"originalTransactionId": "TXN12345"}' http://localhost:5005/upi/status

	if err := http.ListenAndServe(port, nil); err != nil {
		log.Fatalf("Failed to start server: %v", err)
	}
}

