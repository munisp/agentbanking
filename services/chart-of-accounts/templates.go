package main

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/google/uuid"
)

type BankType string

const (
	BankTypeCommercial BankType = "commercial"
	BankTypeMFB        BankType = "mfb"
	BankTypeFintech    BankType = "fintech"
	BankTypeMortgage   BankType = "mortgage"
	BankTypeAgricultural BankType = "agricultural"
	BankTypeDevelopment BankType = "development"
)

type AccountTemplate struct {
	ID          string                 `json:"id"`
	Name        string                 `json:"name"`
	Description string                 `json:"description"`
	BankType    BankType               `json:"bank_type"`
	IsDefault   bool                   `json:"is_default"`
	Accounts    []TemplateAccount      `json:"accounts"`
	CreatedAt   time.Time              `json:"created_at"`
	UpdatedAt   time.Time              `json:"updated_at"`
}

type TemplateAccount struct {
	Code        string            `json:"code"`
	Name        string            `json:"name"`
	Description string            `json:"description"`
	Type        AccountType       `json:"type"`
	ParentCode  string            `json:"parent_code,omitempty"`
	Currency    string            `json:"currency"`
	CBNCode     string            `json:"cbn_code,omitempty"`
	Tags        []string          `json:"tags,omitempty"`
}

type TemplateService struct {
	store      *PostgresStore
	coaService *ChartOfAccountsService
}

func NewTemplateService(store *PostgresStore, coaService *ChartOfAccountsService) *TemplateService {
	return &TemplateService{
		store:      store,
		coaService: coaService,
	}
}

func (s *TemplateService) CreateTemplate(ctx context.Context, template AccountTemplate) (*AccountTemplate, error) {
	if template.Name == "" {
		return nil, errors.New("template name is required")
	}

	if template.BankType == "" {
		return nil, errors.New("bank type is required")
	}

	if len(template.Accounts) == 0 {
		return nil, errors.New("at least one account is required")
	}

	now := time.Now()
	template.ID = uuid.New().String()
	template.CreatedAt = now
	template.UpdatedAt = now

	if s.store != nil {
		if err := s.store.SaveAccountTemplate(ctx, template); err != nil {
			return nil, fmt.Errorf("failed to save template: %w", err)
		}
	}

	return &template, nil
}

func (s *TemplateService) GetTemplate(ctx context.Context, templateID string) (*AccountTemplate, error) {
	if s.store == nil {
		return nil, errors.New("postgres store not initialized")
	}

	return s.store.GetAccountTemplate(ctx, templateID)
}

func (s *TemplateService) GetDefaultTemplate(ctx context.Context, bankType BankType) (*AccountTemplate, error) {
	if s.store == nil {
		return s.getBuiltInTemplate(bankType)
	}

	template, err := s.store.GetDefaultTemplateForBankType(ctx, string(bankType))
	if err != nil {
		return nil, err
	}

	if template == nil {
		return s.getBuiltInTemplate(bankType)
	}

	return template, nil
}

func (s *TemplateService) ListTemplates(ctx context.Context, bankType string) ([]AccountTemplate, error) {
	if s.store == nil {
		return nil, errors.New("postgres store not initialized")
	}

	return s.store.ListAccountTemplates(ctx, bankType)
}

func (s *TemplateService) ApplyTemplate(ctx context.Context, tenantID, templateID string) error {
	template, err := s.GetTemplate(ctx, templateID)
	if err != nil {
		return err
	}
	if template == nil {
		return errors.New("template not found")
	}

	return s.applyTemplateAccounts(ctx, tenantID, template.Accounts)
}

func (s *TemplateService) ApplyDefaultTemplate(ctx context.Context, tenantID string, bankType BankType) error {
	template, err := s.GetDefaultTemplate(ctx, bankType)
	if err != nil {
		return err
	}
	if template == nil {
		return fmt.Errorf("no default template found for bank type: %s", bankType)
	}

	return s.applyTemplateAccounts(ctx, tenantID, template.Accounts)
}

func (s *TemplateService) applyTemplateAccounts(ctx context.Context, tenantID string, accounts []TemplateAccount) error {
	codeToID := make(map[string]string)

	for _, acc := range accounts {
		if acc.ParentCode != "" {
			continue
		}

		req := CreateAccountRequest{
			Code:        acc.Code,
			Name:        acc.Name,
			Description: acc.Description,
			Type:        acc.Type,
			Currency:    acc.Currency,
			CBNCode:     acc.CBNCode,
			Tags:        acc.Tags,
		}

		created, err := s.coaService.CreateAccount(ctx, tenantID, req)
		if err != nil {
			return fmt.Errorf("failed to create account %s: %w", acc.Code, err)
		}
		codeToID[acc.Code] = created.ID
	}

	for _, acc := range accounts {
		if acc.ParentCode == "" {
			continue
		}

		parentID, exists := codeToID[acc.ParentCode]
		if !exists {
			continue
		}

		req := CreateAccountRequest{
			Code:        acc.Code,
			Name:        acc.Name,
			Description: acc.Description,
			Type:        acc.Type,
			ParentID:    parentID,
			Currency:    acc.Currency,
			CBNCode:     acc.CBNCode,
			Tags:        acc.Tags,
		}

		created, err := s.coaService.CreateAccount(ctx, tenantID, req)
		if err != nil {
			return fmt.Errorf("failed to create account %s: %w", acc.Code, err)
		}
		codeToID[acc.Code] = created.ID
	}

	return nil
}

func (s *TemplateService) getBuiltInTemplate(bankType BankType) (*AccountTemplate, error) {
	switch bankType {
	case BankTypeCommercial:
		return s.getCommercialBankTemplate(), nil
	case BankTypeMFB:
		return s.getMFBTemplate(), nil
	case BankTypeFintech:
		return s.getFintechTemplate(), nil
	case BankTypeMortgage:
		return s.getMortgageBankTemplate(), nil
	case BankTypeAgricultural:
		return s.getAgriculturalBankTemplate(), nil
	default:
		return s.getCommercialBankTemplate(), nil
	}
}

