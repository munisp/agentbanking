package main

import (
	"bytes"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

func init() {
	state = NewAppState()
}

func TestTransferHandler(t *testing.T) {
	body := `{"debit_account_id":"acc1","credit_account_id":"acc2","amount":1000,"currency":"NGN"}`
	req := httptest.NewRequest(http.MethodPost, "/transfer", bytes.NewBufferString(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	transferHandler(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}
	var resp map[string]interface{}
	json.NewDecoder(w.Body).Decode(&resp)
	if resp["status"] != "committed" {
		t.Fatalf("expected committed, got %v", resp["status"])
	}
}

func TestBalanceHandler(t *testing.T) {
	// First create a transfer
	body := `{"debit_account_id":"test_debit","credit_account_id":"test_credit","amount":5000,"currency":"NGN"}`
	req := httptest.NewRequest(http.MethodPost, "/transfer", bytes.NewBufferString(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	transferHandler(w, req)

	// Check credit balance
	req2 := httptest.NewRequest(http.MethodGet, "/balance?account_id=test_credit", nil)
	w2 := httptest.NewRecorder()
	balanceHandler(w2, req2)
	if w2.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w2.Code)
	}
	var bal AccountBalance
	json.NewDecoder(w2.Body).Decode(&bal)
	if bal.Balance != 5000 {
		t.Fatalf("expected balance 5000, got %d", bal.Balance)
	}
}

func TestHealthHandler(t *testing.T) {
	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	w := httptest.NewRecorder()
	healthHandler(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}
	var resp map[string]interface{}
	json.NewDecoder(w.Body).Decode(&resp)
	if resp["status"] != "healthy" {
		t.Fatalf("expected healthy, got %v", resp["status"])
	}
}

func TestSignatureVerify(t *testing.T) {
	secret := "test-secret"
	payload := "test-payload"
	mac := hmac.New(sha256.New, []byte(secret))
	mac.Write([]byte(payload))
	sig := hex.EncodeToString(mac.Sum(nil))

	body, _ := json.Marshal(map[string]string{
		"payload":   payload,
		"signature": sig,
		"secret":    secret,
	})
	req := httptest.NewRequest(http.MethodPost, "/signature/verify", bytes.NewBuffer(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	signatureVerifyHandler(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}
	var resp map[string]interface{}
	json.NewDecoder(w.Body).Decode(&resp)
	if resp["valid"] != true {
		t.Fatalf("expected valid=true, got %v", resp["valid"])
	}
}

func TestReconcileHandler(t *testing.T) {
	req := httptest.NewRequest(http.MethodPost, "/reconcile", nil)
	w := httptest.NewRecorder()
	reconcileHandler(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}
	var resp ReconciliationResult
	json.NewDecoder(w.Body).Decode(&resp)
	if resp.Status != "balanced" {
		t.Fatalf("expected balanced, got %s", resp.Status)
	}
}

func TestStatsHandler(t *testing.T) {
	req := httptest.NewRequest(http.MethodGet, "/stats", nil)
	w := httptest.NewRecorder()
	statsHandler(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}
}
