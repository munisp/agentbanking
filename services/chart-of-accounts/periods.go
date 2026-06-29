package main

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/google/uuid"
)

type PeriodType string

const (
	PeriodTypeMonthly    PeriodType = "monthly"
	PeriodTypeQuarterly  PeriodType = "quarterly"
	PeriodTypeAnnual     PeriodType = "annual"
	PeriodTypeAdjustment PeriodType = "adjustment"
)

type PeriodStatus string

const (
	PeriodStatusOpen       PeriodStatus = "open"
	PeriodStatusSoftClosed PeriodStatus = "soft_closed"
	PeriodStatusHardClosed PeriodStatus = "hard_closed"
	PeriodStatusLocked     PeriodStatus = "locked"
)

type AccountingPeriod struct {
	ID                 string       `json:"id"`
	TenantID           string       `json:"tenant_id"`
	Name               string       `json:"name"`
	PeriodType         PeriodType   `json:"period_type"`
	StartDate          time.Time    `json:"start_date"`
	EndDate            time.Time    `json:"end_date"`
	Status             PeriodStatus `json:"status"`
	ClosedAt           time.Time    `json:"closed_at,omitempty"`
	ClosedBy           string       `json:"closed_by,omitempty"`
	FiscalYear         int          `json:"fiscal_year"`
	PeriodNumber       int          `json:"period_number"`
	IsAdjustmentPeriod bool         `json:"is_adjustment_period"`
	CreatedAt          time.Time    `json:"created_at"`
	UpdatedAt          time.Time    `json:"updated_at"`
}

type PeriodCloseResult struct {
	PeriodID          string           `json:"period_id"`
	Status            PeriodStatus     `json:"status"`
	ClosedAt          time.Time        `json:"closed_at"`
	ClosedBy          string           `json:"closed_by"`
	TrialBalanceValid bool             `json:"trial_balance_valid"`
	TotalDebits       int64            `json:"total_debits"`
	TotalCredits      int64            `json:"total_credits"`
	UnpostedEntries   int              `json:"unposted_entries"`
	Warnings          []string         `json:"warnings,omitempty"`
	Errors            []string         `json:"errors,omitempty"`
	ClosingEntries    []JournalEntry   `json:"closing_entries,omitempty"`
	RetainedEarnings  int64            `json:"retained_earnings,omitempty"`
	AccountBalances   map[string]int64 `json:"account_balances,omitempty"`
}

type PeriodService struct {
	store      *PostgresStore
	coaService *ChartOfAccountsService
}

func NewPeriodService(store *PostgresStore, coaService *ChartOfAccountsService) *PeriodService {
	return &PeriodService{
		store:      store,
		coaService: coaService,
	}
}

func (s *PeriodService) CreateFiscalYear(ctx context.Context, tenantID string, year int, startMonth int) ([]AccountingPeriod, error) {
	var periods []AccountingPeriod
	now := time.Now()

	startDate := time.Date(year, time.Month(startMonth), 1, 0, 0, 0, 0, time.UTC)

	for i := 0; i < 12; i++ {
		periodStart := startDate.AddDate(0, i, 0)
		periodEnd := periodStart.AddDate(0, 1, -1)

		period := AccountingPeriod{
			ID:                 uuid.New().String(),
			TenantID:           tenantID,
			Name:               fmt.Sprintf("%s %d", periodStart.Month().String(), periodStart.Year()),
			PeriodType:         PeriodTypeMonthly,
			StartDate:          periodStart,
			EndDate:            periodEnd,
			Status:             PeriodStatusOpen,
			FiscalYear:         year,
			PeriodNumber:       i + 1,
			IsAdjustmentPeriod: false,
			CreatedAt:          now,
			UpdatedAt:          now,
		}

		if s.store != nil {
			if err := s.store.SaveAccountingPeriod(ctx, period); err != nil {
				return nil, fmt.Errorf("failed to save period %d: %w", i+1, err)
			}
		}

		periods = append(periods, period)
	}

	adjustmentPeriod := AccountingPeriod{
		ID:                 uuid.New().String(),
		TenantID:           tenantID,
		Name:               fmt.Sprintf("Adjustment Period FY%d", year),
		PeriodType:         PeriodTypeAdjustment,
		StartDate:          startDate.AddDate(0, 12, -1),
		EndDate:            startDate.AddDate(0, 12, -1),
		Status:             PeriodStatusOpen,
		FiscalYear:         year,
		PeriodNumber:       13,
		IsAdjustmentPeriod: true,
		CreatedAt:          now,
		UpdatedAt:          now,
	}

	if s.store != nil {
		if err := s.store.SaveAccountingPeriod(ctx, adjustmentPeriod); err != nil {
			return nil, fmt.Errorf("failed to save adjustment period: %w", err)
		}
	}

	periods = append(periods, adjustmentPeriod)

	return periods, nil
}

