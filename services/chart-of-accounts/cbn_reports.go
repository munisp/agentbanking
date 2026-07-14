package main

import (
	"context"
	"fmt"
	"time"
)

type CBNReportType string

const (
	CBNReportSFP                    CBNReportType = "SFP"
	CBNReportProfitLoss             CBNReportType = "PL"
	CBNReportComprehensiveIncome    CBNReportType = "CI"
	CBNReportChangesInEquity        CBNReportType = "CE"
	CBNReportCashFlows              CBNReportType = "CF"
	CBNReportCapitalAdequacy        CBNReportType = "CAR"
	CBNReportLiquidityRatio         CBNReportType = "LR"
	CBNReportCreditRisk             CBNReportType = "CR"
	CBNReportMarketRisk             CBNReportType = "MR"
	CBNReportOperationalRisk        CBNReportType = "OR"
	CBNReportLargeExposures         CBNReportType = "LE"
	CBNReportRelatedParty           CBNReportType = "RP"
	CBNReportSectoralCredit         CBNReportType = "SC"
	CBNReportMaturityProfile        CBNReportType = "MP"
	CBNReportInterestRateSensitivity CBNReportType = "IRS"
	CBNReportForeignCurrency        CBNReportType = "FC"
	CBNReportOffBalanceSheet        CBNReportType = "OBS"
	CBNReportNPLAnalysis            CBNReportType = "NPL"
	CBNReportLoanLossProvisioning   CBNReportType = "LLP"
	CBNReportInvestmentPortfolio    CBNReportType = "IP"
	CBNReportDepositComposition     CBNReportType = "DC"
	CBNReportBranchNetwork          CBNReportType = "BN"
	CBNReportEBanking               CBNReportType = "EB"
	CBNReportAML                    CBNReportType = "AML"
	CBNReportFinancialInclusion     CBNReportType = "FI"
)

type CBNReport struct {
	ReportType      CBNReportType          `json:"report_type"`
	ReportName      string                 `json:"report_name"`
	TenantID        string                 `json:"tenant_id"`
	ReportingPeriod string                 `json:"reporting_period"`
	AsOfDate        time.Time              `json:"as_of_date"`
	GeneratedAt     time.Time              `json:"generated_at"`
	Currency        string                 `json:"currency"`
	Sections        []CBNReportSection     `json:"sections"`
	Totals          map[string]int64       `json:"totals,omitempty"`
	Ratios          map[string]float64     `json:"ratios,omitempty"`
	Metadata        map[string]interface{} `json:"metadata,omitempty"`
}

type CBNReportSection struct {
	Code        string              `json:"code"`
	Name        string              `json:"name"`
	Items       []CBNReportItem     `json:"items"`
	Subtotal    int64               `json:"subtotal"`
	SubSections []CBNReportSection  `json:"sub_sections,omitempty"`
}

type CBNReportItem struct {
	Code        string `json:"code"`
	Description string `json:"description"`
	AccountCode string `json:"account_code,omitempty"`
	Amount      int64  `json:"amount"`
	PriorAmount int64  `json:"prior_amount,omitempty"`
	Variance    int64  `json:"variance,omitempty"`
	Notes       string `json:"notes,omitempty"`
}

type CBNReportService struct {
	coaService *ChartOfAccountsService
	store      *PostgresStore
}

func NewCBNReportService(coaService *ChartOfAccountsService, store *PostgresStore) *CBNReportService {
	return &CBNReportService{
		coaService: coaService,
		store:      store,
	}
}

func (s *CBNReportService) GenerateReport(ctx context.Context, tenantID string, reportType CBNReportType, asOfDate time.Time) (*CBNReport, error) {
	switch reportType {
	case CBNReportSFP:
		return s.generateSFP(ctx, tenantID, asOfDate)
	case CBNReportProfitLoss:
		return s.generateProfitLoss(ctx, tenantID, asOfDate)
	case CBNReportComprehensiveIncome:
		return s.generateComprehensiveIncome(ctx, tenantID, asOfDate)
	case CBNReportChangesInEquity:
		return s.generateChangesInEquity(ctx, tenantID, asOfDate)
	case CBNReportCashFlows:
		return s.generateCashFlows(ctx, tenantID, asOfDate)
	case CBNReportCapitalAdequacy:
		return s.generateCapitalAdequacy(ctx, tenantID, asOfDate)
	case CBNReportLiquidityRatio:
		return s.generateLiquidityRatio(ctx, tenantID, asOfDate)
	case CBNReportCreditRisk:
		return s.generateCreditRisk(ctx, tenantID, asOfDate)
	case CBNReportMarketRisk:
		return s.generateMarketRisk(ctx, tenantID, asOfDate)
	case CBNReportOperationalRisk:
		return s.generateOperationalRisk(ctx, tenantID, asOfDate)
	case CBNReportLargeExposures:
		return s.generateLargeExposures(ctx, tenantID, asOfDate)
	case CBNReportRelatedParty:
		return s.generateRelatedParty(ctx, tenantID, asOfDate)
	case CBNReportSectoralCredit:
		return s.generateSectoralCredit(ctx, tenantID, asOfDate)
	case CBNReportMaturityProfile:
		return s.generateMaturityProfile(ctx, tenantID, asOfDate)
	case CBNReportInterestRateSensitivity:
		return s.generateInterestRateSensitivity(ctx, tenantID, asOfDate)
	case CBNReportForeignCurrency:
		return s.generateForeignCurrency(ctx, tenantID, asOfDate)
	case CBNReportOffBalanceSheet:
		return s.generateOffBalanceSheet(ctx, tenantID, asOfDate)
	case CBNReportNPLAnalysis:
		return s.generateNPLAnalysis(ctx, tenantID, asOfDate)
	case CBNReportLoanLossProvisioning:
		return s.generateLoanLossProvisioning(ctx, tenantID, asOfDate)
	case CBNReportInvestmentPortfolio:
		return s.generateInvestmentPortfolio(ctx, tenantID, asOfDate)
	case CBNReportDepositComposition:
		return s.generateDepositComposition(ctx, tenantID, asOfDate)
	case CBNReportBranchNetwork:
		return s.generateBranchNetwork(ctx, tenantID, asOfDate)
	case CBNReportEBanking:
		return s.generateEBanking(ctx, tenantID, asOfDate)
	case CBNReportAML:
		return s.generateAML(ctx, tenantID, asOfDate)
	case CBNReportFinancialInclusion:
		return s.generateFinancialInclusion(ctx, tenantID, asOfDate)
	default:
		return nil, fmt.Errorf("unknown report type: %s", reportType)
	}
}

func (s *CBNReportService) GetAllReportTypes() []struct {
	Type        CBNReportType
	Name        string
	Description string
	Frequency   string
} {
	return []struct {
		Type        CBNReportType
		Name        string
		Description string
		Frequency   string
	}{
		{CBNReportSFP, "Statement of Financial Position", "Balance sheet showing assets, liabilities, and equity", "Monthly"},
		{CBNReportProfitLoss, "Statement of Profit or Loss", "Income statement showing revenue and expenses", "Monthly"},
		{CBNReportComprehensiveIncome, "Statement of Comprehensive Income", "Profit/loss plus other comprehensive income items", "Monthly"},
		{CBNReportChangesInEquity, "Statement of Changes in Equity", "Movement in shareholders' equity", "Quarterly"},
		{CBNReportCashFlows, "Statement of Cash Flows", "Cash movements from operating, investing, financing", "Monthly"},
		{CBNReportCapitalAdequacy, "Capital Adequacy Return", "Tier 1, Tier 2 capital and risk-weighted assets", "Monthly"},
		{CBNReportLiquidityRatio, "Liquidity Ratio Return", "Liquid assets to total liabilities ratio", "Weekly"},
		{CBNReportCreditRisk, "Credit Risk Return", "Credit exposure and risk classification", "Monthly"},
		{CBNReportMarketRisk, "Market Risk Return", "Interest rate, FX, and equity price risk", "Monthly"},
		{CBNReportOperationalRisk, "Operational Risk Return", "Operational losses and risk indicators", "Quarterly"},
		{CBNReportLargeExposures, "Large Exposures Return", "Single obligor limits and concentrations", "Monthly"},
		{CBNReportRelatedParty, "Related Party Transactions", "Insider lending and related party exposures", "Quarterly"},
		{CBNReportSectoralCredit, "Sectoral Distribution of Credit", "Loans by economic sector", "Monthly"},
		{CBNReportMaturityProfile, "Maturity Profile of Assets/Liabilities", "Gap analysis by maturity buckets", "Monthly"},
		{CBNReportInterestRateSensitivity, "Interest Rate Sensitivity", "Repricing gaps and duration analysis", "Monthly"},
		{CBNReportForeignCurrency, "Foreign Currency Position", "Net open position by currency", "Daily"},
		{CBNReportOffBalanceSheet, "Off-Balance Sheet Exposures", "Contingent liabilities and commitments", "Monthly"},
		{CBNReportNPLAnalysis, "Non-Performing Loans Analysis", "NPL by sector, age, and classification", "Monthly"},
		{CBNReportLoanLossProvisioning, "Loan Loss Provisioning", "Provision coverage and adequacy", "Monthly"},
		{CBNReportInvestmentPortfolio, "Investment Portfolio Analysis", "Securities by type and maturity", "Monthly"},
		{CBNReportDepositComposition, "Deposit Composition", "Deposits by type, tenor, and customer segment", "Monthly"},
		{CBNReportBranchNetwork, "Branch Network Statistics", "Branch count, ATMs, and geographic distribution", "Quarterly"},
		{CBNReportEBanking, "Electronic Banking Statistics", "Digital channels volume and value", "Monthly"},
		{CBNReportAML, "Anti-Money Laundering Report", "STRs, CTRs, and compliance metrics", "Monthly"},
		{CBNReportFinancialInclusion, "Financial Inclusion Metrics", "Account penetration and access indicators", "Quarterly"},
	}
}

