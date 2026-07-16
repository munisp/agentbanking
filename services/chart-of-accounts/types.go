package main

import (
	"time"
)

type AccountType string

const (
	AccountTypeAsset     AccountType = "asset"
	AccountTypeLiability AccountType = "liability"
	AccountTypeEquity    AccountType = "equity"
	AccountTypeRevenue   AccountType = "revenue"
	AccountTypeExpense   AccountType = "expense"
)

type NormalBalance string

const (
	NormalBalanceDebit  NormalBalance = "debit"
	NormalBalanceCredit NormalBalance = "credit"
)

type AccountCategory struct {
	Type          AccountType   `json:"type"`
	Name          string        `json:"name"`
	Description   string        `json:"description"`
	NormalBalance NormalBalance `json:"normal_balance"`
	CodeRange     string        `json:"code_range"`
	Subcategories []Subcategory `json:"subcategories"`
}

type Subcategory struct {
	Code        string `json:"code"`
	Name        string `json:"name"`
	Description string `json:"description"`
}

type Account struct {
	ID                string                 `json:"id"`
	TenantID          string                 `json:"tenant_id"`
	Code              string                 `json:"code"`
	Name              string                 `json:"name"`
	Description       string                 `json:"description,omitempty"`
	Type              AccountType            `json:"type"`
	NormalBalance     NormalBalance          `json:"normal_balance"`
	ParentID          string                 `json:"parent_id,omitempty"`
	Level             int                    `json:"level"`
	IsActive          bool                   `json:"is_active"`
	IsSystemAccount   bool                   `json:"is_system_account"`
	Currency          string                 `json:"currency"`
	TigerBeetleID     string                 `json:"tigerbeetle_id,omitempty"`
	TigerBeetleLedger uint32                 `json:"tigerbeetle_ledger"`
	TigerBeetleCode   uint16                 `json:"tigerbeetle_code"`
	CBNCode           string                 `json:"cbn_code,omitempty"`
	Tags              []string               `json:"tags,omitempty"`
	Metadata          map[string]interface{} `json:"metadata,omitempty"`
	CreatedAt         time.Time              `json:"created_at"`
	UpdatedAt         time.Time              `json:"updated_at"`
	
	// Optional balance fields (populated when include_balance=true in query)
	CurrentBalance    *int64 `json:"current_balance,omitempty"`
	DebitBalance      *int64 `json:"debit_balance,omitempty"`
	CreditBalance     *int64 `json:"credit_balance,omitempty"`
}

type AccountBalance struct {
	AccountID      string    `json:"account_id"`
	AccountCode    string    `json:"account_code"`
	AccountName    string    `json:"account_name"`
	Currency       string    `json:"currency"`
	DebitBalance   int64     `json:"debit_balance"`
	CreditBalance  int64     `json:"credit_balance"`
	PendingDebits  int64     `json:"pending_debits"`
	PendingCredits int64     `json:"pending_credits"`
	NetBalance     int64     `json:"net_balance"`
	BalanceType    string    `json:"balance_type"`
	AsOfDate       time.Time `json:"as_of_date"`
}

type AccountHistory struct {
	AccountID    string              `json:"account_id"`
	Transactions []TransactionRecord `json:"transactions"`
	TotalCount   int                 `json:"total_count"`
}

type TransactionRecord struct {
	TransactionID  string    `json:"transaction_id"`
	JournalEntryID string    `json:"journal_entry_id"`
	Date           time.Time `json:"date"`
	Description    string    `json:"description"`
	DebitAmount    int64     `json:"debit_amount"`
	CreditAmount   int64     `json:"credit_amount"`
	RunningBalance int64     `json:"running_balance"`
	Reference      string    `json:"reference,omitempty"`
	CounterpartyID string    `json:"counterparty_id,omitempty"`
}

type JournalEntryStatus string

const (
	JournalEntryStatusDraft    JournalEntryStatus = "draft"
	JournalEntryStatusPending  JournalEntryStatus = "pending"
	JournalEntryStatusPosted   JournalEntryStatus = "posted"
	JournalEntryStatusRejected JournalEntryStatus = "rejected"
	JournalEntryStatusReversed JournalEntryStatus = "reversed"
)

type JournalEntry struct {
	ID                    string                 `json:"id"`
	TenantID              string                 `json:"tenant_id"`
	EntryNumber           string                 `json:"entry_number"`
	Date                  time.Time              `json:"date"`
	EntryDate             time.Time              `json:"entry_date"`
	Description           string                 `json:"description"`
	Reference             string                 `json:"reference,omitempty"`
	Lines                 []JournalLine          `json:"lines"`
	Status                JournalEntryStatus     `json:"status"`
	Currency              string                 `json:"currency"`
	IsReversed            bool                   `json:"is_reversed"`
	ReversalOf            string                 `json:"reversal_of,omitempty"`
	ReversedBy            string                 `json:"reversed_by,omitempty"`
	ReversedAt            *time.Time             `json:"reversed_at,omitempty"`
	ReversalReason        string                 `json:"reversal_reason,omitempty"`
	OriginalEntryID       string                 `json:"original_entry_id,omitempty"`
	TigerBeetleIDs        []string               `json:"tigerbeetle_ids,omitempty"`
	TigerBeetleTransferID string                 `json:"tigerbeetle_transfer_id,omitempty"`
	TotalDebit            int64                  `json:"total_debit"`
	TotalCredit           int64                  `json:"total_credit"`
	PostedBy              string                 `json:"posted_by"`
	PostedAt              *time.Time             `json:"posted_at,omitempty"`
	ApprovedBy            string                 `json:"approved_by,omitempty"`
	Metadata              map[string]interface{} `json:"metadata,omitempty"`
	CreatedAt             time.Time              `json:"created_at"`
	UpdatedAt             time.Time              `json:"updated_at"`
}

