package main

import (
	"bytes"
	"context"
	"crypto/tls"
	"crypto/x509"
	"database/sql"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"syscall"
	"time"

	_ "github.com/lib/pq"
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
	fspID          = envFirst("MOJALOOP_FSP_ID", "MOJALOOP_DFSP_ID")
	simulationMode = os.Getenv("MOJALOOP_SIMULATION_MODE") == "true"
	environment    = os.Getenv("ENVIRONMENT")
)

func envFirst(keys ...string) string {
	for _, k := range keys {
		if v := os.Getenv(k); v != "" {
			return v
		}
	}
	return ""
}

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

// --- mTLS configuration ---

var mtlsClient *http.Client

func initMTLS() {
	certFile := os.Getenv("MOJALOOP_TLS_CERT_FILE")
	keyFile := os.Getenv("MOJALOOP_TLS_KEY_FILE")
	caFile := os.Getenv("MOJALOOP_TLS_CA_FILE")

	if certFile == "" || keyFile == "" {
		log.Println("[mtls] No TLS_CERT_FILE/TLS_KEY_FILE set, using plain HTTP client")
		mtlsClient = &http.Client{Timeout: 30 * time.Second}
		return
	}

	cert, err := tls.LoadX509KeyPair(certFile, keyFile)
	if err != nil {
		log.Printf("[mtls] Failed to load cert/key pair: %v — falling back to plain HTTP", err)
		mtlsClient = &http.Client{Timeout: 30 * time.Second}
		return
	}

	tlsConfig := &tls.Config{
		Certificates: []tls.Certificate{cert},
		MinVersion:   tls.VersionTLS12,
	}

	if caFile != "" {
		caCert, err := os.ReadFile(caFile)
		if err == nil {
			caPool := x509.NewCertPool()
			caPool.AppendCertsFromPEM(caCert)
			tlsConfig.RootCAs = caPool
		} else {
			log.Printf("[mtls] Failed to read CA file: %v — using system CA pool", err)
		}
	}

	mtlsClient = &http.Client{
		Timeout: 30 * time.Second,
		Transport: &http.Transport{
			TLSClientConfig:     tlsConfig,
			MaxIdleConns:        50,
			MaxIdleConnsPerHost: 20,
			IdleConnTimeout:     90 * time.Second,
		},
	}
	log.Println("[mtls] mTLS client initialized with cert/key pair")

	// Set up SIGHUP handler for cert rotation
	go watchCertRotation(certFile, keyFile, caFile)
}

func watchCertRotation(certFile, keyFile, caFile string) {
	sighup := make(chan os.Signal, 1)
	signal.Notify(sighup, syscall.SIGHUP)
	for range sighup {
		log.Println("[mtls] SIGHUP received — reloading certificates")
		cert, err := tls.LoadX509KeyPair(certFile, keyFile)
		if err != nil {
			log.Printf("[mtls] Cert reload failed: %v — keeping existing certs", err)
			continue
		}
		tlsConfig := &tls.Config{
			Certificates: []tls.Certificate{cert},
			MinVersion:   tls.VersionTLS12,
		}
		if caFile != "" {
			if caCert, err := os.ReadFile(caFile); err == nil {
				caPool := x509.NewCertPool()
				caPool.AppendCertsFromPEM(caCert)
				tlsConfig.RootCAs = caPool
			}
		}
		mtlsClient = &http.Client{
			Timeout: 30 * time.Second,
			Transport: &http.Transport{
				TLSClientConfig:     tlsConfig,
				MaxIdleConns:        50,
				MaxIdleConnsPerHost: 20,
				IdleConnTimeout:     90 * time.Second,
			},
		}
		log.Println("[mtls] Certificates reloaded successfully")
	}
}

// --- FSPIOP headers ---

func fspiopHeaders(source, destination string) map[string]string {
	headers := map[string]string{
		"FSPIOP-Source": source,
		"Date":         time.Now().UTC().Format(http.TimeFormat),
	}
	if destination != "" {
		headers["FSPIOP-Destination"] = destination
	}
	return headers
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
	for k, v := range fspiopHeaders(fspID, destination) {
		req.Header.Set(k, v)
	}

	resp, err := mtlsClient.Do(req)
	if err != nil {
		writeJSONError(w, http.StatusServiceUnavailable, "mojaloop hub unreachable: "+err.Error())
		return
	}
	defer resp.Body.Close()
	respBody, _ := io.ReadAll(resp.Body)

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

// --- Settlement window automation ---

func runSettlementAutomation(dfspId string) {
	ticker := time.NewTicker(6 * time.Hour)
	defer ticker.Stop()
	for range ticker.C {
		closeExpiredSettlementWindows(dfspId)
	}
}

func closeExpiredSettlementWindows(dfspId string) {
	req, err := http.NewRequest("GET", hubURL+"/settlementWindows?state=OPEN", nil)
	if err != nil {
		return
	}
	for k, v := range fspiopHeaders(dfspId, "") {
		req.Header.Set(k, v)
	}
	resp, err := mtlsClient.Do(req)
	if err != nil || resp.StatusCode != 200 {
		return
	}
	defer resp.Body.Close()
	var windows []map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&windows); err != nil {
		return
	}
	for _, win := range windows {
		created, ok := win["createdDate"].(string)
		if !ok {
			continue
		}
		t, err := time.Parse(time.RFC3339, created)
		if err != nil {
			continue
		}
		if time.Since(t) > 20*time.Hour {
			winID := fmt.Sprintf("%v", win["settlementWindowId"])
			closeBody, _ := json.Marshal(map[string]string{
				"state":  "CLOSED",
				"reason": fmt.Sprintf("Auto-closed: window age %s exceeded 20h threshold", time.Since(t).Round(time.Minute)),
			})
			closeReq, _ := http.NewRequest("POST", hubURL+"/settlementWindows/"+winID, strings.NewReader(string(closeBody)))
			closeReq.Header.Set("Content-Type", "application/json")
			for k, v := range fspiopHeaders(dfspId, "") {
				closeReq.Header.Set(k, v)
			}
			if closeResp, err := mtlsClient.Do(closeReq); err == nil {
				closeResp.Body.Close()
				log.Printf("[settlement] Auto-closed window %s", winID)
				logAudit("settlement_window_auto_close", winID, string(closeBody))
			}
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
	logAudit("quote_requested", quoteID, fmt.Sprintf(`{"payerFsp":"%s","payeeFsp":"%s","amount":%f}`, req.PayerFSP, req.PayeeFSP, req.Amount))
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

func recoverMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		defer func() {
			if err := recover(); err != nil {
				log.Printf("[recovery] panic: %v", err)
				http.Error(w, "internal server error", http.StatusInternalServerError)
			}
		}()
		next.ServeHTTP(w, r)
	})
}

func jwtAuthMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/health" || r.URL.Path == "/healthz" || r.URL.Path == "/metrics" || r.URL.Path == "/ready" {
			next.ServeHTTP(w, r)
			return
		}
		auth := r.Header.Get("Authorization")
		if auth == "" {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusUnauthorized)
			w.Write([]byte(`{"error":{"code":401,"message":"missing authorization header"}}`))
			return
		}
		parts := strings.SplitN(auth, " ", 2)
		if len(parts) != 2 || strings.ToLower(parts[0]) != "bearer" || len(parts[1]) < 10 {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusUnauthorized)
			w.Write([]byte(`{"error":{"code":401,"message":"invalid bearer token format"}}`))
			return
		}
		next.ServeHTTP(w, r)
	})
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

	initDB()
	initMTLS()

	port := os.Getenv("PORT")
	if port == "" {
		port = "8143"
	}

	mux := http.NewServeMux()
	mux.HandleFunc("/health", healthHandler)
	mux.HandleFunc("/api/v1/quotes", quoteHandler)
	mux.HandleFunc("/api/v1/transfers", transferHandler)
	mux.HandleFunc("/api/v1/participants", participantsHandler)

	handler := recoverMiddleware(jwtAuthMiddleware(mux))

	srv := &http.Server{
		Addr:              fmt.Sprintf(":%s", port),
		Handler:           handler,
		ReadHeaderTimeout: 10 * time.Second,
		WriteTimeout:      30 * time.Second,
		IdleTimeout:       120 * time.Second,
	}

	// Start settlement window automation only against a configured hub.
	if hubConfigured() {
		go runSettlementAutomation(fspID)
	} else {
		log.Println("[settlement] hub not configured; settlement window automation disabled")
	}

	setupGracefulShutdown(srv)

	log.Printf("Mojaloop Connector POS starting on port %s (mTLS=%v)", port, mtlsClient.Transport != nil)
	log.Fatal(srv.ListenAndServe())
}

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

// --- PostgreSQL persistence ---

var db *sql.DB

func initDB() {
	dbURL := os.Getenv("DATABASE_URL")
	if dbURL == "" {
		dbURL = "postgres://postgres:postgres@localhost:5432/mojaloop_connector_pos?sslmode=disable"
	}
	var err error
	db, err = sql.Open("postgres", dbURL)
	if err != nil {
		log.Printf("DB init warning: %v", err)
		return
	}
	db.SetMaxOpenConns(20)
	db.SetMaxIdleConns(5)
	db.SetConnMaxLifetime(30 * time.Minute)

	db.Exec(`CREATE TABLE IF NOT EXISTS audit_log (
		id SERIAL PRIMARY KEY,
		action TEXT, entity_id TEXT, data TEXT,
		created_at TIMESTAMPTZ DEFAULT NOW()
	)`)
	db.Exec(`CREATE TABLE IF NOT EXISTS state_store (
		key TEXT PRIMARY KEY, value TEXT,
		updated_at TIMESTAMPTZ DEFAULT NOW()
	)`)
	db.Exec(`CREATE TABLE IF NOT EXISTS settlement_windows (
		window_id TEXT PRIMARY KEY,
		state TEXT NOT NULL DEFAULT 'OPEN',
		closed_reason TEXT,
		created_at TIMESTAMPTZ DEFAULT NOW(),
		closed_at TIMESTAMPTZ
	)`)
}

func logAudit(action, entityID, data string) {
	if db != nil {
		db.Exec("INSERT INTO audit_log (action, entity_id, data) VALUES ($1, $2, $3)", action, entityID, data)
	}
}

func setState(key, value string) {
	if db != nil {
		db.Exec("INSERT INTO state_store (key, value, updated_at) VALUES ($1, $2, NOW()) ON CONFLICT (key) DO UPDATE SET value = $2, updated_at = NOW()", key, value)
	}
}

func getState(key string) string {
	if db == nil {
		return ""
	}
	var val string
	db.QueryRow("SELECT value FROM state_store WHERE key = $1", key).Scan(&val)
	return val
}
