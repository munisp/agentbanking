package main

import (
	"bytes"
	"context"
	"encoding/csv"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"strconv"
	"strings"
	"time"

	"github.com/google/uuid"
)

type ImportJobStatus string

const (
	ImportJobStatusPending    ImportJobStatus = "pending"
	ImportJobStatusProcessing ImportJobStatus = "processing"
	ImportJobStatusCompleted  ImportJobStatus = "completed"
	ImportJobStatusFailed     ImportJobStatus = "failed"
)

type ImportJob struct {
	ID            string          `json:"id"`
	TenantID      string          `json:"tenant_id"`
	JobType       string          `json:"job_type"`
	Status        ImportJobStatus `json:"status"`
	FileName      string          `json:"file_name"`
	TotalRows     int             `json:"total_rows"`
	ProcessedRows int             `json:"processed_rows"`
	SuccessRows   int             `json:"success_rows"`
	ErrorRows     int             `json:"error_rows"`
	Errors        []ImportError   `json:"errors,omitempty"`
	StartedAt     time.Time       `json:"started_at,omitempty"`
	CompletedAt   time.Time       `json:"completed_at,omitempty"`
	CreatedBy     string          `json:"created_by"`
	CreatedAt     time.Time       `json:"created_at"`
}

type ImportError struct {
	Row     int    `json:"row"`
	Column  string `json:"column,omitempty"`
	Message string `json:"message"`
}

type ImportExportService struct {
	store      *PostgresStore
	coaService *ChartOfAccountsService
}

func NewImportExportService(store *PostgresStore, coaService *ChartOfAccountsService) *ImportExportService {
	return &ImportExportService{
		store:      store,
		coaService: coaService,
	}
}

func (s *ImportExportService) ExportAccountsToCSV(ctx context.Context, tenantID string) ([]byte, error) {
	accounts, err := s.coaService.ListAccounts(ctx, tenantID, "", "", false)
	if err != nil {
		return nil, fmt.Errorf("failed to list accounts: %w", err)
	}

	var buf bytes.Buffer
	writer := csv.NewWriter(&buf)

	header := []string{
		"Code", "Name", "Description", "Type", "Normal Balance",
		"Parent Code", "Currency", "CBN Code", "Is Active", "Is System Account",
		"Tags", "Created At",
	}
	if err := writer.Write(header); err != nil {
		return nil, fmt.Errorf("failed to write header: %w", err)
	}

	codeToAccount := make(map[string]Account)
	for _, acc := range accounts {
		codeToAccount[acc.ID] = acc
	}

	for _, acc := range accounts {
		parentCode := ""
		if acc.ParentID != "" {
			if parent, exists := codeToAccount[acc.ParentID]; exists {
				parentCode = parent.Code
			}
		}

		tags := strings.Join(acc.Tags, ";")

		row := []string{
			acc.Code,
			acc.Name,
			acc.Description,
			string(acc.Type),
			string(acc.NormalBalance),
			parentCode,
			acc.Currency,
			acc.CBNCode,
			strconv.FormatBool(acc.IsActive),
			strconv.FormatBool(acc.IsSystemAccount),
			tags,
			acc.CreatedAt.Format(time.RFC3339),
		}

		if err := writer.Write(row); err != nil {
			return nil, fmt.Errorf("failed to write row: %w", err)
		}
	}

	writer.Flush()
	if err := writer.Error(); err != nil {
		return nil, fmt.Errorf("csv writer error: %w", err)
	}

	return buf.Bytes(), nil
}

func (s *ImportExportService) ExportAccountsToJSON(ctx context.Context, tenantID string) ([]byte, error) {
	accounts, err := s.coaService.ListAccounts(ctx, tenantID, "", "", false)
	if err != nil {
		return nil, fmt.Errorf("failed to list accounts: %w", err)
	}

	export := struct {
		TenantID   string    `json:"tenant_id"`
		ExportedAt time.Time `json:"exported_at"`
		Accounts   []Account `json:"accounts"`
	}{
		TenantID:   tenantID,
		ExportedAt: time.Now(),
		Accounts:   accounts,
	}

	return json.MarshalIndent(export, "", "  ")
}

