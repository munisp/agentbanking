package main

import (
	"context"
	"database/sql"
	"fmt"
	"log"
	"math"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"syscall"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/joho/godotenv"
	_ "github.com/lib/pq"
)

var (
	db              *sql.DB
	engine          *CreditDecisionEngine
	loanKafkaClient *LoanKafkaClient
	coaClient       *CoAClient
)

func main() {
	godotenv.Load()

	if err := initDatabase(); err != nil {
		log.Fatalf("Failed to initialize database: %v", err)
	}
	defer db.Close()

	engine = NewCreditDecisionEngine()
	coaClient = NewCoAClient()

	// Initialize Kafka client if Kafka brokers are configured
	kafkaBrokers := os.Getenv("KAFKA_BROKERS")
	if kafkaBrokers != "" {
		loanKafkaClient = NewLoanKafkaClient()
		log.Printf("Kafka client initialized with brokers: %s", kafkaBrokers)
	} else {
		log.Printf("WARNING: Kafka client not initialized - KAFKA_BROKERS not set")
	}

	router := gin.Default()
	router.Use(corsMiddleware())
	router.Use(loggingMiddleware())

	registerRoutes(router)

	var addr = ":" + GetEnv("PORT", "8011")

	srv := &http.Server{
		Addr:    addr,
		Handler: router,
	}

	go func() {
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatal(err)
		}
	}()

	log.Printf("Loan service started on %s", addr)

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	srv.Shutdown(ctx)
}

func createTables() error {
	schema := `
		-- Loan Applications Table
		CREATE TABLE IF NOT EXISTS loan_applications (
			id SERIAL PRIMARY KEY,
			loan_application_id VARCHAR(50) UNIQUE NOT NULL,
			tenant_id VARCHAR(50) NOT NULL,
			applicant_id VARCHAR(50) NOT NULL,
			loan_amount NUMERIC(15, 2) NOT NULL,
			loan_purpose TEXT NOT NULL,
			requested_term INT NOT NULL,
			monthly_income NUMERIC(15, 2) NOT NULL,
			existing_debt NUMERIC(15, 2),
			collateral_value NUMERIC(15, 2),
			credit_score INT,
			employment_status TEXT,
			employment_duration INT,
			bank_statement_score NUMERIC(5, 2),
			bvn_verified BOOLEAN DEFAULT FALSE,
			nin_verified BOOLEAN DEFAULT FALSE,
			interest_rate_percent NUMERIC(15, 2) NOT NULL,
			status TEXT NOT NULL DEFAULT 'pending',
			loan_started_at TIMESTAMP,
			created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
			updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
		);

		-- Index on id & tenant_id (composite)
		CREATE INDEX IF NOT EXISTS idx_loan_id_tenant ON loan_applications (id, tenant_id);

		-- Index on tenant_id & applicant_id (composite)
		CREATE INDEX IF NOT EXISTS idx_loan_tenant_applicant ON loan_applications (tenant_id, applicant_id);

		--------------------------------------------------------------------------------
		-- Loan Payments Table
		CREATE TABLE IF NOT EXISTS loan_payments (
			id SERIAL PRIMARY KEY,
			loan_payment_id VARCHAR(50) UNIQUE NOT NULL,
			loan_application_id VARCHAR(50) NOT NULL REFERENCES loan_applications(loan_application_id) ON DELETE CASCADE,
			tenant_id VARCHAR(50) NOT NULL,
			transaction_id VARCHAR(100) UNIQUE NOT NULL,
			amount NUMERIC(15, 2) NOT NULL,
			payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
			payment_method TEXT,
			created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
			updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
		);

		-- Index for fast queries on tenant + loan
		CREATE INDEX IF NOT EXISTS idx_payment_tenant_loan ON loan_payments (tenant_id, loan_application_id);

		-- Index for transaction lookups
		CREATE INDEX IF NOT EXISTS idx_payment_transaction ON loan_payments (transaction_id);
	`

	_, err := db.Exec(schema)
	if err != nil {
		return fmt.Errorf("failed to execute schema: %w", err)
	}

	log.Println("Loan database tables created/verified")
	return nil
}