func (s *TemplateService) getCommercialBankTemplate() *AccountTemplate {
	return &AccountTemplate{
		ID:          "builtin-commercial",
		Name:        "Commercial Bank Standard CoA",
		Description: "Standard Chart of Accounts for Nigerian Commercial Banks (CBN compliant)",
		BankType:    BankTypeCommercial,
		IsDefault:   true,
		Accounts: []TemplateAccount{
			{Code: "1000", Name: "Assets", Type: AccountTypeAsset, Currency: "NGN"},
			{Code: "1100", Name: "Cash and Balances with Central Bank", Type: AccountTypeAsset, ParentCode: "1000", Currency: "NGN", CBNCode: "SFP001"},
			{Code: "1110", Name: "Cash on Hand", Type: AccountTypeAsset, ParentCode: "1100", Currency: "NGN"},
			{Code: "1120", Name: "Balances with CBN", Type: AccountTypeAsset, ParentCode: "1100", Currency: "NGN"},
			{Code: "1130", Name: "Cash Reserve Requirement", Type: AccountTypeAsset, ParentCode: "1100", Currency: "NGN"},
			{Code: "1200", Name: "Due from Banks", Type: AccountTypeAsset, ParentCode: "1000", Currency: "NGN", CBNCode: "SFP002"},
			{Code: "1210", Name: "Placements with Local Banks", Type: AccountTypeAsset, ParentCode: "1200", Currency: "NGN"},
			{Code: "1220", Name: "Placements with Foreign Banks", Type: AccountTypeAsset, ParentCode: "1200", Currency: "NGN"},
			{Code: "1300", Name: "Financial Assets at Fair Value", Type: AccountTypeAsset, ParentCode: "1000", Currency: "NGN", CBNCode: "SFP003"},
			{Code: "1310", Name: "Treasury Bills", Type: AccountTypeAsset, ParentCode: "1300", Currency: "NGN"},
			{Code: "1320", Name: "Government Bonds", Type: AccountTypeAsset, ParentCode: "1300", Currency: "NGN"},
			{Code: "1330", Name: "Corporate Bonds", Type: AccountTypeAsset, ParentCode: "1300", Currency: "NGN"},
			{Code: "1340", Name: "Equity Investments", Type: AccountTypeAsset, ParentCode: "1300", Currency: "NGN"},
			{Code: "1400", Name: "Loans and Advances to Customers", Type: AccountTypeAsset, ParentCode: "1000", Currency: "NGN", CBNCode: "SFP005"},
			{Code: "1410", Name: "Consumer Loans", Type: AccountTypeAsset, ParentCode: "1400", Currency: "NGN"},
			{Code: "1420", Name: "Commercial Loans", Type: AccountTypeAsset, ParentCode: "1400", Currency: "NGN"},
			{Code: "1430", Name: "Mortgage Loans", Type: AccountTypeAsset, ParentCode: "1400", Currency: "NGN"},
			{Code: "1440", Name: "Agricultural Loans", Type: AccountTypeAsset, ParentCode: "1400", Currency: "NGN"},
			{Code: "1450", Name: "SME Loans", Type: AccountTypeAsset, ParentCode: "1400", Currency: "NGN"},
			{Code: "1460", Name: "Overdrafts", Type: AccountTypeAsset, ParentCode: "1400", Currency: "NGN"},
			{Code: "1470", Name: "Loan Loss Provision", Type: AccountTypeAsset, ParentCode: "1400", Currency: "NGN"},
			{Code: "1500", Name: "Property and Equipment", Type: AccountTypeAsset, ParentCode: "1000", Currency: "NGN", CBNCode: "SFP007"},
			{Code: "1510", Name: "Land and Buildings", Type: AccountTypeAsset, ParentCode: "1500", Currency: "NGN"},
			{Code: "1520", Name: "Furniture and Fixtures", Type: AccountTypeAsset, ParentCode: "1500", Currency: "NGN"},
			{Code: "1530", Name: "Computer Equipment", Type: AccountTypeAsset, ParentCode: "1500", Currency: "NGN"},
			{Code: "1540", Name: "Motor Vehicles", Type: AccountTypeAsset, ParentCode: "1500", Currency: "NGN"},
			{Code: "1550", Name: "Accumulated Depreciation", Type: AccountTypeAsset, ParentCode: "1500", Currency: "NGN"},
			{Code: "1600", Name: "Intangible Assets", Type: AccountTypeAsset, ParentCode: "1000", Currency: "NGN", CBNCode: "SFP008"},
			{Code: "1610", Name: "Software", Type: AccountTypeAsset, ParentCode: "1600", Currency: "NGN"},
			{Code: "1620", Name: "Goodwill", Type: AccountTypeAsset, ParentCode: "1600", Currency: "NGN"},
			{Code: "1700", Name: "Other Assets", Type: AccountTypeAsset, ParentCode: "1000", Currency: "NGN", CBNCode: "SFP010"},
			{Code: "1710", Name: "Prepaid Expenses", Type: AccountTypeAsset, ParentCode: "1700", Currency: "NGN"},
			{Code: "1720", Name: "Accrued Interest Receivable", Type: AccountTypeAsset, ParentCode: "1700", Currency: "NGN"},
			{Code: "1730", Name: "Deferred Tax Assets", Type: AccountTypeAsset, ParentCode: "1700", Currency: "NGN", CBNCode: "SFP009"},

			{Code: "2000", Name: "Liabilities", Type: AccountTypeLiability, Currency: "NGN"},
			{Code: "2100", Name: "Deposits from Banks", Type: AccountTypeLiability, ParentCode: "2000", Currency: "NGN", CBNCode: "SFP011"},
			{Code: "2110", Name: "Call Deposits from Banks", Type: AccountTypeLiability, ParentCode: "2100", Currency: "NGN"},
			{Code: "2120", Name: "Term Deposits from Banks", Type: AccountTypeLiability, ParentCode: "2100", Currency: "NGN"},
			{Code: "2200", Name: "Deposits from Customers", Type: AccountTypeLiability, ParentCode: "2000", Currency: "NGN", CBNCode: "SFP012"},
			{Code: "2210", Name: "Current Accounts", Type: AccountTypeLiability, ParentCode: "2200", Currency: "NGN"},
			{Code: "2220", Name: "Savings Accounts", Type: AccountTypeLiability, ParentCode: "2200", Currency: "NGN"},
			{Code: "2230", Name: "Fixed Deposits", Type: AccountTypeLiability, ParentCode: "2200", Currency: "NGN"},
			{Code: "2240", Name: "Domiciliary Accounts", Type: AccountTypeLiability, ParentCode: "2200", Currency: "NGN"},
			{Code: "2300", Name: "Borrowings", Type: AccountTypeLiability, ParentCode: "2000", Currency: "NGN", CBNCode: "SFP014"},
			{Code: "2310", Name: "CBN Facilities", Type: AccountTypeLiability, ParentCode: "2300", Currency: "NGN"},
			{Code: "2320", Name: "Interbank Borrowings", Type: AccountTypeLiability, ParentCode: "2300", Currency: "NGN"},
			{Code: "2330", Name: "Bonds Issued", Type: AccountTypeLiability, ParentCode: "2300", Currency: "NGN"},
			{Code: "2400", Name: "Other Liabilities", Type: AccountTypeLiability, ParentCode: "2000", Currency: "NGN", CBNCode: "SFP017"},
			{Code: "2410", Name: "Accrued Interest Payable", Type: AccountTypeLiability, ParentCode: "2400", Currency: "NGN"},
			{Code: "2420", Name: "Accounts Payable", Type: AccountTypeLiability, ParentCode: "2400", Currency: "NGN"},
			{Code: "2430", Name: "Deferred Income", Type: AccountTypeLiability, ParentCode: "2400", Currency: "NGN"},
			{Code: "2440", Name: "Current Tax Liabilities", Type: AccountTypeLiability, ParentCode: "2400", Currency: "NGN", CBNCode: "SFP015"},
			{Code: "2450", Name: "Deferred Tax Liabilities", Type: AccountTypeLiability, ParentCode: "2400", Currency: "NGN", CBNCode: "SFP016"},
			{Code: "2500", Name: "Provisions", Type: AccountTypeLiability, ParentCode: "2000", Currency: "NGN", CBNCode: "SFP018"},
			{Code: "2510", Name: "Provision for Loan Losses", Type: AccountTypeLiability, ParentCode: "2500", Currency: "NGN"},
			{Code: "2520", Name: "Provision for Legal Claims", Type: AccountTypeLiability, ParentCode: "2500", Currency: "NGN"},

			{Code: "3000", Name: "Equity", Type: AccountTypeEquity, Currency: "NGN"},
			{Code: "3100", Name: "Share Capital", Type: AccountTypeEquity, ParentCode: "3000", Currency: "NGN", CBNCode: "SFP019"},
			{Code: "3110", Name: "Authorized Share Capital", Type: AccountTypeEquity, ParentCode: "3100", Currency: "NGN"},
			{Code: "3120", Name: "Issued Share Capital", Type: AccountTypeEquity, ParentCode: "3100", Currency: "NGN"},
			{Code: "3200", Name: "Share Premium", Type: AccountTypeEquity, ParentCode: "3000", Currency: "NGN", CBNCode: "SFP020"},
			{Code: "3300", Name: "Retained Earnings", Type: AccountTypeEquity, ParentCode: "3000", Currency: "NGN", CBNCode: "SFP021"},
			{Code: "3400", Name: "Other Reserves", Type: AccountTypeEquity, ParentCode: "3000", Currency: "NGN", CBNCode: "SFP022"},
			{Code: "3410", Name: "Statutory Reserve", Type: AccountTypeEquity, ParentCode: "3400", Currency: "NGN"},
			{Code: "3420", Name: "General Reserve", Type: AccountTypeEquity, ParentCode: "3400", Currency: "NGN"},
			{Code: "3430", Name: "Revaluation Reserve", Type: AccountTypeEquity, ParentCode: "3400", Currency: "NGN"},
			{Code: "3440", Name: "Foreign Currency Translation Reserve", Type: AccountTypeEquity, ParentCode: "3400", Currency: "NGN"},
			{Code: "3900", Name: "Income Summary", Type: AccountTypeEquity, ParentCode: "3000", Currency: "NGN"},

			{Code: "4000", Name: "Revenue", Type: AccountTypeRevenue, Currency: "NGN"},
			{Code: "4100", Name: "Interest Income", Type: AccountTypeRevenue, ParentCode: "4000", Currency: "NGN", CBNCode: "PL001"},
			{Code: "4110", Name: "Interest on Loans", Type: AccountTypeRevenue, ParentCode: "4100", Currency: "NGN"},
			{Code: "4120", Name: "Interest on Placements", Type: AccountTypeRevenue, ParentCode: "4100", Currency: "NGN"},
			{Code: "4130", Name: "Interest on Securities", Type: AccountTypeRevenue, ParentCode: "4100", Currency: "NGN"},
			{Code: "4200", Name: "Fee and Commission Income", Type: AccountTypeRevenue, ParentCode: "4000", Currency: "NGN", CBNCode: "PL004"},
			{Code: "4210", Name: "Account Maintenance Fees", Type: AccountTypeRevenue, ParentCode: "4200", Currency: "NGN"},
			{Code: "4220", Name: "Transfer Fees", Type: AccountTypeRevenue, ParentCode: "4200", Currency: "NGN"},
			{Code: "4230", Name: "Card Fees", Type: AccountTypeRevenue, ParentCode: "4200", Currency: "NGN"},
			{Code: "4240", Name: "Loan Processing Fees", Type: AccountTypeRevenue, ParentCode: "4200", Currency: "NGN"},
			{Code: "4250", Name: "Trade Finance Fees", Type: AccountTypeRevenue, ParentCode: "4200", Currency: "NGN"},
			{Code: "4300", Name: "Net Trading Income", Type: AccountTypeRevenue, ParentCode: "4000", Currency: "NGN", CBNCode: "PL007"},
			{Code: "4310", Name: "Foreign Exchange Gains", Type: AccountTypeRevenue, ParentCode: "4300", Currency: "NGN"},
			{Code: "4320", Name: "Securities Trading Gains", Type: AccountTypeRevenue, ParentCode: "4300", Currency: "NGN"},
			{Code: "4400", Name: "Other Operating Income", Type: AccountTypeRevenue, ParentCode: "4000", Currency: "NGN", CBNCode: "PL008"},
			{Code: "4410", Name: "Dividend Income", Type: AccountTypeRevenue, ParentCode: "4400", Currency: "NGN"},
			{Code: "4420", Name: "Rental Income", Type: AccountTypeRevenue, ParentCode: "4400", Currency: "NGN"},
			{Code: "4430", Name: "Recoveries", Type: AccountTypeRevenue, ParentCode: "4400", Currency: "NGN"},

			{Code: "5000", Name: "Expenses", Type: AccountTypeExpense, Currency: "NGN"},
			{Code: "5100", Name: "Interest Expense", Type: AccountTypeExpense, ParentCode: "5000", Currency: "NGN", CBNCode: "PL002"},
			{Code: "5110", Name: "Interest on Customer Deposits", Type: AccountTypeExpense, ParentCode: "5100", Currency: "NGN"},
			{Code: "5120", Name: "Interest on Borrowings", Type: AccountTypeExpense, ParentCode: "5100", Currency: "NGN"},
			{Code: "5130", Name: "Interest on Bonds", Type: AccountTypeExpense, ParentCode: "5100", Currency: "NGN"},
			{Code: "5200", Name: "Fee and Commission Expense", Type: AccountTypeExpense, ParentCode: "5000", Currency: "NGN", CBNCode: "PL005"},
			{Code: "5210", Name: "NIBSS Charges", Type: AccountTypeExpense, ParentCode: "5200", Currency: "NGN"},
			{Code: "5220", Name: "Card Scheme Fees", Type: AccountTypeExpense, ParentCode: "5200", Currency: "NGN"},
			{Code: "5230", Name: "Correspondent Bank Charges", Type: AccountTypeExpense, ParentCode: "5200", Currency: "NGN"},
			{Code: "5300", Name: "Impairment Charges", Type: AccountTypeExpense, ParentCode: "5000", Currency: "NGN", CBNCode: "PL009"},
			{Code: "5310", Name: "Loan Impairment", Type: AccountTypeExpense, ParentCode: "5300", Currency: "NGN"},
			{Code: "5320", Name: "Investment Impairment", Type: AccountTypeExpense, ParentCode: "5300", Currency: "NGN"},
			{Code: "5400", Name: "Personnel Expenses", Type: AccountTypeExpense, ParentCode: "5000", Currency: "NGN", CBNCode: "PL010"},
			{Code: "5410", Name: "Salaries and Wages", Type: AccountTypeExpense, ParentCode: "5400", Currency: "NGN"},
			{Code: "5420", Name: "Staff Benefits", Type: AccountTypeExpense, ParentCode: "5400", Currency: "NGN"},
			{Code: "5430", Name: "Pension Contributions", Type: AccountTypeExpense, ParentCode: "5400", Currency: "NGN"},
			{Code: "5440", Name: "Training and Development", Type: AccountTypeExpense, ParentCode: "5400", Currency: "NGN"},
			{Code: "5500", Name: "Depreciation and Amortization", Type: AccountTypeExpense, ParentCode: "5000", Currency: "NGN", CBNCode: "PL011"},
			{Code: "5510", Name: "Depreciation - Buildings", Type: AccountTypeExpense, ParentCode: "5500", Currency: "NGN"},
			{Code: "5520", Name: "Depreciation - Equipment", Type: AccountTypeExpense, ParentCode: "5500", Currency: "NGN"},
			{Code: "5530", Name: "Amortization - Software", Type: AccountTypeExpense, ParentCode: "5500", Currency: "NGN"},
			{Code: "5600", Name: "Other Operating Expenses", Type: AccountTypeExpense, ParentCode: "5000", Currency: "NGN", CBNCode: "PL012"},
			{Code: "5610", Name: "Rent and Utilities", Type: AccountTypeExpense, ParentCode: "5600", Currency: "NGN"},
			{Code: "5620", Name: "Professional Fees", Type: AccountTypeExpense, ParentCode: "5600", Currency: "NGN"},
			{Code: "5630", Name: "Insurance", Type: AccountTypeExpense, ParentCode: "5600", Currency: "NGN"},
			{Code: "5640", Name: "Marketing and Advertising", Type: AccountTypeExpense, ParentCode: "5600", Currency: "NGN"},
			{Code: "5650", Name: "IT and Communication", Type: AccountTypeExpense, ParentCode: "5600", Currency: "NGN"},
			{Code: "5660", Name: "Security", Type: AccountTypeExpense, ParentCode: "5600", Currency: "NGN"},
			{Code: "5670", Name: "Regulatory Fees", Type: AccountTypeExpense, ParentCode: "5600", Currency: "NGN"},
			{Code: "5700", Name: "Income Tax Expense", Type: AccountTypeExpense, ParentCode: "5000", Currency: "NGN", CBNCode: "PL014"},
		},
	}
}

