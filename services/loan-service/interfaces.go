package main

import "time"

// CreditDecisionEngine handles automated loan decisioning
type CreditDecisionEngine struct {
	minCreditScore       int
	maxDebtToIncomeRatio float64
	maxLoanToValueRatio  float64
}
// LoanApplication represents a loan application
type LoanApplication struct {
	ID                 string  `json:"id"`
	TenantID           string  `json:"tenant_id"`
	LoanApplicationID  string  `json:"loan_application_id"`
	Status			   string  `json:"status"`
	ApplicantID        string  `json:"applicant_id"`
	LoanAmount         float64 `json:"loan_amount" binding:"required"`
	LoanPurpose        string  `json:"loan_purpose" binding:"required"`
	LoanInterestRatePercent		float64
	RequestedTerm      int     `json:"requested_term" binding:"required"` // in months
	MonthlyIncome      float64 `json:"monthly_income" binding:"required"`
	ExistingDebt       float64 `json:"existing_debt"`
	CollateralValue    float64 `json:"collateral_value"`
	CreditScore        int     `json:"credit_score"`
	EmploymentStatus   string  `json:"employment_status"`
	EmploymentDuration int     `json:"employment_duration"` // months
	BankStatementScore float64 `json:"bank_statement_score"`
	BVNVerified        bool    `json:"bvn_verified"`
	NINVerified        bool    `json:"nin_verified"`
	LoanStartedAt	   *time.Time
	Payments                 []LoanPayment  `json:"payments"`
}

type LoanPayment struct {
	ID                string     `json:"id"`
	LoanPaymentID     string     `json:"loan_payment_id"`
	LoanApplicationID string     `json:"loan_application_id"`
	TenantID          string     `json:"tenant_id"`
	TransactionID     string     `json:"transaction_id" binding:"required"`
	Amount            float64    `json:"amount" binding:"required"`
	PaymentDate       *time.Time `json:"payment_date,omitempty" binding:"required"`
	PaymentMethod     string     `json:"payment_method" binding:"required"`
}

// CreditDecision represents the automated decision
type CreditDecision struct {
	Decision           string  // "APPROVED", "DECLINED", "REFER"
	ApprovedAmount     float64
	InterestRate       float64
	ApprovedTerm       int
	Conditions         []string
	DeclineReasons     []string
	RiskScore          float64
	ProbabilityDefault float64
	RecommendedAction  string
}

// RepaymentSchedule represents a loan repayment schedule
type RepaymentSchedule struct {
	LoanAmount      float64
	InterestRate    float64
	Term            int
	MonthlyPayment  float64
	TotalInterest   float64
	TotalPayment    float64
	Schedule        []RepaymentInstallment
}

// RepaymentInstallment represents a single payment
type RepaymentInstallment struct {
	InstallmentNumber int
	DueDate           time.Time
	PrincipalPayment  float64
	InterestPayment   float64
	TotalPayment      float64
	RemainingBalance  float64
}