func (s *ImportExportService) ImportAccountsFromCSV(ctx context.Context, tenantID, userID string, data []byte) (*ImportJob, error) {
	job := &ImportJob{
		ID:        uuid.New().String(),
		TenantID:  tenantID,
		JobType:   "accounts_csv",
		Status:    ImportJobStatusPending,
		CreatedBy: userID,
		CreatedAt: time.Now(),
	}

	reader := csv.NewReader(bytes.NewReader(data))

	header, err := reader.Read()
	if err != nil {
		job.Status = ImportJobStatusFailed
		job.Errors = append(job.Errors, ImportError{Row: 1, Message: "Failed to read header: " + err.Error()})
		return job, nil
	}

	columnIndex := make(map[string]int)
	for i, col := range header {
		columnIndex[strings.ToLower(strings.TrimSpace(col))] = i
	}

	requiredColumns := []string{"code", "name", "type"}
	for _, col := range requiredColumns {
		if _, exists := columnIndex[col]; !exists {
			job.Status = ImportJobStatusFailed
			job.Errors = append(job.Errors, ImportError{Row: 1, Message: fmt.Sprintf("Missing required column: %s", col)})
			return job, nil
		}
	}

	job.Status = ImportJobStatusProcessing
	job.StartedAt = time.Now()

	var rows [][]string
	for {
		row, err := reader.Read()
		if err == io.EOF {
			break
		}
		if err != nil {
			job.Errors = append(job.Errors, ImportError{Row: len(rows) + 2, Message: "Failed to read row: " + err.Error()})
			continue
		}
		rows = append(rows, row)
	}

	job.TotalRows = len(rows)

	codeToID := make(map[string]string)
	existingAccounts, _ := s.coaService.ListAccounts(ctx, tenantID, "", "", false)
	for _, acc := range existingAccounts {
		codeToID[acc.Code] = acc.ID
	}

	for i, row := range rows {
		rowNum := i + 2
		job.ProcessedRows++

		code := getColumnValue(row, columnIndex, "code")
		name := getColumnValue(row, columnIndex, "name")
		accountType := getColumnValue(row, columnIndex, "type")

		if code == "" {
			job.Errors = append(job.Errors, ImportError{Row: rowNum, Column: "code", Message: "Code is required"})
			job.ErrorRows++
			continue
		}

		if name == "" {
			job.Errors = append(job.Errors, ImportError{Row: rowNum, Column: "name", Message: "Name is required"})
			job.ErrorRows++
			continue
		}

		if accountType == "" {
			job.Errors = append(job.Errors, ImportError{Row: rowNum, Column: "type", Message: "Type is required"})
			job.ErrorRows++
			continue
		}

		accType := AccountType(strings.ToLower(accountType))
		if !isValidAccountType(accType) {
			job.Errors = append(job.Errors, ImportError{Row: rowNum, Column: "type", Message: fmt.Sprintf("Invalid account type: %s", accountType)})
			job.ErrorRows++
			continue
		}

		description := getColumnValue(row, columnIndex, "description")
		parentCode := getColumnValue(row, columnIndex, "parent code")
		currency := getColumnValue(row, columnIndex, "currency")
		cbnCode := getColumnValue(row, columnIndex, "cbn code")
		tagsStr := getColumnValue(row, columnIndex, "tags")

		if currency == "" {
			currency = "NGN"
		}

		var tags []string
		if tagsStr != "" {
			tags = strings.Split(tagsStr, ";")
			for i := range tags {
				tags[i] = strings.TrimSpace(tags[i])
			}
		}

		parentID := ""
		if parentCode != "" {
			if id, exists := codeToID[parentCode]; exists {
				parentID = id
			}
		}

		req := CreateAccountRequest{
			Code:        code,
			Name:        name,
			Description: description,
			Type:        accType,
			ParentID:    parentID,
			Currency:    currency,
			CBNCode:     cbnCode,
			Tags:        tags,
		}

		account, err := s.coaService.CreateAccount(ctx, tenantID, req)
		if err != nil {
			job.Errors = append(job.Errors, ImportError{Row: rowNum, Message: fmt.Sprintf("Failed to create account: %v", err)})
			job.ErrorRows++
			continue
		}

		codeToID[code] = account.ID
		job.SuccessRows++
	}

	job.Status = ImportJobStatusCompleted
	job.CompletedAt = time.Now()

	if s.store != nil {
		s.store.SaveImportJob(ctx, *job)
	}

	return job, nil
}

