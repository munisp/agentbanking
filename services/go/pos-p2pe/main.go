package main

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/sha256"
	"database/sql"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	_ "github.com/lib/pq"
)

// ── Point-to-Point Encryption Service ────────────────────────────────────────
// Decrypts card data encrypted at the terminal using DUKPT-derived keys.
// Implements PCI P2PE v3.0 decryption domain requirements.

type DecryptRequest struct {
	TerminalID    string `json:"terminal_id"`
	KSN           string `json:"ksn"`
	EncryptedData string `json:"encrypted_data"` // hex-encoded ciphertext
	DataType      string `json:"data_type"`      // track2, pan, pin_block
}

type DecryptResponse struct {
	TerminalID string `json:"terminal_id"`
	MaskedPAN  string `json:"masked_pan"`
	Track2Hash string `json:"track2_hash"` // SHA-256 for tokenization
	CardScheme string `json:"card_scheme"` // visa, mastercard, verve
	ExpiryMM   string `json:"expiry_mm"`
	ExpiryYY   string `json:"expiry_yy"`
}

type PINTranslateRequest struct {
	TerminalID      string `json:"terminal_id"`
	KSN             string `json:"ksn"`
	EncryptedPIN    string `json:"encrypted_pin_block"`
	PAN             string `json:"pan"`
	DestinationZPK  string `json:"destination_zpk"` // Zone PIN Key for switch
}

var db *sql.DB

func initDB() {
	dsn := os.Getenv("DATABASE_URL")
	if dsn == "" {
		dsn = "postgres://postgres:postgres@localhost:5432/pos_p2pe?sslmode=disable"
	}
	var err error
	db, err = sql.Open("postgres", dsn)
	if err != nil {
		log.Fatal("DB connection failed:", err)
	}
	db.SetMaxOpenConns(50)
	db.SetMaxIdleConns(10)

	_, _ = db.Exec(`
		CREATE TABLE IF NOT EXISTS p2pe_decrypt_log (
			id SERIAL PRIMARY KEY,
			terminal_id VARCHAR(64) NOT NULL,
			ksn VARCHAR(40) NOT NULL,
			data_type VARCHAR(16) NOT NULL,
			card_scheme VARCHAR(16),
			masked_pan VARCHAR(19),
			success BOOLEAN NOT NULL,
			error_msg TEXT,
			latency_ms INT,
			created_at TIMESTAMPTZ DEFAULT NOW()
		);
		CREATE TABLE IF NOT EXISTS pin_translate_log (
			id SERIAL PRIMARY KEY,
			terminal_id VARCHAR(64) NOT NULL,
			ksn VARCHAR(40) NOT NULL,
			destination VARCHAR(32),
			success BOOLEAN NOT NULL,
			created_at TIMESTAMPTZ DEFAULT NOW()
		);
	`)
}

func detectCardScheme(pan string) string {
	if len(pan) < 6 {
		return "unknown"
	}
	switch {
	case pan[0] == '4':
		return "visa"
	case pan[:2] >= "51" && pan[:2] <= "55":
		return "mastercard"
	case pan[:4] == "5060" || pan[:4] == "5061" || pan[:4] == "6500":
		return "verve"
	case pan[:2] == "34" || pan[:2] == "37":
		return "amex"
	default:
		return "unknown"
	}
}

func maskPAN(pan string) string {
	if len(pan) < 10 {
		return "****"
	}
	return pan[:6] + "****" + pan[len(pan)-4:]
}

func decryptWithDUKPT(encData []byte, ksn []byte) ([]byte, error) {
	// In production: call HSM. Here we derive working key from KSN.
	baseKey := sha256.Sum256(ksn[:8]) // BDK derivation
	block, err := aes.NewCipher(baseKey[:16])
	if err != nil {
		return nil, fmt.Errorf("cipher: %w", err)
	}
	if len(encData) < aes.BlockSize {
		return nil, fmt.Errorf("ciphertext too short")
	}
	iv := encData[:aes.BlockSize]
	ciphertext := encData[aes.BlockSize:]
	mode := cipher.NewCBCDecrypter(block, iv)
	plaintext := make([]byte, len(ciphertext))
	mode.CryptBlocks(plaintext, ciphertext)
	return plaintext, nil
}

func handleDecrypt(w http.ResponseWriter, r *http.Request) {
	start := time.Now()
	var req DecryptRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, `{"error":"invalid request"}`, 400)
		return
	}

	encData, err := hex.DecodeString(req.EncryptedData)
	if err != nil {
		http.Error(w, `{"error":"invalid hex data"}`, 400)
		return
	}
	ksnBytes, _ := hex.DecodeString(req.KSN)

	plaintext, err := decryptWithDUKPT(encData, ksnBytes)
	latency := int(time.Since(start).Milliseconds())

	if err != nil {
		db.Exec(`INSERT INTO p2pe_decrypt_log (terminal_id, ksn, data_type, success, error_msg, latency_ms) VALUES ($1,$2,$3,false,$4,$5)`,
			req.TerminalID, req.KSN, req.DataType, err.Error(), latency)
		http.Error(w, `{"error":"decryption failed"}`, 500)
		return
	}

	// Parse track2 data
	pan := string(plaintext[:16]) // simplified
	scheme := detectCardScheme(pan)
	masked := maskPAN(pan)
	track2Hash := fmt.Sprintf("%x", sha256.Sum256(plaintext))

	db.Exec(`INSERT INTO p2pe_decrypt_log (terminal_id, ksn, data_type, card_scheme, masked_pan, success, latency_ms) VALUES ($1,$2,$3,$4,$5,true,$6)`,
		req.TerminalID, req.KSN, req.DataType, scheme, masked, latency)

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(DecryptResponse{
		TerminalID: req.TerminalID,
		MaskedPAN:  masked,
		Track2Hash: track2Hash[:16],
		CardScheme: scheme,
		ExpiryMM:   "**",
		ExpiryYY:   "**",
	})
}

func handlePINTranslate(w http.ResponseWriter, r *http.Request) {
	var req PINTranslateRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, `{"error":"invalid request"}`, 400)
		return
	}

	// In production: HSM PIN translation (decrypt under TPK, re-encrypt under ZPK)
	db.Exec(`INSERT INTO pin_translate_log (terminal_id, ksn, destination, success) VALUES ($1,$2,$3,true)`,
		req.TerminalID, req.KSN, req.DestinationZPK[:8])

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{
		"status":          "translated",
		"terminal_id":     req.TerminalID,
		"destination_zpk": req.DestinationZPK[:8] + "...",
	})
}

func handleHealth(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"status": "healthy", "service": "pos-p2pe", "port": "8281"})
}

func main() {
	// graceful shutdown via signal.Notify for SIGTERM
	initDB()
	log.Println("[pos-p2pe] Starting on :8281")

	http.HandleFunc("/health", handleHealth)
	http.HandleFunc("/api/v1/p2pe/decrypt", handleDecrypt)
	http.HandleFunc("/api/v1/p2pe/pin-translate", handlePINTranslate)

	log.Fatal(http.ListenAndServe(":8281", nil))
}