func (s *PeriodService) GetPeriodForDate(ctx context.Context, tenantID string, date time.Time) (*AccountingPeriod, error) {
	if s.store == nil {
		return nil, errors.New("postgres store not initialized")
	}

	return s.store.GetOpenPeriodForDate(ctx, tenantID, date)
}

func (s *PeriodService) ListPeriods(ctx context.Context, tenantID string, fiscalYear int) ([]AccountingPeriod, error) {
	if s.store == nil {
		return nil, errors.New("postgres store not initialized")
	}

	return s.store.ListAccountingPeriods(ctx, tenantID, fiscalYear)
}

func (s *PeriodService) SoftClosePeriod(ctx context.Context, tenantID, periodID, userID string) (*PeriodCloseResult, error) {
	if s.store == nil {
		return nil, errors.New("postgres store not initialized")
	}

	period, err := s.store.GetAccountingPeriod(ctx, tenantID, periodID)
	if err != nil {
		return nil, err
	}
	if period == nil {
		return nil, errors.New("period not found")
	}

	if period.Status != PeriodStatusOpen {
		return nil, fmt.Errorf("period is already %s", period.Status)
	}

	result := &PeriodCloseResult{
		PeriodID: periodID,
		ClosedBy: userID,
	}

	trialBalance, err := s.coaService.GetTrialBalance(ctx, tenantID, period.EndDate.Format("2006-01-02"))
	if err != nil {
		result.Errors = append(result.Errors, fmt.Sprintf("Failed to get trial balance: %v", err))
	} else {
		result.TotalDebits = trialBalance.TotalDebits
		result.TotalCredits = trialBalance.TotalCredits
		result.TrialBalanceValid = trialBalance.IsBalanced
		if !trialBalance.IsBalanced {
			result.Warnings = append(result.Warnings, "Trial balance is not balanced")
		}
	}

	entries, err := s.coaService.ListJournalEntries(ctx, tenantID)
	if err == nil {
		for _, entry := range entries {
			if entry.Status == JournalEntryStatusDraft || entry.Status == JournalEntryStatusPending {
				if !entry.EntryDate.Before(period.StartDate) && !entry.EntryDate.After(period.EndDate) {
					result.UnpostedEntries++
				}
			}
		}
		if result.UnpostedEntries > 0 {
			result.Warnings = append(result.Warnings, fmt.Sprintf("%d unposted journal entries in this period", result.UnpostedEntries))
		}
	}

	period.Status = PeriodStatusSoftClosed
	period.ClosedAt = time.Now()
	period.ClosedBy = userID
	period.UpdatedAt = time.Now()

	if err := s.store.SaveAccountingPeriod(ctx, *period); err != nil {
		return nil, fmt.Errorf("failed to update period: %w", err)
	}

	result.Status = PeriodStatusSoftClosed
	result.ClosedAt = period.ClosedAt

	return result, nil
}