func (s *TemplateService) getMFBTemplate() *AccountTemplate {
	return &AccountTemplate{
		ID:          "builtin-mfb",
		Name:        "Microfinance Bank Standard CoA",
		Description: "Standard Chart of Accounts for Nigerian Microfinance Banks",
		BankType:    BankTypeMFB,
		IsDefault:   true,
		Accounts: []TemplateAccount{
			{Code: "1000", Name: "Assets", Type: AccountTypeAsset, Currency: "NGN"},
			{Code: "1100", Name: "Cash and Bank Balances", Type: AccountTypeAsset, ParentCode: "1000", Currency: "NGN"},
			{Code: "1110", Name: "Cash on Hand", Type: AccountTypeAsset, ParentCode: "1100", Currency: "NGN"},
			{Code: "1120", Name: "Bank Balances", Type: AccountTypeAsset, ParentCode: "1100", Currency: "NGN"},
			{Code: "1200", Name: "Loans and Advances", Type: AccountTypeAsset, ParentCode: "1000", Currency: "NGN"},
			{Code: "1210", Name: "Microloans", Type: AccountTypeAsset, ParentCode: "1200", Currency: "NGN"},
			{Code: "1220", Name: "Group Loans", Type: AccountTypeAsset, ParentCode: "1200", Currency: "NGN"},
			{Code: "1230", Name: "SME Loans", Type: AccountTypeAsset, ParentCode: "1200", Currency: "NGN"},
			{Code: "1240", Name: "Agricultural Loans", Type: AccountTypeAsset, ParentCode: "1200", Currency: "NGN"},
			{Code: "1250", Name: "Salary Loans", Type: AccountTypeAsset, ParentCode: "1200", Currency: "NGN"},
			{Code: "1260", Name: "Loan Loss Provision", Type: AccountTypeAsset, ParentCode: "1200", Currency: "NGN"},
			{Code: "1300", Name: "Investments", Type: AccountTypeAsset, ParentCode: "1000", Currency: "NGN"},
			{Code: "1310", Name: "Treasury Bills", Type: AccountTypeAsset, ParentCode: "1300", Currency: "NGN"},
			{Code: "1320", Name: "Fixed Deposits with Banks", Type: AccountTypeAsset, ParentCode: "1300", Currency: "NGN"},
			{Code: "1400", Name: "Fixed Assets", Type: AccountTypeAsset, ParentCode: "1000", Currency: "NGN"},
			{Code: "1410", Name: "Office Equipment", Type: AccountTypeAsset, ParentCode: "1400", Currency: "NGN"},
			{Code: "1420", Name: "Furniture and Fittings", Type: AccountTypeAsset, ParentCode: "1400", Currency: "NGN"},
			{Code: "1430", Name: "Motor Vehicles", Type: AccountTypeAsset, ParentCode: "1400", Currency: "NGN"},
			{Code: "1440", Name: "Computer Equipment", Type: AccountTypeAsset, ParentCode: "1400", Currency: "NGN"},
			{Code: "1450", Name: "Accumulated Depreciation", Type: AccountTypeAsset, ParentCode: "1400", Currency: "NGN"},
			{Code: "1500", Name: "Other Assets", Type: AccountTypeAsset, ParentCode: "1000", Currency: "NGN"},
			{Code: "1510", Name: "Prepaid Expenses", Type: AccountTypeAsset, ParentCode: "1500", Currency: "NGN"},
			{Code: "1520", Name: "Accrued Interest Receivable", Type: AccountTypeAsset, ParentCode: "1500", Currency: "NGN"},

			{Code: "2000", Name: "Liabilities", Type: AccountTypeLiability, Currency: "NGN"},
			{Code: "2100", Name: "Customer Deposits", Type: AccountTypeLiability, ParentCode: "2000", Currency: "NGN"},
			{Code: "2110", Name: "Savings Deposits", Type: AccountTypeLiability, ParentCode: "2100", Currency: "NGN"},
			{Code: "2120", Name: "Fixed Deposits", Type: AccountTypeLiability, ParentCode: "2100", Currency: "NGN"},
			{Code: "2130", Name: "Target Savings", Type: AccountTypeLiability, ParentCode: "2100", Currency: "NGN"},
			{Code: "2140", Name: "Group Savings", Type: AccountTypeLiability, ParentCode: "2100", Currency: "NGN"},
			{Code: "2200", Name: "Borrowings", Type: AccountTypeLiability, ParentCode: "2000", Currency: "NGN"},
			{Code: "2210", Name: "Bank Loans", Type: AccountTypeLiability, ParentCode: "2200", Currency: "NGN"},
			{Code: "2220", Name: "Development Finance Loans", Type: AccountTypeLiability, ParentCode: "2200", Currency: "NGN"},
			{Code: "2300", Name: "Other Liabilities", Type: AccountTypeLiability, ParentCode: "2000", Currency: "NGN"},
			{Code: "2310", Name: "Accrued Interest Payable", Type: AccountTypeLiability, ParentCode: "2300", Currency: "NGN"},
			{Code: "2320", Name: "Accounts Payable", Type: AccountTypeLiability, ParentCode: "2300", Currency: "NGN"},
			{Code: "2330", Name: "Tax Payable", Type: AccountTypeLiability, ParentCode: "2300", Currency: "NGN"},

			{Code: "3000", Name: "Equity", Type: AccountTypeEquity, Currency: "NGN"},
			{Code: "3100", Name: "Share Capital", Type: AccountTypeEquity, ParentCode: "3000", Currency: "NGN"},
			{Code: "3200", Name: "Retained Earnings", Type: AccountTypeEquity, ParentCode: "3000", Currency: "NGN"},
			{Code: "3300", Name: "Statutory Reserve", Type: AccountTypeEquity, ParentCode: "3000", Currency: "NGN"},
			{Code: "3900", Name: "Income Summary", Type: AccountTypeEquity, ParentCode: "3000", Currency: "NGN"},

			{Code: "4000", Name: "Revenue", Type: AccountTypeRevenue, Currency: "NGN"},
			{Code: "4100", Name: "Interest Income", Type: AccountTypeRevenue, ParentCode: "4000", Currency: "NGN"},
			{Code: "4110", Name: "Interest on Microloans", Type: AccountTypeRevenue, ParentCode: "4100", Currency: "NGN"},
			{Code: "4120", Name: "Interest on Group Loans", Type: AccountTypeRevenue, ParentCode: "4100", Currency: "NGN"},
			{Code: "4130", Name: "Interest on SME Loans", Type: AccountTypeRevenue, ParentCode: "4100", Currency: "NGN"},
			{Code: "4140", Name: "Interest on Investments", Type: AccountTypeRevenue, ParentCode: "4100", Currency: "NGN"},
			{Code: "4200", Name: "Fee Income", Type: AccountTypeRevenue, ParentCode: "4000", Currency: "NGN"},
			{Code: "4210", Name: "Loan Processing Fees", Type: AccountTypeRevenue, ParentCode: "4200", Currency: "NGN"},
			{Code: "4220", Name: "Account Maintenance Fees", Type: AccountTypeRevenue, ParentCode: "4200", Currency: "NGN"},
			{Code: "4230", Name: "Transfer Fees", Type: AccountTypeRevenue, ParentCode: "4200", Currency: "NGN"},
			{Code: "4300", Name: "Other Income", Type: AccountTypeRevenue, ParentCode: "4000", Currency: "NGN"},
			{Code: "4310", Name: "Penalty Income", Type: AccountTypeRevenue, ParentCode: "4300", Currency: "NGN"},
			{Code: "4320", Name: "Recoveries", Type: AccountTypeRevenue, ParentCode: "4300", Currency: "NGN"},

			{Code: "5000", Name: "Expenses", Type: AccountTypeExpense, Currency: "NGN"},
			{Code: "5100", Name: "Interest Expense", Type: AccountTypeExpense, ParentCode: "5000", Currency: "NGN"},
			{Code: "5110", Name: "Interest on Savings", Type: AccountTypeExpense, ParentCode: "5100", Currency: "NGN"},
			{Code: "5120", Name: "Interest on Fixed Deposits", Type: AccountTypeExpense, ParentCode: "5100", Currency: "NGN"},
			{Code: "5130", Name: "Interest on Borrowings", Type: AccountTypeExpense, ParentCode: "5100", Currency: "NGN"},
			{Code: "5200", Name: "Provision for Loan Losses", Type: AccountTypeExpense, ParentCode: "5000", Currency: "NGN"},
			{Code: "5300", Name: "Personnel Expenses", Type: AccountTypeExpense, ParentCode: "5000", Currency: "NGN"},
			{Code: "5310", Name: "Salaries and Wages", Type: AccountTypeExpense, ParentCode: "5300", Currency: "NGN"},
			{Code: "5320", Name: "Staff Benefits", Type: AccountTypeExpense, ParentCode: "5300", Currency: "NGN"},
			{Code: "5330", Name: "Training", Type: AccountTypeExpense, ParentCode: "5300", Currency: "NGN"},
			{Code: "5400", Name: "Administrative Expenses", Type: AccountTypeExpense, ParentCode: "5000", Currency: "NGN"},
			{Code: "5410", Name: "Rent", Type: AccountTypeExpense, ParentCode: "5400", Currency: "NGN"},
			{Code: "5420", Name: "Utilities", Type: AccountTypeExpense, ParentCode: "5400", Currency: "NGN"},
			{Code: "5430", Name: "Office Supplies", Type: AccountTypeExpense, ParentCode: "5400", Currency: "NGN"},
			{Code: "5440", Name: "Communication", Type: AccountTypeExpense, ParentCode: "5400", Currency: "NGN"},
			{Code: "5450", Name: "Insurance", Type: AccountTypeExpense, ParentCode: "5400", Currency: "NGN"},
			{Code: "5500", Name: "Depreciation", Type: AccountTypeExpense, ParentCode: "5000", Currency: "NGN"},
			{Code: "5600", Name: "Other Expenses", Type: AccountTypeExpense, ParentCode: "5000", Currency: "NGN"},
			{Code: "5610", Name: "Professional Fees", Type: AccountTypeExpense, ParentCode: "5600", Currency: "NGN"},
			{Code: "5620", Name: "Regulatory Fees", Type: AccountTypeExpense, ParentCode: "5600", Currency: "NGN"},
			{Code: "5630", Name: "Marketing", Type: AccountTypeExpense, ParentCode: "5600", Currency: "NGN"},
			{Code: "5700", Name: "Income Tax Expense", Type: AccountTypeExpense, ParentCode: "5000", Currency: "NGN"},
		},
	}
}