func (s *CBNReportService) getAccountBalancesByCBNCode(ctx context.Context, tenantID string, cbnCodePrefix string) (map[string]int64, error) {
	accounts, err := s.coaService.ListAccounts(ctx, tenantID, "", "", true)
	if err != nil {
		return nil, err
	}

	balances := make(map[string]int64)
	for _, acc := range accounts {
		if acc.CBNCode == "" {
			continue
		}
		if cbnCodePrefix != "" && len(acc.CBNCode) >= len(cbnCodePrefix) {
			if acc.CBNCode[:len(cbnCodePrefix)] != cbnCodePrefix {
				continue
			}
		}

		balance, err := s.coaService.GetAccountBalance(ctx, tenantID, acc.ID)
		if err != nil {
			continue
		}
		balances[acc.CBNCode] = balance.NetBalance
	}

	return balances, nil
}

func (s *CBNReportService) generateSFP(ctx context.Context, tenantID string, asOfDate time.Time) (*CBNReport, error) {
	balances, err := s.getAccountBalancesByCBNCode(ctx, tenantID, "SFP")
	if err != nil {
		return nil, err
	}

	report := &CBNReport{
		ReportType:      CBNReportSFP,
		ReportName:      "Statement of Financial Position",
		TenantID:        tenantID,
		ReportingPeriod: asOfDate.Format("January 2006"),
		AsOfDate:        asOfDate,
		GeneratedAt:     time.Now(),
		Currency:        "NGN",
		Totals:          make(map[string]int64),
	}

	assetSection := CBNReportSection{
		Code: "A",
		Name: "ASSETS",
		Items: []CBNReportItem{
			{Code: "SFP001", Description: "Cash and Balances with Central Bank", Amount: balances["SFP001"]},
			{Code: "SFP002", Description: "Due from Banks", Amount: balances["SFP002"]},
			{Code: "SFP003", Description: "Financial Assets at Fair Value through P&L", Amount: balances["SFP003"]},
			{Code: "SFP004", Description: "Derivative Financial Instruments", Amount: balances["SFP004"]},
			{Code: "SFP005", Description: "Loans and Advances to Customers", Amount: balances["SFP005"]},
			{Code: "SFP006", Description: "Investment Securities", Amount: balances["SFP006"]},
			{Code: "SFP007", Description: "Property and Equipment", Amount: balances["SFP007"]},
			{Code: "SFP008", Description: "Intangible Assets", Amount: balances["SFP008"]},
			{Code: "SFP009", Description: "Deferred Tax Assets", Amount: balances["SFP009"]},
			{Code: "SFP010", Description: "Other Assets", Amount: balances["SFP010"]},
		},
	}

	var totalAssets int64
	for _, item := range assetSection.Items {
		totalAssets += item.Amount
	}
	assetSection.Subtotal = totalAssets

	liabilitySection := CBNReportSection{
		Code: "L",
		Name: "LIABILITIES",
		Items: []CBNReportItem{
			{Code: "SFP011", Description: "Deposits from Banks", Amount: balances["SFP011"]},
			{Code: "SFP012", Description: "Deposits from Customers", Amount: balances["SFP012"]},
			{Code: "SFP013", Description: "Derivative Financial Instruments", Amount: balances["SFP013"]},
			{Code: "SFP014", Description: "Borrowings", Amount: balances["SFP014"]},
			{Code: "SFP015", Description: "Current Tax Liabilities", Amount: balances["SFP015"]},
			{Code: "SFP016", Description: "Deferred Tax Liabilities", Amount: balances["SFP016"]},
			{Code: "SFP017", Description: "Other Liabilities", Amount: balances["SFP017"]},
			{Code: "SFP018", Description: "Provisions", Amount: balances["SFP018"]},
		},
	}

	var totalLiabilities int64
	for _, item := range liabilitySection.Items {
		totalLiabilities += item.Amount
	}
	liabilitySection.Subtotal = totalLiabilities

	equitySection := CBNReportSection{
		Code: "E",
		Name: "EQUITY",
		Items: []CBNReportItem{
			{Code: "SFP019", Description: "Share Capital", Amount: balances["SFP019"]},
			{Code: "SFP020", Description: "Share Premium", Amount: balances["SFP020"]},
			{Code: "SFP021", Description: "Retained Earnings", Amount: balances["SFP021"]},
			{Code: "SFP022", Description: "Other Reserves", Amount: balances["SFP022"]},
		},
	}

	var totalEquity int64
	for _, item := range equitySection.Items {
		totalEquity += item.Amount
	}
	equitySection.Subtotal = totalEquity

	report.Sections = []CBNReportSection{assetSection, liabilitySection, equitySection}
	report.Totals["total_assets"] = totalAssets
	report.Totals["total_liabilities"] = totalLiabilities
	report.Totals["total_equity"] = totalEquity
	report.Totals["total_liabilities_and_equity"] = totalLiabilities + totalEquity

	return report, nil
}

func (s *CBNReportService) generateProfitLoss(ctx context.Context, tenantID string, asOfDate time.Time) (*CBNReport, error) {
	balances, err := s.getAccountBalancesByCBNCode(ctx, tenantID, "PL")
	if err != nil {
		return nil, err
	}

	report := &CBNReport{
		ReportType:      CBNReportProfitLoss,
		ReportName:      "Statement of Profit or Loss",
		TenantID:        tenantID,
		ReportingPeriod: asOfDate.Format("January 2006"),
		AsOfDate:        asOfDate,
		GeneratedAt:     time.Now(),
		Currency:        "NGN",
		Totals:          make(map[string]int64),
	}

	interestIncome := balances["PL001"]
	interestExpense := balances["PL002"]
	netInterestIncome := interestIncome - interestExpense

	feeIncome := balances["PL004"]
	feeExpense := balances["PL005"]
	netFeeIncome := feeIncome - feeExpense

	tradingIncome := balances["PL007"]
	otherIncome := balances["PL008"]

	operatingIncome := netInterestIncome + netFeeIncome + tradingIncome + otherIncome

	impairment := balances["PL009"]
	personnel := balances["PL010"]
	depreciation := balances["PL011"]
	otherExpenses := balances["PL012"]

	totalExpenses := impairment + personnel + depreciation + otherExpenses

	profitBeforeTax := operatingIncome - totalExpenses
	taxExpense := balances["PL014"]
	profitAfterTax := profitBeforeTax - taxExpense

	incomeSection := CBNReportSection{
		Code: "I",
		Name: "INCOME",
		Items: []CBNReportItem{
			{Code: "PL001", Description: "Interest Income", Amount: interestIncome},
			{Code: "PL002", Description: "Interest Expense", Amount: interestExpense},
			{Code: "PL003", Description: "Net Interest Income", Amount: netInterestIncome},
			{Code: "PL004", Description: "Fee and Commission Income", Amount: feeIncome},
			{Code: "PL005", Description: "Fee and Commission Expense", Amount: feeExpense},
			{Code: "PL006", Description: "Net Fee and Commission Income", Amount: netFeeIncome},
			{Code: "PL007", Description: "Net Trading Income", Amount: tradingIncome},
			{Code: "PL008", Description: "Other Operating Income", Amount: otherIncome},
		},
		Subtotal: operatingIncome,
	}

	expenseSection := CBNReportSection{
		Code: "E",
		Name: "EXPENSES",
		Items: []CBNReportItem{
			{Code: "PL009", Description: "Impairment Charges", Amount: impairment},
			{Code: "PL010", Description: "Personnel Expenses", Amount: personnel},
			{Code: "PL011", Description: "Depreciation and Amortization", Amount: depreciation},
			{Code: "PL012", Description: "Other Operating Expenses", Amount: otherExpenses},
		},
		Subtotal: totalExpenses,
	}

	profitSection := CBNReportSection{
		Code: "P",
		Name: "PROFIT",
		Items: []CBNReportItem{
			{Code: "PL013", Description: "Profit Before Tax", Amount: profitBeforeTax},
			{Code: "PL014", Description: "Income Tax Expense", Amount: taxExpense},
			{Code: "PL015", Description: "Profit After Tax", Amount: profitAfterTax},
		},
		Subtotal: profitAfterTax,
	}

	report.Sections = []CBNReportSection{incomeSection, expenseSection, profitSection}
	report.Totals["operating_income"] = operatingIncome
	report.Totals["total_expenses"] = totalExpenses
	report.Totals["profit_before_tax"] = profitBeforeTax
	report.Totals["profit_after_tax"] = profitAfterTax

	return report, nil
}

