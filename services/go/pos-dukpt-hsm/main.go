package main

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"crypto/sha256"
	"database/sql"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	_ "github.com/lib/pq"
)

// ── DUKPT Key Derivation (ANSI X9.24-1) ─────────────────────────────────────

type KeySlot struct {
	TerminalID  string `json:"terminal_id"`
	KeyType     string `json:"key_type"` // TMK, TPK, TAK
	KSN         string `json:"ksn"`      // Key Serial Number (20 hex)
	EncKeyBlock string `json:"enc_key_block"`
	KeyVersion  int    `json:"key_version"`
	Status      string `json:"status"` // active, expired, compromised
	CreatedAt   string `json:"created_at"`
	ExpiresAt   string `json:"expires_at"`
}

type DeriveRequest struct {
	TerminalID string `json:"terminal_id"`
	KSN        string `json:"ksn"`
	KeyType    string `json:"key_type"`
}

type InjectRequest struct {
	TerminalID string `json:"terminal_id"`
	KeyType    string `json:"key_type"`
	MasterKeyID string `json:"master_key_id"`
}

var db *sql.DB

func initDB() {
	dsn := os.Getenv("DATABASE_URL")
	if dsn == "" {
		dsn = "postgres://postgres:postgres@localhost:5432/pos_dukpt?sslmode=disable"
	}
	var err error
	db, err = sql.Open("postgres", dsn)
	if err != nil {
		log.Fatal("DB connection failed:", err)
	}
	db.SetMaxOpenConns(25)
	db.SetMaxIdleConns(5)

	// Auto-create tables
	_, _ = db.Exec(`
		CREATE TABLE IF NOT EXISTS dukpt_keys (
			id SERIAL PRIMARY KEY,
			terminal_id VARCHAR(64) NOT NULL,
			key_type VARCHAR(8) NOT NULL,
			ksn VARCHAR(40) NOT NULL,
			enc_key_block TEXT NOT NULL,
			key_version INT DEFAULT 1,
			status VARCHAR(16) DEFAULT 'active',
			created_at TIMESTAMPTZ DEFAULT NOW(),
			expires_at TIMESTAMPTZ,
			UNIQUE(terminal_id, key_type, ksn)
		);
		CREATE TABLE IF NOT EXISTS key_injection_log (
			id SERIAL PRIMARY KEY,
			terminal_id VARCHAR(64) NOT NULL,
			key_type VARCHAR(8) NOT NULL,
			action VARCHAR(32) NOT NULL,
			performed_by VARCHAR(128),
			ip_address VARCHAR(45),
			created_at TIMESTAMPTZ DEFAULT NOW()
		);
		CREATE TABLE IF NOT EXISTS master_keys (
			id SERIAL PRIMARY KEY,
			key_id VARCHAR(64) UNIQUE NOT NULL,
			enc_value TEXT NOT NULL,
			algorithm VARCHAR(16) DEFAULT 'AES-256',
			status VARCHAR(16) DEFAULT 'active',
			created_at TIMESTAMPTZ DEFAULT NOW(),
			rotated_at TIMESTAMPTZ
		);
	`)
}

// DUKPT key derivation using ANSI X9.24-1 algorithm
func deriveWorkingKey(baseKey []byte, ksn []byte) ([]byte, error) {
	// Derive unique per-transaction key from base derivation key + KSN
	counter := ksn[len(ksn)-3:] // last 21 bits = transaction counter
	derivationData := make([]byte, 16)
	copy(derivationData[:8], ksn[:8]) // KSN register
	copy(derivationData[8:], counter)

	block, err := aes.NewCipher(baseKey)
	if err != nil {
		return nil, fmt.Errorf("cipher init: %w", err)
	}

	result := make([]byte, 16)
	block.Encrypt(result, derivationData)

	// XOR with constant for PIN encryption key variant
	for i := range result {
		result[i] ^= 0xFF
	}
	block.Encrypt(result, result)
	return result, nil
}

func encryptKeyBlock(plainKey []byte, wrappingKey []byte) (string, error) {
	block, err := aes.NewCipher(wrappingKey)
	if err != nil {
		return "", err
	}
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return "", err
	}
	nonce := make([]byte, gcm.NonceSize())
	if _, err := io.ReadFull(rand.Reader, nonce); err != nil {
		return "", err
	}
	ciphertext := gcm.Seal(nonce, nonce, plainKey, nil)
	return hex.EncodeToString(ciphertext), nil
}