func (s *TemplateService) getFintechTemplate() *AccountTemplate {
	return &AccountTemplate{
		ID:          "builtin-fintech",
		Name:        "Fintech/Payment Service Provider CoA",
		Description: "Chart of Accounts for Nigerian Fintechs and Payment Service Providers",
		BankType:    BankTypeFintech,
		IsDefault:   true,
		Accounts: []TemplateAccount{
			{Code: "1000", Name: "Assets", Type: AccountTypeAsset, Currency: "NGN"},
			{Code: "1100", Name: "Cash and Cash Equivalents", Type: AccountTypeAsset, ParentCode: "1000", Currency: "NGN"},
			{Code: "1110", Name: "Operating Bank Accounts", Type: AccountTypeAsset, ParentCode: "1100", Currency: "NGN"},
			{Code: "1120", Name: "Settlement Accounts", Type: AccountTypeAsset, ParentCode: "1100", Currency: "NGN"},
			{Code: "1130", Name: "Escrow Accounts", Type: AccountTypeAsset, ParentCode: "1100", Currency: "NGN"},
			{Code: "1200", Name: "Customer Funds", Type: AccountTypeAsset, ParentCode: "1000", Currency: "NGN"},
			{Code: "1210", Name: "Wallet Balances", Type: AccountTypeAsset, ParentCode: "1200", Currency: "NGN"},
			{Code: "1220", Name: "Pending Settlements", Type: AccountTypeAsset, ParentCode: "1200", Currency: "NGN"},
			{Code: "1300", Name: "Receivables", Type: AccountTypeAsset, ParentCode: "1000", Currency: "NGN"},
			{Code: "1310", Name: "Merchant Receivables", Type: AccountTypeAsset, ParentCode: "1300", Currency: "NGN"},
			{Code: "1320", Name: "Partner Receivables", Type: AccountTypeAsset, ParentCode: "1300", Currency: "NGN"},
			{Code: "1330", Name: "Interchange Receivables", Type: AccountTypeAsset, ParentCode: "1300", Currency: "NGN"},
			{Code: "1400", Name: "Fixed Assets", Type: AccountTypeAsset, ParentCode: "1000", Currency: "NGN"},
			{Code: "1410", Name: "Computer Equipment", Type: AccountTypeAsset, ParentCode: "1400", Currency: "NGN"},
			{Code: "1420", Name: "Office Equipment", Type: AccountTypeAsset, ParentCode: "1400", Currency: "NGN"},
			{Code: "1430", Name: "Accumulated Depreciation", Type: AccountTypeAsset, ParentCode: "1400", Currency: "NGN"},
			{Code: "1500", Name: "Intangible Assets", Type: AccountTypeAsset, ParentCode: "1000", Currency: "NGN"},
			{Code: "1510", Name: "Software Development", Type: AccountTypeAsset, ParentCode: "1500", Currency: "NGN"},
			{Code: "1520", Name: "Licenses", Type: AccountTypeAsset, ParentCode: "1500", Currency: "NGN"},
			{Code: "1530", Name: "Accumulated Amortization", Type: AccountTypeAsset, ParentCode: "1500", Currency: "NGN"},
			{Code: "1600", Name: "Other Assets", Type: AccountTypeAsset, ParentCode: "1000", Currency: "NGN"},
			{Code: "1610", Name: "Prepaid Expenses", Type: AccountTypeAsset, ParentCode: "1600", Currency: "NGN"},
			{Code: "1620", Name: "Security Deposits", Type: AccountTypeAsset, ParentCode: "1600", Currency: "NGN"},

			{Code: "2000", Name: "Liabilities", Type: AccountTypeLiability, Currency: "NGN"},
			{Code: "2100", Name: "Customer Funds Payable", Type: AccountTypeLiability, ParentCode: "2000", Currency: "NGN"},
			{Code: "2110", Name: "Wallet Liabilities", Type: AccountTypeLiability, ParentCode: "2100", Currency: "NGN"},
			{Code: "2120", Name: "Pending Payouts", Type: AccountTypeLiability, ParentCode: "2100", Currency: "NGN"},
			{Code: "2130", Name: "Merchant Settlements Payable", Type: AccountTypeLiability, ParentCode: "2100", Currency: "NGN"},
			{Code: "2200", Name: "Payables", Type: AccountTypeLiability, ParentCode: "2000", Currency: "NGN"},
			{Code: "2210", Name: "Partner Payables", Type: AccountTypeLiability, ParentCode: "2200", Currency: "NGN"},
			{Code: "2220", Name: "Interchange Payables", Type: AccountTypeLiability, ParentCode: "2200", Currency: "NGN"},
			{Code: "2230", Name: "Vendor Payables", Type: AccountTypeLiability, ParentCode: "2200", Currency: "NGN"},
			{Code: "2300", Name: "Accrued Liabilities", Type: AccountTypeLiability, ParentCode: "2000", Currency: "NGN"},
			{Code: "2310", Name: "Accrued Expenses", Type: AccountTypeLiability, ParentCode: "2300", Currency: "NGN"},
			{Code: "2320", Name: "Tax Payable", Type: AccountTypeLiability, ParentCode: "2300", Currency: "NGN"},
			{Code: "2330", Name: "Deferred Revenue", Type: AccountTypeLiability, ParentCode: "2300", Currency: "NGN"},
			{Code: "2400", Name: "Borrowings", Type: AccountTypeLiability, ParentCode: "2000", Currency: "NGN"},
			{Code: "2410", Name: "Bank Loans", Type: AccountTypeLiability, ParentCode: "2400", Currency: "NGN"},
			{Code: "2420", Name: "Investor Notes", Type: AccountTypeLiability, ParentCode: "2400", Currency: "NGN"},

			{Code: "3000", Name: "Equity", Type: AccountTypeEquity, Currency: "NGN"},
			{Code: "3100", Name: "Share Capital", Type: AccountTypeEquity, ParentCode: "3000", Currency: "NGN"},
			{Code: "3200", Name: "Additional Paid-in Capital", Type: AccountTypeEquity, ParentCode: "3000", Currency: "NGN"},
			{Code: "3300", Name: "Retained Earnings", Type: AccountTypeEquity, ParentCode: "3000", Currency: "NGN"},
			{Code: "3400", Name: "Stock Options Reserve", Type: AccountTypeEquity, ParentCode: "3000", Currency: "NGN"},
			{Code: "3900", Name: "Income Summary", Type: AccountTypeEquity, ParentCode: "3000", Currency: "NGN"},

			{Code: "4000", Name: "Revenue", Type: AccountTypeRevenue, Currency: "NGN"},
			{Code: "4100", Name: "Transaction Revenue", Type: AccountTypeRevenue, ParentCode: "4000", Currency: "NGN"},
			{Code: "4110", Name: "Payment Processing Fees", Type: AccountTypeRevenue, ParentCode: "4100", Currency: "NGN"},
			{Code: "4120", Name: "Transfer Fees", Type: AccountTypeRevenue, ParentCode: "4100", Currency: "NGN"},
			{Code: "4130", Name: "Withdrawal Fees", Type: AccountTypeRevenue, ParentCode: "4100", Currency: "NGN"},
			{Code: "4140", Name: "Bill Payment Fees", Type: AccountTypeRevenue, ParentCode: "4100", Currency: "NGN"},
			{Code: "4150", Name: "Airtime/Data Fees", Type: AccountTypeRevenue, ParentCode: "4100", Currency: "NGN"},
			{Code: "4200", Name: "Merchant Revenue", Type: AccountTypeRevenue, ParentCode: "4000", Currency: "NGN"},
			{Code: "4210", Name: "Merchant Discount Rate", Type: AccountTypeRevenue, ParentCode: "4200", Currency: "NGN"},
			{Code: "4220", Name: "POS Terminal Fees", Type: AccountTypeRevenue, ParentCode: "4200", Currency: "NGN"},
			{Code: "4230", Name: "Gateway Fees", Type: AccountTypeRevenue, ParentCode: "4200", Currency: "NGN"},
			{Code: "4300", Name: "Interchange Revenue", Type: AccountTypeRevenue, ParentCode: "4000", Currency: "NGN"},
			{Code: "4400", Name: "Float Income", Type: AccountTypeRevenue, ParentCode: "4000", Currency: "NGN"},
			{Code: "4500", Name: "Other Revenue", Type: AccountTypeRevenue, ParentCode: "4000", Currency: "NGN"},
			{Code: "4510", Name: "API Access Fees", Type: AccountTypeRevenue, ParentCode: "4500", Currency: "NGN"},
			{Code: "4520", Name: "Subscription Revenue", Type: AccountTypeRevenue, ParentCode: "4500", Currency: "NGN"},
			{Code: "4530", Name: "FX Spread Income", Type: AccountTypeRevenue, ParentCode: "4500", Currency: "NGN"},

			{Code: "5000", Name: "Expenses", Type: AccountTypeExpense, Currency: "NGN"},
			{Code: "5100", Name: "Cost of Revenue", Type: AccountTypeExpense, ParentCode: "5000", Currency: "NGN"},
			{Code: "5110", Name: "Payment Processing Costs", Type: AccountTypeExpense, ParentCode: "5100", Currency: "NGN"},
			{Code: "5120", Name: "Interchange Costs", Type: AccountTypeExpense, ParentCode: "5100", Currency: "NGN"},
			{Code: "5130", Name: "Bank Charges", Type: AccountTypeExpense, ParentCode: "5100", Currency: "NGN"},
			{Code: "5140", Name: "NIBSS Charges", Type: AccountTypeExpense, ParentCode: "5100", Currency: "NGN"},
			{Code: "5150", Name: "Partner Commissions", Type: AccountTypeExpense, ParentCode: "5100", Currency: "NGN"},
			{Code: "5200", Name: "Technology Expenses", Type: AccountTypeExpense, ParentCode: "5000", Currency: "NGN"},
			{Code: "5210", Name: "Cloud Infrastructure", Type: AccountTypeExpense, ParentCode: "5200", Currency: "NGN"},
			{Code: "5220", Name: "Software Licenses", Type: AccountTypeExpense, ParentCode: "5200", Currency: "NGN"},
			{Code: "5230", Name: "Security Services", Type: AccountTypeExpense, ParentCode: "5200", Currency: "NGN"},
			{Code: "5240", Name: "Third-party APIs", Type: AccountTypeExpense, ParentCode: "5200", Currency: "NGN"},
			{Code: "5300", Name: "Personnel Expenses", Type: AccountTypeExpense, ParentCode: "5000", Currency: "NGN"},
			{Code: "5310", Name: "Salaries", Type: AccountTypeExpense, ParentCode: "5300", Currency: "NGN"},
			{Code: "5320", Name: "Benefits", Type: AccountTypeExpense, ParentCode: "5300", Currency: "NGN"},
			{Code: "5330", Name: "Stock Compensation", Type: AccountTypeExpense, ParentCode: "5300", Currency: "NGN"},
			{Code: "5340", Name: "Contractors", Type: AccountTypeExpense, ParentCode: "5300", Currency: "NGN"},
			{Code: "5400", Name: "Marketing Expenses", Type: AccountTypeExpense, ParentCode: "5000", Currency: "NGN"},
			{Code: "5410", Name: "Digital Marketing", Type: AccountTypeExpense, ParentCode: "5400", Currency: "NGN"},
			{Code: "5420", Name: "Customer Acquisition", Type: AccountTypeExpense, ParentCode: "5400", Currency: "NGN"},
			{Code: "5430", Name: "Promotions and Cashback", Type: AccountTypeExpense, ParentCode: "5400", Currency: "NGN"},
			{Code: "5500", Name: "General & Administrative", Type: AccountTypeExpense, ParentCode: "5000", Currency: "NGN"},
			{Code: "5510", Name: "Office Rent", Type: AccountTypeExpense, ParentCode: "5500", Currency: "NGN"},
			{Code: "5520", Name: "Legal Fees", Type: AccountTypeExpense, ParentCode: "5500", Currency: "NGN"},
			{Code: "5530", Name: "Audit Fees", Type: AccountTypeExpense, ParentCode: "5500", Currency: "NGN"},
			{Code: "5540", Name: "Insurance", Type: AccountTypeExpense, ParentCode: "5500", Currency: "NGN"},
			{Code: "5550", Name: "Regulatory Fees", Type: AccountTypeExpense, ParentCode: "5500", Currency: "NGN"},
			{Code: "5600", Name: "Depreciation & Amortization", Type: AccountTypeExpense, ParentCode: "5000", Currency: "NGN"},
			{Code: "5700", Name: "Fraud Losses", Type: AccountTypeExpense, ParentCode: "5000", Currency: "NGN"},
			{Code: "5800", Name: "Income Tax Expense", Type: AccountTypeExpense, ParentCode: "5000", Currency: "NGN"},
		},
	}
}