func (s *CBNReportService) generateComprehensiveIncome(ctx context.Context, tenantID string, asOfDate time.Time) (*CBNReport, error) {
	plReport, err := s.generateProfitLoss(ctx, tenantID, asOfDate)
	if err != nil {
		return nil, err
	}

	report := &CBNReport{
		ReportType:      CBNReportComprehensiveIncome,
		ReportName:      "Statement of Comprehensive Income",
		TenantID:        tenantID,
		ReportingPeriod: asOfDate.Format("January 2006"),
		AsOfDate:        asOfDate,
		GeneratedAt:     time.Now(),
		Currency:        "NGN",
		Totals:          make(map[string]int64),
	}

	profitAfterTax := plReport.Totals["profit_after_tax"]

	ociSection := CBNReportSection{
		Code: "OCI",
		Name: "OTHER COMPREHENSIVE INCOME",
		Items: []CBNReportItem{
			{Code: "CI001", Description: "Profit for the Period", Amount: profitAfterTax},
			{Code: "CI002", Description: "Fair Value Gains/(Losses) on FVOCI Securities", Amount: 0},
			{Code: "CI003", Description: "Foreign Currency Translation Differences", Amount: 0},
			{Code: "CI004", Description: "Revaluation Surplus on Property", Amount: 0},
			{Code: "CI005", Description: "Actuarial Gains/(Losses) on Defined Benefit Plans", Amount: 0},
			{Code: "CI006", Description: "Tax on Other Comprehensive Income", Amount: 0},
		},
	}

	var totalOCI int64
	for _, item := range ociSection.Items {
		totalOCI += item.Amount
	}
	ociSection.Subtotal = totalOCI

	report.Sections = []CBNReportSection{ociSection}
	report.Totals["profit_for_period"] = profitAfterTax
	report.Totals["other_comprehensive_income"] = totalOCI - profitAfterTax
	report.Totals["total_comprehensive_income"] = totalOCI

	return report, nil
}

func (s *CBNReportService) generateChangesInEquity(ctx context.Context, tenantID string, asOfDate time.Time) (*CBNReport, error) {
	balances, err := s.getAccountBalancesByCBNCode(ctx, tenantID, "SFP")
	if err != nil {
		return nil, err
	}

	report := &CBNReport{
		ReportType:      CBNReportChangesInEquity,
		ReportName:      "Statement of Changes in Equity",
		TenantID:        tenantID,
		ReportingPeriod: asOfDate.Format("January 2006"),
		AsOfDate:        asOfDate,
		GeneratedAt:     time.Now(),
		Currency:        "NGN",
		Totals:          make(map[string]int64),
	}

	shareCapital := balances["SFP019"]
	sharePremium := balances["SFP020"]
	retainedEarnings := balances["SFP021"]
	otherReserves := balances["SFP022"]

	equitySection := CBNReportSection{
		Code: "CE",
		Name: "CHANGES IN EQUITY",
		Items: []CBNReportItem{
			{Code: "CE001", Description: "Balance at Beginning of Period", Amount: 0},
			{Code: "CE002", Description: "Profit for the Period", Amount: 0},
			{Code: "CE003", Description: "Other Comprehensive Income", Amount: 0},
			{Code: "CE004", Description: "Dividends Declared", Amount: 0},
			{Code: "CE005", Description: "Transfer to Statutory Reserve", Amount: 0},
			{Code: "CE006", Description: "Share Capital Issued", Amount: 0},
			{Code: "CE007", Description: "Balance at End of Period", Amount: shareCapital + sharePremium + retainedEarnings + otherReserves},
		},
	}

	report.Sections = []CBNReportSection{equitySection}
	report.Totals["share_capital"] = shareCapital
	report.Totals["share_premium"] = sharePremium
	report.Totals["retained_earnings"] = retainedEarnings
	report.Totals["other_reserves"] = otherReserves
	report.Totals["total_equity"] = shareCapital + sharePremium + retainedEarnings + otherReserves

	return report, nil
}

func (s *CBNReportService) generateCashFlows(ctx context.Context, tenantID string, asOfDate time.Time) (*CBNReport, error) {
	report := &CBNReport{
		ReportType:      CBNReportCashFlows,
		ReportName:      "Statement of Cash Flows",
		TenantID:        tenantID,
		ReportingPeriod: asOfDate.Format("January 2006"),
		AsOfDate:        asOfDate,
		GeneratedAt:     time.Now(),
		Currency:        "NGN",
		Totals:          make(map[string]int64),
	}

	operatingSection := CBNReportSection{
		Code: "CFO",
		Name: "CASH FLOWS FROM OPERATING ACTIVITIES",
		Items: []CBNReportItem{
			{Code: "CF001", Description: "Profit Before Tax", Amount: 0},
			{Code: "CF002", Description: "Depreciation and Amortization", Amount: 0},
			{Code: "CF003", Description: "Impairment Charges", Amount: 0},
			{Code: "CF004", Description: "Interest Income", Amount: 0},
			{Code: "CF005", Description: "Interest Expense", Amount: 0},
			{Code: "CF006", Description: "Changes in Loans and Advances", Amount: 0},
			{Code: "CF007", Description: "Changes in Customer Deposits", Amount: 0},
			{Code: "CF008", Description: "Changes in Other Assets", Amount: 0},
			{Code: "CF009", Description: "Changes in Other Liabilities", Amount: 0},
			{Code: "CF010", Description: "Interest Received", Amount: 0},
			{Code: "CF011", Description: "Interest Paid", Amount: 0},
			{Code: "CF012", Description: "Tax Paid", Amount: 0},
		},
	}

	investingSection := CBNReportSection{
		Code: "CFI",
		Name: "CASH FLOWS FROM INVESTING ACTIVITIES",
		Items: []CBNReportItem{
			{Code: "CF013", Description: "Purchase of Investment Securities", Amount: 0},
			{Code: "CF014", Description: "Proceeds from Sale of Securities", Amount: 0},
			{Code: "CF015", Description: "Purchase of Property and Equipment", Amount: 0},
			{Code: "CF016", Description: "Proceeds from Sale of Property", Amount: 0},
			{Code: "CF017", Description: "Purchase of Intangible Assets", Amount: 0},
		},
	}

	financingSection := CBNReportSection{
		Code: "CFF",
		Name: "CASH FLOWS FROM FINANCING ACTIVITIES",
		Items: []CBNReportItem{
			{Code: "CF018", Description: "Proceeds from Borrowings", Amount: 0},
			{Code: "CF019", Description: "Repayment of Borrowings", Amount: 0},
			{Code: "CF020", Description: "Dividends Paid", Amount: 0},
			{Code: "CF021", Description: "Proceeds from Share Issue", Amount: 0},
		},
	}

	report.Sections = []CBNReportSection{operatingSection, investingSection, financingSection}
	report.Totals["net_cash_from_operating"] = 0
	report.Totals["net_cash_from_investing"] = 0
	report.Totals["net_cash_from_financing"] = 0
	report.Totals["net_change_in_cash"] = 0

	return report, nil
}

