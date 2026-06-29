package main

import (
	"fmt"
	"math"
	"time"
)

// NewCreditDecisionEngine creates a new credit decision engine
func NewCreditDecisionEngine() *CreditDecisionEngine {
	return &CreditDecisionEngine{
		minCreditScore:       550,  // Minimum credit score for approval
		maxDebtToIncomeRatio: 0.40, // Maximum 40% DTI
		maxLoanToValueRatio:  0.80, // Maximum 80% LTV
	}
}

// EvaluateLoanApplication performs comprehensive credit assessment
func (e *CreditDecisionEngine) EvaluateLoanApplication(app *LoanApplication) *CreditDecision {
	decision := &CreditDecision{
		Conditions:     []string{},
		DeclineReasons: []string{},
	}

	// Step 1: Identity Verification Check
	if !app.BVNVerified || !app.NINVerified {
		decision.Decision = "DECLINED"
		decision.DeclineReasons = append(decision.DeclineReasons, "Identity verification incomplete.")
		return decision
	}

	// Step 2: Credit Score Assessment
	creditScorePass := e.assessCreditScore(app, decision)
	if !creditScorePass {
		decision.Decision = "DECLINED"
		return decision
	}

	// Step 3: Affordability Assessment (Debt-to-Income Ratio)
	dtiPass := e.assessAffordability(app, decision)
	if !dtiPass {
		decision.Decision = "DECLINED"
		return decision
	}

	// Step 4: Collateral Assessment (Loan-to-Value Ratio)
	ltvPass := e.assessCollateral(app, decision)

	// Step 5: Employment Stability Check
	employmentPass := e.assessEmployment(app, decision)

	// Step 6: Bank Statement Analysis
	bankStatementPass := e.assessBankStatement(app, decision)

	// Step 7: Calculate Risk Score
	decision.RiskScore = e.calculateRiskScore(app)
	decision.ProbabilityDefault = e.calculateProbabilityOfDefault(decision.RiskScore)

	// Step 8: Make Final Decision
	if creditScorePass && dtiPass && ltvPass && employmentPass && bankStatementPass {
		if decision.RiskScore < 0.15 { // Low risk
			decision.Decision = "APPROVED"
			decision.ApprovedAmount = app.LoanAmount
			decision.ApprovedTerm = app.RequestedTerm
			decision.InterestRate = e.calculateInterestRate(app, decision.RiskScore)
		} else if decision.RiskScore < 0.30 { // Medium risk
			decision.Decision = "APPROVED"
			decision.ApprovedAmount = app.LoanAmount * 0.80 // Reduce by 20%
			decision.ApprovedTerm = app.RequestedTerm
			decision.InterestRate = e.calculateInterestRate(app, decision.RiskScore)
			decision.Conditions = append(decision.Conditions, "Loan amount reduced due to risk assessment")
		} else { // High risk
			decision.Decision = "REFER"
			decision.RecommendedAction = "Refer to credit committee for manual review"
		}
	} else {
		decision.Decision = "DECLINED"
	}

	return decision
}

// assessCreditScore evaluates credit score
func (e *CreditDecisionEngine) assessCreditScore(app *LoanApplication, decision *CreditDecision) bool {
	if app.CreditScore < e.minCreditScore {
		decision.DeclineReasons = append(decision.DeclineReasons,
			fmt.Sprintf("Credit score %d below minimum %d", app.CreditScore, e.minCreditScore))
		return false
	}

	if app.CreditScore >= 750 {
		decision.Conditions = append(decision.Conditions, "Excellent credit score")
	} else if app.CreditScore >= 650 {
		decision.Conditions = append(decision.Conditions, "Good credit score")
	} else {
		decision.Conditions = append(decision.Conditions, "Fair credit score - higher interest rate may apply")
	}

	return true
}