func (s *TemplateService) getMortgageBankTemplate() *AccountTemplate {
	return &AccountTemplate{
		ID:          "builtin-mortgage",
		Name:        "Mortgage Bank Standard CoA",
		Description: "Chart of Accounts for Nigerian Primary Mortgage Banks",
		BankType:    BankTypeMortgage,
		IsDefault:   true,
		Accounts: []TemplateAccount{
			{Code: "1000", Name: "Assets", Type: AccountTypeAsset, Currency: "NGN"},
			{Code: "1100", Name: "Cash and Bank Balances", Type: AccountTypeAsset, ParentCode: "1000", Currency: "NGN"},
			{Code: "1200", Name: "Mortgage Loans", Type: AccountTypeAsset, ParentCode: "1000", Currency: "NGN"},
			{Code: "1210", Name: "Residential Mortgages", Type: AccountTypeAsset, ParentCode: "1200", Currency: "NGN"},
			{Code: "1220", Name: "Commercial Mortgages", Type: AccountTypeAsset, ParentCode: "1200", Currency: "NGN"},
			{Code: "1230", Name: "Construction Loans", Type: AccountTypeAsset, ParentCode: "1200", Currency: "NGN"},
			{Code: "1240", Name: "NHF Mortgages", Type: AccountTypeAsset, ParentCode: "1200", Currency: "NGN"},
			{Code: "1250", Name: "Mortgage Loan Provision", Type: AccountTypeAsset, ParentCode: "1200", Currency: "NGN"},
			{Code: "1300", Name: "Real Estate Assets", Type: AccountTypeAsset, ParentCode: "1000", Currency: "NGN"},
			{Code: "1310", Name: "Real Estate Held for Sale", Type: AccountTypeAsset, ParentCode: "1300", Currency: "NGN"},
			{Code: "1320", Name: "Foreclosed Properties", Type: AccountTypeAsset, ParentCode: "1300", Currency: "NGN"},
			{Code: "1400", Name: "Investments", Type: AccountTypeAsset, ParentCode: "1000", Currency: "NGN"},
			{Code: "1410", Name: "Government Securities", Type: AccountTypeAsset, ParentCode: "1400", Currency: "NGN"},
			{Code: "1420", Name: "Mortgage-Backed Securities", Type: AccountTypeAsset, ParentCode: "1400", Currency: "NGN"},
			{Code: "1500", Name: "Fixed Assets", Type: AccountTypeAsset, ParentCode: "1000", Currency: "NGN"},
			{Code: "1600", Name: "Other Assets", Type: AccountTypeAsset, ParentCode: "1000", Currency: "NGN"},

			{Code: "2000", Name: "Liabilities", Type: AccountTypeLiability, Currency: "NGN"},
			{Code: "2100", Name: "Customer Deposits", Type: AccountTypeLiability, ParentCode: "2000", Currency: "NGN"},
			{Code: "2110", Name: "Savings Deposits", Type: AccountTypeLiability, ParentCode: "2100", Currency: "NGN"},
			{Code: "2120", Name: "Fixed Deposits", Type: AccountTypeLiability, ParentCode: "2100", Currency: "NGN"},
			{Code: "2130", Name: "NHF Contributions", Type: AccountTypeLiability, ParentCode: "2100", Currency: "NGN"},
			{Code: "2200", Name: "Borrowings", Type: AccountTypeLiability, ParentCode: "2000", Currency: "NGN"},
			{Code: "2210", Name: "FMBN Refinancing", Type: AccountTypeLiability, ParentCode: "2200", Currency: "NGN"},
			{Code: "2220", Name: "Bank Loans", Type: AccountTypeLiability, ParentCode: "2200", Currency: "NGN"},
			{Code: "2230", Name: "Mortgage Bonds", Type: AccountTypeLiability, ParentCode: "2200", Currency: "NGN"},
			{Code: "2300", Name: "Other Liabilities", Type: AccountTypeLiability, ParentCode: "2000", Currency: "NGN"},

			{Code: "3000", Name: "Equity", Type: AccountTypeEquity, Currency: "NGN"},
			{Code: "3100", Name: "Share Capital", Type: AccountTypeEquity, ParentCode: "3000", Currency: "NGN"},
			{Code: "3200", Name: "Retained Earnings", Type: AccountTypeEquity, ParentCode: "3000", Currency: "NGN"},
			{Code: "3300", Name: "Reserves", Type: AccountTypeEquity, ParentCode: "3000", Currency: "NGN"},
			{Code: "3900", Name: "Income Summary", Type: AccountTypeEquity, ParentCode: "3000", Currency: "NGN"},

			{Code: "4000", Name: "Revenue", Type: AccountTypeRevenue, Currency: "NGN"},
			{Code: "4100", Name: "Interest Income", Type: AccountTypeRevenue, ParentCode: "4000", Currency: "NGN"},
			{Code: "4110", Name: "Interest on Mortgages", Type: AccountTypeRevenue, ParentCode: "4100", Currency: "NGN"},
			{Code: "4120", Name: "Interest on Investments", Type: AccountTypeRevenue, ParentCode: "4100", Currency: "NGN"},
			{Code: "4200", Name: "Fee Income", Type: AccountTypeRevenue, ParentCode: "4000", Currency: "NGN"},
			{Code: "4210", Name: "Mortgage Processing Fees", Type: AccountTypeRevenue, ParentCode: "4200", Currency: "NGN"},
			{Code: "4220", Name: "Valuation Fees", Type: AccountTypeRevenue, ParentCode: "4200", Currency: "NGN"},
			{Code: "4230", Name: "Insurance Commissions", Type: AccountTypeRevenue, ParentCode: "4200", Currency: "NGN"},
			{Code: "4300", Name: "Real Estate Income", Type: AccountTypeRevenue, ParentCode: "4000", Currency: "NGN"},
			{Code: "4310", Name: "Property Sales", Type: AccountTypeRevenue, ParentCode: "4300", Currency: "NGN"},
			{Code: "4320", Name: "Rental Income", Type: AccountTypeRevenue, ParentCode: "4300", Currency: "NGN"},

			{Code: "5000", Name: "Expenses", Type: AccountTypeExpense, Currency: "NGN"},
			{Code: "5100", Name: "Interest Expense", Type: AccountTypeExpense, ParentCode: "5000", Currency: "NGN"},
			{Code: "5200", Name: "Provision for Loan Losses", Type: AccountTypeExpense, ParentCode: "5000", Currency: "NGN"},
			{Code: "5300", Name: "Personnel Expenses", Type: AccountTypeExpense, ParentCode: "5000", Currency: "NGN"},
			{Code: "5400", Name: "Administrative Expenses", Type: AccountTypeExpense, ParentCode: "5000", Currency: "NGN"},
			{Code: "5500", Name: "Depreciation", Type: AccountTypeExpense, ParentCode: "5000", Currency: "NGN"},
			{Code: "5600", Name: "Real Estate Costs", Type: AccountTypeExpense, ParentCode: "5000", Currency: "NGN"},
			{Code: "5610", Name: "Property Maintenance", Type: AccountTypeExpense, ParentCode: "5600", Currency: "NGN"},
			{Code: "5620", Name: "Foreclosure Costs", Type: AccountTypeExpense, ParentCode: "5600", Currency: "NGN"},
			{Code: "5700", Name: "Income Tax Expense", Type: AccountTypeExpense, ParentCode: "5000", Currency: "NGN"},
		},
	}
}