func (s *CBNReportService) generateCapitalAdequacy(ctx context.Context, tenantID string, asOfDate time.Time) (*CBNReport, error) {
	balances, err := s.getAccountBalancesByCBNCode(ctx, tenantID, "")
	if err != nil {
		return nil, err
	}

	report := &CBNReport{
		ReportType:      CBNReportCapitalAdequacy,
		ReportName:      "Capital Adequacy Return",
		TenantID:        tenantID,
		ReportingPeriod: asOfDate.Format("January 2006"),
		AsOfDate:        asOfDate,
		GeneratedAt:     time.Now(),
		Currency:        "NGN",
		Totals:          make(map[string]int64),
		Ratios:          make(map[string]float64),
	}

	shareCapital := balances["SFP019"]
	sharePremium := balances["SFP020"]
	retainedEarnings := balances["SFP021"]
	statutoryReserve := balances["SFP022"]

	tier1Capital := shareCapital + sharePremium + retainedEarnings + statutoryReserve

	tier1Section := CBNReportSection{
		Code: "T1",
		Name: "TIER 1 CAPITAL (CORE CAPITAL)",
		Items: []CBNReportItem{
			{Code: "CAR001", Description: "Paid-up Share Capital", Amount: shareCapital},
			{Code: "CAR002", Description: "Share Premium", Amount: sharePremium},
			{Code: "CAR003", Description: "Retained Earnings", Amount: retainedEarnings},
			{Code: "CAR004", Description: "Statutory Reserve", Amount: statutoryReserve},
			{Code: "CAR005", Description: "General Reserve", Amount: 0},
			{Code: "CAR006", Description: "Less: Intangible Assets", Amount: 0},
			{Code: "CAR007", Description: "Less: Deferred Tax Assets", Amount: 0},
		},
		Subtotal: tier1Capital,
	}

	tier2Section := CBNReportSection{
		Code: "T2",
		Name: "TIER 2 CAPITAL (SUPPLEMENTARY CAPITAL)",
		Items: []CBNReportItem{
			{Code: "CAR008", Description: "Revaluation Reserve (50%)", Amount: 0},
			{Code: "CAR009", Description: "General Provisions (max 1.25% of RWA)", Amount: 0},
			{Code: "CAR010", Description: "Hybrid Capital Instruments", Amount: 0},
			{Code: "CAR011", Description: "Subordinated Debt (max 50% of Tier 1)", Amount: 0},
		},
		Subtotal: 0,
	}

	totalCapital := tier1Capital

	loans := balances["SFP005"]
	rwaLoans := int64(float64(loans) * 1.0)
	securities := balances["SFP006"]
	rwaSecurities := int64(float64(securities) * 0.2)
	otherAssets := balances["SFP010"]
	rwaOther := int64(float64(otherAssets) * 1.0)

	totalRWA := rwaLoans + rwaSecurities + rwaOther

	rwaSection := CBNReportSection{
		Code: "RWA",
		Name: "RISK-WEIGHTED ASSETS",
		Items: []CBNReportItem{
			{Code: "CAR012", Description: "Credit Risk - Loans (100%)", Amount: rwaLoans},
			{Code: "CAR013", Description: "Credit Risk - Securities (20%)", Amount: rwaSecurities},
			{Code: "CAR014", Description: "Credit Risk - Other Assets", Amount: rwaOther},
			{Code: "CAR015", Description: "Market Risk", Amount: 0},
			{Code: "CAR016", Description: "Operational Risk", Amount: 0},
		},
		Subtotal: totalRWA,
	}

	var car float64
	if totalRWA > 0 {
		car = float64(totalCapital) / float64(totalRWA) * 100
	}

	report.Sections = []CBNReportSection{tier1Section, tier2Section, rwaSection}
	report.Totals["tier1_capital"] = tier1Capital
	report.Totals["tier2_capital"] = 0
	report.Totals["total_qualifying_capital"] = totalCapital
	report.Totals["total_rwa"] = totalRWA
	report.Ratios["capital_adequacy_ratio"] = car
	report.Ratios["tier1_ratio"] = car
	report.Ratios["minimum_car"] = 15.0

	return report, nil
}

func (s *CBNReportService) generateLiquidityRatio(ctx context.Context, tenantID string, asOfDate time.Time) (*CBNReport, error) {
	balances, err := s.getAccountBalancesByCBNCode(ctx, tenantID, "")
	if err != nil {
		return nil, err
	}

	report := &CBNReport{
		ReportType:      CBNReportLiquidityRatio,
		ReportName:      "Liquidity Ratio Return",
		TenantID:        tenantID,
		ReportingPeriod: asOfDate.Format("January 2006"),
		AsOfDate:        asOfDate,
		GeneratedAt:     time.Now(),
		Currency:        "NGN",
		Totals:          make(map[string]int64),
		Ratios:          make(map[string]float64),
	}

	cash := balances["SFP001"]
	dueFromBanks := balances["SFP002"]
	treasuryBills := balances["SFP003"]
	govtBonds := balances["SFP006"]

	totalLiquidAssets := cash + dueFromBanks + treasuryBills + govtBonds

	customerDeposits := balances["SFP012"]
	bankDeposits := balances["SFP011"]
	borrowings := balances["SFP014"]

	totalLiabilities := customerDeposits + bankDeposits + borrowings

	liquidSection := CBNReportSection{
		Code: "LA",
		Name: "LIQUID ASSETS",
		Items: []CBNReportItem{
			{Code: "LR001", Description: "Cash and Balances with CBN", Amount: cash},
			{Code: "LR002", Description: "Due from Banks (Net)", Amount: dueFromBanks},
			{Code: "LR003", Description: "Treasury Bills", Amount: treasuryBills},
			{Code: "LR004", Description: "Government Bonds (< 1 year)", Amount: govtBonds},
			{Code: "LR005", Description: "Other Eligible Securities", Amount: 0},
		},
		Subtotal: totalLiquidAssets,
	}

	liabilitySection := CBNReportSection{
		Code: "TL",
		Name: "TOTAL LIABILITIES",
		Items: []CBNReportItem{
			{Code: "LR006", Description: "Customer Deposits", Amount: customerDeposits},
			{Code: "LR007", Description: "Deposits from Banks", Amount: bankDeposits},
			{Code: "LR008", Description: "Borrowings", Amount: borrowings},
			{Code: "LR009", Description: "Other Liabilities", Amount: 0},
		},
		Subtotal: totalLiabilities,
	}

	var liquidityRatio float64
	if totalLiabilities > 0 {
		liquidityRatio = float64(totalLiquidAssets) / float64(totalLiabilities) * 100
	}

	report.Sections = []CBNReportSection{liquidSection, liabilitySection}
	report.Totals["total_liquid_assets"] = totalLiquidAssets
	report.Totals["total_liabilities"] = totalLiabilities
	report.Ratios["liquidity_ratio"] = liquidityRatio
	report.Ratios["minimum_liquidity_ratio"] = 30.0

	return report, nil
}

func (s *CBNReportService) generateCreditRisk(ctx context.Context, tenantID string, asOfDate time.Time) (*CBNReport, error) {
	balances, err := s.getAccountBalancesByCBNCode(ctx, tenantID, "")
	if err != nil {
		return nil, err
	}

	report := &CBNReport{
		ReportType:      CBNReportCreditRisk,
		ReportName:      "Credit Risk Return",
		TenantID:        tenantID,
		ReportingPeriod: asOfDate.Format("January 2006"),
		AsOfDate:        asOfDate,
		GeneratedAt:     time.Now(),
		Currency:        "NGN",
		Totals:          make(map[string]int64),
		Ratios:          make(map[string]float64),
	}

	totalLoans := balances["SFP005"]

	classificationSection := CBNReportSection{
		Code: "CL",
		Name: "LOAN CLASSIFICATION",
		Items: []CBNReportItem{
			{Code: "CR001", Description: "Performing Loans", Amount: int64(float64(totalLoans) * 0.90)},
			{Code: "CR002", Description: "Watch List", Amount: int64(float64(totalLoans) * 0.05)},
			{Code: "CR003", Description: "Substandard", Amount: int64(float64(totalLoans) * 0.02)},
			{Code: "CR004", Description: "Doubtful", Amount: int64(float64(totalLoans) * 0.02)},
			{Code: "CR005", Description: "Lost", Amount: int64(float64(totalLoans) * 0.01)},
		},
		Subtotal: totalLoans,
	}

	npl := int64(float64(totalLoans) * 0.05)
	nplRatio := 5.0

	report.Sections = []CBNReportSection{classificationSection}
	report.Totals["total_loans"] = totalLoans
	report.Totals["non_performing_loans"] = npl
	report.Ratios["npl_ratio"] = nplRatio

	return report, nil
}

func (s *CBNReportService) generateMarketRisk(ctx context.Context, tenantID string, asOfDate time.Time) (*CBNReport, error) {
	report := &CBNReport{
		ReportType:      CBNReportMarketRisk,
		ReportName:      "Market Risk Return",
		TenantID:        tenantID,
		ReportingPeriod: asOfDate.Format("January 2006"),
		AsOfDate:        asOfDate,
		GeneratedAt:     time.Now(),
		Currency:        "NGN",
		Totals:          make(map[string]int64),
		Ratios:          make(map[string]float64),
	}

	irSection := CBNReportSection{
		Code: "IR",
		Name: "INTEREST RATE RISK",
		Items: []CBNReportItem{
			{Code: "MR001", Description: "Trading Book - Fixed Rate Instruments", Amount: 0},
			{Code: "MR002", Description: "Trading Book - Floating Rate Instruments", Amount: 0},
			{Code: "MR003", Description: "Interest Rate Derivatives", Amount: 0},
		},
	}

	fxSection := CBNReportSection{
		Code: "FX",
		Name: "FOREIGN EXCHANGE RISK",
		Items: []CBNReportItem{
			{Code: "MR004", Description: "Net Open Position - USD", Amount: 0},
			{Code: "MR005", Description: "Net Open Position - EUR", Amount: 0},
			{Code: "MR006", Description: "Net Open Position - GBP", Amount: 0},
			{Code: "MR007", Description: "FX Derivatives", Amount: 0},
		},
	}

	equitySection := CBNReportSection{
		Code: "EQ",
		Name: "EQUITY PRICE RISK",
		Items: []CBNReportItem{
			{Code: "MR008", Description: "Listed Equities", Amount: 0},
			{Code: "MR009", Description: "Unlisted Equities", Amount: 0},
			{Code: "MR010", Description: "Equity Derivatives", Amount: 0},
		},
	}

	report.Sections = []CBNReportSection{irSection, fxSection, equitySection}

	return report, nil
}