type JournalLine struct {
	ID           string `json:"id"`
	AccountID    string `json:"account_id"`
	AccountCode  string `json:"account_code"`
	AccountName  string `json:"account_name"`
	Description  string `json:"description,omitempty"`
	DebitAmount  int64  `json:"debit_amount"`
	CreditAmount int64  `json:"credit_amount"`
}

type TrialBalance struct {
	TenantID     string             `json:"tenant_id"`
	AsOfDate     string             `json:"as_of_date"`
	Accounts     []TrialBalanceLine `json:"accounts"`
	TotalDebits  int64              `json:"total_debits"`
	TotalCredits int64              `json:"total_credits"`
	IsBalanced   bool               `json:"is_balanced"`
	GeneratedAt  time.Time          `json:"generated_at"`
}

type TrialBalanceLine struct {
	AccountCode   string `json:"account_code"`
	AccountName   string `json:"account_name"`
	AccountType   string `json:"account_type"`
	DebitBalance  int64  `json:"debit_balance"`
	CreditBalance int64  `json:"credit_balance"`
}

type BalanceSheet struct {
	TenantID         string              `json:"tenant_id"`
	AsOfDate         string              `json:"as_of_date"`
	Assets           BalanceSheetSection `json:"assets"`
	Liabilities      BalanceSheetSection `json:"liabilities"`
	Equity           BalanceSheetSection `json:"equity"`
	TotalAssets      int64               `json:"total_assets"`
	TotalLiabilities int64               `json:"total_liabilities"`
	TotalEquity      int64               `json:"total_equity"`
	IsBalanced       bool                `json:"is_balanced"`
	GeneratedAt      time.Time           `json:"generated_at"`
}

type BalanceSheetSection struct {
	Name     string             `json:"name"`
	Items    []BalanceSheetItem `json:"items"`
	Subtotal int64              `json:"subtotal"`
}

type BalanceSheetItem struct {
	AccountCode string `json:"account_code"`
	AccountName string `json:"account_name"`
	Balance     int64  `json:"balance"`
	Level       int    `json:"level"`
}

type IncomeStatement struct {
	TenantID      string                 `json:"tenant_id"`
	StartDate     string                 `json:"start_date"`
	EndDate       string                 `json:"end_date"`
	Revenue       IncomeStatementSection `json:"revenue"`
	Expenses      IncomeStatementSection `json:"expenses"`
	TotalRevenue  int64                  `json:"total_revenue"`
	TotalExpenses int64                  `json:"total_expenses"`
	NetIncome     int64                  `json:"net_income"`
	GeneratedAt   time.Time              `json:"generated_at"`
}

type IncomeStatementSection struct {
	Name     string                `json:"name"`
	Items    []IncomeStatementItem `json:"items"`
	Subtotal int64                 `json:"subtotal"`
}

type IncomeStatementItem struct {
	AccountCode string `json:"account_code"`
	AccountName string `json:"account_name"`
	Amount      int64  `json:"amount"`
}

type CBNReturn struct {
	TenantID      string                 `json:"tenant_id"`
	ReturnType    string                 `json:"return_type"`
	ReportingDate string                 `json:"reporting_date"`
	Data          map[string]interface{} `json:"data"`
	GeneratedAt   time.Time              `json:"generated_at"`
}

type CBNAccountMapping struct {
	CBNCode    string `json:"cbn_code"`
	CBNName    string `json:"cbn_name"`
	CoACode    string `json:"coa_code"`
	CoAName    string `json:"coa_name"`
	ReturnType string `json:"return_type"`
	LineNumber string `json:"line_number"`
}

type ReconciliationResult struct {
	TenantID        string        `json:"tenant_id"`
	StartedAt       time.Time     `json:"started_at"`
	CompletedAt     time.Time     `json:"completed_at"`
	AccountsChecked int           `json:"accounts_checked"`
	Discrepancies   []Discrepancy `json:"discrepancies"`
	Status          string        `json:"status"`
}

type Discrepancy struct {
	AccountID          string `json:"account_id"`
	AccountCode        string `json:"account_code"`
	Type               string `json:"type"`
	CoABalance         int64  `json:"coa_balance"`
	TigerBeetleBalance int64  `json:"tigerbeetle_balance"`
	Difference         int64  `json:"difference"`
	Severity           string `json:"severity"`
}