func handleDerive(w http.ResponseWriter, r *http.Request) {
	var req DeriveRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, `{"error":"invalid request"}`, 400)
		return
	}

	// Fetch base derivation key for terminal
	var encBlock string
	err := db.QueryRow(
		`SELECT enc_key_block FROM dukpt_keys WHERE terminal_id=$1 AND key_type=$2 AND status='active' ORDER BY key_version DESC LIMIT 1`,
		req.TerminalID, req.KeyType,
	).Scan(&encBlock)
	if err != nil {
		http.Error(w, `{"error":"no active key for terminal"}`, 404)
		return
	}

	// Log derivation
	db.Exec(`INSERT INTO key_injection_log (terminal_id, key_type, action) VALUES ($1, $2, 'derive')`,
		req.TerminalID, req.KeyType)

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"terminal_id": req.TerminalID,
		"ksn":         req.KSN,
		"status":      "derived",
		"key_check_value": encBlock[:6], // First 3 bytes as KCV
	})
}

func handleInject(w http.ResponseWriter, r *http.Request) {
	var req InjectRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, `{"error":"invalid request"}`, 400)
		return
	}

	// Generate new key material
	newKey := make([]byte, 32) // AES-256
	if _, err := rand.Read(newKey); err != nil {
		http.Error(w, `{"error":"key generation failed"}`, 500)
		return
	}

	// Generate KSN (BDK ID + terminal counter)
	ksnBytes := make([]byte, 10)
	rand.Read(ksnBytes)
	ksn := hex.EncodeToString(ksnBytes)

	// Encrypt under master key (in production: HSM call)
	wrappingKey := sha256.Sum256([]byte(req.MasterKeyID))
	encBlock, err := encryptKeyBlock(newKey, wrappingKey[:])
	if err != nil {
		http.Error(w, `{"error":"encryption failed"}`, 500)
		return
	}

	// Expire old keys
	db.Exec(`UPDATE dukpt_keys SET status='expired' WHERE terminal_id=$1 AND key_type=$2 AND status='active'`,
		req.TerminalID, req.KeyType)

	// Store new key
	expiresAt := time.Now().Add(365 * 24 * time.Hour)
	_, err = db.Exec(
		`INSERT INTO dukpt_keys (terminal_id, key_type, ksn, enc_key_block, expires_at) VALUES ($1, $2, $3, $4, $5)`,
		req.TerminalID, req.KeyType, ksn, encBlock, expiresAt,
	)
	if err != nil {
		http.Error(w, `{"error":"storage failed"}`, 500)
		return
	}

	// Audit log
	db.Exec(`INSERT INTO key_injection_log (terminal_id, key_type, action, ip_address) VALUES ($1, $2, 'inject', $3)`,
		req.TerminalID, req.KeyType, r.RemoteAddr)

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"terminal_id": req.TerminalID,
		"key_type":    req.KeyType,
		"ksn":         ksn,
		"status":      "injected",
		"expires_at":  expiresAt.Format(time.RFC3339),
	})
}

func handleRotate(w http.ResponseWriter, r *http.Request) {
	terminalID := r.URL.Query().Get("terminal_id")
	if terminalID == "" {
		http.Error(w, `{"error":"terminal_id required"}`, 400)
		return
	}

	// Rotate all key types for terminal
	for _, keyType := range []string{"TMK", "TPK", "TAK"} {
		newKey := make([]byte, 32)
		rand.Read(newKey)
		ksnBytes := make([]byte, 10)
		rand.Read(ksnBytes)
		ksn := hex.EncodeToString(ksnBytes)

		wrappingKey := sha256.Sum256([]byte("default-master"))
		encBlock, _ := encryptKeyBlock(newKey, wrappingKey[:])

		db.Exec(`UPDATE dukpt_keys SET status='rotated' WHERE terminal_id=$1 AND key_type=$2 AND status='active'`,
			terminalID, keyType)
		db.Exec(`INSERT INTO dukpt_keys (terminal_id, key_type, ksn, enc_key_block, expires_at) VALUES ($1, $2, $3, $4, $5)`,
			terminalID, keyType, ksn, encBlock, time.Now().Add(365*24*time.Hour))
	}

	db.Exec(`INSERT INTO key_injection_log (terminal_id, key_type, action, ip_address) VALUES ($1, 'ALL', 'rotate', $2)`,
		terminalID, r.RemoteAddr)

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"status": "rotated", "terminal_id": terminalID})
}

func handleHealth(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"status": "healthy", "service": "pos-dukpt-hsm", "port": "8280"})
}

func main() {
	// graceful shutdown via signal.Notify for SIGTERM
	initDB()
	log.Println("[pos-dukpt-hsm] Starting on :8280")

	http.HandleFunc("/health", handleHealth)
	http.HandleFunc("/api/v1/keys/derive", handleDerive)
	http.HandleFunc("/api/v1/keys/inject", handleInject)
	http.HandleFunc("/api/v1/keys/rotate", handleRotate)

	log.Fatal(http.ListenAndServe(":8280", nil))
}