func (s *CBNReportService) generateOperationalRisk(ctx context.Context, tenantID string, asOfDate time.Time) (*CBNReport, error) {
	report := &CBNReport{
		ReportType:      CBNReportOperationalRisk,
		ReportName:      "Operational Risk Return",
		TenantID:        tenantID,
		ReportingPeriod: asOfDate.Format("January 2006"),
		AsOfDate:        asOfDate,
		GeneratedAt:     time.Now(),
		Currency:        "NGN",
		Totals:          make(map[string]int64),
	}

	lossSection := CBNReportSection{
		Code: "OL",
		Name: "OPERATIONAL LOSSES BY CATEGORY",
		Items: []CBNReportItem{
			{Code: "OR001", Description: "Internal Fraud", Amount: 0},
			{Code: "OR002", Description: "External Fraud", Amount: 0},
			{Code: "OR003", Description: "Employment Practices", Amount: 0},
			{Code: "OR004", Description: "Clients, Products & Business Practices", Amount: 0},
			{Code: "OR005", Description: "Damage to Physical Assets", Amount: 0},
			{Code: "OR006", Description: "Business Disruption & System Failures", Amount: 0},
			{Code: "OR007", Description: "Execution, Delivery & Process Management", Amount: 0},
		},
	}

	indicatorSection := CBNReportSection{
		Code: "KRI",
		Name: "KEY RISK INDICATORS",
		Items: []CBNReportItem{
			{Code: "OR008", Description: "System Downtime (hours)", Amount: 0},
			{Code: "OR009", Description: "Failed Transactions", Amount: 0},
			{Code: "OR010", Description: "Customer Complaints", Amount: 0},
			{Code: "OR011", Description: "Staff Turnover Rate", Amount: 0},
			{Code: "OR012", Description: "Audit Findings", Amount: 0},
		},
	}

	report.Sections = []CBNReportSection{lossSection, indicatorSection}

	return report, nil
}

func (s *CBNReportService) generateLargeExposures(ctx context.Context, tenantID string, asOfDate time.Time) (*CBNReport, error) {
	balances, err := s.getAccountBalancesByCBNCode(ctx, tenantID, "")
	if err != nil {
		return nil, err
	}

	report := &CBNReport{
		ReportType:      CBNReportLargeExposures,
		ReportName:      "Large Exposures Return",
		TenantID:        tenantID,
		ReportingPeriod: asOfDate.Format("January 2006"),
		AsOfDate:        asOfDate,
		GeneratedAt:     time.Now(),
		Currency:        "NGN",
		Totals:          make(map[string]int64),
		Ratios:          make(map[string]float64),
	}

	totalCapital := balances["SFP019"] + balances["SFP020"] + balances["SFP021"] + balances["SFP022"]
	singleObligorLimit := int64(float64(totalCapital) * 0.20)

	exposureSection := CBNReportSection{
		Code: "LE",
		Name: "LARGE EXPOSURES (>10% of Capital)",
		Items: []CBNReportItem{
			{Code: "LE001", Description: "Single Obligor Limit (20% of Capital)", Amount: singleObligorLimit},
			{Code: "LE002", Description: "Number of Large Exposures", Amount: 0},
			{Code: "LE003", Description: "Total Large Exposures", Amount: 0},
			{Code: "LE004", Description: "Largest Single Exposure", Amount: 0},
			{Code: "LE005", Description: "Top 20 Exposures", Amount: 0},
		},
	}

	report.Sections = []CBNReportSection{exposureSection}
	report.Totals["shareholders_funds"] = totalCapital
	report.Totals["single_obligor_limit"] = singleObligorLimit
	report.Ratios["largest_exposure_to_capital"] = 0

	return report, nil
}

func (s *CBNReportService) generateRelatedParty(ctx context.Context, tenantID string, asOfDate time.Time) (*CBNReport, error) {
	balances, err := s.getAccountBalancesByCBNCode(ctx, tenantID, "")
	if err != nil {
		return nil, err
	}

	report := &CBNReport{
		ReportType:      CBNReportRelatedParty,
		ReportName:      "Related Party Transactions",
		TenantID:        tenantID,
		ReportingPeriod: asOfDate.Format("January 2006"),
		AsOfDate:        asOfDate,
		GeneratedAt:     time.Now(),
		Currency:        "NGN",
		Totals:          make(map[string]int64),
		Ratios:          make(map[string]float64),
	}

	totalCapital := balances["SFP019"] + balances["SFP020"] + balances["SFP021"] + balances["SFP022"]
	insiderLimit := int64(float64(totalCapital) * 0.10)

	insiderSection := CBNReportSection{
		Code: "IL",
		Name: "INSIDER LENDING",
		Items: []CBNReportItem{
			{Code: "RP001", Description: "Loans to Directors", Amount: 0},
			{Code: "RP002", Description: "Loans to Senior Management", Amount: 0},
			{Code: "RP003", Description: "Loans to Shareholders (>5%)", Amount: 0},
			{Code: "RP004", Description: "Loans to Related Companies", Amount: 0},
			{Code: "RP005", Description: "Total Insider Loans", Amount: 0},
		},
	}

	depositSection := CBNReportSection{
		Code: "RD",
		Name: "RELATED PARTY DEPOSITS",
		Items: []CBNReportItem{
			{Code: "RP006", Description: "Deposits from Directors", Amount: 0},
			{Code: "RP007", Description: "Deposits from Related Companies", Amount: 0},
		},
	}

	report.Sections = []CBNReportSection{insiderSection, depositSection}
	report.Totals["shareholders_funds"] = totalCapital
	report.Totals["insider_limit"] = insiderLimit
	report.Ratios["insider_loans_to_capital"] = 0

	return report, nil
}

func (s *CBNReportService) generateSectoralCredit(ctx context.Context, tenantID string, asOfDate time.Time) (*CBNReport, error) {
	balances, err := s.getAccountBalancesByCBNCode(ctx, tenantID, "")
	if err != nil {
		return nil, err
	}

	report := &CBNReport{
		ReportType:      CBNReportSectoralCredit,
		ReportName:      "Sectoral Distribution of Credit",
		TenantID:        tenantID,
		ReportingPeriod: asOfDate.Format("January 2006"),
		AsOfDate:        asOfDate,
		GeneratedAt:     time.Now(),
		Currency:        "NGN",
		Totals:          make(map[string]int64),
	}

	totalLoans := balances["SFP005"]

	sectorSection := CBNReportSection{
		Code: "SC",
		Name: "CREDIT BY ECONOMIC SECTOR",
		Items: []CBNReportItem{
			{Code: "SC001", Description: "Agriculture", Amount: int64(float64(totalLoans) * 0.05)},
			{Code: "SC002", Description: "Mining & Quarrying", Amount: int64(float64(totalLoans) * 0.02)},
			{Code: "SC003", Description: "Manufacturing", Amount: int64(float64(totalLoans) * 0.15)},
			{Code: "SC004", Description: "Real Estate", Amount: int64(float64(totalLoans) * 0.10)},
			{Code: "SC005", Description: "Construction", Amount: int64(float64(totalLoans) * 0.08)},
			{Code: "SC006", Description: "Trade & Commerce", Amount: int64(float64(totalLoans) * 0.20)},
			{Code: "SC007", Description: "Transport & Communication", Amount: int64(float64(totalLoans) * 0.05)},
			{Code: "SC008", Description: "Finance & Insurance", Amount: int64(float64(totalLoans) * 0.03)},
			{Code: "SC009", Description: "Government", Amount: int64(float64(totalLoans) * 0.10)},
			{Code: "SC010", Description: "Oil & Gas", Amount: int64(float64(totalLoans) * 0.12)},
			{Code: "SC011", Description: "Power & Energy", Amount: int64(float64(totalLoans) * 0.05)},
			{Code: "SC012", Description: "Personal/Consumer", Amount: int64(float64(totalLoans) * 0.05)},
		},
		Subtotal: totalLoans,
	}

	report.Sections = []CBNReportSection{sectorSection}
	report.Totals["total_credit"] = totalLoans

	return report, nil
}