type ReconciliationStatus struct {
	TenantID           string    `json:"tenant_id"`
	LastReconciliation time.Time `json:"last_reconciliation"`
	Status             string    `json:"status"`
	DiscrepancyCount   int       `json:"discrepancy_count"`
}

// TenantCOAMapping links a semantic key (e.g. "loans.interest.sme") to a
// tenant-specific COA account UUID so services never hardcode account codes.
type TenantCOAMapping struct {
	ID          string    `json:"id"`
	TenantID    string    `json:"tenant_id"`
	MappingKey  string    `json:"mapping_key"`
	AccountID   string    `json:"account_id"`
	AccountCode string    `json:"account_code,omitempty"`
	AccountName string    `json:"account_name,omitempty"`
	Description string    `json:"description,omitempty"`
	CreatedAt   time.Time `json:"created_at"`
	UpdatedAt   time.Time `json:"updated_at"`
}

type UpsertCOAMappingRequest struct {
	MappingKey  string `json:"mapping_key"`
	AccountID   string `json:"account_id"`
	Description string `json:"description,omitempty"`
}

type CreateAccountRequest struct {
	Code        string                 `json:"code"`
	Name        string                 `json:"name"`
	Description string                 `json:"description,omitempty"`
	Type        AccountType            `json:"type"`
	ParentID    string                 `json:"parent_id,omitempty"`
	Currency    string                 `json:"currency,omitempty"`
	CBNCode     string                 `json:"cbn_code,omitempty"`
	Tags        []string               `json:"tags,omitempty"`
	Metadata    map[string]interface{} `json:"metadata,omitempty"`
}

type UpdateAccountRequest struct {
	Name        string                 `json:"name,omitempty"`
	Description string                 `json:"description,omitempty"`
	IsActive    *bool                  `json:"is_active,omitempty"`
	CBNCode     string                 `json:"cbn_code,omitempty"`
	Tags        []string               `json:"tags,omitempty"`
	Metadata    map[string]interface{} `json:"metadata,omitempty"`
}

type CreateJournalEntryRequest struct {
	Date        time.Time              `json:"date"`
	Description string                 `json:"description"`
	Reference   string                 `json:"reference,omitempty"`
	Lines       []JournalLineRequest   `json:"lines"`
	PostedBy    string                 `json:"posted_by"`
	Metadata    map[string]interface{} `json:"metadata,omitempty"`
}

type JournalLineRequest struct {
	AccountID    string `json:"account_id"`
	Description  string `json:"description,omitempty"`
	DebitAmount  int64  `json:"debit_amount"`
	CreditAmount int64  `json:"credit_amount"`
}

type AccountHierarchy struct {
	TenantID string        `json:"tenant_id"`
	Roots    []AccountNode `json:"roots"`
}

type AccountNode struct {
	Account  Account       `json:"account"`
	Children []AccountNode `json:"children,omitempty"`
}

type ServiceHealth struct {
	Status             string `json:"status"`
	TigerBeetleHealthy bool   `json:"tigerbeetle_healthy"`
	RedisHealthy       bool   `json:"redis_healthy"`
	KafkaHealthy       bool   `json:"kafka_healthy"`
	PostgresHealthy    bool   `json:"postgres_healthy"`
}

type CoAEvent struct {
	EventID     string                 `json:"event_id"`
	EventType   string                 `json:"event_type"`
	TenantID    string                 `json:"tenant_id"`
	EntityID    string                 `json:"entity_id"`
	EntityType  string                 `json:"entity_type"`
	Payload     map[string]interface{} `json:"payload"`
	Timestamp   time.Time              `json:"timestamp"`
	ServiceName string                 `json:"service_name"`
}

const (
	EventAccountCreated       = "account.created"
	EventAccountUpdated       = "account.updated"
	EventAccountDeleted       = "account.deleted"
	EventJournalEntryCreated  = "journal_entry.created"
	EventJournalEntryReversed = "journal_entry.reversed"
	EventReconciliationRun    = "reconciliation.run"
	EventCBNReturnGenerated   = "cbn_return.generated"
)

type AuditLogEntry struct {
	ID         string                 `json:"id"`
	TenantID   string                 `json:"tenant_id"`
	EntityType string                 `json:"entity_type"`
	EntityID   string                 `json:"entity_id"`
	Action     string                 `json:"action"`
	UserID     string                 `json:"user_id"`
	UserRole   string                 `json:"user_role"`
	Resource   string                 `json:"resource"`
	ResourceID string                 `json:"resource_id,omitempty"`
	IPAddress  string                 `json:"ip_address"`
	UserAgent  string                 `json:"user_agent"`
	Timestamp  time.Time              `json:"timestamp"`
	Details    map[string]interface{} `json:"details,omitempty"`
	OldValues  map[string]interface{} `json:"old_values,omitempty"`
	NewValues  map[string]interface{} `json:"new_values,omitempty"`
	CreatedAt  time.Time              `json:"created_at"`
}