func initDatabase() error {
	connStr := GetEnv("DATABASE_URI", "")

	if connStr == "" {
		log.Fatal("Failed to connect to database: connection string is empty")
	}

	var err error
	db, err = sql.Open("postgres", connStr)
	if err != nil {
		log.Fatal("Failed to connect to database:", err)
	}

	if err := db.Ping(); err != nil {
		log.Fatal("Failed to ping database:", err)
	}

	db.SetMaxOpenConns(25)
	db.SetMaxIdleConns(5)
	db.SetConnMaxLifetime(5 * time.Minute)

	if err = db.Ping(); err != nil {
		return fmt.Errorf("failed to ping database: %w", err)
	}

	log.Println("Loan database connection established")

	if err = createTables(); err != nil {
		return fmt.Errorf("failed to create tables: %w", err)
	}

	return nil
}

func registerRoutes(router *gin.Engine) {
	router.GET("/health", healthCheck)

	api := router.Group("/api/v1/loans")
	{
		api.POST("/applications", createLoanApplication)
		api.GET("/applications/administration", getAllLoanApplications)
		api.GET("/applications/:id", getLoanApplication)
		api.GET("/applications", getLoanApplications)
		api.POST("/applications/:id/evaluate", evaluateLoanApplication)
		api.POST("/applications/:id/approve", approveLoanApplication)
		api.POST("/applications/:id/decline", declineLoanApplication)
		api.POST("/:id/disburse", disburseLoan)
		api.GET("/:id/schedule", getRepaymentSchedule)
		api.POST("/:id/record-payment", recordPayment)
	}
}

func healthCheck(c *gin.Context) {
	c.JSON(200, gin.H{"status": "healthy", "service": "loan-service"})
}

func createLoanApplication(c *gin.Context) {
	var application LoanApplication
	if err := c.ShouldBindJSON(&application); err != nil {
		SendErrorGin(c, "validation_failed", err.Error(), 400)
		return
	}

	application.TenantID = c.GetHeader("X-Tenant-ID")
	application.ApplicantID = c.GetHeader("X-Keycloak-ID")
	application.LoanApplicationID = generateID("LOAN")
	application.LoanInterestRatePercent = CalculateInterestRate(application.LoanAmount)

	query := `
		INSERT INTO loan_applications (loan_application_id, tenant_id, applicant_id, loan_amount, loan_purpose, 
			requested_term, monthly_income, existing_debt, collateral_value, credit_score,
			employment_status, employment_duration, bank_statement_score, bvn_verified, nin_verified, interest_rate_percent)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
		RETURNING id
	`

	err := db.QueryRow(query, application.LoanApplicationID, application.TenantID, application.ApplicantID, application.LoanAmount, application.LoanPurpose,
		application.RequestedTerm, application.MonthlyIncome, application.ExistingDebt, application.CollateralValue, application.CreditScore,
		application.EmploymentStatus, application.EmploymentDuration, application.BankStatementScore, application.BVNVerified, application.NINVerified, application.LoanInterestRatePercent).Scan(&application.ID)

	if err != nil {
		log.Println("Insert error:", err)
		SendErrorGin(c, "internal_error", "Failed to create loan application", 500)
		return
	}

	// Publish event to Kafka
	event := LoanEvent{
		Type:      "loan.application.created",
		EntityID:  application.LoanApplicationID,
		TenantID:  application.TenantID,
		Status:    "pending",
		Timestamp: time.Now(),
		Metadata: map[string]interface{}{
			"applicant_id":      application.ApplicantID,
			"loan_amount":       application.LoanAmount,
			"loan_purpose":      application.LoanPurpose,
			"requested_term":    application.RequestedTerm,
			"credit_score":      application.CreditScore,
			"employment_status": application.EmploymentStatus,
		},
	}

	// Publish event to Kafka if client is available
	if loanKafkaClient != nil {
		loanKafkaClient.PublishEvent("loan.application.created", event)
	}

	c.JSON(201, application)
}