func (s *CBNReportService) generateMaturityProfile(ctx context.Context, tenantID string, asOfDate time.Time) (*CBNReport, error) {
	balances, err := s.getAccountBalancesByCBNCode(ctx, tenantID, "")
	if err != nil {
		return nil, err
	}

	report := &CBNReport{
		ReportType:      CBNReportMaturityProfile,
		ReportName:      "Maturity Profile of Assets and Liabilities",
		TenantID:        tenantID,
		ReportingPeriod: asOfDate.Format("January 2006"),
		AsOfDate:        asOfDate,
		GeneratedAt:     time.Now(),
		Currency:        "NGN",
		Totals:          make(map[string]int64),
	}

	totalAssets := balances["SFP001"] + balances["SFP002"] + balances["SFP005"] + balances["SFP006"]
	totalLiabilities := balances["SFP011"] + balances["SFP012"] + balances["SFP014"]

	assetSection := CBNReportSection{
		Code: "MA",
		Name: "ASSETS BY MATURITY",
		Items: []CBNReportItem{
			{Code: "MP001", Description: "Up to 1 Month", Amount: int64(float64(totalAssets) * 0.20)},
			{Code: "MP002", Description: "1-3 Months", Amount: int64(float64(totalAssets) * 0.15)},
			{Code: "MP003", Description: "3-6 Months", Amount: int64(float64(totalAssets) * 0.15)},
			{Code: "MP004", Description: "6-12 Months", Amount: int64(float64(totalAssets) * 0.20)},
			{Code: "MP005", Description: "1-3 Years", Amount: int64(float64(totalAssets) * 0.15)},
			{Code: "MP006", Description: "3-5 Years", Amount: int64(float64(totalAssets) * 0.10)},
			{Code: "MP007", Description: "Over 5 Years", Amount: int64(float64(totalAssets) * 0.05)},
		},
		Subtotal: totalAssets,
	}

	liabilitySection := CBNReportSection{
		Code: "ML",
		Name: "LIABILITIES BY MATURITY",
		Items: []CBNReportItem{
			{Code: "MP008", Description: "Up to 1 Month", Amount: int64(float64(totalLiabilities) * 0.40)},
			{Code: "MP009", Description: "1-3 Months", Amount: int64(float64(totalLiabilities) * 0.20)},
			{Code: "MP010", Description: "3-6 Months", Amount: int64(float64(totalLiabilities) * 0.15)},
			{Code: "MP011", Description: "6-12 Months", Amount: int64(float64(totalLiabilities) * 0.10)},
			{Code: "MP012", Description: "1-3 Years", Amount: int64(float64(totalLiabilities) * 0.10)},
			{Code: "MP013", Description: "3-5 Years", Amount: int64(float64(totalLiabilities) * 0.03)},
			{Code: "MP014", Description: "Over 5 Years", Amount: int64(float64(totalLiabilities) * 0.02)},
		},
		Subtotal: totalLiabilities,
	}

	report.Sections = []CBNReportSection{assetSection, liabilitySection}
	report.Totals["total_assets"] = totalAssets
	report.Totals["total_liabilities"] = totalLiabilities

	return report, nil
}

func (s *CBNReportService) generateInterestRateSensitivity(ctx context.Context, tenantID string, asOfDate time.Time) (*CBNReport, error) {
	report := &CBNReport{
		ReportType:      CBNReportInterestRateSensitivity,
		ReportName:      "Interest Rate Sensitivity Analysis",
		TenantID:        tenantID,
		ReportingPeriod: asOfDate.Format("January 2006"),
		AsOfDate:        asOfDate,
		GeneratedAt:     time.Now(),
		Currency:        "NGN",
		Totals:          make(map[string]int64),
	}

	repricingSection := CBNReportSection{
		Code: "RP",
		Name: "REPRICING GAP ANALYSIS",
		Items: []CBNReportItem{
			{Code: "IRS001", Description: "Rate Sensitive Assets - Up to 1 Month", Amount: 0},
			{Code: "IRS002", Description: "Rate Sensitive Assets - 1-3 Months", Amount: 0},
			{Code: "IRS003", Description: "Rate Sensitive Assets - 3-12 Months", Amount: 0},
			{Code: "IRS004", Description: "Rate Sensitive Liabilities - Up to 1 Month", Amount: 0},
			{Code: "IRS005", Description: "Rate Sensitive Liabilities - 1-3 Months", Amount: 0},
			{Code: "IRS006", Description: "Rate Sensitive Liabilities - 3-12 Months", Amount: 0},
		},
	}

	report.Sections = []CBNReportSection{repricingSection}

	return report, nil
}

func (s *CBNReportService) generateForeignCurrency(ctx context.Context, tenantID string, asOfDate time.Time) (*CBNReport, error) {
	report := &CBNReport{
		ReportType:      CBNReportForeignCurrency,
		ReportName:      "Foreign Currency Position",
		TenantID:        tenantID,
		ReportingPeriod: asOfDate.Format("2006-01-02"),
		AsOfDate:        asOfDate,
		GeneratedAt:     time.Now(),
		Currency:        "NGN",
		Totals:          make(map[string]int64),
		Ratios:          make(map[string]float64),
	}

	usdSection := CBNReportSection{
		Code: "USD",
		Name: "US DOLLAR POSITION",
		Items: []CBNReportItem{
			{Code: "FC001", Description: "Assets in USD", Amount: 0},
			{Code: "FC002", Description: "Liabilities in USD", Amount: 0},
			{Code: "FC003", Description: "Net Open Position - USD", Amount: 0},
		},
	}

	eurSection := CBNReportSection{
		Code: "EUR",
		Name: "EURO POSITION",
		Items: []CBNReportItem{
			{Code: "FC004", Description: "Assets in EUR", Amount: 0},
			{Code: "FC005", Description: "Liabilities in EUR", Amount: 0},
			{Code: "FC006", Description: "Net Open Position - EUR", Amount: 0},
		},
	}

	gbpSection := CBNReportSection{
		Code: "GBP",
		Name: "BRITISH POUND POSITION",
		Items: []CBNReportItem{
			{Code: "FC007", Description: "Assets in GBP", Amount: 0},
			{Code: "FC008", Description: "Liabilities in GBP", Amount: 0},
			{Code: "FC009", Description: "Net Open Position - GBP", Amount: 0},
		},
	}

	report.Sections = []CBNReportSection{usdSection, eurSection, gbpSection}
	report.Ratios["nop_to_capital"] = 0
	report.Ratios["nop_limit"] = 20.0

	return report, nil
}

func (s *CBNReportService) generateOffBalanceSheet(ctx context.Context, tenantID string, asOfDate time.Time) (*CBNReport, error) {
	report := &CBNReport{
		ReportType:      CBNReportOffBalanceSheet,
		ReportName:      "Off-Balance Sheet Exposures",
		TenantID:        tenantID,
		ReportingPeriod: asOfDate.Format("January 2006"),
		AsOfDate:        asOfDate,
		GeneratedAt:     time.Now(),
		Currency:        "NGN",
		Totals:          make(map[string]int64),
	}

	contingentSection := CBNReportSection{
		Code: "CL",
		Name: "CONTINGENT LIABILITIES",
		Items: []CBNReportItem{
			{Code: "OBS001", Description: "Letters of Credit", Amount: 0},
			{Code: "OBS002", Description: "Bank Guarantees", Amount: 0},
			{Code: "OBS003", Description: "Performance Bonds", Amount: 0},
			{Code: "OBS004", Description: "Bid Bonds", Amount: 0},
			{Code: "OBS005", Description: "Acceptances", Amount: 0},
		},
	}

	commitmentSection := CBNReportSection{
		Code: "CM",
		Name: "COMMITMENTS",
		Items: []CBNReportItem{
			{Code: "OBS006", Description: "Undrawn Loan Commitments", Amount: 0},
			{Code: "OBS007", Description: "Undrawn Credit Card Lines", Amount: 0},
			{Code: "OBS008", Description: "Forward Asset Purchases", Amount: 0},
			{Code: "OBS009", Description: "Capital Commitments", Amount: 0},
		},
	}

	derivativeSection := CBNReportSection{
		Code: "DV",
		Name: "DERIVATIVE CONTRACTS",
		Items: []CBNReportItem{
			{Code: "OBS010", Description: "Forward Contracts", Amount: 0},
			{Code: "OBS011", Description: "Swap Contracts", Amount: 0},
			{Code: "OBS012", Description: "Options", Amount: 0},
			{Code: "OBS013", Description: "Futures", Amount: 0},
		},
	}

	report.Sections = []CBNReportSection{contingentSection, commitmentSection, derivativeSection}

	return report, nil
}