func (s *PeriodService) HardClosePeriod(ctx context.Context, tenantID, periodID, userID string) (*PeriodCloseResult, error) {
	if s.store == nil {
		return nil, errors.New("postgres store not initialized")
	}

	period, err := s.store.GetAccountingPeriod(ctx, tenantID, periodID)
	if err != nil {
		return nil, err
	}
	if period == nil {
		return nil, errors.New("period not found")
	}

	if period.Status != PeriodStatusSoftClosed {
		return nil, fmt.Errorf("period must be soft closed first (current status: %s)", period.Status)
	}

	result := &PeriodCloseResult{
		PeriodID: periodID,
		ClosedBy: userID,
	}

	trialBalance, err := s.coaService.GetTrialBalance(ctx, tenantID, period.EndDate.Format("2006-01-02"))
	if err != nil {
		return nil, fmt.Errorf("failed to get trial balance: %w", err)
	}

	if !trialBalance.IsBalanced {
		return nil, errors.New("cannot hard close period: trial balance is not balanced")
	}

	result.TotalDebits = trialBalance.TotalDebits
	result.TotalCredits = trialBalance.TotalCredits
	result.TrialBalanceValid = true

	if period.PeriodNumber == 12 || period.IsAdjustmentPeriod {
		closingEntries, retainedEarnings, err := s.generateClosingEntries(ctx, tenantID, period)
		if err != nil {
			result.Warnings = append(result.Warnings, fmt.Sprintf("Failed to generate closing entries: %v", err))
		} else {
			result.ClosingEntries = closingEntries
			result.RetainedEarnings = retainedEarnings
		}
	}

	period.Status = PeriodStatusHardClosed
	period.ClosedAt = time.Now()
	period.ClosedBy = userID
	period.UpdatedAt = time.Now()

	if err := s.store.SaveAccountingPeriod(ctx, *period); err != nil {
		return nil, fmt.Errorf("failed to update period: %w", err)
	}

	result.Status = PeriodStatusHardClosed
	result.ClosedAt = period.ClosedAt

	return result, nil
}

func (s *PeriodService) LockPeriod(ctx context.Context, tenantID, periodID, userID string) error {
	if s.store == nil {
		return errors.New("postgres store not initialized")
	}

	period, err := s.store.GetAccountingPeriod(ctx, tenantID, periodID)
	if err != nil {
		return err
	}
	if period == nil {
		return errors.New("period not found")
	}

	if period.Status != PeriodStatusHardClosed {
		return fmt.Errorf("period must be hard closed first (current status: %s)", period.Status)
	}

	period.Status = PeriodStatusLocked
	period.UpdatedAt = time.Now()

	return s.store.SaveAccountingPeriod(ctx, *period)
}

func (s *PeriodService) ReopenPeriod(ctx context.Context, tenantID, periodID, userID, reason string) error {
	if s.store == nil {
		return errors.New("postgres store not initialized")
	}

	period, err := s.store.GetAccountingPeriod(ctx, tenantID, periodID)
	if err != nil {
		return err
	}
	if period == nil {
		return errors.New("period not found")
	}

	if period.Status == PeriodStatusLocked {
		return errors.New("cannot reopen a locked period")
	}

	if period.Status == PeriodStatusOpen {
		return errors.New("period is already open")
	}

	period.Status = PeriodStatusOpen
	period.ClosedAt = time.Time{}
	period.ClosedBy = ""
	period.UpdatedAt = time.Now()

	return s.store.SaveAccountingPeriod(ctx, *period)
}

func (s *PeriodService) CanPostToDate(ctx context.Context, tenantID string, date time.Time) (bool, string, error) {
	if s.store == nil {
		return true, "", nil
	}

	period, err := s.store.GetOpenPeriodForDate(ctx, tenantID, date)
	if err != nil {
		return false, "", err
	}

	if period == nil {
		return false, "No open accounting period found for this date", nil
	}

	switch period.Status {
	case PeriodStatusOpen:
		return true, "", nil
	case PeriodStatusSoftClosed:
		return true, "Warning: Period is soft closed. Posting is allowed but discouraged.", nil
	case PeriodStatusHardClosed:
		return false, "Period is hard closed. No posting allowed.", nil
	case PeriodStatusLocked:
		return false, "Period is locked. No posting allowed.", nil
	default:
		return false, fmt.Sprintf("Unknown period status: %s", period.Status), nil
	}
}