func getAllLoanApplications(c *gin.Context) {
	tenantID := c.GetHeader("X-Tenant-ID")

	if tenantID == "" {
		SendErrorGin(c, "bad_request", "Missing X-Tenant-ID header", 400)
		return
	}

	query := `
		SELECT id, tenant_id, applicant_id, loan_application_id, loan_amount, loan_purpose, requested_term,
		       monthly_income, existing_debt, collateral_value, credit_score, employment_status,
		       employment_duration, bank_statement_score, bvn_verified, nin_verified, status,
		       interest_rate_percent, loan_started_at
		FROM loan_applications
		WHERE tenant_id = $1
		ORDER BY created_at DESC
	`

	rows, err := db.Query(query, tenantID)
	if err != nil {
		SendErrorGin(c, "internal_error", "Database query failed", 500)
		return
	}
	defer rows.Close()

	var apps []LoanApplication

	for rows.Next() {
		var app LoanApplication
		if err := rows.Scan(
			&app.ID,
			&app.TenantID,
			&app.ApplicantID,
			&app.LoanApplicationID,
			&app.LoanAmount,
			&app.LoanPurpose,
			&app.RequestedTerm,
			&app.MonthlyIncome,
			&app.ExistingDebt,
			&app.CollateralValue,
			&app.CreditScore,
			&app.EmploymentStatus,
			&app.EmploymentDuration,
			&app.BankStatementScore,
			&app.BVNVerified,
			&app.NINVerified,
			&app.Status,
			&app.LoanInterestRatePercent,
			&app.LoanStartedAt,
		); err != nil {
			SendErrorGin(c, "internal_error", "Failed to scan loan data", 500)
			return
		}
		apps = append(apps, app)
	}

	c.JSON(200, apps)
}

func getLoanApplications(c *gin.Context) {
	tenantID := c.GetHeader("X-Tenant-ID")
	keycloakID := c.GetHeader("X-Keycloak-ID")

	if tenantID == "" || keycloakID == "" {
		SendErrorGin(c, "bad_request", "Missing required headers", 400)
		return
	}

	query := `
		SELECT id, tenant_id, applicant_id, loan_application_id, loan_amount, loan_purpose, requested_term,
		       monthly_income, existing_debt, collateral_value, credit_score, employment_status,
		       employment_duration, bank_statement_score, bvn_verified, nin_verified, status,
		       interest_rate_percent, loan_started_at
		FROM loan_applications
		WHERE applicant_id = $1 AND tenant_id = $2
		ORDER BY created_at DESC
	`

	rows, err := db.Query(query, keycloakID, tenantID)
	if err != nil {
		SendErrorGin(c, "internal_error", "Database query failed", 500)
		return
	}
	defer rows.Close()

	var apps []LoanApplication

	for rows.Next() {
		var app LoanApplication
		if err := rows.Scan(
			&app.ID,
			&app.TenantID,
			&app.ApplicantID,
			&app.LoanApplicationID,
			&app.LoanAmount,
			&app.LoanPurpose,
			&app.RequestedTerm,
			&app.MonthlyIncome,
			&app.ExistingDebt,
			&app.CollateralValue,
			&app.CreditScore,
			&app.EmploymentStatus,
			&app.EmploymentDuration,
			&app.BankStatementScore,
			&app.BVNVerified,
			&app.NINVerified,
			&app.Status,
			&app.LoanInterestRatePercent,
			&app.LoanStartedAt,
		); err != nil {
			SendErrorGin(c, "internal_error", "Failed to scan loan data", 500)
			return
		}
		apps = append(apps, app)
	}

	c.JSON(200, apps)
}