func (s *TemplateService) getAgriculturalBankTemplate() *AccountTemplate {
	return &AccountTemplate{
		ID:          "builtin-agricultural",
		Name:        "Agricultural Bank Standard CoA",
		Description: "Chart of Accounts for Nigerian Agricultural Finance Institutions",
		BankType:    BankTypeAgricultural,
		IsDefault:   true,
		Accounts: []TemplateAccount{
			{Code: "1000", Name: "Assets", Type: AccountTypeAsset, Currency: "NGN"},
			{Code: "1100", Name: "Cash and Bank Balances", Type: AccountTypeAsset, ParentCode: "1000", Currency: "NGN"},
			{Code: "1200", Name: "Agricultural Loans", Type: AccountTypeAsset, ParentCode: "1000", Currency: "NGN"},
			{Code: "1210", Name: "Crop Production Loans", Type: AccountTypeAsset, ParentCode: "1200", Currency: "NGN"},
			{Code: "1220", Name: "Livestock Loans", Type: AccountTypeAsset, ParentCode: "1200", Currency: "NGN"},
			{Code: "1230", Name: "Fishery Loans", Type: AccountTypeAsset, ParentCode: "1200", Currency: "NGN"},
			{Code: "1240", Name: "Agro-Processing Loans", Type: AccountTypeAsset, ParentCode: "1200", Currency: "NGN"},
			{Code: "1250", Name: "Farm Equipment Loans", Type: AccountTypeAsset, ParentCode: "1200", Currency: "NGN"},
			{Code: "1260", Name: "Anchor Borrower Loans", Type: AccountTypeAsset, ParentCode: "1200", Currency: "NGN"},
			{Code: "1270", Name: "Agricultural Loan Provision", Type: AccountTypeAsset, ParentCode: "1200", Currency: "NGN"},
			{Code: "1300", Name: "Warehouse Receipts", Type: AccountTypeAsset, ParentCode: "1000", Currency: "NGN"},
			{Code: "1400", Name: "Investments", Type: AccountTypeAsset, ParentCode: "1000", Currency: "NGN"},
			{Code: "1500", Name: "Fixed Assets", Type: AccountTypeAsset, ParentCode: "1000", Currency: "NGN"},
			{Code: "1510", Name: "Agricultural Equipment", Type: AccountTypeAsset, ParentCode: "1500", Currency: "NGN"},
			{Code: "1520", Name: "Warehouses", Type: AccountTypeAsset, ParentCode: "1500", Currency: "NGN"},
			{Code: "1530", Name: "Office Equipment", Type: AccountTypeAsset, ParentCode: "1500", Currency: "NGN"},
			{Code: "1600", Name: "Other Assets", Type: AccountTypeAsset, ParentCode: "1000", Currency: "NGN"},

			{Code: "2000", Name: "Liabilities", Type: AccountTypeLiability, Currency: "NGN"},
			{Code: "2100", Name: "Customer Deposits", Type: AccountTypeLiability, ParentCode: "2000", Currency: "NGN"},
			{Code: "2110", Name: "Farmer Savings", Type: AccountTypeLiability, ParentCode: "2100", Currency: "NGN"},
			{Code: "2120", Name: "Cooperative Deposits", Type: AccountTypeLiability, ParentCode: "2100", Currency: "NGN"},
			{Code: "2200", Name: "Borrowings", Type: AccountTypeLiability, ParentCode: "2000", Currency: "NGN"},
			{Code: "2210", Name: "CBN Agricultural Facilities", Type: AccountTypeLiability, ParentCode: "2200", Currency: "NGN"},
			{Code: "2220", Name: "BOA Refinancing", Type: AccountTypeLiability, ParentCode: "2200", Currency: "NGN"},
			{Code: "2230", Name: "Development Partner Funds", Type: AccountTypeLiability, ParentCode: "2200", Currency: "NGN"},
			{Code: "2300", Name: "Other Liabilities", Type: AccountTypeLiability, ParentCode: "2000", Currency: "NGN"},

			{Code: "3000", Name: "Equity", Type: AccountTypeEquity, Currency: "NGN"},
			{Code: "3100", Name: "Share Capital", Type: AccountTypeEquity, ParentCode: "3000", Currency: "NGN"},
			{Code: "3200", Name: "Retained Earnings", Type: AccountTypeEquity, ParentCode: "3000", Currency: "NGN"},
			{Code: "3300", Name: "Reserves", Type: AccountTypeEquity, ParentCode: "3000", Currency: "NGN"},
			{Code: "3900", Name: "Income Summary", Type: AccountTypeEquity, ParentCode: "3000", Currency: "NGN"},

			{Code: "4000", Name: "Revenue", Type: AccountTypeRevenue, Currency: "NGN"},
			{Code: "4100", Name: "Interest Income", Type: AccountTypeRevenue, ParentCode: "4000", Currency: "NGN"},
			{Code: "4110", Name: "Interest on Agricultural Loans", Type: AccountTypeRevenue, ParentCode: "4100", Currency: "NGN"},
			{Code: "4120", Name: "Interest on Investments", Type: AccountTypeRevenue, ParentCode: "4100", Currency: "NGN"},
			{Code: "4200", Name: "Fee Income", Type: AccountTypeRevenue, ParentCode: "4000", Currency: "NGN"},
			{Code: "4210", Name: "Loan Processing Fees", Type: AccountTypeRevenue, ParentCode: "4200", Currency: "NGN"},
			{Code: "4220", Name: "Insurance Commissions", Type: AccountTypeRevenue, ParentCode: "4200", Currency: "NGN"},
			{Code: "4230", Name: "Warehouse Receipt Fees", Type: AccountTypeRevenue, ParentCode: "4200", Currency: "NGN"},
			{Code: "4300", Name: "Agricultural Services Income", Type: AccountTypeRevenue, ParentCode: "4000", Currency: "NGN"},
			{Code: "4310", Name: "Extension Services", Type: AccountTypeRevenue, ParentCode: "4300", Currency: "NGN"},
			{Code: "4320", Name: "Input Supply Margins", Type: AccountTypeRevenue, ParentCode: "4300", Currency: "NGN"},
			{Code: "4400", Name: "Grant Income", Type: AccountTypeRevenue, ParentCode: "4000", Currency: "NGN"},

			{Code: "5000", Name: "Expenses", Type: AccountTypeExpense, Currency: "NGN"},
			{Code: "5100", Name: "Interest Expense", Type: AccountTypeExpense, ParentCode: "5000", Currency: "NGN"},
			{Code: "5200", Name: "Provision for Loan Losses", Type: AccountTypeExpense, ParentCode: "5000", Currency: "NGN"},
			{Code: "5300", Name: "Personnel Expenses", Type: AccountTypeExpense, ParentCode: "5000", Currency: "NGN"},
			{Code: "5310", Name: "Salaries", Type: AccountTypeExpense, ParentCode: "5300", Currency: "NGN"},
			{Code: "5320", Name: "Extension Officers", Type: AccountTypeExpense, ParentCode: "5300", Currency: "NGN"},
			{Code: "5400", Name: "Agricultural Program Costs", Type: AccountTypeExpense, ParentCode: "5000", Currency: "NGN"},
			{Code: "5410", Name: "Farmer Training", Type: AccountTypeExpense, ParentCode: "5400", Currency: "NGN"},
			{Code: "5420", Name: "Input Subsidies", Type: AccountTypeExpense, ParentCode: "5400", Currency: "NGN"},
			{Code: "5430", Name: "Crop Insurance Premiums", Type: AccountTypeExpense, ParentCode: "5400", Currency: "NGN"},
			{Code: "5500", Name: "Administrative Expenses", Type: AccountTypeExpense, ParentCode: "5000", Currency: "NGN"},
			{Code: "5600", Name: "Depreciation", Type: AccountTypeExpense, ParentCode: "5000", Currency: "NGN"},
			{Code: "5700", Name: "Income Tax Expense", Type: AccountTypeExpense, ParentCode: "5000", Currency: "NGN"},
		},
	}
}

func (s *TemplateService) InitializeDefaultTemplates(ctx context.Context) error {
	if s.store == nil {
		return errors.New("postgres store not initialized")
	}

	templates := []*AccountTemplate{
		s.getCommercialBankTemplate(),
		s.getMFBTemplate(),
		s.getFintechTemplate(),
		s.getMortgageBankTemplate(),
		s.getAgriculturalBankTemplate(),
	}

	for _, template := range templates {
		template.ID = uuid.New().String()
		template.CreatedAt = time.Now()
		template.UpdatedAt = time.Now()

		if err := s.store.SaveAccountTemplate(ctx, *template); err != nil {
			return fmt.Errorf("failed to save template %s: %w", template.Name, err)
		}
	}

	return nil
}