func (s *PeriodService) generateClosingEntries(ctx context.Context, tenantID string, period *AccountingPeriod) ([]JournalEntry, int64, error) {
	incomeStatement, err := s.coaService.GetIncomeStatement(ctx, tenantID, period.StartDate.Format("2006-01-02"), period.EndDate.Format("2006-01-02"))
	if err != nil {
		return nil, 0, err
	}

	var closingEntries []JournalEntry
	now := time.Now()
	netIncome := incomeStatement.NetIncome

	accounts, err := s.coaService.ListAccounts(ctx, tenantID, "", "", true)
	if err != nil {
		return nil, 0, err
	}

	var incomeSummaryID string
	var retainedEarningsID string
	for _, acc := range accounts {
		if acc.Code == "3900" || acc.Name == "Income Summary" {
			incomeSummaryID = acc.ID
		}
		if acc.Code == "3200" || acc.Name == "Retained Earnings" {
			retainedEarningsID = acc.ID
		}
	}

	if incomeSummaryID == "" || retainedEarningsID == "" {
		return nil, netIncome, errors.New("income summary or retained earnings account not found")
	}

	var revenueLines []JournalLine
	for _, item := range incomeStatement.Revenue.Items {
		if item.Amount > 0 {
			revenueLines = append(revenueLines, JournalLine{
				AccountCode: item.AccountCode,
				AccountName: item.AccountName,
				DebitAmount: item.Amount,
			})
		}
	}

	if len(revenueLines) > 0 {
		var totalRevenue int64
		for _, line := range revenueLines {
			totalRevenue += line.DebitAmount
		}
		revenueLines = append(revenueLines, JournalLine{
			AccountCode:  "3900",
			AccountName:  "Income Summary",
			CreditAmount: totalRevenue,
		})

		nowPosted := now
		revenueClosingEntry := JournalEntry{
			ID:          uuid.New().String(),
			TenantID:    tenantID,
			EntryNumber: fmt.Sprintf("CLOSE-REV-%d-%02d", period.FiscalYear, period.PeriodNumber),
			Date:        period.EndDate,
			EntryDate:   period.EndDate,
			Description: fmt.Sprintf("Close revenue accounts for %s", period.Name),
			Status:      JournalEntryStatusPosted,
			Lines:       revenueLines,
			Currency:    "NGN",
			PostedAt:    &nowPosted,
			CreatedAt:   now,
			UpdatedAt:   now,
		}
		closingEntries = append(closingEntries, revenueClosingEntry)
	}

	var expenseLines []JournalLine
	for _, item := range incomeStatement.Expenses.Items {
		if item.Amount > 0 {
			expenseLines = append(expenseLines, JournalLine{
				AccountCode:  item.AccountCode,
				AccountName:  item.AccountName,
				CreditAmount: item.Amount,
			})
		}
	}

	if len(expenseLines) > 0 {
		var totalExpenses int64
		for _, line := range expenseLines {
			totalExpenses += line.CreditAmount
		}
		expenseLines = append([]JournalLine{{
			AccountCode: "3900",
			AccountName: "Income Summary",
			DebitAmount: totalExpenses,
		}}, expenseLines...)

		nowPosted := now
		expenseClosingEntry := JournalEntry{
			ID:          uuid.New().String(),
			TenantID:    tenantID,
			EntryNumber: fmt.Sprintf("CLOSE-EXP-%d-%02d", period.FiscalYear, period.PeriodNumber),
			Date:        period.EndDate,
			EntryDate:   period.EndDate,
			Description: fmt.Sprintf("Close expense accounts for %s", period.Name),
			Status:      JournalEntryStatusPosted,
			Lines:       expenseLines,
			Currency:    "NGN",
			PostedAt:    &nowPosted,
			CreatedAt:   now,
			UpdatedAt:   now,
		}
		closingEntries = append(closingEntries, expenseClosingEntry)
	}

	if netIncome != 0 {
		var netIncomeEntry JournalEntry
		nowPosted := now
		if netIncome > 0 {
			netIncomeEntry = JournalEntry{
				ID:          uuid.New().String(),
				TenantID:    tenantID,
				EntryNumber: fmt.Sprintf("CLOSE-NET-%d-%02d", period.FiscalYear, period.PeriodNumber),
				Date:        period.EndDate,
				EntryDate:   period.EndDate,
				Description: fmt.Sprintf("Transfer net income to retained earnings for %s", period.Name),
				Status:      JournalEntryStatusPosted,
				Lines: []JournalLine{
					{AccountCode: "3900", AccountName: "Income Summary", DebitAmount: netIncome},
					{AccountCode: "3200", AccountName: "Retained Earnings", CreditAmount: netIncome},
				},
				Currency:  "NGN",
				PostedAt:  &nowPosted,
				CreatedAt: now,
				UpdatedAt: now,
			}
		} else {
			absNetIncome := -netIncome
			netIncomeEntry = JournalEntry{
				ID:          uuid.New().String(),
				TenantID:    tenantID,
				EntryNumber: fmt.Sprintf("CLOSE-NET-%d-%02d", period.FiscalYear, period.PeriodNumber),
				Date:        period.EndDate,
				EntryDate:   period.EndDate,
				Description: fmt.Sprintf("Transfer net loss to retained earnings for %s", period.Name),
				Status:      JournalEntryStatusPosted,
				Lines: []JournalLine{
					{AccountCode: "3200", AccountName: "Retained Earnings", DebitAmount: absNetIncome},
					{AccountCode: "3900", AccountName: "Income Summary", CreditAmount: absNetIncome},
				},
				Currency:  "NGN",
				PostedAt:  &nowPosted,
				CreatedAt: now,
				UpdatedAt: now,
			}
		}
		closingEntries = append(closingEntries, netIncomeEntry)
	}

	return closingEntries, netIncome, nil
}