// assessAffordability calculates and evaluates debt-to-income ratio
func (e *CreditDecisionEngine) assessAffordability(app *LoanApplication, decision *CreditDecision) bool {
	// Calculate monthly payment (simplified - using 2% of loan amount as proxy)
	estimatedMonthlyPayment := (app.LoanAmount * 0.20) / float64(app.RequestedTerm)

	// Calculate DTI ratio
	totalMonthlyDebt := app.ExistingDebt + estimatedMonthlyPayment
	dtiRatio := totalMonthlyDebt / app.MonthlyIncome

	if dtiRatio > e.maxDebtToIncomeRatio {
		decision.DeclineReasons = append(decision.DeclineReasons,
			fmt.Sprintf("Debt-to-income ratio %.2f%% exceeds maximum %.2f%%",
				dtiRatio*100, e.maxDebtToIncomeRatio*100))
		return false
	}

	if dtiRatio > 0.30 {
		decision.Conditions = append(decision.Conditions,
			fmt.Sprintf("DTI ratio %.2f%% is acceptable but elevated", dtiRatio*100))
	}

	return true
}

// assessCollateral evaluates loan-to-value ratio
func (e *CreditDecisionEngine) assessCollateral(app *LoanApplication, decision *CreditDecision) bool {
	if app.CollateralValue == 0 {
		// Unsecured loan - higher risk
		decision.Conditions = append(decision.Conditions, "Unsecured loan - higher interest rate")
		return true
	}

	ltvRatio := app.LoanAmount / app.CollateralValue

	if ltvRatio > e.maxLoanToValueRatio {
		decision.DeclineReasons = append(decision.DeclineReasons,
			fmt.Sprintf("Loan-to-value ratio %.2f%% exceeds maximum %.2f%%",
				ltvRatio*100, e.maxLoanToValueRatio*100))
		return false
	}

	if ltvRatio < 0.60 {
		decision.Conditions = append(decision.Conditions, "Strong collateral coverage")
	}

	return true
}

// assessEmployment evaluates employment stability
func (e *CreditDecisionEngine) assessEmployment(app *LoanApplication, decision *CreditDecision) bool {
	if app.EmploymentStatus == "unemployed" {
		decision.DeclineReasons = append(decision.DeclineReasons, "Applicant is unemployed")
		return false
	}

	if app.EmploymentDuration < 6 {
		decision.Conditions = append(decision.Conditions,
			"Recent employment - additional verification required")
		return false
	}

	if app.EmploymentDuration >= 24 {
		decision.Conditions = append(decision.Conditions, "Stable employment history")
	}

	return true
}

// assessBankStatement evaluates bank statement analysis score
func (e *CreditDecisionEngine) assessBankStatement(app *LoanApplication, decision *CreditDecision) bool {
	if app.BankStatementScore < 0.50 {
		decision.DeclineReasons = append(decision.DeclineReasons,
			"Bank statement analysis indicates insufficient cash flow")
		return false
	}

	if app.BankStatementScore >= 0.80 {
		decision.Conditions = append(decision.Conditions, "Strong cash flow pattern")
	}

	return true
}

// calculateRiskScore computes overall risk score (0-1 scale)
func (e *CreditDecisionEngine) calculateRiskScore(app *LoanApplication) float64 {
	// Weighted risk factors
	creditScoreWeight := 0.30
	dtiWeight := 0.25
	ltvWeight := 0.20
	employmentWeight := 0.15
	bankStatementWeight := 0.10

	// Normalize credit score (300-850 range to 0-1)
	creditScoreRisk := 1.0 - ((float64(app.CreditScore) - 300.0) / 550.0)

	// Calculate DTI risk
	estimatedMonthlyPayment := (app.LoanAmount * 0.20) / float64(app.RequestedTerm)
	totalMonthlyDebt := app.ExistingDebt + estimatedMonthlyPayment
	dtiRatio := totalMonthlyDebt / app.MonthlyIncome
	dtiRisk := dtiRatio / e.maxDebtToIncomeRatio

	// Calculate LTV risk
	var ltvRisk float64
	if app.CollateralValue > 0 {
		ltvRatio := app.LoanAmount / app.CollateralValue
		ltvRisk = ltvRatio / e.maxLoanToValueRatio
	} else {
		ltvRisk = 1.0 // Maximum risk for unsecured
	}

	// Calculate employment risk
	employmentRisk := 1.0 - math.Min(float64(app.EmploymentDuration)/24.0, 1.0)

	// Bank statement risk
	bankStatementRisk := 1.0 - app.BankStatementScore

	// Weighted total risk
	totalRisk := (creditScoreRisk * creditScoreWeight) +
		(dtiRisk * dtiWeight) +
		(ltvRisk * ltvWeight) +
		(employmentRisk * employmentWeight) +
		(bankStatementRisk * bankStatementWeight)

	return math.Min(totalRisk, 1.0)
}