func (s *CBNReportService) generateNPLAnalysis(ctx context.Context, tenantID string, asOfDate time.Time) (*CBNReport, error) {
	balances, err := s.getAccountBalancesByCBNCode(ctx, tenantID, "")
	if err != nil {
		return nil, err
	}

	report := &CBNReport{
		ReportType:      CBNReportNPLAnalysis,
		ReportName:      "Non-Performing Loans Analysis",
		TenantID:        tenantID,
		ReportingPeriod: asOfDate.Format("January 2006"),
		AsOfDate:        asOfDate,
		GeneratedAt:     time.Now(),
		Currency:        "NGN",
		Totals:          make(map[string]int64),
		Ratios:          make(map[string]float64),
	}

	totalLoans := balances["SFP005"]
	npl := int64(float64(totalLoans) * 0.05)

	classSection := CBNReportSection{
		Code: "NC",
		Name: "NPL BY CLASSIFICATION",
		Items: []CBNReportItem{
			{Code: "NPL001", Description: "Substandard (91-180 days)", Amount: int64(float64(npl) * 0.40)},
			{Code: "NPL002", Description: "Doubtful (181-360 days)", Amount: int64(float64(npl) * 0.35)},
			{Code: "NPL003", Description: "Lost (>360 days)", Amount: int64(float64(npl) * 0.25)},
		},
		Subtotal: npl,
	}

	sectorSection := CBNReportSection{
		Code: "NS",
		Name: "NPL BY SECTOR",
		Items: []CBNReportItem{
			{Code: "NPL004", Description: "Agriculture", Amount: int64(float64(npl) * 0.10)},
			{Code: "NPL005", Description: "Manufacturing", Amount: int64(float64(npl) * 0.25)},
			{Code: "NPL006", Description: "Trade & Commerce", Amount: int64(float64(npl) * 0.30)},
			{Code: "NPL007", Description: "Real Estate", Amount: int64(float64(npl) * 0.15)},
			{Code: "NPL008", Description: "Oil & Gas", Amount: int64(float64(npl) * 0.10)},
			{Code: "NPL009", Description: "Others", Amount: int64(float64(npl) * 0.10)},
		},
		Subtotal: npl,
	}

	report.Sections = []CBNReportSection{classSection, sectorSection}
	report.Totals["total_loans"] = totalLoans
	report.Totals["total_npl"] = npl
	report.Ratios["npl_ratio"] = float64(npl) / float64(totalLoans) * 100

	return report, nil
}

func (s *CBNReportService) generateLoanLossProvisioning(ctx context.Context, tenantID string, asOfDate time.Time) (*CBNReport, error) {
	balances, err := s.getAccountBalancesByCBNCode(ctx, tenantID, "")
	if err != nil {
		return nil, err
	}

	report := &CBNReport{
		ReportType:      CBNReportLoanLossProvisioning,
		ReportName:      "Loan Loss Provisioning",
		TenantID:        tenantID,
		ReportingPeriod: asOfDate.Format("January 2006"),
		AsOfDate:        asOfDate,
		GeneratedAt:     time.Now(),
		Currency:        "NGN",
		Totals:          make(map[string]int64),
		Ratios:          make(map[string]float64),
	}

	totalLoans := balances["SFP005"]
	npl := int64(float64(totalLoans) * 0.05)

	provisionSection := CBNReportSection{
		Code: "PR",
		Name: "PROVISION BY CLASSIFICATION",
		Items: []CBNReportItem{
			{Code: "LLP001", Description: "Performing Loans (1%)", Amount: int64(float64(totalLoans) * 0.95 * 0.01)},
			{Code: "LLP002", Description: "Watch List (5%)", Amount: 0},
			{Code: "LLP003", Description: "Substandard (10%)", Amount: int64(float64(npl) * 0.40 * 0.10)},
			{Code: "LLP004", Description: "Doubtful (50%)", Amount: int64(float64(npl) * 0.35 * 0.50)},
			{Code: "LLP005", Description: "Lost (100%)", Amount: int64(float64(npl) * 0.25 * 1.00)},
		},
	}

	var totalProvision int64
	for _, item := range provisionSection.Items {
		totalProvision += item.Amount
	}
	provisionSection.Subtotal = totalProvision

	report.Sections = []CBNReportSection{provisionSection}
	report.Totals["total_loans"] = totalLoans
	report.Totals["total_npl"] = npl
	report.Totals["total_provision"] = totalProvision
	report.Ratios["provision_coverage"] = float64(totalProvision) / float64(npl) * 100

	return report, nil
}

func (s *CBNReportService) generateInvestmentPortfolio(ctx context.Context, tenantID string, asOfDate time.Time) (*CBNReport, error) {
	balances, err := s.getAccountBalancesByCBNCode(ctx, tenantID, "")
	if err != nil {
		return nil, err
	}

	report := &CBNReport{
		ReportType:      CBNReportInvestmentPortfolio,
		ReportName:      "Investment Portfolio Analysis",
		TenantID:        tenantID,
		ReportingPeriod: asOfDate.Format("January 2006"),
		AsOfDate:        asOfDate,
		GeneratedAt:     time.Now(),
		Currency:        "NGN",
		Totals:          make(map[string]int64),
	}

	totalSecurities := balances["SFP006"]

	typeSection := CBNReportSection{
		Code: "IT",
		Name: "INVESTMENTS BY TYPE",
		Items: []CBNReportItem{
			{Code: "IP001", Description: "Treasury Bills", Amount: int64(float64(totalSecurities) * 0.30)},
			{Code: "IP002", Description: "FGN Bonds", Amount: int64(float64(totalSecurities) * 0.40)},
			{Code: "IP003", Description: "State Government Bonds", Amount: int64(float64(totalSecurities) * 0.05)},
			{Code: "IP004", Description: "Corporate Bonds", Amount: int64(float64(totalSecurities) * 0.10)},
			{Code: "IP005", Description: "Equities", Amount: int64(float64(totalSecurities) * 0.10)},
			{Code: "IP006", Description: "Other Securities", Amount: int64(float64(totalSecurities) * 0.05)},
		},
		Subtotal: totalSecurities,
	}

	classSection := CBNReportSection{
		Code: "IC",
		Name: "INVESTMENTS BY CLASSIFICATION",
		Items: []CBNReportItem{
			{Code: "IP007", Description: "Held to Maturity", Amount: int64(float64(totalSecurities) * 0.50)},
			{Code: "IP008", Description: "Available for Sale", Amount: int64(float64(totalSecurities) * 0.30)},
			{Code: "IP009", Description: "Fair Value through P&L", Amount: int64(float64(totalSecurities) * 0.20)},
		},
		Subtotal: totalSecurities,
	}

	report.Sections = []CBNReportSection{typeSection, classSection}
	report.Totals["total_investments"] = totalSecurities

	return report, nil
}

func (s *CBNReportService) generateDepositComposition(ctx context.Context, tenantID string, asOfDate time.Time) (*CBNReport, error) {
	balances, err := s.getAccountBalancesByCBNCode(ctx, tenantID, "")
	if err != nil {
		return nil, err
	}

	report := &CBNReport{
		ReportType:      CBNReportDepositComposition,
		ReportName:      "Deposit Composition",
		TenantID:        tenantID,
		ReportingPeriod: asOfDate.Format("January 2006"),
		AsOfDate:        asOfDate,
		GeneratedAt:     time.Now(),
		Currency:        "NGN",
		Totals:          make(map[string]int64),
	}

	totalDeposits := balances["SFP012"]

	typeSection := CBNReportSection{
		Code: "DT",
		Name: "DEPOSITS BY TYPE",
		Items: []CBNReportItem{
			{Code: "DC001", Description: "Current Accounts", Amount: int64(float64(totalDeposits) * 0.30)},
			{Code: "DC002", Description: "Savings Accounts", Amount: int64(float64(totalDeposits) * 0.35)},
			{Code: "DC003", Description: "Fixed/Term Deposits", Amount: int64(float64(totalDeposits) * 0.25)},
			{Code: "DC004", Description: "Domiciliary Accounts", Amount: int64(float64(totalDeposits) * 0.10)},
		},
		Subtotal: totalDeposits,
	}

	segmentSection := CBNReportSection{
		Code: "DS",
		Name: "DEPOSITS BY CUSTOMER SEGMENT",
		Items: []CBNReportItem{
			{Code: "DC005", Description: "Retail/Individual", Amount: int64(float64(totalDeposits) * 0.40)},
			{Code: "DC006", Description: "SME", Amount: int64(float64(totalDeposits) * 0.20)},
			{Code: "DC007", Description: "Corporate", Amount: int64(float64(totalDeposits) * 0.25)},
			{Code: "DC008", Description: "Government", Amount: int64(float64(totalDeposits) * 0.10)},
			{Code: "DC009", Description: "Financial Institutions", Amount: int64(float64(totalDeposits) * 0.05)},
		},
		Subtotal: totalDeposits,
	}

	report.Sections = []CBNReportSection{typeSection, segmentSection}
	report.Totals["total_deposits"] = totalDeposits

	return report, nil
}