func getLoanApplication(c *gin.Context) {
	id := c.Param("id")
	tenantID := c.GetHeader("X-Tenant-ID")

	var app LoanApplication
	query := `
		SELECT id, tenant_id, applicant_id, loan_application_id, loan_amount, loan_purpose, requested_term,
			monthly_income, existing_debt, collateral_value, credit_score, employment_status,
			employment_duration, bank_statement_score, bvn_verified, nin_verified, status, interest_rate_percent,
			loan_started_at
		FROM loan_applications
		WHERE loan_application_id = $1 AND tenant_id = $2
	`

	err := db.QueryRow(query, id, tenantID).Scan(
		&app.ID, &app.TenantID, &app.ApplicantID, &app.LoanApplicationID, &app.LoanAmount, &app.LoanPurpose,
		&app.RequestedTerm, &app.MonthlyIncome, &app.ExistingDebt, &app.CollateralValue,
		&app.CreditScore, &app.EmploymentStatus, &app.EmploymentDuration,
		&app.BankStatementScore, &app.BVNVerified, &app.NINVerified, &app.Status, &app.LoanInterestRatePercent,
		&app.LoanStartedAt,
	)

	if err != nil {
		SendErrorGin(c, "not_found", "Loan Application not found", 404)
		return
	}

	var totalPaid float64
	err = db.QueryRow(`
		SELECT COALESCE(SUM(amount), 0) 
		FROM loan_payments 
		WHERE loan_application_id = $1 AND tenant_id = $2
	`, app.LoanApplicationID, tenantID).Scan(&totalPaid)

	if err != nil {
		log.Println("Failed to fetch total payments:", err)
		SendErrorGin(c, "internal_error", "Failed to fetch payment total", 500)
		return
	}

	log.Printf("Total Amount Paid: %f", totalPaid)

	app.ExistingDebt = app.ExistingDebt + app.LoanAmount + (app.LoanAmount * app.LoanInterestRatePercent / 100) - totalPaid

	// Fetch all payments
	paymentsQuery := `
		SELECT id, loan_payment_id, loan_application_id, tenant_id, transaction_id, amount, payment_date, payment_method
		FROM loan_payments
		WHERE loan_application_id = $1 AND tenant_id = $2
		ORDER BY payment_date DESC
	`

	rows, err := db.Query(paymentsQuery, app.LoanApplicationID, tenantID)
	if err != nil {
		SendErrorGin(c, "internal_error", "Failed to fetch payments", 500)
		return
	}
	defer rows.Close()

	var payments []LoanPayment
	for rows.Next() {
		var p LoanPayment
		if err := rows.Scan(&p.ID, &p.LoanPaymentID, &p.LoanApplicationID, &p.TenantID, &p.TransactionID, &p.Amount, &p.PaymentDate, &p.PaymentMethod); err != nil {
			log.Println("Error scanning payment:", err)
			continue
		}
		payments = append(payments, p)
	}

	app.Payments = payments

	c.JSON(200, app)
}

func evaluateLoanApplication(c *gin.Context) {
	id := c.Param("id")
	tenantID := c.GetHeader("X-Tenant-ID")

	var app LoanApplication
	query := `
		SELECT id, tenant_id, applicant_id, loan_application_id, loan_amount, loan_purpose, requested_term,
			monthly_income, existing_debt, collateral_value, credit_score, employment_status,
			employment_duration, bank_statement_score, bvn_verified, nin_verified
		FROM loan_applications
		WHERE loan_application_id = $1 AND tenant_id = $2
	`

	err := db.QueryRow(query, id, tenantID).Scan(
		&app.ID, &app.TenantID, &app.ApplicantID, &app.LoanApplicationID, &app.LoanAmount, &app.LoanPurpose,
		&app.RequestedTerm, &app.MonthlyIncome, &app.ExistingDebt, &app.CollateralValue,
		&app.CreditScore, &app.EmploymentStatus, &app.EmploymentDuration,
		&app.BankStatementScore, &app.BVNVerified, &app.NINVerified,
	)

	if err != nil {
		SendErrorGin(c, "not_found", "Application not found", 404)
		return
	}

	decision := engine.EvaluateLoanApplication(&app)

	c.JSON(200, decision)
}

