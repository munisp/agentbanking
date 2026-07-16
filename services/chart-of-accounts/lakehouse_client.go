package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"time"
)

type LakehouseClient struct {
	baseURL    string
	apiKey     string
	httpClient *http.Client
}

func NewLakehouseClient() *LakehouseClient {
	baseURL := os.Getenv("LAKEHOUSE_API_URL")
	if baseURL == "" {
		baseURL = "http://lakehouse-api:8000"
	}

	apiKey := os.Getenv("LAKEHOUSE_API_KEY")

	return &LakehouseClient{
		baseURL: baseURL,
		apiKey:  apiKey,
		httpClient: &http.Client{
			Timeout: 30 * time.Second,
		},
	}
}

type LakehouseEvent struct {
	EventID       string                 `json:"event_id"`
	EventType     string                 `json:"event_type"`
	ServiceName   string                 `json:"service_name"`
	TenantID      string                 `json:"tenant_id"`
	EntityID      string                 `json:"entity_id"`
	EntityType    string                 `json:"entity_type"`
	Payload       map[string]interface{} `json:"payload"`
	Timestamp     time.Time              `json:"timestamp"`
	IngestionTime time.Time              `json:"ingestion_time"`
}

type LakehouseQueryRequest struct {
	Query      string                 `json:"query"`
	Parameters map[string]interface{} `json:"parameters,omitempty"`
	Timeout    int                    `json:"timeout,omitempty"`
}

type LakehouseQueryResponse struct {
	Columns []string                 `json:"columns"`
	Rows    []map[string]interface{} `json:"rows"`
	RowCount int                     `json:"row_count"`
	Duration float64                 `json:"duration_ms"`
}

