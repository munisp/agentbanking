package main

import (
	"syscall"
	"os/signal"
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"time"
)

type Biller struct {
	ID       string `json:"id"`
	Name     string `json:"name"`
	Category string `json:"category"`
	Active   bool   `json:"active"`
}

type PaymentResult struct {
	Reference string    `json:"reference"`
	BillerID  string    `json:"billerId"`
	Amount    float64   `json:"amount"`
	Status    string    `json:"status"`
	Token     string    `json:"token,omitempty"`
	Timestamp time.Time `json:"timestamp"`
}

var billers = []Biller{
	{ID: "DSTV", Name: "DSTV", Category: "cable_tv", Active: true},
	{ID: "GOTV", Name: "GOtv", Category: "cable_tv", Active: true},
	{ID: "IKEDC", Name: "Ikeja Electric", Category: "electricity", Active: true},
	{ID: "EKEDC", Name: "Eko Electric", Category: "electricity", Active: true},
	{ID: "AEDC", Name: "Abuja Electric", Category: "electricity", Active: true},
	{ID: "LWC", Name: "Lagos Water Corporation", Category: "water", Active: true},
	{ID: "FIRS", Name: "Federal Inland Revenue", Category: "government", Active: true},
}

// Simulation mode is only honoured outside production; in production the
// combination BILLER_SIMULATION_MODE=true + ENVIRONMENT=production is fatal.
var (
	simulationMode = os.Getenv("BILLER_SIMULATION_MODE") == "true"
	environment    = os.Getenv("ENVIRONMENT")
)

func findBiller(id string) *Biller {
	for i := range billers {
		if billers[i].ID == id {
			return &billers[i]
		}
	}
	return nil
}

func writeJSONError(w http.ResponseWriter, status int, message string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	if err := json.NewEncoder(w).Encode(map[string]string{"status": "error", "message": message}); err != nil {
		log.Printf("Error encoding error response: %v", err)
	}
}

func healthHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"status": "healthy", "service": "bill-payment-gateway"})
}

func billersHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{"billers": billers})
}

func validateHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	var req struct {
		BillerID    string `json:"billerId"`
		CustomerRef string `json:"customerReference"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	biller := findBiller(req.BillerID)
	if biller == nil {
		writeJSONError(w, http.StatusNotFound, fmt.Sprintf("unknown billerId: %s", req.BillerID))
		return
	}

	if simulationMode {
		log.Printf("WARNING: returning simulated customer validation for biller %s (BILLER_SIMULATION_MODE)", req.BillerID)
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"valid":             true,
			"billerId":          req.BillerID,
			"customerReference": req.CustomerRef,
			"customerName":      "SIMULATED CUSTOMER " + req.CustomerRef,
			"simulated":         true,
		})
		return
	}

	// No real biller aggregator API is configured; fail loud rather than
	// fabricating a customer name for an arbitrary meter/smartcard number.
	log.Printf("Refusing validation for biller %s: no biller validation API configured", req.BillerID)
	writeJSONError(w, http.StatusServiceUnavailable,
		"biller validation API is not configured; refusing to fabricate a customer name")
}

func payHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	var req struct {
		BillerID    string  `json:"billerId"`
		CustomerRef string  `json:"customerReference"`
		Amount      float64 `json:"amount"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	biller := findBiller(req.BillerID)
	if biller == nil {
		writeJSONError(w, http.StatusNotFound, fmt.Sprintf("unknown billerId: %s", req.BillerID))
		return
	}
	if req.Amount <= 0 {
		writeJSONError(w, http.StatusBadRequest, "amount must be greater than zero")
		return
	}

	if simulationMode {
		log.Printf("WARNING: returning simulated payment result for biller %s (BILLER_SIMULATION_MODE)", req.BillerID)
		result := PaymentResult{
			Reference: fmt.Sprintf("SIM-BPG-%d", time.Now().UnixNano()),
			BillerID:  req.BillerID,
			Amount:    req.Amount,
			Status:    "simulated_success",
			Timestamp: time.Now(),
		}

		if biller.Category == "electricity" {
			result.Token = "SIMULATED-TOKEN-NOT-VALID"
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(result)
		return
	}

	// No real biller payment API is configured; fail loud rather than
	// fabricating a success reference or an electricity token.
	log.Printf("Refusing payment for biller %s: no biller payment API configured", req.BillerID)
	writeJSONError(w, http.StatusServiceUnavailable,
		"biller payment API is not configured; refusing to fabricate a payment reference or token")
}

func main() {
	if simulationMode && environment == "production" {
		log.Fatal("BILLER_SIMULATION_MODE=true is forbidden when ENVIRONMENT=production")
	}
	if simulationMode {
		log.Println("WARNING: running with SIMULATED biller responses (non-production only)")
	} else {
		log.Println("WARNING: no biller API configured; /api/v1/validate and /api/v1/pay will return 503")
	}

	port := os.Getenv("PORT")
	if port == "" {
		port = "8141"
	}

	http.HandleFunc("/health", healthHandler)
	http.HandleFunc("/api/v1/billers", billersHandler)
	http.HandleFunc("/api/v1/validate", validateHandler)
	http.HandleFunc("/api/v1/pay", payHandler)

	log.Printf("Bill Payment Gateway starting on port %s", port)
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