func approveLoanApplication(c *gin.Context) {
	id := c.Param("id")
	tenantID := c.GetHeader("X-Tenant-ID")

	query := `UPDATE loan_applications SET status = 'approved' WHERE loan_application_id = $1 AND tenant_id = $2`
	_, err := db.Exec(query, id, tenantID)

	if err != nil {
		SendErrorGin(c, "internal_error", "Failed to approve application", 500)
		return
	}

	c.JSON(200, gin.H{"status": "approved"})
}

func declineLoanApplication(c *gin.Context) {
	id := c.Param("id")
	tenantID := c.GetHeader("X-Tenant-ID")

	query := `UPDATE loan_applications SET status = 'declined' WHERE loan_application_id = $1 AND tenant_id = $2`
	_, err := db.Exec(query, id, tenantID)

	if err != nil {
		SendErrorGin(c, "internal_error", "Failed to decline application", 500)
		return
	}

	c.JSON(200, gin.H{"status": "declined"})
}

func disburseLoan(c *gin.Context) {
	id := c.Param("id")
	tenantID := c.GetHeader("X-Tenant-ID")
	keycloakID := c.GetHeader("X-Keycloak-ID")
	ledgerID := c.GetHeader("X-Ledger-ID")
	mintAccountID := c.GetHeader("X-Mint-Account-ID")

	var app LoanApplication
	query := `
		SELECT id, tenant_id, applicant_id, loan_application_id, loan_amount, loan_purpose, requested_term,
			monthly_income, existing_debt, collateral_value, credit_score, employment_status,
			employment_duration, bank_statement_score, bvn_verified, nin_verified, status
		FROM loan_applications
		WHERE loan_application_id = $1 AND tenant_id = $2
	`

	err := db.QueryRow(query, id, tenantID).Scan(
		&app.ID, &app.TenantID, &app.ApplicantID, &app.LoanApplicationID, &app.LoanAmount, &app.LoanPurpose,
		&app.RequestedTerm, &app.MonthlyIncome, &app.ExistingDebt, &app.CollateralValue,
		&app.CreditScore, &app.EmploymentStatus, &app.EmploymentDuration,
		&app.BankStatementScore, &app.BVNVerified, &app.NINVerified, &app.Status,
	)

	if app.Status == "disbursed" {
		SendErrorGin(c, "already_exists", "Loan already disbursed", 400)
		return
	}

	if app.Status != "approved" {
		SendErrorGin(c, "bad_request", "Loan must be approved first", 400)
		return
	}

	if err != nil {
		SendErrorGin(c, "not_found", "Invalid Loan Application", 404)
		return
	}

	var AmountString = strconv.FormatFloat(app.LoanAmount, 'f', 2, 64)

	// Deposit loan value into user account
	_, err = Payment(&PaymentStruct{
		Recipient:     app.ApplicantID,
		Amount:        AmountString,
		Note:          "LOAN_DISBURSEMENT/" + AmountString,
		TenantID:      tenantID,
		KeycloakID:    keycloakID,
		LedgerID:      ledgerID,
		MintAccountID: mintAccountID,
	})

	if err != nil {
		SendErrorGin(c, "internal_error", "Payment processing failed", 500)
		return
	}

	updateQuery := `
		UPDATE loan_applications
		SET status = 'disbursed', loan_started_at = $1
		WHERE loan_application_id = $2 AND tenant_id = $3
	`
	_, err = db.Exec(updateQuery, time.Now(), id, tenantID)

	if err != nil {
		SendErrorGin(c, "internal_error", "Failed to disburse loan", 500)
		return
	}

	// Record double-entry journal in Chart of Accounts.
	// Debit: Loan Receivable (1100), Credit: Customer Deposits (2000).
	// This MUST succeed; if it fails we roll back the DB status and refund via payment service.
	amountInKobo := int64(math.Round(app.LoanAmount * 100))
	_, coaErr := coaClient.RecordLoanDisbursement(
		tenantID,
		keycloakID,
		"finance_admin",
		id,
		amountInKobo,
		"2000",
	)
	if coaErr != nil {
		log.Printf("ERROR: CoA journal failed for loan disbursement %s: %v — rolling back DB status and issuing refund", id, coaErr)

		// Revert DB status back to 'approved' so a retry is possible.
		rollbackQuery := `UPDATE loan_applications SET status = 'approved', loan_started_at = NULL WHERE loan_application_id = $1 AND tenant_id = $2`
		if _, rbErr := db.Exec(rollbackQuery, id, tenantID); rbErr != nil {
			log.Printf("CRITICAL: Failed to rollback loan status after CoA failure %s: %v", id, rbErr)
		}

		// Compensating payment: reclaim the disbursed funds.
		var AmountStringRefund = strconv.FormatFloat(app.LoanAmount, 'f', 2, 64)
		if _, refundErr := Payment(&PaymentStruct{
			Recipient:     app.ApplicantID,
			Amount:        AmountStringRefund,
			Note:          "LOAN_DISBURSEMENT_REVERSAL/" + AmountStringRefund,
			TenantID:      tenantID,
			KeycloakID:    keycloakID,
			LedgerID:      ledgerID,
			MintAccountID: mintAccountID,
		}); refundErr != nil {
			log.Printf("CRITICAL: Compensating refund ALSO FAILED for loan %s: %v — MANUAL INTERVENTION REQUIRED", id, refundErr)
		}

		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to record accounting entry. Disbursement reversed."})
		return
	}

	log.Printf("INFO: Loan %s disbursed and CoA journal recorded. amount_kobo=%d tenant=%s", id, amountInKobo, tenantID)
	c.JSON(200, gin.H{"status": "disbursed"})
}