func (c *LakehouseClient) PublishEvent(ctx context.Context, event LakehouseEvent) error {
	event.IngestionTime = time.Now()

	data, err := json.Marshal(event)
	if err != nil {
		return fmt.Errorf("failed to marshal event: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, "POST", c.baseURL+"/api/v1/ingest/event", bytes.NewReader(data))
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	if c.apiKey != "" {
		req.Header.Set("Authorization", "Bearer "+c.apiKey)
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("failed to send request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("lakehouse error: %s - %s", resp.Status, string(body))
	}

	return nil
}

func (c *LakehouseClient) PublishBatch(ctx context.Context, events []LakehouseEvent) error {
	now := time.Now()
	for i := range events {
		events[i].IngestionTime = now
	}

	data, err := json.Marshal(events)
	if err != nil {
		return fmt.Errorf("failed to marshal events: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, "POST", c.baseURL+"/api/v1/ingest/batch", bytes.NewReader(data))
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	if c.apiKey != "" {
		req.Header.Set("Authorization", "Bearer "+c.apiKey)
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("failed to send request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("lakehouse error: %s - %s", resp.Status, string(body))
	}

	return nil
}

func (c *LakehouseClient) Query(ctx context.Context, query string, params map[string]interface{}) (*LakehouseQueryResponse, error) {
	reqBody := LakehouseQueryRequest{
		Query:      query,
		Parameters: params,
		Timeout:    30000,
	}

	data, err := json.Marshal(reqBody)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal query: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, "POST", c.baseURL+"/api/v1/query", bytes.NewReader(data))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	if c.apiKey != "" {
		req.Header.Set("Authorization", "Bearer "+c.apiKey)
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to send request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("lakehouse error: %s - %s", resp.Status, string(body))
	}

	var result LakehouseQueryResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}

	return &result, nil
}

func (c *LakehouseClient) PublishTrialBalance(ctx context.Context, tenantID string, trialBalance *TrialBalance) error {
	event := LakehouseEvent{
		EventID:     fmt.Sprintf("trial_balance-%s-%d", tenantID, time.Now().UnixNano()),
		EventType:   "trial_balance_generated",
		ServiceName: ServiceName,
		TenantID:    tenantID,
		EntityID:    tenantID,
		EntityType:  "trial_balance",
		Payload: map[string]interface{}{
			"as_of_date":    trialBalance.AsOfDate,
			"total_debits":  trialBalance.TotalDebits,
			"total_credits": trialBalance.TotalCredits,
			"is_balanced":   trialBalance.IsBalanced,
			"account_count": len(trialBalance.Accounts),
		},
		Timestamp: time.Now(),
	}

	return c.PublishEvent(ctx, event)
}

func (c *LakehouseClient) PublishBalanceSheet(ctx context.Context, tenantID string, balanceSheet *BalanceSheet) error {
	event := LakehouseEvent{
		EventID:     fmt.Sprintf("balance_sheet-%s-%d", tenantID, time.Now().UnixNano()),
		EventType:   "balance_sheet_generated",
		ServiceName: ServiceName,
		TenantID:    tenantID,
		EntityID:    tenantID,
		EntityType:  "balance_sheet",
		Payload: map[string]interface{}{
			"as_of_date":        balanceSheet.AsOfDate,
			"total_assets":      balanceSheet.TotalAssets,
			"total_liabilities": balanceSheet.TotalLiabilities,
			"total_equity":      balanceSheet.TotalEquity,
			"is_balanced":       balanceSheet.IsBalanced,
		},
		Timestamp: time.Now(),
	}

	return c.PublishEvent(ctx, event)
}

func (c *LakehouseClient) PublishIncomeStatement(ctx context.Context, tenantID string, incomeStatement *IncomeStatement) error {
	event := LakehouseEvent{
		EventID:     fmt.Sprintf("income_statement-%s-%d", tenantID, time.Now().UnixNano()),
		EventType:   "income_statement_generated",
		ServiceName: ServiceName,
		TenantID:    tenantID,
		EntityID:    tenantID,
		EntityType:  "income_statement",
		Payload: map[string]interface{}{
			"start_date":     incomeStatement.StartDate,
			"end_date":       incomeStatement.EndDate,
			"total_revenue":  incomeStatement.TotalRevenue,
			"total_expenses": incomeStatement.TotalExpenses,
			"net_income":     incomeStatement.NetIncome,
		},
		Timestamp: time.Now(),
	}

	return c.PublishEvent(ctx, event)
}

func (c *LakehouseClient) PublishCBNReturn(ctx context.Context, tenantID string, cbnReturn *CBNReturn) error {
	event := LakehouseEvent{
		EventID:     fmt.Sprintf("cbn_return-%s-%s-%d", tenantID, cbnReturn.ReturnType, time.Now().UnixNano()),
		EventType:   "cbn_return_generated",
		ServiceName: ServiceName,
		TenantID:    tenantID,
		EntityID:    fmt.Sprintf("%s-%s", cbnReturn.ReturnType, cbnReturn.ReportingDate),
		EntityType:  "cbn_return",
		Payload: map[string]interface{}{
			"return_type":    cbnReturn.ReturnType,
			"reporting_date": cbnReturn.ReportingDate,
			"data":           cbnReturn.Data,
		},
		Timestamp: time.Now(),
	}

	return c.PublishEvent(ctx, event)
}

func (c *LakehouseClient) GetHistoricalTrialBalance(ctx context.Context, tenantID string, startDate, endDate string) (*LakehouseQueryResponse, error) {
	query := `
		SELECT 
			as_of_date,
			total_debits,
			total_credits,
			is_balanced,
			account_count
		FROM gold.trial_balances
		WHERE tenant_id = :tenant_id
		AND as_of_date BETWEEN :start_date AND :end_date
		ORDER BY as_of_date DESC
	`

	params := map[string]interface{}{
		"tenant_id":  tenantID,
		"start_date": startDate,
		"end_date":   endDate,
	}

	return c.Query(ctx, query, params)
}

func (c *LakehouseClient) GetAccountTrends(ctx context.Context, tenantID, accountCode string, months int) (*LakehouseQueryResponse, error) {
	query := `
		SELECT 
			DATE_TRUNC('month', timestamp) as month,
			account_code,
			account_name,
			AVG(balance) as avg_balance,
			MAX(balance) as max_balance,
			MIN(balance) as min_balance
		FROM gold.account_balances
		WHERE tenant_id = :tenant_id
		AND account_code = :account_code
		AND timestamp >= DATE_SUB(CURRENT_DATE, INTERVAL :months MONTH)
		GROUP BY DATE_TRUNC('month', timestamp), account_code, account_name
		ORDER BY month DESC
	`

	params := map[string]interface{}{
		"tenant_id":    tenantID,
		"account_code": accountCode,
		"months":       months,
	}

	return c.Query(ctx, query, params)
}

func (c *LakehouseClient) GetRevenueByCategory(ctx context.Context, tenantID, startDate, endDate string) (*LakehouseQueryResponse, error) {
	query := `
		SELECT 
			SUBSTRING(account_code, 1, 2) as category_code,
			SUM(amount) as total_amount,
			COUNT(*) as transaction_count
		FROM gold.journal_entries
		WHERE tenant_id = :tenant_id
		AND account_type = 'revenue'
		AND date BETWEEN :start_date AND :end_date
		GROUP BY SUBSTRING(account_code, 1, 2)
		ORDER BY total_amount DESC
	`

	params := map[string]interface{}{
		"tenant_id":  tenantID,
		"start_date": startDate,
		"end_date":   endDate,
	}

	return c.Query(ctx, query, params)
}

func (c *LakehouseClient) GetExpenseByCategory(ctx context.Context, tenantID, startDate, endDate string) (*LakehouseQueryResponse, error) {
	query := `
		SELECT 
			SUBSTRING(account_code, 1, 2) as category_code,
			SUM(amount) as total_amount,
			COUNT(*) as transaction_count
		FROM gold.journal_entries
		WHERE tenant_id = :tenant_id
		AND account_type = 'expense'
		AND date BETWEEN :start_date AND :end_date
		GROUP BY SUBSTRING(account_code, 1, 2)
		ORDER BY total_amount DESC
	`

	params := map[string]interface{}{
		"tenant_id":  tenantID,
		"start_date": startDate,
		"end_date":   endDate,
	}

	return c.Query(ctx, query, params)
}

func (c *LakehouseClient) GetLoanPortfolioAnalytics(ctx context.Context, tenantID string) (*LakehouseQueryResponse, error) {
	query := `
		SELECT 
			account_code,
			account_name,
			balance as outstanding_balance,
			CASE 
				WHEN account_code LIKE '1410%' THEN 'Consumer Loans'
				WHEN account_code LIKE '1420%' THEN 'Mortgage Loans'
				WHEN account_code LIKE '1430%' THEN 'SME Loans'
				WHEN account_code LIKE '1440%' THEN 'Corporate Loans'
				WHEN account_code LIKE '1450%' THEN 'Agricultural Loans'
				ELSE 'Other Loans'
			END as loan_category
		FROM gold.account_balances
		WHERE tenant_id = :tenant_id
		AND account_code LIKE '14%'
		ORDER BY balance DESC
	`

	params := map[string]interface{}{
		"tenant_id": tenantID,
	}

	return c.Query(ctx, query, params)
}

func (c *LakehouseClient) GetDepositAnalytics(ctx context.Context, tenantID string) (*LakehouseQueryResponse, error) {
	query := `
		SELECT 
			account_code,
			account_name,
			balance as deposit_balance,
			CASE 
				WHEN account_code LIKE '2010%' OR account_code LIKE '2020%' THEN 'Current Accounts'
				WHEN account_code LIKE '2030%' THEN 'Savings Accounts'
				WHEN account_code LIKE '204%' OR account_code LIKE '205%' OR account_code LIKE '206%' THEN 'Domiciliary Accounts'
				WHEN account_code LIKE '211%' OR account_code LIKE '212%' OR account_code LIKE '213%' OR account_code LIKE '214%' OR account_code LIKE '215%' THEN 'Fixed Deposits'
				ELSE 'Other Deposits'
			END as deposit_category
		FROM gold.account_balances
		WHERE tenant_id = :tenant_id
		AND (account_code LIKE '20%' OR account_code LIKE '21%')
		ORDER BY balance DESC
	`

	params := map[string]interface{}{
		"tenant_id": tenantID,
	}

	return c.Query(ctx, query, params)
}

func (c *LakehouseClient) GetNetInterestMargin(ctx context.Context, tenantID, startDate, endDate string) (*LakehouseQueryResponse, error) {
	query := `
		WITH interest_income AS (
			SELECT SUM(amount) as total_interest_income
			FROM gold.journal_entries
			WHERE tenant_id = :tenant_id
			AND account_code LIKE '40%'
			AND date BETWEEN :start_date AND :end_date
		),
		interest_expense AS (
			SELECT SUM(amount) as total_interest_expense
			FROM gold.journal_entries
			WHERE tenant_id = :tenant_id
			AND account_code LIKE '50%'
			AND date BETWEEN :start_date AND :end_date
		),
		earning_assets AS (
			SELECT AVG(balance) as avg_earning_assets
			FROM gold.account_balances
			WHERE tenant_id = :tenant_id
			AND account_code LIKE '14%'
		)
		SELECT 
			ii.total_interest_income,
			ie.total_interest_expense,
			(ii.total_interest_income - ie.total_interest_expense) as net_interest_income,
			ea.avg_earning_assets,
			CASE 
				WHEN ea.avg_earning_assets > 0 
				THEN ((ii.total_interest_income - ie.total_interest_expense) / ea.avg_earning_assets) * 100
				ELSE 0 
			END as net_interest_margin_pct
		FROM interest_income ii, interest_expense ie, earning_assets ea
	`

	params := map[string]interface{}{
		"tenant_id":  tenantID,
		"start_date": startDate,
		"end_date":   endDate,
	}

	return c.Query(ctx, query, params)
}

func (c *LakehouseClient) PublishCBNReport(ctx context.Context, report *CBNReport) error {
	sectionsData := make([]map[string]interface{}, len(report.Sections))
	for i, section := range report.Sections {
		items := make([]map[string]interface{}, len(section.Items))
		for j, item := range section.Items {
			items[j] = map[string]interface{}{
				"code":        item.Code,
				"description": item.Description,
				"amount":      item.Amount,
				"prior":       item.PriorAmount,
				"variance":    item.Variance,
			}
		}
		sectionsData[i] = map[string]interface{}{
			"code":     section.Code,
			"name":     section.Name,
			"subtotal": section.Subtotal,
			"items":    items,
		}
	}

	event := LakehouseEvent{
		EventID:     fmt.Sprintf("cbn_report-%s-%s-%d", report.TenantID, report.ReportType, time.Now().UnixNano()),
		EventType:   "cbn_report_generated",
		ServiceName: ServiceName,
		TenantID:    report.TenantID,
		EntityID:    fmt.Sprintf("%s-%s", report.ReportType, report.AsOfDate.Format("2006-01-02")),
		EntityType:  "cbn_report",
		Payload: map[string]interface{}{
			"report_type":      string(report.ReportType),
			"report_name":      report.ReportName,
			"reporting_period": report.ReportingPeriod,
			"as_of_date":       report.AsOfDate.Format("2006-01-02"),
			"currency":         report.Currency,
			"sections":         sectionsData,
			"totals":           report.Totals,
			"ratios":           report.Ratios,
			"metadata":         report.Metadata,
		},
		Timestamp: time.Now(),
	}

	return c.PublishEvent(ctx, event)
}

func (c *LakehouseClient) GetHistoricalCBNReports(ctx context.Context, tenantID string, reportType CBNReportType, months int) (*LakehouseQueryResponse, error) {
	query := `
		SELECT 
			report_type,
			report_name,
			as_of_date,
			reporting_period,
			totals,
			ratios,
			generated_at
		FROM gold.cbn_reports
		WHERE tenant_id = :tenant_id
		AND report_type = :report_type
		AND as_of_date >= DATE_SUB(CURRENT_DATE, INTERVAL :months MONTH)
		ORDER BY as_of_date DESC
	`

	params := map[string]interface{}{
		"tenant_id":   tenantID,
		"report_type": string(reportType),
		"months":      months,
	}

	return c.Query(ctx, query, params)
}

func (c *LakehouseClient) GetCARTrend(ctx context.Context, tenantID string, months int) (*LakehouseQueryResponse, error) {
	query := `
		SELECT 
			as_of_date,
			JSON_EXTRACT(totals, '$.tier1_capital') as tier1_capital,
			JSON_EXTRACT(totals, '$.tier2_capital') as tier2_capital,
			JSON_EXTRACT(totals, '$.total_qualifying_capital') as total_capital,
			JSON_EXTRACT(totals, '$.total_rwa') as total_rwa,
			JSON_EXTRACT(ratios, '$.capital_adequacy_ratio') as car,
			JSON_EXTRACT(ratios, '$.tier1_ratio') as tier1_ratio,
			JSON_EXTRACT(ratios, '$.minimum_car') as minimum_car
		FROM gold.cbn_reports
		WHERE tenant_id = :tenant_id
		AND report_type = 'CAR'
		AND as_of_date >= DATE_SUB(CURRENT_DATE, INTERVAL :months MONTH)
		ORDER BY as_of_date ASC
	`

	params := map[string]interface{}{
		"tenant_id": tenantID,
		"months":    months,
	}

	return c.Query(ctx, query, params)
}

func (c *LakehouseClient) GetLiquidityRatioTrend(ctx context.Context, tenantID string, months int) (*LakehouseQueryResponse, error) {
	query := `
		SELECT 
			as_of_date,
			JSON_EXTRACT(totals, '$.total_liquid_assets') as liquid_assets,
			JSON_EXTRACT(totals, '$.total_liabilities') as total_liabilities,
			JSON_EXTRACT(ratios, '$.liquidity_ratio') as liquidity_ratio,
			JSON_EXTRACT(ratios, '$.minimum_liquidity_ratio') as minimum_ratio
		FROM gold.cbn_reports
		WHERE tenant_id = :tenant_id
		AND report_type = 'LR'
		AND as_of_date >= DATE_SUB(CURRENT_DATE, INTERVAL :months MONTH)
		ORDER BY as_of_date ASC
	`

	params := map[string]interface{}{
		"tenant_id": tenantID,
		"months":    months,
	}

	return c.Query(ctx, query, params)
}

func (c *LakehouseClient) GetNPLTrend(ctx context.Context, tenantID string, months int) (*LakehouseQueryResponse, error) {
	query := `
		SELECT 
			as_of_date,
			JSON_EXTRACT(totals, '$.total_loans') as total_loans,
			JSON_EXTRACT(totals, '$.total_npl') as total_npl,
			JSON_EXTRACT(ratios, '$.npl_ratio') as npl_ratio
		FROM gold.cbn_reports
		WHERE tenant_id = :tenant_id
		AND report_type = 'NPL'
		AND as_of_date >= DATE_SUB(CURRENT_DATE, INTERVAL :months MONTH)
		ORDER BY as_of_date ASC
	`

	params := map[string]interface{}{
		"tenant_id": tenantID,
		"months":    months,
	}

	return c.Query(ctx, query, params)
}

func (c *LakehouseClient) GetProvisionCoverageTrend(ctx context.Context, tenantID string, months int) (*LakehouseQueryResponse, error) {
	query := `
		SELECT 
			as_of_date,
			JSON_EXTRACT(totals, '$.total_npl') as total_npl,
			JSON_EXTRACT(totals, '$.total_provision') as total_provision,
			JSON_EXTRACT(ratios, '$.provision_coverage') as provision_coverage
		FROM gold.cbn_reports
		WHERE tenant_id = :tenant_id
		AND report_type = 'LLP'
		AND as_of_date >= DATE_SUB(CURRENT_DATE, INTERVAL :months MONTH)
		ORDER BY as_of_date ASC
	`

	params := map[string]interface{}{
		"tenant_id": tenantID,
		"months":    months,
	}

	return c.Query(ctx, query, params)
}

func (c *LakehouseClient) GetSectoralCreditDistribution(ctx context.Context, tenantID string, asOfDate string) (*LakehouseQueryResponse, error) {
	query := `
		SELECT 
			s.code,
			s.description,
			s.amount,
			(s.amount * 100.0 / t.total_credit) as percentage
		FROM gold.cbn_report_sections s
		JOIN (
			SELECT JSON_EXTRACT(totals, '$.total_credit') as total_credit
			FROM gold.cbn_reports
			WHERE tenant_id = :tenant_id
			AND report_type = 'SC'
			AND as_of_date = :as_of_date
		) t ON 1=1
		WHERE s.tenant_id = :tenant_id
		AND s.report_type = 'SC'
		AND s.as_of_date = :as_of_date
		ORDER BY s.amount DESC
	`

	params := map[string]interface{}{
		"tenant_id":  tenantID,
		"as_of_date": asOfDate,
	}

	return c.Query(ctx, query, params)
}

func (c *LakehouseClient) GetDepositCompositionTrend(ctx context.Context, tenantID string, months int) (*LakehouseQueryResponse, error) {
	query := `
		SELECT 
			as_of_date,
			JSON_EXTRACT(totals, '$.total_deposits') as total_deposits,
			JSON_EXTRACT_SCALAR(sections, '$[0].items[0].amount') as current_accounts,
			JSON_EXTRACT_SCALAR(sections, '$[0].items[1].amount') as savings_accounts,
			JSON_EXTRACT_SCALAR(sections, '$[0].items[2].amount') as fixed_deposits,
			JSON_EXTRACT_SCALAR(sections, '$[0].items[3].amount') as domiciliary_accounts
		FROM gold.cbn_reports
		WHERE tenant_id = :tenant_id
		AND report_type = 'DC'
		AND as_of_date >= DATE_SUB(CURRENT_DATE, INTERVAL :months MONTH)
		ORDER BY as_of_date ASC
	`

	params := map[string]interface{}{
		"tenant_id": tenantID,
		"months":    months,
	}

	return c.Query(ctx, query, params)
}

func (c *LakehouseClient) GetProfitabilityTrend(ctx context.Context, tenantID string, months int) (*LakehouseQueryResponse, error) {
	query := `
		SELECT 
			as_of_date,
			JSON_EXTRACT(totals, '$.operating_income') as operating_income,
			JSON_EXTRACT(totals, '$.total_expenses') as total_expenses,
			JSON_EXTRACT(totals, '$.profit_before_tax') as profit_before_tax,
			JSON_EXTRACT(totals, '$.profit_after_tax') as profit_after_tax
		FROM gold.cbn_reports
		WHERE tenant_id = :tenant_id
		AND report_type = 'PL'
		AND as_of_date >= DATE_SUB(CURRENT_DATE, INTERVAL :months MONTH)
		ORDER BY as_of_date ASC
	`

	params := map[string]interface{}{
		"tenant_id": tenantID,
		"months":    months,
	}

	return c.Query(ctx, query, params)
}

func (c *LakehouseClient) GetBalanceSheetTrend(ctx context.Context, tenantID string, months int) (*LakehouseQueryResponse, error) {
	query := `
		SELECT 
			as_of_date,
			JSON_EXTRACT(totals, '$.total_assets') as total_assets,
			JSON_EXTRACT(totals, '$.total_liabilities') as total_liabilities,
			JSON_EXTRACT(totals, '$.total_equity') as total_equity
		FROM gold.cbn_reports
		WHERE tenant_id = :tenant_id
		AND report_type = 'SFP'
		AND as_of_date >= DATE_SUB(CURRENT_DATE, INTERVAL :months MONTH)
		ORDER BY as_of_date ASC
	`

	params := map[string]interface{}{
		"tenant_id": tenantID,
		"months":    months,
	}

	return c.Query(ctx, query, params)
}

func (c *LakehouseClient) GetRegulatoryComplianceStatus(ctx context.Context, tenantID string) (*LakehouseQueryResponse, error) {
	query := `
		WITH latest_reports AS (
			SELECT 
				report_type,
				as_of_date,
				totals,
				ratios,
				ROW_NUMBER() OVER (PARTITION BY report_type ORDER BY as_of_date DESC) as rn
			FROM gold.cbn_reports
			WHERE tenant_id = :tenant_id
		)
		SELECT 
			report_type,
			as_of_date,
			CASE report_type
				WHEN 'CAR' THEN JSON_EXTRACT(ratios, '$.capital_adequacy_ratio')
				WHEN 'LR' THEN JSON_EXTRACT(ratios, '$.liquidity_ratio')
				WHEN 'NPL' THEN JSON_EXTRACT(ratios, '$.npl_ratio')
				WHEN 'LLP' THEN JSON_EXTRACT(ratios, '$.provision_coverage')
				ELSE NULL
			END as current_ratio,
			CASE report_type
				WHEN 'CAR' THEN 15.0
				WHEN 'LR' THEN 30.0
				WHEN 'NPL' THEN 5.0
				WHEN 'LLP' THEN 100.0
				ELSE NULL
			END as minimum_requirement,
			CASE 
				WHEN report_type = 'CAR' AND JSON_EXTRACT(ratios, '$.capital_adequacy_ratio') >= 15.0 THEN 'COMPLIANT'
				WHEN report_type = 'LR' AND JSON_EXTRACT(ratios, '$.liquidity_ratio') >= 30.0 THEN 'COMPLIANT'
				WHEN report_type = 'NPL' AND JSON_EXTRACT(ratios, '$.npl_ratio') <= 5.0 THEN 'COMPLIANT'
				WHEN report_type = 'LLP' AND JSON_EXTRACT(ratios, '$.provision_coverage') >= 100.0 THEN 'COMPLIANT'
				ELSE 'NON-COMPLIANT'
			END as compliance_status
		FROM latest_reports
		WHERE rn = 1
		AND report_type IN ('CAR', 'LR', 'NPL', 'LLP')
	`

	params := map[string]interface{}{
		"tenant_id": tenantID,
	}

	return c.Query(ctx, query, params)
}

func (c *LakehouseClient) GetAMLMetrics(ctx context.Context, tenantID string, months int) (*LakehouseQueryResponse, error) {
	query := `
		SELECT 
			as_of_date,
			JSON_EXTRACT_SCALAR(sections, '$[0].items[0].amount') as strs_filed,
			JSON_EXTRACT_SCALAR(sections, '$[1].items[0].amount') as ctrs_filed,
			JSON_EXTRACT_SCALAR(sections, '$[2].items[0].amount') as complete_kyc,
			JSON_EXTRACT_SCALAR(sections, '$[2].items[1].amount') as incomplete_kyc,
			JSON_EXTRACT_SCALAR(sections, '$[3].items[0].amount') as transactions_screened,
			JSON_EXTRACT_SCALAR(sections, '$[3].items[3].amount') as blocked_transactions
		FROM gold.cbn_reports
		WHERE tenant_id = :tenant_id
		AND report_type = 'AML'
		AND as_of_date >= DATE_SUB(CURRENT_DATE, INTERVAL :months MONTH)
		ORDER BY as_of_date ASC
	`

	params := map[string]interface{}{
		"tenant_id": tenantID,
		"months":    months,
	}

	return c.Query(ctx, query, params)
}

func (c *LakehouseClient) GetFinancialInclusionMetrics(ctx context.Context, tenantID string, quarters int) (*LakehouseQueryResponse, error) {
	query := `
		SELECT 
			as_of_date,
			JSON_EXTRACT_SCALAR(sections, '$[0].items[0].amount') as total_accounts,
			JSON_EXTRACT_SCALAR(sections, '$[0].items[1].amount') as new_accounts,
			JSON_EXTRACT_SCALAR(sections, '$[0].items[5].amount') as women_accounts,
			JSON_EXTRACT_SCALAR(sections, '$[0].items[6].amount') as youth_accounts,
			JSON_EXTRACT_SCALAR(sections, '$[2].items[0].amount') as active_accounts,
			JSON_EXTRACT_SCALAR(sections, '$[2].items[1].amount') as dormant_accounts
		FROM gold.cbn_reports
		WHERE tenant_id = :tenant_id
		AND report_type = 'FI'
		AND as_of_date >= DATE_SUB(CURRENT_DATE, INTERVAL :quarters QUARTER)
		ORDER BY as_of_date ASC
	`

	params := map[string]interface{}{
		"tenant_id": tenantID,
		"quarters":  quarters,
	}

	return c.Query(ctx, query, params)
}

func (c *LakehouseClient) GetEBankingTrend(ctx context.Context, tenantID string, months int) (*LakehouseQueryResponse, error) {
	query := `
		SELECT 
			as_of_date,
			JSON_EXTRACT_SCALAR(sections, '$[0].items[0].amount') as mobile_users,
			JSON_EXTRACT_SCALAR(sections, '$[0].items[2].amount') as mobile_volume,
			JSON_EXTRACT_SCALAR(sections, '$[0].items[3].amount') as mobile_value,
			JSON_EXTRACT_SCALAR(sections, '$[1].items[0].amount') as internet_users,
			JSON_EXTRACT_SCALAR(sections, '$[1].items[2].amount') as internet_volume,
			JSON_EXTRACT_SCALAR(sections, '$[2].items[1].amount') as ussd_volume,
			JSON_EXTRACT_SCALAR(sections, '$[3].items[1].amount') as pos_volume
		FROM gold.cbn_reports
		WHERE tenant_id = :tenant_id
		AND report_type = 'EB'
		AND as_of_date >= DATE_SUB(CURRENT_DATE, INTERVAL :months MONTH)
		ORDER BY as_of_date ASC
	`

	params := map[string]interface{}{
		"tenant_id": tenantID,
		"months":    months,
	}

	return c.Query(ctx, query, params)
}

func (c *LakehouseClient) GetMaturityGapAnalysis(ctx context.Context, tenantID string, asOfDate string) (*LakehouseQueryResponse, error) {
	query := `
		WITH assets AS (
			SELECT 
				JSON_EXTRACT_SCALAR(sections, '$[0].items[0].amount') as up_to_1m,
				JSON_EXTRACT_SCALAR(sections, '$[0].items[1].amount') as m1_to_3m,
				JSON_EXTRACT_SCALAR(sections, '$[0].items[2].amount') as m3_to_6m,
				JSON_EXTRACT_SCALAR(sections, '$[0].items[3].amount') as m6_to_12m,
				JSON_EXTRACT_SCALAR(sections, '$[0].items[4].amount') as y1_to_3y,
				JSON_EXTRACT_SCALAR(sections, '$[0].items[5].amount') as y3_to_5y,
				JSON_EXTRACT_SCALAR(sections, '$[0].items[6].amount') as over_5y
			FROM gold.cbn_reports
			WHERE tenant_id = :tenant_id
			AND report_type = 'MP'
			AND as_of_date = :as_of_date
		),
		liabilities AS (
			SELECT 
				JSON_EXTRACT_SCALAR(sections, '$[1].items[0].amount') as up_to_1m,
				JSON_EXTRACT_SCALAR(sections, '$[1].items[1].amount') as m1_to_3m,
				JSON_EXTRACT_SCALAR(sections, '$[1].items[2].amount') as m3_to_6m,
				JSON_EXTRACT_SCALAR(sections, '$[1].items[3].amount') as m6_to_12m,
				JSON_EXTRACT_SCALAR(sections, '$[1].items[4].amount') as y1_to_3y,
				JSON_EXTRACT_SCALAR(sections, '$[1].items[5].amount') as y3_to_5y,
				JSON_EXTRACT_SCALAR(sections, '$[1].items[6].amount') as over_5y
			FROM gold.cbn_reports
			WHERE tenant_id = :tenant_id
			AND report_type = 'MP'
			AND as_of_date = :as_of_date
		)
		SELECT 
			'Up to 1 Month' as bucket,
			a.up_to_1m as assets,
			l.up_to_1m as liabilities,
			(a.up_to_1m - l.up_to_1m) as gap
		FROM assets a, liabilities l
		UNION ALL
		SELECT '1-3 Months', a.m1_to_3m, l.m1_to_3m, (a.m1_to_3m - l.m1_to_3m) FROM assets a, liabilities l
		UNION ALL
		SELECT '3-6 Months', a.m3_to_6m, l.m3_to_6m, (a.m3_to_6m - l.m3_to_6m) FROM assets a, liabilities l
		UNION ALL
		SELECT '6-12 Months', a.m6_to_12m, l.m6_to_12m, (a.m6_to_12m - l.m6_to_12m) FROM assets a, liabilities l
		UNION ALL
		SELECT '1-3 Years', a.y1_to_3y, l.y1_to_3y, (a.y1_to_3y - l.y1_to_3y) FROM assets a, liabilities l
		UNION ALL
		SELECT '3-5 Years', a.y3_to_5y, l.y3_to_5y, (a.y3_to_5y - l.y3_to_5y) FROM assets a, liabilities l
		UNION ALL
		SELECT 'Over 5 Years', a.over_5y, l.over_5y, (a.over_5y - l.over_5y) FROM assets a, liabilities l
	`

	params := map[string]interface{}{
		"tenant_id":  tenantID,
		"as_of_date": asOfDate,
	}

	return c.Query(ctx, query, params)
}

func (c *LakehouseClient) ScheduleCBNReportGeneration(ctx context.Context, tenantID string, reportType CBNReportType, schedule string) error {
	event := LakehouseEvent{
		EventID:     fmt.Sprintf("cbn_schedule-%s-%s-%d", tenantID, reportType, time.Now().UnixNano()),
		EventType:   "cbn_report_scheduled",
		ServiceName: ServiceName,
		TenantID:    tenantID,
		EntityID:    fmt.Sprintf("schedule-%s", reportType),
		EntityType:  "cbn_schedule",
		Payload: map[string]interface{}{
			"report_type": string(reportType),
			"schedule":    schedule,
			"enabled":     true,
		},
		Timestamp: time.Now(),
	}

	return c.PublishEvent(ctx, event)
}

func (c *LakehouseClient) GetReportSubmissionHistory(ctx context.Context, tenantID string, months int) (*LakehouseQueryResponse, error) {
	query := `
		SELECT 
			report_type,
			as_of_date,
			generated_at,
			submitted_at,
			submission_status,
			cbn_reference_number,
			rejection_reason
		FROM gold.cbn_report_submissions
		WHERE tenant_id = :tenant_id
		AND generated_at >= DATE_SUB(CURRENT_DATE, INTERVAL :months MONTH)
		ORDER BY generated_at DESC
	`

	params := map[string]interface{}{
		"tenant_id": tenantID,
		"months":    months,
	}

	return c.Query(ctx, query, params)
}

func (c *LakehouseClient) GetCBNReportComparison(ctx context.Context, tenantID string, reportType CBNReportType, date1, date2 string) (*LakehouseQueryResponse, error) {
	query := `
		WITH report1 AS (
			SELECT sections, totals, ratios
			FROM gold.cbn_reports
			WHERE tenant_id = :tenant_id
			AND report_type = :report_type
			AND as_of_date = :date1
		),
		report2 AS (
			SELECT sections, totals, ratios
			FROM gold.cbn_reports
			WHERE tenant_id = :tenant_id
			AND report_type = :report_type
			AND as_of_date = :date2
		)
		SELECT 
			:date1 as period1,
			:date2 as period2,
			r1.totals as totals_period1,
			r2.totals as totals_period2,
			r1.ratios as ratios_period1,
			r2.ratios as ratios_period2
		FROM report1 r1, report2 r2
	`

	params := map[string]interface{}{
		"tenant_id":   tenantID,
		"report_type": string(reportType),
		"date1":       date1,
		"date2":       date2,
	}

	return c.Query(ctx, query, params)
}
