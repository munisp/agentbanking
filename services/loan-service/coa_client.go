package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"time"
)

// CoAClient is a client for interacting with the Chart of Accounts service
type CoAClient struct {
	baseURL    string
	httpClient *http.Client
}

// NewCoAClient creates a new Chart of Accounts client
func NewCoAClient() *CoAClient {
	baseURL := os.Getenv("COA_SERVICE_URL")
	if baseURL == "" {
		// Try gateway URL first, fall back to direct service
		gatewayURL := os.Getenv("BACKEND_URL")
		if gatewayURL != "" {
			baseURL = gatewayURL + "/chart-of-accounts"
		} else {
			// Direct service-to-service call (no /chart-of-accounts prefix needed)
			baseURL = "http://chart-of-accounts-service:8080"
		}
	}

	return &CoAClient{
		baseURL: baseURL,
		httpClient: &http.Client{
			Timeout: 60 * time.Second, // Increased timeout to 60 seconds
		},
	}
}

// CoAAccount represents an account in the Chart of Accounts
type CoAAccount struct {
	ID               string    `json:"id,omitempty"`
	TenantID         string    `json:"tenant_id"`
	Code             string    `json:"code"`
	Name             string    `json:"name"`
	Type             string    `json:"type"` // asset, liability, equity, revenue, expense
	ParentID         string    `json:"parent_id,omitempty"`
	NormalBalance    string    `json:"normal_balance,omitempty"`
	Level            int       `json:"level,omitempty"`
	IsActive         bool      `json:"is_active"`
	IsSystemAccount  bool      `json:"is_system_account"`
	Currency         string    `json:"currency"`
	Description      string    `json:"description,omitempty"`
	CreatedAt        time.Time `json:"created_at,omitempty"`
	UpdatedAt        time.Time `json:"updated_at,omitempty"`
}

// JournalLineRequest represents a single line in a journal entry
type JournalLineRequest struct {
	AccountID    string `json:"account_id"`    // Can be account code or UUID
	Description  string `json:"description,omitempty"`
	DebitAmount  int64  `json:"debit_amount"`  // Amount in smallest currency unit (e.g., kobo for NGN)
	CreditAmount int64  `json:"credit_amount"` // Amount in smallest currency unit
}

// CreateJournalEntryRequest represents a request to create a journal entry
type CreateJournalEntryRequest struct {
	Date        time.Time              `json:"date"`
	Description string                 `json:"description"`
	Reference   string                 `json:"reference,omitempty"`
	Lines       []JournalLineRequest   `json:"lines"`
	PostedBy    string                 `json:"posted_by"`
	Metadata    map[string]interface{} `json:"metadata,omitempty"`
}

// JournalEntryResponse represents the response from creating a journal entry
type JournalEntryResponse struct {
	ID          string                 `json:"id"`
	TenantID    string                 `json:"tenant_id"`
	EntryNumber string                 `json:"entry_number"`
	Date        time.Time              `json:"date"`
	Description string                 `json:"description"`
	Status      string                 `json:"status"`
	Lines       []JournalLine          `json:"lines"`
	Metadata    map[string]interface{} `json:"metadata,omitempty"`
	CreatedAt   time.Time              `json:"created_at"`
	UpdatedAt   time.Time              `json:"updated_at"`
}

// JournalLine represents a line in a journal entry
type JournalLine struct {
	ID           string `json:"id"`
	AccountID    string `json:"account_id"`
	AccountCode  string `json:"account_code"`
	AccountName  string `json:"account_name"`
	Description  string `json:"description"`
	DebitAmount  int64  `json:"debit_amount"`
	CreditAmount int64  `json:"credit_amount"`
}

// CreateAccount creates a new account in the Chart of Accounts
func (c *CoAClient) CreateAccount(tenantID, userID, userRole string, account CoAAccount) (*CoAAccount, error) {
	account.TenantID = tenantID

	body, err := json.Marshal(account)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal account: %w", err)
	}

	req, err := http.NewRequest("POST", c.baseURL+"/api/v1/accounts", bytes.NewBuffer(body))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Tenant-ID", tenantID)
	req.Header.Set("X-User-ID", userID)
	req.Header.Set("X-User-Role", userRole)

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to send request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusCreated {
		bodyBytes, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("failed to create account: %s (status: %d)", string(bodyBytes), resp.StatusCode)
	}

	var result CoAAccount
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}

	return &result, nil
}