func getRepaymentSchedule(c *gin.Context) {
	id := c.Param("id")
	tenantID := c.GetHeader("X-Tenant-ID")

	var app LoanApplication
	query := `
		SELECT id, tenant_id, applicant_id, loan_application_id, loan_amount, loan_purpose, requested_term,
			monthly_income, existing_debt, collateral_value, credit_score, employment_status,
			employment_duration, bank_statement_score, bvn_verified, nin_verified, status, interest_rate_percent,
			loan_started_at
		FROM loan_applications
		WHERE loan_application_id = $1 AND tenant_id = $2
	`

	err := db.QueryRow(query, id, tenantID).Scan(
		&app.ID, &app.TenantID, &app.ApplicantID, &app.LoanApplicationID, &app.LoanAmount, &app.LoanPurpose,
		&app.RequestedTerm, &app.MonthlyIncome, &app.ExistingDebt, &app.CollateralValue,
		&app.CreditScore, &app.EmploymentStatus, &app.EmploymentDuration,
		&app.BankStatementScore, &app.BVNVerified, &app.NINVerified, &app.Status, &app.LoanInterestRatePercent,
		&app.LoanStartedAt,
	)

	if err != nil {
		SendErrorGin(c, "not_found", "Loan Application not found", 404)
		return
	}

	schedule := GenerateRepaymentSchedule(app.LoanAmount, app.LoanInterestRatePercent, app.RequestedTerm, *app.LoanStartedAt)

	c.JSON(200, schedule)
}