func (s *PeriodService) GetPeriodSummary(ctx context.Context, tenantID, periodID string) (*PeriodSummary, error) {
	if s.store == nil {
		return nil, errors.New("postgres store not initialized")
	}

	period, err := s.store.GetAccountingPeriod(ctx, tenantID, periodID)
	if err != nil {
		return nil, err
	}
	if period == nil {
		return nil, errors.New("period not found")
	}

	summary := &PeriodSummary{
		Period: *period,
	}

	trialBalance, err := s.coaService.GetTrialBalance(ctx, tenantID, period.EndDate.Format("2006-01-02"))
	if err == nil {
		summary.TotalDebits = trialBalance.TotalDebits
		summary.TotalCredits = trialBalance.TotalCredits
		summary.IsBalanced = trialBalance.IsBalanced
	}

	incomeStatement, err := s.coaService.GetIncomeStatement(ctx, tenantID, period.StartDate.Format("2006-01-02"), period.EndDate.Format("2006-01-02"))
	if err == nil {
		summary.TotalRevenue = incomeStatement.TotalRevenue
		summary.TotalExpenses = incomeStatement.TotalExpenses
		summary.NetIncome = incomeStatement.NetIncome
	}

	entries, err := s.coaService.ListJournalEntries(ctx, tenantID)
	if err == nil {
		for _, entry := range entries {
			if !entry.EntryDate.Before(period.StartDate) && !entry.EntryDate.After(period.EndDate) {
				summary.JournalEntryCount++
				if entry.Status == JournalEntryStatusPosted {
					summary.PostedEntryCount++
				}
			}
		}
	}

	return summary, nil
}

type PeriodSummary struct {
	Period            AccountingPeriod `json:"period"`
	TotalDebits       int64            `json:"total_debits"`
	TotalCredits      int64            `json:"total_credits"`
	IsBalanced        bool             `json:"is_balanced"`
	TotalRevenue      int64            `json:"total_revenue"`
	TotalExpenses     int64            `json:"total_expenses"`
	NetIncome         int64            `json:"net_income"`
	JournalEntryCount int              `json:"journal_entry_count"`
	PostedEntryCount  int              `json:"posted_entry_count"`
}