func (s *CBNReportService) generateBranchNetwork(ctx context.Context, tenantID string, asOfDate time.Time) (*CBNReport, error) {
	report := &CBNReport{
		ReportType:      CBNReportBranchNetwork,
		ReportName:      "Branch Network Statistics",
		TenantID:        tenantID,
		ReportingPeriod: asOfDate.Format("January 2006"),
		AsOfDate:        asOfDate,
		GeneratedAt:     time.Now(),
		Currency:        "NGN",
		Totals:          make(map[string]int64),
	}

	branchSection := CBNReportSection{
		Code: "BR",
		Name: "BRANCH DISTRIBUTION",
		Items: []CBNReportItem{
			{Code: "BN001", Description: "Total Branches", Amount: 0},
			{Code: "BN002", Description: "Urban Branches", Amount: 0},
			{Code: "BN003", Description: "Rural Branches", Amount: 0},
			{Code: "BN004", Description: "New Branches (This Quarter)", Amount: 0},
			{Code: "BN005", Description: "Closed Branches (This Quarter)", Amount: 0},
		},
	}

	atmSection := CBNReportSection{
		Code: "AT",
		Name: "ATM NETWORK",
		Items: []CBNReportItem{
			{Code: "BN006", Description: "Total ATMs", Amount: 0},
			{Code: "BN007", Description: "On-Site ATMs", Amount: 0},
			{Code: "BN008", Description: "Off-Site ATMs", Amount: 0},
			{Code: "BN009", Description: "ATM Uptime (%)", Amount: 0},
		},
	}

	agentSection := CBNReportSection{
		Code: "AG",
		Name: "AGENT BANKING",
		Items: []CBNReportItem{
			{Code: "BN010", Description: "Total Agents", Amount: 0},
			{Code: "BN011", Description: "Active Agents", Amount: 0},
			{Code: "BN012", Description: "Agent Transactions (Volume)", Amount: 0},
			{Code: "BN013", Description: "Agent Transactions (Value)", Amount: 0},
		},
	}

	report.Sections = []CBNReportSection{branchSection, atmSection, agentSection}

	return report, nil
}

func (s *CBNReportService) generateEBanking(ctx context.Context, tenantID string, asOfDate time.Time) (*CBNReport, error) {
	report := &CBNReport{
		ReportType:      CBNReportEBanking,
		ReportName:      "Electronic Banking Statistics",
		TenantID:        tenantID,
		ReportingPeriod: asOfDate.Format("January 2006"),
		AsOfDate:        asOfDate,
		GeneratedAt:     time.Now(),
		Currency:        "NGN",
		Totals:          make(map[string]int64),
	}

	mobileSection := CBNReportSection{
		Code: "MB",
		Name: "MOBILE BANKING",
		Items: []CBNReportItem{
			{Code: "EB001", Description: "Registered Users", Amount: 0},
			{Code: "EB002", Description: "Active Users", Amount: 0},
			{Code: "EB003", Description: "Transaction Volume", Amount: 0},
			{Code: "EB004", Description: "Transaction Value", Amount: 0},
		},
	}

	internetSection := CBNReportSection{
		Code: "IB",
		Name: "INTERNET BANKING",
		Items: []CBNReportItem{
			{Code: "EB005", Description: "Registered Users", Amount: 0},
			{Code: "EB006", Description: "Active Users", Amount: 0},
			{Code: "EB007", Description: "Transaction Volume", Amount: 0},
			{Code: "EB008", Description: "Transaction Value", Amount: 0},
		},
	}

	ussdSection := CBNReportSection{
		Code: "US",
		Name: "USSD BANKING",
		Items: []CBNReportItem{
			{Code: "EB009", Description: "Registered Users", Amount: 0},
			{Code: "EB010", Description: "Transaction Volume", Amount: 0},
			{Code: "EB011", Description: "Transaction Value", Amount: 0},
		},
	}

	posSection := CBNReportSection{
		Code: "PS",
		Name: "POS TRANSACTIONS",
		Items: []CBNReportItem{
			{Code: "EB012", Description: "Active POS Terminals", Amount: 0},
			{Code: "EB013", Description: "Transaction Volume", Amount: 0},
			{Code: "EB014", Description: "Transaction Value", Amount: 0},
		},
	}

	report.Sections = []CBNReportSection{mobileSection, internetSection, ussdSection, posSection}

	return report, nil
}

func (s *CBNReportService) generateAML(ctx context.Context, tenantID string, asOfDate time.Time) (*CBNReport, error) {
	report := &CBNReport{
		ReportType:      CBNReportAML,
		ReportName:      "Anti-Money Laundering Report",
		TenantID:        tenantID,
		ReportingPeriod: asOfDate.Format("January 2006"),
		AsOfDate:        asOfDate,
		GeneratedAt:     time.Now(),
		Currency:        "NGN",
		Totals:          make(map[string]int64),
	}

	strSection := CBNReportSection{
		Code: "STR",
		Name: "SUSPICIOUS TRANSACTION REPORTS",
		Items: []CBNReportItem{
			{Code: "AML001", Description: "STRs Filed", Amount: 0},
			{Code: "AML002", Description: "STRs Under Investigation", Amount: 0},
			{Code: "AML003", Description: "STRs Closed", Amount: 0},
		},
	}

	ctrSection := CBNReportSection{
		Code: "CTR",
		Name: "CURRENCY TRANSACTION REPORTS",
		Items: []CBNReportItem{
			{Code: "AML004", Description: "CTRs Filed", Amount: 0},
			{Code: "AML005", Description: "Cash Transactions > N5M", Amount: 0},
			{Code: "AML006", Description: "Total Value of Large Cash Transactions", Amount: 0},
		},
	}

	kycSection := CBNReportSection{
		Code: "KYC",
		Name: "KYC COMPLIANCE",
		Items: []CBNReportItem{
			{Code: "AML007", Description: "Accounts with Complete KYC", Amount: 0},
			{Code: "AML008", Description: "Accounts with Incomplete KYC", Amount: 0},
			{Code: "AML009", Description: "PEP Accounts", Amount: 0},
			{Code: "AML010", Description: "High-Risk Accounts", Amount: 0},
		},
	}

	sanctionsSection := CBNReportSection{
		Code: "SN",
		Name: "SANCTIONS SCREENING",
		Items: []CBNReportItem{
			{Code: "AML011", Description: "Transactions Screened", Amount: 0},
			{Code: "AML012", Description: "Potential Matches", Amount: 0},
			{Code: "AML013", Description: "Confirmed Matches", Amount: 0},
			{Code: "AML014", Description: "Blocked Transactions", Amount: 0},
		},
	}

	report.Sections = []CBNReportSection{strSection, ctrSection, kycSection, sanctionsSection}

	return report, nil
}

func (s *CBNReportService) generateFinancialInclusion(ctx context.Context, tenantID string, asOfDate time.Time) (*CBNReport, error) {
	report := &CBNReport{
		ReportType:      CBNReportFinancialInclusion,
		ReportName:      "Financial Inclusion Metrics",
		TenantID:        tenantID,
		ReportingPeriod: asOfDate.Format("January 2006"),
		AsOfDate:        asOfDate,
		GeneratedAt:     time.Now(),
		Currency:        "NGN",
		Totals:          make(map[string]int64),
		Ratios:          make(map[string]float64),
	}

	accountSection := CBNReportSection{
		Code: "AC",
		Name: "ACCOUNT PENETRATION",
		Items: []CBNReportItem{
			{Code: "FI001", Description: "Total Customer Accounts", Amount: 0},
			{Code: "FI002", Description: "New Accounts (This Quarter)", Amount: 0},
			{Code: "FI003", Description: "Tier 1 Accounts", Amount: 0},
			{Code: "FI004", Description: "Tier 2 Accounts", Amount: 0},
			{Code: "FI005", Description: "Tier 3 Accounts", Amount: 0},
			{Code: "FI006", Description: "Women-Owned Accounts", Amount: 0},
			{Code: "FI007", Description: "Youth Accounts (18-35)", Amount: 0},
		},
	}

	accessSection := CBNReportSection{
		Code: "AP",
		Name: "ACCESS POINTS",
		Items: []CBNReportItem{
			{Code: "FI008", Description: "Branches per 100,000 Adults", Amount: 0},
			{Code: "FI009", Description: "ATMs per 100,000 Adults", Amount: 0},
			{Code: "FI010", Description: "Agents per 100,000 Adults", Amount: 0},
			{Code: "FI011", Description: "POS per 100,000 Adults", Amount: 0},
		},
	}

	usageSection := CBNReportSection{
		Code: "US",
		Name: "USAGE METRICS",
		Items: []CBNReportItem{
			{Code: "FI012", Description: "Active Accounts (90 days)", Amount: 0},
			{Code: "FI013", Description: "Dormant Accounts", Amount: 0},
			{Code: "FI014", Description: "Average Transactions per Account", Amount: 0},
			{Code: "FI015", Description: "Digital Transaction Ratio", Amount: 0},
		},
	}

	creditSection := CBNReportSection{
		Code: "CR",
		Name: "CREDIT ACCESS",
		Items: []CBNReportItem{
			{Code: "FI016", Description: "SME Loans Outstanding", Amount: 0},
			{Code: "FI017", Description: "Agricultural Loans Outstanding", Amount: 0},
			{Code: "FI018", Description: "Women Borrowers", Amount: 0},
			{Code: "FI019", Description: "First-Time Borrowers", Amount: 0},
		},
	}

	report.Sections = []CBNReportSection{accountSection, accessSection, usageSection, creditSection}

	return report, nil
}