// CreateJournalEntry creates a new journal entry
func (c *CoAClient) CreateJournalEntry(tenantID, userID, userRole string, entry CreateJournalEntryRequest) (*JournalEntryResponse, error) {
	body, err := json.Marshal(entry)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal journal entry: %w", err)
	}

	req, err := http.NewRequest("POST", c.baseURL+"/api/v1/journal-entries", bytes.NewBuffer(body))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Tenant-ID", tenantID)
	req.Header.Set("X-User-ID", userID)
	req.Header.Set("X-User-Role", userRole)

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to send request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusCreated {
		bodyBytes, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("failed to create journal entry: %s (status: %d)", string(bodyBytes), resp.StatusCode)
	}

	var result JournalEntryResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}

	return &result, nil
}

// GetAccounts retrieves all accounts for a tenant
func (c *CoAClient) GetAccounts(tenantID, userID, userRole string) ([]CoAAccount, error) {
	req, err := http.NewRequest("GET", c.baseURL+"/api/v1/accounts", nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("X-Tenant-ID", tenantID)
	req.Header.Set("X-User-ID", userID)
	req.Header.Set("X-User-Role", userRole)

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to send request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		bodyBytes, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("failed to get accounts: %s (status: %d)", string(bodyBytes), resp.StatusCode)
	}

	var accounts []CoAAccount
	if err := json.NewDecoder(resp.Body).Decode(&accounts); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}

	return accounts, nil
}

// RecordLoanDisbursement creates a journal entry for loan disbursement
// Debit: Loans Receivable (1400)
// Credit: Customer Account (liability account)
func (c *CoAClient) RecordLoanDisbursement(tenantID, userID, userRole, loanID string, amount int64, customerAccountCode string) (*JournalEntryResponse, error) {
	entry := CreateJournalEntryRequest{
		Date:        time.Now(),
		Description: fmt.Sprintf("Loan disbursement for loan %s", loanID),
		Reference:   loanID,
		PostedBy:    userID,
		Lines: []JournalLineRequest{
			{
				AccountID:    "1400", // Loans Receivable
				Description:  "Loan principal disbursed",
				DebitAmount:  amount,
				CreditAmount: 0,
			},
			{
				AccountID:    customerAccountCode,
				Description:  "Credit to customer account",
				DebitAmount:  0,
				CreditAmount: amount,
			},
		},
		Metadata: map[string]interface{}{
			"loan_id":     loanID,
			"source":      "loan-service",
			"event_type":  "disbursement",
		},
	}

	return c.CreateJournalEntry(tenantID, userID, userRole, entry)
}

// RecordLoanRepayment creates a journal entry for loan repayment
// Debit: Customer Account (or Cash)
// Credit: Loans Receivable (1400)
func (c *CoAClient) RecordLoanRepayment(tenantID, userID, userRole, loanID string, principalAmount, interestAmount int64, sourceAccountCode string) (*JournalEntryResponse, error) {
	totalAmount := principalAmount + interestAmount

	lines := []JournalLineRequest{
		{
			AccountID:    sourceAccountCode,
			Description:  "Loan repayment received",
			DebitAmount:  totalAmount,
			CreditAmount: 0,
		},
		{
			AccountID:    "1400", // Loans Receivable
			Description:  "Principal repayment",
			DebitAmount:  0,
			CreditAmount: principalAmount,
		},
	}

	// If there's interest, add a credit to interest revenue account
	if interestAmount > 0 {
		lines = append(lines, JournalLineRequest{
			AccountID:    "4100", // Interest Revenue
			Description:  "Interest earned",
			DebitAmount:  0,
			CreditAmount: interestAmount,
		})
	}

	entry := CreateJournalEntryRequest{
		Date:        time.Now(),
		Description: fmt.Sprintf("Loan repayment for loan %s", loanID),
		Reference:   loanID,
		PostedBy:    userID,
		Lines:       lines,
		Metadata: map[string]interface{}{
			"loan_id":          loanID,
			"source":           "loan-service",
			"event_type":       "repayment",
			"principal_amount": principalAmount,
			"interest_amount":  interestAmount,
		},
	}

	return c.CreateJournalEntry(tenantID, userID, userRole, entry)
}