// calculateProbabilityOfDefault estimates default probability
func (e *CreditDecisionEngine) calculateProbabilityOfDefault(riskScore float64) float64 {
	// Logistic function to map risk score to PD
	// PD = 1 / (1 + e^(-10*(riskScore - 0.5)))
	pd := 1.0 / (1.0 + math.Exp(-10.0*(riskScore-0.5)))
	return pd
}

// calculateInterestRate determines interest rate based on risk
func (e *CreditDecisionEngine) calculateInterestRate(app *LoanApplication, riskScore float64) float64 {
	baseRate := 15.0 // Base interest rate (15% per annum)

	// Risk premium (0-10% based on risk score)
	riskPremium := riskScore * 10.0

	// Credit score adjustment
	var creditScoreAdjustment float64
	if app.CreditScore >= 750 {
		creditScoreAdjustment = -2.0 // 2% discount
	} else if app.CreditScore >= 650 {
		creditScoreAdjustment = -1.0 // 1% discount
	} else if app.CreditScore < 600 {
		creditScoreAdjustment = 2.0 // 2% premium
	}

	// Collateral adjustment
	var collateralAdjustment float64
	if app.CollateralValue > 0 {
		ltvRatio := app.LoanAmount / app.CollateralValue
		if ltvRatio < 0.50 {
			collateralAdjustment = -1.5 // 1.5% discount for strong collateral
		}
	} else {
		collateralAdjustment = 3.0 // 3% premium for unsecured
	}

	totalRate := baseRate + riskPremium + creditScoreAdjustment + collateralAdjustment

	// Cap between 12% and 35%
	return math.Max(12.0, math.Min(totalRate, 35.0))
}

// GenerateRepaymentSchedule creates a complete amortization schedule
func GenerateRepaymentSchedule(loanAmount float64, annualRate float64, termMonths int, startDate time.Time) *RepaymentSchedule {
	monthlyRate := annualRate / 12.0 / 100.0

	// Calculate monthly payment using amortization formula
	// M = P * [r(1+r)^n] / [(1+r)^n - 1]
	monthlyPayment := loanAmount * (monthlyRate * math.Pow(1+monthlyRate, float64(termMonths))) /
		(math.Pow(1+monthlyRate, float64(termMonths)) - 1)

	schedule := &RepaymentSchedule{
		LoanAmount:     loanAmount,
		InterestRate:   annualRate,
		Term:           termMonths,
		MonthlyPayment: monthlyPayment,
		Schedule:       make([]RepaymentInstallment, termMonths),
	}

	remainingBalance := loanAmount

	for i := 0; i < termMonths; i++ {
		interestPayment := remainingBalance * monthlyRate
		principalPayment := monthlyPayment - interestPayment
		remainingBalance -= principalPayment

		// Handle final payment rounding
		if i == termMonths-1 {
			principalPayment += remainingBalance
			remainingBalance = 0
		}

		installment := RepaymentInstallment{
			InstallmentNumber: i + 1,
			DueDate:           startDate.AddDate(0, i+1, 0),
			PrincipalPayment:  principalPayment,
			InterestPayment:   interestPayment,
			TotalPayment:      monthlyPayment,
			RemainingBalance:  math.Max(remainingBalance, 0),
		}

		schedule.Schedule[i] = installment
		schedule.TotalInterest += interestPayment
	}

	schedule.TotalPayment = schedule.TotalInterest + loanAmount

	return schedule
}

// CalculateInterestRate returns interest rate as a percentage based on the loan amount
func CalculateInterestRate(loanAmount float64) float64 {
	var baseRate float64 = 5.0 // base interest rate in %
	var extraRate float64

	switch {
		case loanAmount <= 1000:
			extraRate = 0
		case loanAmount <= 10000:
			extraRate = 1.5
		case loanAmount <= 50000:
			extraRate = 2.5
		default:
			extraRate = 4.0
	}

	// You can add some fine-tuning formula, e.g., logarithmic or percentage-based
	rate := baseRate + extraRate + math.Log10(loanAmount)*0.5

	// Round to 2 decimal places
	return math.Round(rate*100) / 100
}