func (s *ImportExportService) ImportAccountsFromJSON(ctx context.Context, tenantID, userID string, data []byte) (*ImportJob, error) {
	job := &ImportJob{
		ID:        uuid.New().String(),
		TenantID:  tenantID,
		JobType:   "accounts_json",
		Status:    ImportJobStatusPending,
		CreatedBy: userID,
		CreatedAt: time.Now(),
	}

	var importData struct {
		Accounts []struct {
			Code        string                 `json:"code"`
			Name        string                 `json:"name"`
			Description string                 `json:"description"`
			Type        string                 `json:"type"`
			ParentCode  string                 `json:"parent_code,omitempty"`
			Currency    string                 `json:"currency"`
			CBNCode     string                 `json:"cbn_code,omitempty"`
			Tags        []string               `json:"tags,omitempty"`
			Metadata    map[string]interface{} `json:"metadata,omitempty"`
		} `json:"accounts"`
	}

	if err := json.Unmarshal(data, &importData); err != nil {
		job.Status = ImportJobStatusFailed
		job.Errors = append(job.Errors, ImportError{Row: 0, Message: "Invalid JSON format: " + err.Error()})
		return job, nil
	}

	job.TotalRows = len(importData.Accounts)
	job.Status = ImportJobStatusProcessing
	job.StartedAt = time.Now()

	codeToID := make(map[string]string)
	existingAccounts, _ := s.coaService.ListAccounts(ctx, tenantID, "", "", false)
	for _, acc := range existingAccounts {
		codeToID[acc.Code] = acc.ID
	}

	for i, acc := range importData.Accounts {
		job.ProcessedRows++

		if acc.Code == "" || acc.Name == "" || acc.Type == "" {
			job.Errors = append(job.Errors, ImportError{Row: i + 1, Message: "Code, name, and type are required"})
			job.ErrorRows++
			continue
		}

		accType := AccountType(strings.ToLower(acc.Type))
		if !isValidAccountType(accType) {
			job.Errors = append(job.Errors, ImportError{Row: i + 1, Message: fmt.Sprintf("Invalid account type: %s", acc.Type)})
			job.ErrorRows++
			continue
		}

		currency := acc.Currency
		if currency == "" {
			currency = "NGN"
		}

		parentID := ""
		if acc.ParentCode != "" {
			if id, exists := codeToID[acc.ParentCode]; exists {
				parentID = id
			}
		}

		req := CreateAccountRequest{
			Code:        acc.Code,
			Name:        acc.Name,
			Description: acc.Description,
			Type:        accType,
			ParentID:    parentID,
			Currency:    currency,
			CBNCode:     acc.CBNCode,
			Tags:        acc.Tags,
			Metadata:    acc.Metadata,
		}

		account, err := s.coaService.CreateAccount(ctx, tenantID, req)
		if err != nil {
			job.Errors = append(job.Errors, ImportError{Row: i + 1, Message: fmt.Sprintf("Failed to create account: %v", err)})
			job.ErrorRows++
			continue
		}

		codeToID[acc.Code] = account.ID
		job.SuccessRows++
	}

	job.Status = ImportJobStatusCompleted
	job.CompletedAt = time.Now()

	if s.store != nil {
		s.store.SaveImportJob(ctx, *job)
	}

	return job, nil
}

func (s *ImportExportService) ExportJournalEntriesToCSV(ctx context.Context, tenantID string, startDate, endDate *time.Time) ([]byte, error) {
	entries, err := s.coaService.ListJournalEntries(ctx, tenantID)
	if err != nil {
		return nil, fmt.Errorf("failed to list journal entries: %w", err)
	}

	var filteredEntries []JournalEntry
	for _, entry := range entries {
		if startDate != nil && entry.EntryDate.Before(*startDate) {
			continue
		}
		if endDate != nil && entry.EntryDate.After(*endDate) {
			continue
		}
		filteredEntries = append(filteredEntries, entry)
	}

	var buf bytes.Buffer
	writer := csv.NewWriter(&buf)

	header := []string{
		"Entry Number", "Entry Date", "Description", "Reference", "Status",
		"Account Code", "Account Name", "Debit", "Credit", "Line Description",
		"Currency", "Posted At", "Posted By",
	}
	if err := writer.Write(header); err != nil {
		return nil, fmt.Errorf("failed to write header: %w", err)
	}

	for _, entry := range filteredEntries {
		for _, line := range entry.Lines {
			row := []string{
				entry.EntryNumber,
				entry.EntryDate.Format("2006-01-02"),
				entry.Description,
				entry.Reference,
				string(entry.Status),
				line.AccountCode,
				line.AccountName,
				strconv.FormatInt(line.DebitAmount, 10),
				strconv.FormatInt(line.CreditAmount, 10),
				line.Description,
				entry.Currency,
				entry.PostedAt.Format(time.RFC3339),
				entry.PostedBy,
			}

			if err := writer.Write(row); err != nil {
				return nil, fmt.Errorf("failed to write row: %w", err)
			}
		}
	}

	writer.Flush()
	if err := writer.Error(); err != nil {
		return nil, fmt.Errorf("csv writer error: %w", err)
	}

	return buf.Bytes(), nil
}

