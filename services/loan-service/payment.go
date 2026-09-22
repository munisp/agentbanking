package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

type PaymentStruct struct {
	Recipient     string `json:"recipient"`
	Amount        string `json:"amount"`
	Note          string `json:"note"`
	TenantID      string `json:"tenant_id"`
	KeycloakID    string `json:"keycloak_id"`
	LedgerID      string `json:"ledger_id"`
	MintAccountID string `json:"mint_account_id"`
}

// paymentHTTPClient is shared across calls (F17): a per-call &http.Client{}
// created a new Transport per call — no TCP/TLS reuse.
var paymentHTTPClient = &http.Client{
	Timeout: 10 * time.Second,
}

func Payment(payload *PaymentStruct) ([]byte, error) {
	url := GetEnv("PAYMENT_URL", "")

	jsonData, err := json.Marshal(payload)
	if err != nil {
		return nil, fmt.Errorf("marshal payment payload: %w", err)
	}

	req, err := http.NewRequest("POST", url, bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, fmt.Errorf("build payment request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")
	req.Header.Set("x-tenant-id", payload.TenantID)
	req.Header.Set("x-keycloak-id", payload.KeycloakID)
	req.Header.Set("x-ledger-id", payload.LedgerID)
	req.Header.Set("x-mint-account-id", payload.MintAccountID)

	resp, err := paymentHTTPClient.Do(req)

	if err != nil {
		return nil, err
	}

	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)

	fmt.Println("Status:", resp.Status)
	fmt.Println("Response:", string(body))

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusCreated {
		return nil, fmt.Errorf(
			"payment failed | status: %d | response: %s",
			resp.StatusCode,
			string(body),
		)
	}

	return body, nil
}
