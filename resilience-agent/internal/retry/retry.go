// Package retry implements an exponential-backoff retry engine for
// POS transactions that fail due to transient network errors.
//
// Backoff schedule (Nigeria-tuned):
//   Attempt 1 — immediate
//   Attempt 2 — 1 s
//   Attempt 3 — 2 s
//   Attempt 4 — 4 s
//   After 4 attempts — mark as "queue_offline" for the Rust offline queue
package retry

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"time"
)

const (
	MaxAttempts    = 4
	BaseDelay      = 1 * time.Second
	MaxDelay       = 8 * time.Second
	RequestTimeout = 5 * time.Second
)

// TxPayload is the transaction body forwarded to the POS backend.
type TxPayload struct {
	Type            string                 `json:"type"`
	Amount          float64                `json:"amount"`
	CustomerName    string                 `json:"customerName,omitempty"`
	CustomerPhone   string                 `json:"customerPhone,omitempty"`
	DestinationBank string                 `json:"destinationBank,omitempty"`
	DestinationAcct string                 `json:"destinationAccount,omitempty"`
	Channel         string                 `json:"channel,omitempty"`
	Metadata        map[string]interface{} `json:"metadata,omitempty"`
}

// RetryResult describes the outcome of a retry sequence.
type RetryResult struct {
	Success    bool   `json:"success"`
	Attempts   int    `json:"attempts"`
	FinalError string `json:"final_error,omitempty"`
	Ref        string `json:"ref,omitempty"`
	// QueueOffline is true when all retries are exhausted — the caller
	// should hand the payload to the Rust offline queue service.
	QueueOffline bool `json:"queue_offline"`
}

// Submit attempts to POST the payload to targetURL with exponential backoff.
// It returns as soon as a 2xx response is received or all attempts are exhausted.
func Submit(ctx context.Context, targetURL string, payload TxPayload) RetryResult {
	body, err := json.Marshal(payload)
	if err != nil {
		return RetryResult{Success: false, FinalError: err.Error(), QueueOffline: true}
	}

	client := &http.Client{Timeout: RequestTimeout}
	var lastErr string

	for attempt := 1; attempt <= MaxAttempts; attempt++ {
		req, err := http.NewRequestWithContext(ctx, http.MethodPost, targetURL, bytes.NewReader(body))
		if err != nil {
			lastErr = err.Error()
			break
		}
		req.Header.Set("Content-Type", "application/json")

		resp, err := client.Do(req)
		if err == nil && resp.StatusCode >= 200 && resp.StatusCode < 300 {
			resp.Body.Close()
			// Extract ref from response if present
			var result map[string]interface{}
			ref := ""
			if json.NewDecoder(resp.Body).Decode(&result) == nil {
				if r, ok := result["ref"].(string); ok {
					ref = r
				}
			}
			return RetryResult{Success: true, Attempts: attempt, Ref: ref}
		}

		if err != nil {
			lastErr = err.Error()
		} else {
			resp.Body.Close()
			lastErr = fmt.Sprintf("HTTP %d", resp.StatusCode)
		}

		if attempt < MaxAttempts {
			delay := time.Duration(1<<uint(attempt-1)) * BaseDelay
			if delay > MaxDelay {
				delay = MaxDelay
			}
			select {
			case <-ctx.Done():
				return RetryResult{
					Success:      false,
					Attempts:     attempt,
					FinalError:   ctx.Err().Error(),
					QueueOffline: true,
				}
			case <-time.After(delay):
			}
		}
	}

	return RetryResult{
		Success:      false,
		Attempts:     MaxAttempts,
		FinalError:   lastErr,
		QueueOffline: true,
	}
}