func recordPayment(c *gin.Context) {
	id := c.Param("id")
	tenantID := c.GetHeader("X-Tenant-ID")

	var payment LoanPayment
	if err := c.ShouldBindJSON(&payment); err != nil {
		SendErrorGin(c, "validation_failed", err.Error(), 400)
		return
	}

	var app LoanApplication
	query := `
		SELECT id, tenant_id, applicant_id, loan_application_id, loan_amount, loan_purpose, requested_term,
			monthly_income, existing_debt, collateral_value, credit_score, employment_status,
			employment_duration, bank_statement_score, bvn_verified, nin_verified, status, interest_rate_percent,
			loan_started_at
		FROM loan_applications
		WHERE loan_application_id = $1 AND tenant_id = $2
	`

	err := db.QueryRow(query, id, tenantID).Scan(
		&app.ID, &app.TenantID, &app.ApplicantID, &app.LoanApplicationID, &app.LoanAmount, &app.LoanPurpose,
		&app.RequestedTerm, &app.MonthlyIncome, &app.ExistingDebt, &app.CollateralValue,
		&app.CreditScore, &app.EmploymentStatus, &app.EmploymentDuration,
		&app.BankStatementScore, &app.BVNVerified, &app.NINVerified, &app.Status, &app.LoanInterestRatePercent,
		&app.LoanStartedAt,
	)

	if err != nil {
		SendErrorGin(c, "not_found", "Loan Application not found", 404)
		return
	}

	if app.Status == "completed" {
		SendErrorGin(c, "bad_request", "Loan payment already completed", 400)
		return
	}

	var totalPaid float64
	err = db.QueryRow(`
		SELECT COALESCE(SUM(amount), 0) 
		FROM loan_payments 
		WHERE loan_application_id = $1 AND tenant_id = $2
	`, app.LoanApplicationID, tenantID).Scan(&totalPaid)

	if err != nil {
		log.Println("Failed to fetch total payments:", err)
		SendErrorGin(c, "internal_error", "Failed to fetch payment total", 500)
		return
	}

	log.Printf("Total Amount Paid: %f", totalPaid)

	var recordedPaymentAmount = payment.Amount

	var totalRequiredPaymentAmount = app.LoanAmount + (app.LoanAmount * app.LoanInterestRatePercent / 100)

	var totalUnpaid = totalRequiredPaymentAmount - totalPaid

	// Ensure no over-payment.
	if recordedPaymentAmount > totalUnpaid {
		recordedPaymentAmount = totalUnpaid
	}

	loanPaymentQuery := `
		INSERT INTO loan_payments 
			(loan_payment_id, loan_application_id, tenant_id, transaction_id, amount, payment_date, payment_method)
		VALUES 
			($1, $2, $3, $4, $5, $6, $7)
		RETURNING id
	`

	err = db.QueryRow(
		loanPaymentQuery,
		generateID("LOAN_PAYMENT"),
		app.LoanApplicationID,
		tenantID,
		payment.TransactionID,
		recordedPaymentAmount,
		payment.PaymentDate,
		payment.PaymentMethod,
	).Scan(&payment.ID)

	if err != nil {
		log.Println("Insert error:", err)
		SendErrorGin(c, "internal_error", "Failed to record payment", 500)
		return
	}

	// Record journal entry for loan repayment
	keycloakID := c.GetHeader("X-Keycloak-ID")
	totalInterest := app.LoanAmount * app.LoanInterestRatePercent / 100
	// remainingPrincipal := app.LoanAmount - totalPaid

	// Calculate interest and principal portions of this payment
	var principalPortion, interestPortion float64
	if totalPaid < totalInterest {
		// Still paying off interest first
		if recordedPaymentAmount <= (totalInterest - totalPaid) {
			interestPortion = recordedPaymentAmount
			principalPortion = 0
		} else {
			interestPortion = totalInterest - totalPaid
			principalPortion = recordedPaymentAmount - interestPortion
		}
	} else {
		// Interest fully paid, all goes to principal
		principalPortion = recordedPaymentAmount
		interestPortion = 0
	}

	// Convert to kobo (smallest currency unit)
	principalKobo := int64(principalPortion * 100)
	interestKobo := int64(interestPortion * 100)

	_, err = coaClient.RecordLoanRepayment(
		tenantID,
		keycloakID,
		"finance_admin",
		app.LoanApplicationID,
		principalKobo,
		interestKobo,
		"2000", // Customer deposits account
	)
	if err != nil {
		log.Printf("ERROR: Failed to record journal entry for loan repayment %s: %v", app.LoanApplicationID, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to record accounting entry. Repayment not processed."})
		return
	}

	if totalPaid+recordedPaymentAmount >= totalRequiredPaymentAmount {
		_, err := db.Exec(`
			UPDATE loan_applications
			SET status = 'completed'
			WHERE loan_application_id = $1 AND tenant_id = $2
		`, app.LoanApplicationID, app.TenantID)
		if err != nil {
			log.Println("Failed to update loan status:", err)
		}
	}

	c.JSON(200, gin.H{"status": "success", "amount": recordedPaymentAmount})
}