func (s *ImportExportService) ExportTrialBalanceToCSV(ctx context.Context, tenantID string, asOfDate time.Time) ([]byte, error) {
	trialBalance, err := s.coaService.GetTrialBalance(ctx, tenantID, asOfDate.Format("2006-01-02"))
	if err != nil {
		return nil, fmt.Errorf("failed to get trial balance: %w", err)
	}

	var buf bytes.Buffer
	writer := csv.NewWriter(&buf)

	header := []string{"Account Code", "Account Name", "Account Type", "Debit Balance", "Credit Balance"}
	if err := writer.Write(header); err != nil {
		return nil, fmt.Errorf("failed to write header: %w", err)
	}

	for _, acc := range trialBalance.Accounts {
		row := []string{
			acc.AccountCode,
			acc.AccountName,
			string(acc.AccountType),
			strconv.FormatInt(acc.DebitBalance, 10),
			strconv.FormatInt(acc.CreditBalance, 10),
		}

		if err := writer.Write(row); err != nil {
			return nil, fmt.Errorf("failed to write row: %w", err)
		}
	}

	totalsRow := []string{
		"",
		"TOTALS",
		"",
		strconv.FormatInt(trialBalance.TotalDebits, 10),
		strconv.FormatInt(trialBalance.TotalCredits, 10),
	}
	if err := writer.Write(totalsRow); err != nil {
		return nil, fmt.Errorf("failed to write totals row: %w", err)
	}

	writer.Flush()
	if err := writer.Error(); err != nil {
		return nil, fmt.Errorf("csv writer error: %w", err)
	}

	return buf.Bytes(), nil
}

func (s *ImportExportService) GetImportJob(ctx context.Context, tenantID, jobID string) (*ImportJob, error) {
	if s.store == nil {
		return nil, errors.New("postgres store not initialized")
	}

	return s.store.GetImportJob(ctx, tenantID, jobID)
}

func (s *ImportExportService) GenerateCSVTemplate(accountType string) []byte {
	var buf bytes.Buffer
	writer := csv.NewWriter(&buf)

	header := []string{
		"Code", "Name", "Description", "Type", "Parent Code",
		"Currency", "CBN Code", "Tags",
	}
	writer.Write(header)

	examples := [][]string{
		{"1000", "Cash and Cash Equivalents", "All cash accounts", "asset", "", "NGN", "SFP001", "cash;liquid"},
		{"1100", "Cash on Hand", "Physical cash", "asset", "1000", "NGN", "", "cash"},
		{"1200", "Bank Balances", "Bank account balances", "asset", "1000", "NGN", "", "bank"},
		{"2000", "Liabilities", "All liability accounts", "liability", "", "NGN", "", ""},
		{"2100", "Customer Deposits", "Customer deposit accounts", "liability", "2000", "NGN", "SFP012", "deposits"},
		{"4000", "Revenue", "All revenue accounts", "revenue", "", "NGN", "", ""},
		{"4100", "Interest Income", "Interest earned on loans", "revenue", "4000", "NGN", "PL001", "interest"},
		{"5000", "Expenses", "All expense accounts", "expense", "", "NGN", "", ""},
		{"5100", "Interest Expense", "Interest paid on deposits", "expense", "5000", "NGN", "PL002", "interest"},
	}

	for _, example := range examples {
		writer.Write(example)
	}

	writer.Flush()
	return buf.Bytes()
}

func getColumnValue(row []string, columnIndex map[string]int, columnName string) string {
	if idx, exists := columnIndex[strings.ToLower(columnName)]; exists && idx < len(row) {
		return strings.TrimSpace(row[idx])
	}
	return ""
}

func isValidAccountType(t AccountType) bool {
	switch t {
	case AccountTypeAsset, AccountTypeLiability, AccountTypeEquity, AccountTypeRevenue, AccountTypeExpense:
		return true
	default:
		return false
	}
}
