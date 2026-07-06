package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"strings"
	"time"

	"github.com/lib/pq"
)

type PostgresStore struct {
	db *sql.DB
}

func NewPostgresStore(ctx context.Context) (*PostgresStore, error) {
	connStr := os.Getenv("POSTGRES_URL")
	if connStr == "" {
		host := os.Getenv("POSTGRES_HOST")
		if host == "" {
			host = "postgres"
		}
		port := os.Getenv("POSTGRES_PORT")
		if port == "" {
			port = "5432"
		}
		user := os.Getenv("POSTGRES_USER")
		if user == "" {
			user = "coa_user"
		}
		password := os.Getenv("POSTGRES_PASSWORD")
		if password == "" {
			password = "coa_password"
		}
		dbname := os.Getenv("POSTGRES_DB")
		if dbname == "" {
			dbname = "coa_db"
		}
		connStr = fmt.Sprintf("host=%s port=%s user=%s password=%s dbname=%s sslmode=disable",
			host, port, user, password, dbname)
	}

	db, err := sql.Open("postgres", connStr)
	if err != nil {
		return nil, fmt.Errorf("failed to open database: %w", err)
	}

	db.SetMaxOpenConns(25)
	db.SetMaxIdleConns(5)
	db.SetConnMaxLifetime(5 * time.Minute)

	if err := db.PingContext(ctx); err != nil {
		return nil, fmt.Errorf("failed to ping database: %w", err)
	}

	store := &PostgresStore{db: db}

	if err := store.migrate(ctx); err != nil {
		return nil, fmt.Errorf("failed to run migrations: %w", err)
	}

	log.Printf("Connected to PostgreSQL database")
	return store, nil
}

func (s *PostgresStore) migrate(ctx context.Context) error {
	migrations := []string{
		// tenant_id stored as string without FK constraint (like other services)
		// Tenant data is managed by tenant-management service

		`CREATE TABLE IF NOT EXISTS coa_accounts (
			id VARCHAR(255) PRIMARY KEY,
			tenant_id VARCHAR(255) NOT NULL,
			code VARCHAR(50) NOT NULL,
			name VARCHAR(255) NOT NULL,
			description TEXT,
			type VARCHAR(50) NOT NULL,
			normal_balance VARCHAR(10) NOT NULL,
			parent_id VARCHAR(255),
			level INTEGER NOT NULL DEFAULT 0,
			is_active BOOLEAN NOT NULL DEFAULT true,
			is_system_account BOOLEAN NOT NULL DEFAULT false,
			currency VARCHAR(10) NOT NULL DEFAULT 'NGN',
			tigerbeetle_id VARCHAR(255),
			tigerbeetle_ledger INTEGER,
			tigerbeetle_code INTEGER,
			cbn_code VARCHAR(50),
			tags TEXT[],
			metadata JSONB DEFAULT '{}',
			created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
			updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
			UNIQUE(tenant_id, code)
		)`,

		`CREATE INDEX IF NOT EXISTS idx_coa_accounts_tenant_id ON coa_accounts(tenant_id)`,
		`CREATE INDEX IF NOT EXISTS idx_coa_accounts_type ON coa_accounts(type)`,
		`CREATE INDEX IF NOT EXISTS idx_coa_accounts_parent_id ON coa_accounts(parent_id)`,
		`CREATE INDEX IF NOT EXISTS idx_coa_accounts_code ON coa_accounts(code)`,
		`CREATE INDEX IF NOT EXISTS idx_coa_accounts_cbn_code ON coa_accounts(cbn_code)`,

		`CREATE TABLE IF NOT EXISTS journal_entries (
			id VARCHAR(255) PRIMARY KEY,
			tenant_id VARCHAR(255) NOT NULL,
			entry_number VARCHAR(50) NOT NULL,
			entry_date DATE NOT NULL,
			description TEXT,
			reference VARCHAR(255),
			status VARCHAR(50) NOT NULL DEFAULT 'draft',
			total_debit BIGINT NOT NULL DEFAULT 0,
			total_credit BIGINT NOT NULL DEFAULT 0,
			currency VARCHAR(10) NOT NULL DEFAULT 'NGN',
			posted_at TIMESTAMP WITH TIME ZONE,
			posted_by VARCHAR(255),
			reversed_at TIMESTAMP WITH TIME ZONE,
			reversed_by VARCHAR(255),
			reversal_reason TEXT,
			original_entry_id VARCHAR(255),
			tigerbeetle_transfer_id VARCHAR(255),
			metadata JSONB DEFAULT '{}',
			created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
			updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
			UNIQUE(tenant_id, entry_number)
		)`,

		`CREATE INDEX IF NOT EXISTS idx_journal_entries_tenant_id ON journal_entries(tenant_id)`,
		`CREATE INDEX IF NOT EXISTS idx_journal_entries_status ON journal_entries(status)`,
		`CREATE INDEX IF NOT EXISTS idx_journal_entries_entry_date ON journal_entries(entry_date)`,

		`CREATE TABLE IF NOT EXISTS journal_entry_lines (
			id VARCHAR(255) PRIMARY KEY,
			journal_entry_id VARCHAR(255) NOT NULL REFERENCES journal_entries(id) ON DELETE CASCADE,
			account_id VARCHAR(255) NOT NULL REFERENCES coa_accounts(id),
			description TEXT,
			debit_amount BIGINT NOT NULL DEFAULT 0,
			credit_amount BIGINT NOT NULL DEFAULT 0,
			line_number INTEGER NOT NULL,
			created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
		)`,

		`CREATE INDEX IF NOT EXISTS idx_journal_entry_lines_entry_id ON journal_entry_lines(journal_entry_id)`,
		`CREATE INDEX IF NOT EXISTS idx_journal_entry_lines_account_id ON journal_entry_lines(account_id)`,

		`CREATE TABLE IF NOT EXISTS accounting_periods (
			id VARCHAR(255) PRIMARY KEY,
			tenant_id VARCHAR(255) NOT NULL,
			name VARCHAR(100) NOT NULL,
			period_type VARCHAR(50) NOT NULL,
			start_date DATE NOT NULL,
			end_date DATE NOT NULL,
			status VARCHAR(50) NOT NULL DEFAULT 'open',
			closed_at TIMESTAMP WITH TIME ZONE,
			closed_by VARCHAR(255),
			fiscal_year INTEGER NOT NULL,
			period_number INTEGER NOT NULL,
			is_adjustment_period BOOLEAN NOT NULL DEFAULT false,
			created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
			updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
			UNIQUE(tenant_id, fiscal_year, period_number)
		)`,

		`CREATE INDEX IF NOT EXISTS idx_accounting_periods_tenant_id ON accounting_periods(tenant_id)`,
		`CREATE INDEX IF NOT EXISTS idx_accounting_periods_status ON accounting_periods(status)`,
		`CREATE INDEX IF NOT EXISTS idx_accounting_periods_dates ON accounting_periods(start_date, end_date)`,

		`CREATE TABLE IF NOT EXISTS approval_workflows (
			id VARCHAR(255) PRIMARY KEY,
			tenant_id VARCHAR(255) NOT NULL,
			name VARCHAR(255) NOT NULL,
			entity_type VARCHAR(50) NOT NULL,
			min_amount BIGINT,
			max_amount BIGINT,
			is_active BOOLEAN NOT NULL DEFAULT true,
			created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
			updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
		)`,

		`CREATE TABLE IF NOT EXISTS approval_workflow_steps (
			id VARCHAR(255) PRIMARY KEY,
			workflow_id VARCHAR(255) NOT NULL REFERENCES approval_workflows(id) ON DELETE CASCADE,
			step_order INTEGER NOT NULL,
			approver_role VARCHAR(100) NOT NULL,
			approver_user_id VARCHAR(255),
			is_mandatory BOOLEAN NOT NULL DEFAULT true,
			created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
		)`,

		`CREATE TABLE IF NOT EXISTS approval_requests (
			id VARCHAR(255) PRIMARY KEY,
			tenant_id VARCHAR(255) NOT NULL,
			workflow_id VARCHAR(255) NOT NULL REFERENCES approval_workflows(id),
			entity_type VARCHAR(50) NOT NULL,
			entity_id VARCHAR(255) NOT NULL,
			current_step INTEGER NOT NULL DEFAULT 1,
			status VARCHAR(50) NOT NULL DEFAULT 'pending',
			requested_by VARCHAR(255) NOT NULL,
			requested_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
			completed_at TIMESTAMP WITH TIME ZONE,
			metadata JSONB DEFAULT '{}'
		)`,

		`CREATE TABLE IF NOT EXISTS approval_actions (
			id VARCHAR(255) PRIMARY KEY,
			request_id VARCHAR(255) NOT NULL REFERENCES approval_requests(id) ON DELETE CASCADE,
			step_number INTEGER NOT NULL,
			action VARCHAR(50) NOT NULL,
			action_by VARCHAR(255) NOT NULL,
			action_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
			comments TEXT
		)`,

		`CREATE INDEX IF NOT EXISTS idx_approval_requests_tenant_id ON approval_requests(tenant_id)`,
		`CREATE INDEX IF NOT EXISTS idx_approval_requests_status ON approval_requests(status)`,
		`CREATE INDEX IF NOT EXISTS idx_approval_requests_entity ON approval_requests(entity_type, entity_id)`,

		`CREATE TABLE IF NOT EXISTS account_templates (
			id VARCHAR(255) PRIMARY KEY,
			name VARCHAR(255) NOT NULL,
			description TEXT,
			bank_type VARCHAR(50) NOT NULL,
			is_default BOOLEAN NOT NULL DEFAULT false,
			accounts JSONB NOT NULL,
			created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
			updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
			UNIQUE(name, bank_type)
		)`,

		`CREATE TABLE IF NOT EXISTS import_jobs (
			id VARCHAR(255) PRIMARY KEY,
			tenant_id VARCHAR(255) NOT NULL,
			job_type VARCHAR(50) NOT NULL,
			status VARCHAR(50) NOT NULL DEFAULT 'pending',
			file_name VARCHAR(255),
			total_rows INTEGER,
			processed_rows INTEGER DEFAULT 0,
			success_rows INTEGER DEFAULT 0,
			error_rows INTEGER DEFAULT 0,
			errors JSONB DEFAULT '[]',
			started_at TIMESTAMP WITH TIME ZONE,
			completed_at TIMESTAMP WITH TIME ZONE,
			created_by VARCHAR(255) NOT NULL,
			created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
		)`,

		`CREATE INDEX IF NOT EXISTS idx_import_jobs_tenant_id ON import_jobs(tenant_id)`,
		`CREATE INDEX IF NOT EXISTS idx_import_jobs_status ON import_jobs(status)`,

		`CREATE TABLE IF NOT EXISTS audit_log (
			id VARCHAR(255) PRIMARY KEY,
			tenant_id VARCHAR(255) NOT NULL,
			entity_type VARCHAR(50) NOT NULL,
			entity_id VARCHAR(255) NOT NULL,
			action VARCHAR(50) NOT NULL,
			old_values JSONB,
			new_values JSONB,
			user_id VARCHAR(255) NOT NULL,
			user_role VARCHAR(50),
			ip_address VARCHAR(50),
			user_agent TEXT,
			created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
		)`,

		`CREATE INDEX IF NOT EXISTS idx_audit_log_tenant_id ON audit_log(tenant_id)`,
		`CREATE INDEX IF NOT EXISTS idx_audit_log_entity ON audit_log(entity_type, entity_id)`,
		`CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON audit_log(created_at)`,

		// Per-tenant mapping of transaction type keys to COA account UUIDs.
		// Services (loan, payment, etc.) call GET /api/v1/mappings?key=loans.interest.sme
		// to resolve which account to debit/credit without hardcoding codes.
		`CREATE TABLE IF NOT EXISTS tenant_coa_mappings (
			id VARCHAR(255) PRIMARY KEY,
			tenant_id VARCHAR(255) NOT NULL,
			mapping_key VARCHAR(255) NOT NULL,
			account_id VARCHAR(255) NOT NULL REFERENCES coa_accounts(id),
			description TEXT,
			created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
			updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
			UNIQUE(tenant_id, mapping_key)
		)`,

		`CREATE INDEX IF NOT EXISTS idx_tenant_coa_mappings_tenant_id ON tenant_coa_mappings(tenant_id)`,
		`CREATE INDEX IF NOT EXISTS idx_tenant_coa_mappings_key ON tenant_coa_mappings(tenant_id, mapping_key)`,
	}

	for _, migration := range migrations {
		if _, err := s.db.ExecContext(ctx, migration); err != nil {
			return fmt.Errorf("migration failed: %w", err)
		}
	}

	return nil
}

func (s *PostgresStore) Close() error {
	return s.db.Close()
}

func (s *PostgresStore) UpsertCOAMapping(ctx context.Context, m TenantCOAMapping) error {
	query := `
		INSERT INTO tenant_coa_mappings (id, tenant_id, mapping_key, account_id, description, created_at, updated_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7)
		ON CONFLICT (tenant_id, mapping_key) DO UPDATE SET
			account_id  = EXCLUDED.account_id,
			description = EXCLUDED.description,
			updated_at  = CURRENT_TIMESTAMP
	`
	_, err := s.db.ExecContext(ctx, query, m.ID, m.TenantID, m.MappingKey, m.AccountID, m.Description, m.CreatedAt, m.UpdatedAt)
	return err
}

func (s *PostgresStore) GetCOAMapping(ctx context.Context, tenantID, mappingKey string) (*TenantCOAMapping, error) {
	query := `
		SELECT m.id, m.tenant_id, m.mapping_key, m.account_id, m.description, m.created_at, m.updated_at,
		       a.code, a.name
		FROM tenant_coa_mappings m
		JOIN coa_accounts a ON a.id = m.account_id
		WHERE m.tenant_id = $1 AND m.mapping_key = $2
	`
	var m TenantCOAMapping
	err := s.db.QueryRowContext(ctx, query, tenantID, mappingKey).Scan(
		&m.ID, &m.TenantID, &m.MappingKey, &m.AccountID, &m.Description, &m.CreatedAt, &m.UpdatedAt,
		&m.AccountCode, &m.AccountName,
	)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	return &m, err
}

func (s *PostgresStore) ListCOAMappings(ctx context.Context, tenantID string) ([]TenantCOAMapping, error) {
	query := `
		SELECT m.id, m.tenant_id, m.mapping_key, m.account_id, m.description, m.created_at, m.updated_at,
		       a.code, a.name
		FROM tenant_coa_mappings m
		JOIN coa_accounts a ON a.id = m.account_id
		WHERE m.tenant_id = $1
		ORDER BY m.mapping_key
	`
	rows, err := s.db.QueryContext(ctx, query, tenantID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var mappings []TenantCOAMapping
	for rows.Next() {
		var m TenantCOAMapping
		if err := rows.Scan(
			&m.ID, &m.TenantID, &m.MappingKey, &m.AccountID, &m.Description, &m.CreatedAt, &m.UpdatedAt,
			&m.AccountCode, &m.AccountName,
		); err != nil {
			return nil, err
		}
		mappings = append(mappings, m)
	}
	return mappings, rows.Err()
}

func (s *PostgresStore) DeleteCOAMapping(ctx context.Context, tenantID, mappingKey string) error {
	_, err := s.db.ExecContext(ctx, `DELETE FROM tenant_coa_mappings WHERE tenant_id = $1 AND mapping_key = $2`, tenantID, mappingKey)
	return err
}

func (s *PostgresStore) CreateTenant(ctx context.Context, tenant Tenant) error {
	query := `
		INSERT INTO tenants (id, name, type, is_active, created_at)
		VALUES ($1, $2, $3, $4, $5)
		ON CONFLICT (id) DO UPDATE SET
			name = EXCLUDED.name,
			type = EXCLUDED.type,
			updated_at = CURRENT_TIMESTAMP
	`
	_, err := s.db.ExecContext(ctx, query, tenant.ID, tenant.Name, tenant.Type, tenant.IsActive, tenant.CreatedAt)
	return err
}

func (s *PostgresStore) GetTenant(ctx context.Context, tenantID string) (*Tenant, error) {
	query := `SELECT id, name, type, is_active, created_at FROM tenants WHERE id = $1`
	var tenant Tenant
	err := s.db.QueryRowContext(ctx, query, tenantID).Scan(
		&tenant.ID, &tenant.Name, &tenant.Type, &tenant.IsActive, &tenant.CreatedAt,
	)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	return &tenant, nil
}

func (s *PostgresStore) ListTenants(ctx context.Context) ([]Tenant, error) {
	query := `SELECT id, name, type, is_active, created_at FROM tenants ORDER BY name`
	rows, err := s.db.QueryContext(ctx, query)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var tenants []Tenant
	for rows.Next() {
		var tenant Tenant
		if err := rows.Scan(&tenant.ID, &tenant.Name, &tenant.Type, &tenant.IsActive, &tenant.CreatedAt); err != nil {
			return nil, err
		}
		tenants = append(tenants, tenant)
	}
	return tenants, rows.Err()
}

func (s *PostgresStore) SaveAccount(ctx context.Context, account Account) error {
	metadataJSON, _ := json.Marshal(account.Metadata)

	query := `
		INSERT INTO coa_accounts (
			id, tenant_id, code, name, description, type, normal_balance,
			parent_id, level, is_active, is_system_account, currency,
			tigerbeetle_id, tigerbeetle_ledger, tigerbeetle_code, cbn_code,
			tags, metadata, created_at, updated_at
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20)
		ON CONFLICT (tenant_id, code) DO UPDATE SET
			name = EXCLUDED.name,
			description = EXCLUDED.description,
			is_active = EXCLUDED.is_active,
			cbn_code = EXCLUDED.cbn_code,
			tags = EXCLUDED.tags,
			metadata = EXCLUDED.metadata,
			tigerbeetle_id = EXCLUDED.tigerbeetle_id,
			tigerbeetle_ledger = EXCLUDED.tigerbeetle_ledger,
			tigerbeetle_code = EXCLUDED.tigerbeetle_code,
			updated_at = CURRENT_TIMESTAMP
	`

	parentID := sql.NullString{String: account.ParentID, Valid: account.ParentID != ""}

	_, err := s.db.ExecContext(ctx, query,
		account.ID, account.TenantID, account.Code, account.Name, account.Description,
		string(account.Type), string(account.NormalBalance), parentID, account.Level,
		account.IsActive, account.IsSystemAccount, account.Currency,
		account.TigerBeetleID, account.TigerBeetleLedger, account.TigerBeetleCode, account.CBNCode,
		pq.Array(account.Tags), metadataJSON, account.CreatedAt, account.UpdatedAt,
	)
	return err
}

func (s *PostgresStore) BulkSaveAccounts(ctx context.Context, accounts []Account) error {
	if len(accounts) == 0 {
		return nil
	}

	// Start transaction
	tx, err := s.db.BeginTx(ctx, nil)
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer tx.Rollback()

	// Prepare bulk insert statement
	query := `
		INSERT INTO coa_accounts (
			id, tenant_id, code, name, description, type, normal_balance,
			parent_id, level, is_active, is_system_account, currency,
			tigerbeetle_id, tigerbeetle_ledger, tigerbeetle_code, cbn_code,
			tags, metadata, created_at, updated_at
		) VALUES `

	// Build value placeholders and args
	values := make([]string, 0, len(accounts))
	args := make([]interface{}, 0, len(accounts)*20)

	for i, account := range accounts {
		metadataJSON, _ := json.Marshal(account.Metadata)
		parentID := sql.NullString{String: account.ParentID, Valid: account.ParentID != ""}

		// Add placeholder for this row
		offset := i * 20
		placeholder := fmt.Sprintf("($%d, $%d, $%d, $%d, $%d, $%d, $%d, $%d, $%d, $%d, $%d, $%d, $%d, $%d, $%d, $%d, $%d, $%d, $%d, $%d)",
			offset+1, offset+2, offset+3, offset+4, offset+5, offset+6, offset+7, offset+8, offset+9, offset+10,
			offset+11, offset+12, offset+13, offset+14, offset+15, offset+16, offset+17, offset+18, offset+19, offset+20)
		values = append(values, placeholder)

		// Add args
		args = append(args,
			account.ID, account.TenantID, account.Code, account.Name, account.Description,
			string(account.Type), string(account.NormalBalance), parentID, account.Level,
			account.IsActive, account.IsSystemAccount, account.Currency,
			account.TigerBeetleID, account.TigerBeetleLedger, account.TigerBeetleCode, account.CBNCode,
			pq.Array(account.Tags), metadataJSON, account.CreatedAt, account.UpdatedAt,
		)
	}

	query += strings.Join(values, ",")
	query += `
		ON CONFLICT (tenant_id, code) DO UPDATE SET
			name = EXCLUDED.name,
			description = EXCLUDED.description,
			is_active = EXCLUDED.is_active,
			cbn_code = EXCLUDED.cbn_code,
			tags = EXCLUDED.tags,
			metadata = EXCLUDED.metadata,
			tigerbeetle_id = EXCLUDED.tigerbeetle_id,
			tigerbeetle_ledger = EXCLUDED.tigerbeetle_ledger,
			tigerbeetle_code = EXCLUDED.tigerbeetle_code,
			updated_at = CURRENT_TIMESTAMP
	`

	// Execute bulk insert
	if _, err := tx.ExecContext(ctx, query, args...); err != nil {
		return fmt.Errorf("failed to bulk insert accounts: %w", err)
	}

	// Commit transaction
	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit transaction: %w", err)
	}

	return nil
}

func (s *PostgresStore) GetAccount(ctx context.Context, tenantID, accountID string) (*Account, error) {
	query := `
		SELECT id, tenant_id, code, name, description, type, normal_balance,
			parent_id, level, is_active, is_system_account, currency,
			tigerbeetle_id, tigerbeetle_ledger, tigerbeetle_code, cbn_code,
			tags, metadata, created_at, updated_at
		FROM coa_accounts WHERE tenant_id = $1 AND id = $2
	`

	var account Account
	var parentID, descriptionNull, tigerBeetleIDNull, cbnCodeNull sql.NullString
	var tigerBeetleLedgerNull, tigerBeetleCodeNull sql.NullInt64
	var metadataJSON []byte

	err := s.db.QueryRowContext(ctx, query, tenantID, accountID).Scan(
		&account.ID, &account.TenantID, &account.Code, &account.Name, &descriptionNull,
		&account.Type, &account.NormalBalance, &parentID, &account.Level,
		&account.IsActive, &account.IsSystemAccount, &account.Currency,
		&tigerBeetleIDNull, &tigerBeetleLedgerNull, &tigerBeetleCodeNull, &cbnCodeNull,
		pq.Array(&account.Tags), &metadataJSON, &account.CreatedAt, &account.UpdatedAt,
	)

	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}

	if parentID.Valid {
		account.ParentID = parentID.String
	}
	if descriptionNull.Valid {
		account.Description = descriptionNull.String
	}
	if tigerBeetleIDNull.Valid {
		account.TigerBeetleID = tigerBeetleIDNull.String
	}
	if tigerBeetleLedgerNull.Valid {
		account.TigerBeetleLedger = uint32(tigerBeetleLedgerNull.Int64)
	}
	if tigerBeetleCodeNull.Valid {
		account.TigerBeetleCode = uint16(tigerBeetleCodeNull.Int64)
	}
	if cbnCodeNull.Valid {
		account.CBNCode = cbnCodeNull.String
	}
	json.Unmarshal(metadataJSON, &account.Metadata)

	return &account, nil
}

func (s *PostgresStore) GetAccountByCode(ctx context.Context, tenantID, code string) (*Account, error) {
	log.Printf("Fetching account for tenant_id: %s with code: %s", tenantID, code)
	query := `
		SELECT id, tenant_id, code, name, description, type, normal_balance,
			parent_id, level, is_active, is_system_account, currency,
			tigerbeetle_id, tigerbeetle_ledger, tigerbeetle_code, cbn_code,
			tags, metadata, created_at, updated_at
		FROM coa_accounts WHERE tenant_id = $1 AND code = $2
	`

	var account Account
	var parentID, descriptionNull, tigerBeetleIDNull, cbnCodeNull sql.NullString
	var tigerBeetleLedgerNull, tigerBeetleCodeNull sql.NullInt64
	var metadataJSON []byte

	err := s.db.QueryRowContext(ctx, query, tenantID, code).Scan(
		&account.ID, &account.TenantID, &account.Code, &account.Name, &descriptionNull,
		&account.Type, &account.NormalBalance, &parentID, &account.Level,
		&account.IsActive, &account.IsSystemAccount, &account.Currency,
		&tigerBeetleIDNull, &tigerBeetleLedgerNull, &tigerBeetleCodeNull, &cbnCodeNull,
		pq.Array(&account.Tags), &metadataJSON, &account.CreatedAt, &account.UpdatedAt,
	)

	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}

	if parentID.Valid {
		account.ParentID = parentID.String
	}
	if descriptionNull.Valid {
		account.Description = descriptionNull.String
	}
	if tigerBeetleIDNull.Valid {
		account.TigerBeetleID = tigerBeetleIDNull.String
	}
	if tigerBeetleLedgerNull.Valid {
		account.TigerBeetleLedger = uint32(tigerBeetleLedgerNull.Int64)
	}
	if tigerBeetleCodeNull.Valid {
		account.TigerBeetleCode = uint16(tigerBeetleCodeNull.Int64)
	}
	if cbnCodeNull.Valid {
		account.CBNCode = cbnCodeNull.String
	}
	json.Unmarshal(metadataJSON, &account.Metadata)

	return &account, nil
}

func (s *PostgresStore) ListAccounts(ctx context.Context, tenantID, accountType, parentID string, activeOnly bool) ([]Account, error) {
	query := `
		SELECT id, tenant_id, code, name, description, type, normal_balance,
			parent_id, level, is_active, is_system_account, currency,
			tigerbeetle_id, tigerbeetle_ledger, tigerbeetle_code, cbn_code,
			tags, metadata, created_at, updated_at
		FROM coa_accounts WHERE tenant_id = $1
	`
	args := []interface{}{tenantID}
	argNum := 2

	if accountType != "" {
		query += fmt.Sprintf(" AND type = $%d", argNum)
		args = append(args, accountType)
		argNum++
	}
	if parentID != "" {
		query += fmt.Sprintf(" AND parent_id = $%d", argNum)
		args = append(args, parentID)
		argNum++
	}
	if activeOnly {
		query += " AND is_active = true"
	}
	query += " ORDER BY code"

	rows, err := s.db.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var accounts []Account
	for rows.Next() {
		var account Account
		var parentIDNull, descriptionNull, tigerBeetleIDNull, cbnCodeNull sql.NullString
		var tigerBeetleLedgerNull, tigerBeetleCodeNull sql.NullInt64
		var metadataJSON []byte

		if err := rows.Scan(
			&account.ID, &account.TenantID, &account.Code, &account.Name, &descriptionNull,
			&account.Type, &account.NormalBalance, &parentIDNull, &account.Level,
			&account.IsActive, &account.IsSystemAccount, &account.Currency,
			&tigerBeetleIDNull, &tigerBeetleLedgerNull, &tigerBeetleCodeNull, &cbnCodeNull,
			pq.Array(&account.Tags), &metadataJSON, &account.CreatedAt, &account.UpdatedAt,
		); err != nil {
			return nil, err
		}

		if parentIDNull.Valid {
			account.ParentID = parentIDNull.String
		}
		if descriptionNull.Valid {
			account.Description = descriptionNull.String
		}
		if tigerBeetleIDNull.Valid {
			account.TigerBeetleID = tigerBeetleIDNull.String
		}
		if tigerBeetleLedgerNull.Valid {
			account.TigerBeetleLedger = uint32(tigerBeetleLedgerNull.Int64)
		}
		if tigerBeetleCodeNull.Valid {
			account.TigerBeetleCode = uint16(tigerBeetleCodeNull.Int64)
		}
		if cbnCodeNull.Valid {
			account.CBNCode = cbnCodeNull.String
		}
		json.Unmarshal(metadataJSON, &account.Metadata)

		accounts = append(accounts, account)
	}

	return accounts, rows.Err()
}

func (s *PostgresStore) DeleteAccount(ctx context.Context, tenantID, accountID string) error {
	query := `UPDATE coa_accounts SET is_active = false, updated_at = CURRENT_TIMESTAMP WHERE tenant_id = $1 AND id = $2`
	_, err := s.db.ExecContext(ctx, query, tenantID, accountID)
	return err
}

func (s *PostgresStore) SaveJournalEntry(ctx context.Context, entry JournalEntry) error {
	tx, err := s.db.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	defer tx.Rollback()

	metadataJSON, _ := json.Marshal(entry.Metadata)

	entryQuery := `
		INSERT INTO journal_entries (
			id, tenant_id, entry_number, entry_date, description, reference,
			status, total_debit, total_credit, currency, posted_at, posted_by,
			reversed_at, reversed_by, reversal_reason, original_entry_id,
			tigerbeetle_transfer_id, metadata, created_at, updated_at
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20)
		ON CONFLICT (tenant_id, entry_number) DO UPDATE SET
			status = EXCLUDED.status,
			posted_at = EXCLUDED.posted_at,
			posted_by = EXCLUDED.posted_by,
			reversed_at = EXCLUDED.reversed_at,
			reversed_by = EXCLUDED.reversed_by,
			reversal_reason = EXCLUDED.reversal_reason,
			updated_at = CURRENT_TIMESTAMP
	`

	var postedAt sql.NullTime
	if entry.PostedAt != nil {
		postedAt = sql.NullTime{Time: *entry.PostedAt, Valid: true}
	}

	var reversedAt sql.NullTime
	if entry.ReversedAt != nil {
		reversedAt = sql.NullTime{Time: *entry.ReversedAt, Valid: true}
	}

	originalEntryID := sql.NullString{String: entry.OriginalEntryID, Valid: entry.OriginalEntryID != ""}

	_, err = tx.ExecContext(ctx, entryQuery,
		entry.ID, entry.TenantID, entry.EntryNumber, entry.EntryDate, entry.Description, entry.Reference,
		string(entry.Status), entry.TotalDebit, entry.TotalCredit, entry.Currency, postedAt, entry.PostedBy,
		reversedAt, entry.ReversedBy, entry.ReversalReason, originalEntryID,
		entry.TigerBeetleTransferID, metadataJSON, entry.CreatedAt, entry.UpdatedAt,
	)
	if err != nil {
		return err
	}

	deleteQuery := `DELETE FROM journal_entry_lines WHERE journal_entry_id = $1`
	if _, err := tx.ExecContext(ctx, deleteQuery, entry.ID); err != nil {
		return err
	}

	lineQuery := `
		INSERT INTO journal_entry_lines (id, journal_entry_id, account_id, description, debit_amount, credit_amount, line_number)
		VALUES ($1, $2, $3, $4, $5, $6, $7)
	`
	for i, line := range entry.Lines {
		lineID := fmt.Sprintf("%s-line-%d", entry.ID, i+1)
		if _, err := tx.ExecContext(ctx, lineQuery, lineID, entry.ID, line.AccountID, line.Description, line.DebitAmount, line.CreditAmount, i+1); err != nil {
			return err
		}
	}

	return tx.Commit()
}

func (s *PostgresStore) GetJournalEntry(ctx context.Context, tenantID, entryID string) (*JournalEntry, error) {
	query := `
		SELECT id, tenant_id, entry_number, entry_date, description, reference,
			status, total_debit, total_credit, currency, posted_at, posted_by,
			reversed_at, reversed_by, reversal_reason, original_entry_id,
			tigerbeetle_transfer_id, metadata, created_at, updated_at
		FROM journal_entries WHERE tenant_id = $1 AND id = $2
	`

	var entry JournalEntry
	var postedAt, reversedAt sql.NullTime
	var originalEntryID sql.NullString
	var metadataJSON []byte

	err := s.db.QueryRowContext(ctx, query, tenantID, entryID).Scan(
		&entry.ID, &entry.TenantID, &entry.EntryNumber, &entry.EntryDate, &entry.Description, &entry.Reference,
		&entry.Status, &entry.TotalDebit, &entry.TotalCredit, &entry.Currency, &postedAt, &entry.PostedBy,
		&reversedAt, &entry.ReversedBy, &entry.ReversalReason, &originalEntryID,
		&entry.TigerBeetleTransferID, &metadataJSON, &entry.CreatedAt, &entry.UpdatedAt,
	)

	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}

	if postedAt.Valid {
		t := postedAt.Time
		entry.PostedAt = &t
	}
	if reversedAt.Valid {
		t := reversedAt.Time
		entry.ReversedAt = &t
	}
	if originalEntryID.Valid {
		entry.OriginalEntryID = originalEntryID.String
	}
	json.Unmarshal(metadataJSON, &entry.Metadata)

	linesQuery := `
		SELECT jel.account_id, jel.description, jel.debit_amount, jel.credit_amount, a.code, a.name
		FROM journal_entry_lines jel
		JOIN coa_accounts a ON jel.account_id = a.id
		WHERE jel.journal_entry_id = $1
		ORDER BY jel.line_number
	`
	rows, err := s.db.QueryContext(ctx, linesQuery, entryID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	for rows.Next() {
		var line JournalLine
		if err := rows.Scan(&line.AccountID, &line.Description, &line.DebitAmount, &line.CreditAmount, &line.AccountCode, &line.AccountName); err != nil {
			return nil, err
		}
		entry.Lines = append(entry.Lines, line)
	}

	return &entry, rows.Err()
}

func (s *PostgresStore) ListJournalEntries(ctx context.Context, tenantID string, status string, startDate, endDate *time.Time) ([]JournalEntry, error) {
	query := `
		SELECT id, tenant_id, entry_number, entry_date, description, reference,
			status, total_debit, total_credit, currency, posted_at, posted_by,
			reversed_at, reversed_by, reversal_reason, original_entry_id,
			tigerbeetle_transfer_id, metadata, created_at, updated_at
		FROM journal_entries WHERE tenant_id = $1
	`
	args := []interface{}{tenantID}
	argNum := 2

	if status != "" {
		query += fmt.Sprintf(" AND status = $%d", argNum)
		args = append(args, status)
		argNum++
	}
	if startDate != nil {
		query += fmt.Sprintf(" AND entry_date >= $%d", argNum)
		args = append(args, *startDate)
		argNum++
	}
	if endDate != nil {
		query += fmt.Sprintf(" AND entry_date <= $%d", argNum)
		args = append(args, *endDate)
		argNum++
	}
	query += " ORDER BY entry_date DESC, entry_number DESC"

	rows, err := s.db.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var entries []JournalEntry
	for rows.Next() {
		var entry JournalEntry
		var postedAt, reversedAt sql.NullTime
		var originalEntryID sql.NullString
		var metadataJSON []byte

		if err := rows.Scan(
			&entry.ID, &entry.TenantID, &entry.EntryNumber, &entry.EntryDate, &entry.Description, &entry.Reference,
			&entry.Status, &entry.TotalDebit, &entry.TotalCredit, &entry.Currency, &postedAt, &entry.PostedBy,
			&reversedAt, &entry.ReversedBy, &entry.ReversalReason, &originalEntryID,
			&entry.TigerBeetleTransferID, &metadataJSON, &entry.CreatedAt, &entry.UpdatedAt,
		); err != nil {
			return nil, err
		}

		if postedAt.Valid {
			t := postedAt.Time
			entry.PostedAt = &t
		}
		if reversedAt.Valid {
			t := reversedAt.Time
			entry.ReversedAt = &t
		}
		if originalEntryID.Valid {
			entry.OriginalEntryID = originalEntryID.String
		}
		json.Unmarshal(metadataJSON, &entry.Metadata)

		entries = append(entries, entry)
	}

	return entries, rows.Err()
}

func (s *PostgresStore) SaveAccountingPeriod(ctx context.Context, period AccountingPeriod) error {
	query := `
		INSERT INTO accounting_periods (
			id, tenant_id, name, period_type, start_date, end_date,
			status, closed_at, closed_by, fiscal_year, period_number, is_adjustment_period,
			created_at, updated_at
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
		ON CONFLICT (tenant_id, fiscal_year, period_number) DO UPDATE SET
			status = EXCLUDED.status,
			closed_at = EXCLUDED.closed_at,
			closed_by = EXCLUDED.closed_by,
			updated_at = CURRENT_TIMESTAMP
	`

	closedAt := sql.NullTime{Time: period.ClosedAt, Valid: !period.ClosedAt.IsZero()}

	_, err := s.db.ExecContext(ctx, query,
		period.ID, period.TenantID, period.Name, period.PeriodType, period.StartDate, period.EndDate,
		string(period.Status), closedAt, period.ClosedBy, period.FiscalYear, period.PeriodNumber, period.IsAdjustmentPeriod,
		period.CreatedAt, period.UpdatedAt,
	)
	return err
}

func (s *PostgresStore) GetAccountingPeriod(ctx context.Context, tenantID, periodID string) (*AccountingPeriod, error) {
	query := `
		SELECT id, tenant_id, name, period_type, start_date, end_date,
			status, closed_at, closed_by, fiscal_year, period_number, is_adjustment_period,
			created_at, updated_at
		FROM accounting_periods WHERE tenant_id = $1 AND id = $2
	`

	var period AccountingPeriod
	var closedAt sql.NullTime

	err := s.db.QueryRowContext(ctx, query, tenantID, periodID).Scan(
		&period.ID, &period.TenantID, &period.Name, &period.PeriodType, &period.StartDate, &period.EndDate,
		&period.Status, &closedAt, &period.ClosedBy, &period.FiscalYear, &period.PeriodNumber, &period.IsAdjustmentPeriod,
		&period.CreatedAt, &period.UpdatedAt,
	)

	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}

	if closedAt.Valid {
		period.ClosedAt = closedAt.Time
	}

	return &period, nil
}

func (s *PostgresStore) GetOpenPeriodForDate(ctx context.Context, tenantID string, date time.Time) (*AccountingPeriod, error) {
	query := `
		SELECT id, tenant_id, name, period_type, start_date, end_date,
			status, closed_at, closed_by, fiscal_year, period_number, is_adjustment_period,
			created_at, updated_at
		FROM accounting_periods
		WHERE tenant_id = $1 AND status = 'open' AND start_date <= $2 AND end_date >= $2
		LIMIT 1
	`

	var period AccountingPeriod
	var closedAt sql.NullTime

	err := s.db.QueryRowContext(ctx, query, tenantID, date).Scan(
		&period.ID, &period.TenantID, &period.Name, &period.PeriodType, &period.StartDate, &period.EndDate,
		&period.Status, &closedAt, &period.ClosedBy, &period.FiscalYear, &period.PeriodNumber, &period.IsAdjustmentPeriod,
		&period.CreatedAt, &period.UpdatedAt,
	)

	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}

	if closedAt.Valid {
		period.ClosedAt = closedAt.Time
	}

	return &period, nil
}

func (s *PostgresStore) ListAccountingPeriods(ctx context.Context, tenantID string, fiscalYear int) ([]AccountingPeriod, error) {
	query := `
		SELECT id, tenant_id, name, period_type, start_date, end_date,
			status, closed_at, closed_by, fiscal_year, period_number, is_adjustment_period,
			created_at, updated_at
		FROM accounting_periods WHERE tenant_id = $1
	`
	args := []interface{}{tenantID}

	if fiscalYear > 0 {
		query += " AND fiscal_year = $2"
		args = append(args, fiscalYear)
	}
	query += " ORDER BY fiscal_year DESC, period_number"

	rows, err := s.db.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var periods []AccountingPeriod
	for rows.Next() {
		var period AccountingPeriod
		var closedAt sql.NullTime

		if err := rows.Scan(
			&period.ID, &period.TenantID, &period.Name, &period.PeriodType, &period.StartDate, &period.EndDate,
			&period.Status, &closedAt, &period.ClosedBy, &period.FiscalYear, &period.PeriodNumber, &period.IsAdjustmentPeriod,
			&period.CreatedAt, &period.UpdatedAt,
		); err != nil {
			return nil, err
		}

		if closedAt.Valid {
			period.ClosedAt = closedAt.Time
		}

		periods = append(periods, period)
	}

	return periods, rows.Err()
}

func (s *PostgresStore) SaveApprovalWorkflow(ctx context.Context, workflow ApprovalWorkflow) error {
	tx, err := s.db.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	defer tx.Rollback()

	workflowQuery := `
		INSERT INTO approval_workflows (id, tenant_id, name, entity_type, min_amount, max_amount, is_active, created_at, updated_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
		ON CONFLICT (id) DO UPDATE SET
			name = EXCLUDED.name,
			min_amount = EXCLUDED.min_amount,
			max_amount = EXCLUDED.max_amount,
			is_active = EXCLUDED.is_active,
			updated_at = CURRENT_TIMESTAMP
	`

	minAmount := sql.NullInt64{Int64: workflow.MinAmount, Valid: workflow.MinAmount > 0}
	maxAmount := sql.NullInt64{Int64: workflow.MaxAmount, Valid: workflow.MaxAmount > 0}

	_, err = tx.ExecContext(ctx, workflowQuery,
		workflow.ID, workflow.TenantID, workflow.Name, workflow.EntityType,
		minAmount, maxAmount, workflow.IsActive, workflow.CreatedAt, workflow.UpdatedAt,
	)
	if err != nil {
		return err
	}

	deleteQuery := `DELETE FROM approval_workflow_steps WHERE workflow_id = $1`
	if _, err := tx.ExecContext(ctx, deleteQuery, workflow.ID); err != nil {
		return err
	}

	stepQuery := `
		INSERT INTO approval_workflow_steps (id, workflow_id, step_order, approver_role, approver_user_id, is_mandatory)
		VALUES ($1, $2, $3, $4, $5, $6)
	`
	for i, step := range workflow.Steps {
		stepID := fmt.Sprintf("%s-step-%d", workflow.ID, i+1)
		approverUserID := sql.NullString{String: step.ApproverUserID, Valid: step.ApproverUserID != ""}
		if _, err := tx.ExecContext(ctx, stepQuery, stepID, workflow.ID, step.StepOrder, step.ApproverRole, approverUserID, step.IsMandatory); err != nil {
			return err
		}
	}

	return tx.Commit()
}

func (s *PostgresStore) GetApprovalWorkflow(ctx context.Context, tenantID, workflowID string) (*ApprovalWorkflow, error) {
	query := `
		SELECT id, tenant_id, name, entity_type, min_amount, max_amount, is_active, created_at, updated_at
		FROM approval_workflows WHERE tenant_id = $1 AND id = $2
	`

	var workflow ApprovalWorkflow
	var minAmount, maxAmount sql.NullInt64

	err := s.db.QueryRowContext(ctx, query, tenantID, workflowID).Scan(
		&workflow.ID, &workflow.TenantID, &workflow.Name, &workflow.EntityType,
		&minAmount, &maxAmount, &workflow.IsActive, &workflow.CreatedAt, &workflow.UpdatedAt,
	)

	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}

	if minAmount.Valid {
		workflow.MinAmount = minAmount.Int64
	}
	if maxAmount.Valid {
		workflow.MaxAmount = maxAmount.Int64
	}

	stepsQuery := `
		SELECT step_order, approver_role, approver_user_id, is_mandatory
		FROM approval_workflow_steps WHERE workflow_id = $1 ORDER BY step_order
	`
	rows, err := s.db.QueryContext(ctx, stepsQuery, workflowID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	for rows.Next() {
		var step ApprovalWorkflowStep
		var approverUserID sql.NullString
		if err := rows.Scan(&step.StepOrder, &step.ApproverRole, &approverUserID, &step.IsMandatory); err != nil {
			return nil, err
		}
		if approverUserID.Valid {
			step.ApproverUserID = approverUserID.String
		}
		workflow.Steps = append(workflow.Steps, step)
	}

	return &workflow, rows.Err()
}

func (s *PostgresStore) GetApprovalWorkflowForAmount(ctx context.Context, tenantID, entityType string, amount int64) (*ApprovalWorkflow, error) {
	query := `
		SELECT id, tenant_id, name, entity_type, min_amount, max_amount, is_active, created_at, updated_at
		FROM approval_workflows
		WHERE tenant_id = $1 AND entity_type = $2 AND is_active = true
			AND (min_amount IS NULL OR min_amount <= $3)
			AND (max_amount IS NULL OR max_amount >= $3)
		ORDER BY min_amount DESC NULLS LAST
		LIMIT 1
	`

	var workflow ApprovalWorkflow
	var minAmount, maxAmount sql.NullInt64

	err := s.db.QueryRowContext(ctx, query, tenantID, entityType, amount).Scan(
		&workflow.ID, &workflow.TenantID, &workflow.Name, &workflow.EntityType,
		&minAmount, &maxAmount, &workflow.IsActive, &workflow.CreatedAt, &workflow.UpdatedAt,
	)

	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}

	if minAmount.Valid {
		workflow.MinAmount = minAmount.Int64
	}
	if maxAmount.Valid {
		workflow.MaxAmount = maxAmount.Int64
	}

	stepsQuery := `
		SELECT step_order, approver_role, approver_user_id, is_mandatory
		FROM approval_workflow_steps WHERE workflow_id = $1 ORDER BY step_order
	`
	rows, err := s.db.QueryContext(ctx, stepsQuery, workflow.ID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	for rows.Next() {
		var step ApprovalWorkflowStep
		var approverUserID sql.NullString
		if err := rows.Scan(&step.StepOrder, &step.ApproverRole, &approverUserID, &step.IsMandatory); err != nil {
			return nil, err
		}
		if approverUserID.Valid {
			step.ApproverUserID = approverUserID.String
		}
		workflow.Steps = append(workflow.Steps, step)
	}

	return &workflow, rows.Err()
}

func (s *PostgresStore) SaveApprovalRequest(ctx context.Context, request ApprovalRequest) error {
	metadataJSON, _ := json.Marshal(request.Metadata)

	query := `
		INSERT INTO approval_requests (
			id, tenant_id, workflow_id, entity_type, entity_id, current_step,
			status, requested_by, requested_at, completed_at, metadata
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
		ON CONFLICT (id) DO UPDATE SET
			current_step = EXCLUDED.current_step,
			status = EXCLUDED.status,
			completed_at = EXCLUDED.completed_at
	`

	completedAt := sql.NullTime{Time: request.CompletedAt, Valid: !request.CompletedAt.IsZero()}

	_, err := s.db.ExecContext(ctx, query,
		request.ID, request.TenantID, request.WorkflowID, request.EntityType, request.EntityID,
		request.CurrentStep, string(request.Status), request.RequestedBy, request.RequestedAt,
		completedAt, metadataJSON,
	)
	return err
}

func (s *PostgresStore) GetApprovalRequest(ctx context.Context, tenantID, requestID string) (*ApprovalRequest, error) {
	query := `
		SELECT id, tenant_id, workflow_id, entity_type, entity_id, current_step,
			status, requested_by, requested_at, completed_at, metadata
		FROM approval_requests WHERE tenant_id = $1 AND id = $2
	`

	var request ApprovalRequest
	var completedAt sql.NullTime
	var metadataJSON []byte

	err := s.db.QueryRowContext(ctx, query, tenantID, requestID).Scan(
		&request.ID, &request.TenantID, &request.WorkflowID, &request.EntityType, &request.EntityID,
		&request.CurrentStep, &request.Status, &request.RequestedBy, &request.RequestedAt,
		&completedAt, &metadataJSON,
	)

	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}

	if completedAt.Valid {
		request.CompletedAt = completedAt.Time
	}
	json.Unmarshal(metadataJSON, &request.Metadata)

	actionsQuery := `
		SELECT step_number, action, action_by, action_at, comments
		FROM approval_actions WHERE request_id = $1 ORDER BY action_at
	`
	rows, err := s.db.QueryContext(ctx, actionsQuery, requestID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	for rows.Next() {
		var action ApprovalAction
		if err := rows.Scan(&action.StepNumber, &action.Action, &action.ActionBy, &action.ActionAt, &action.Comments); err != nil {
			return nil, err
		}
		request.Actions = append(request.Actions, action)
	}

	return &request, rows.Err()
}

func (s *PostgresStore) GetPendingApprovalForEntity(ctx context.Context, tenantID, entityType, entityID string) (*ApprovalRequest, error) {
	query := `
		SELECT id, tenant_id, workflow_id, entity_type, entity_id, current_step,
			status, requested_by, requested_at, completed_at, metadata
		FROM approval_requests
		WHERE tenant_id = $1 AND entity_type = $2 AND entity_id = $3 AND status = 'pending'
		LIMIT 1
	`

	var request ApprovalRequest
	var completedAt sql.NullTime
	var metadataJSON []byte

	err := s.db.QueryRowContext(ctx, query, tenantID, entityType, entityID).Scan(
		&request.ID, &request.TenantID, &request.WorkflowID, &request.EntityType, &request.EntityID,
		&request.CurrentStep, &request.Status, &request.RequestedBy, &request.RequestedAt,
		&completedAt, &metadataJSON,
	)

	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}

	if completedAt.Valid {
		request.CompletedAt = completedAt.Time
	}
	json.Unmarshal(metadataJSON, &request.Metadata)

	return &request, nil
}

func (s *PostgresStore) SaveApprovalAction(ctx context.Context, requestID string, action ApprovalAction) error {
	query := `
		INSERT INTO approval_actions (id, request_id, step_number, action, action_by, action_at, comments)
		VALUES ($1, $2, $3, $4, $5, $6, $7)
	`
	actionID := fmt.Sprintf("%s-action-%d", requestID, time.Now().UnixNano())
	_, err := s.db.ExecContext(ctx, query, actionID, requestID, action.StepNumber, action.Action, action.ActionBy, action.ActionAt, action.Comments)
	return err
}

func (s *PostgresStore) SaveAccountTemplate(ctx context.Context, template AccountTemplate) error {
	accountsJSON, _ := json.Marshal(template.Accounts)

	query := `
		INSERT INTO account_templates (id, name, description, bank_type, is_default, accounts, created_at, updated_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
		ON CONFLICT (name, bank_type) DO UPDATE SET
			description = EXCLUDED.description,
			is_default = EXCLUDED.is_default,
			accounts = EXCLUDED.accounts,
			updated_at = CURRENT_TIMESTAMP
	`

	_, err := s.db.ExecContext(ctx, query,
		template.ID, template.Name, template.Description, template.BankType,
		template.IsDefault, accountsJSON, template.CreatedAt, template.UpdatedAt,
	)
	return err
}

func (s *PostgresStore) GetAccountTemplate(ctx context.Context, templateID string) (*AccountTemplate, error) {
	query := `
		SELECT id, name, description, bank_type, is_default, accounts, created_at, updated_at
		FROM account_templates WHERE id = $1
	`

	var template AccountTemplate
	var accountsJSON []byte

	err := s.db.QueryRowContext(ctx, query, templateID).Scan(
		&template.ID, &template.Name, &template.Description, &template.BankType,
		&template.IsDefault, &accountsJSON, &template.CreatedAt, &template.UpdatedAt,
	)

	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}

	json.Unmarshal(accountsJSON, &template.Accounts)
	return &template, nil
}

func (s *PostgresStore) GetDefaultTemplateForBankType(ctx context.Context, bankType string) (*AccountTemplate, error) {
	query := `
		SELECT id, name, description, bank_type, is_default, accounts, created_at, updated_at
		FROM account_templates WHERE bank_type = $1 AND is_default = true
		LIMIT 1
	`

	var template AccountTemplate
	var accountsJSON []byte

	err := s.db.QueryRowContext(ctx, query, bankType).Scan(
		&template.ID, &template.Name, &template.Description, &template.BankType,
		&template.IsDefault, &accountsJSON, &template.CreatedAt, &template.UpdatedAt,
	)

	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}

	json.Unmarshal(accountsJSON, &template.Accounts)
	return &template, nil
}

func (s *PostgresStore) ListAccountTemplates(ctx context.Context, bankType string) ([]AccountTemplate, error) {
	query := `SELECT id, name, description, bank_type, is_default, accounts, created_at, updated_at FROM account_templates`
	args := []interface{}{}

	if bankType != "" {
		query += " WHERE bank_type = $1"
		args = append(args, bankType)
	}
	query += " ORDER BY bank_type, name"

	rows, err := s.db.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var templates []AccountTemplate
	for rows.Next() {
		var template AccountTemplate
		var accountsJSON []byte

		if err := rows.Scan(
			&template.ID, &template.Name, &template.Description, &template.BankType,
			&template.IsDefault, &accountsJSON, &template.CreatedAt, &template.UpdatedAt,
		); err != nil {
			return nil, err
		}

		json.Unmarshal(accountsJSON, &template.Accounts)
		templates = append(templates, template)
	}

	return templates, rows.Err()
}

func (s *PostgresStore) SaveImportJob(ctx context.Context, job ImportJob) error {
	errorsJSON, _ := json.Marshal(job.Errors)

	query := `
		INSERT INTO import_jobs (
			id, tenant_id, job_type, status, file_name, total_rows,
			processed_rows, success_rows, error_rows, errors,
			started_at, completed_at, created_by, created_at
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
		ON CONFLICT (id) DO UPDATE SET
			status = EXCLUDED.status,
			processed_rows = EXCLUDED.processed_rows,
			success_rows = EXCLUDED.success_rows,
			error_rows = EXCLUDED.error_rows,
			errors = EXCLUDED.errors,
			completed_at = EXCLUDED.completed_at
	`

	startedAt := sql.NullTime{Time: job.StartedAt, Valid: !job.StartedAt.IsZero()}
	completedAt := sql.NullTime{Time: job.CompletedAt, Valid: !job.CompletedAt.IsZero()}

	_, err := s.db.ExecContext(ctx, query,
		job.ID, job.TenantID, job.JobType, string(job.Status), job.FileName, job.TotalRows,
		job.ProcessedRows, job.SuccessRows, job.ErrorRows, errorsJSON,
		startedAt, completedAt, job.CreatedBy, job.CreatedAt,
	)
	return err
}

func (s *PostgresStore) GetImportJob(ctx context.Context, tenantID, jobID string) (*ImportJob, error) {
	query := `
		SELECT id, tenant_id, job_type, status, file_name, total_rows,
			processed_rows, success_rows, error_rows, errors,
			started_at, completed_at, created_by, created_at
		FROM import_jobs WHERE tenant_id = $1 AND id = $2
	`

	var job ImportJob
	var startedAt, completedAt sql.NullTime
	var errorsJSON []byte

	err := s.db.QueryRowContext(ctx, query, tenantID, jobID).Scan(
		&job.ID, &job.TenantID, &job.JobType, &job.Status, &job.FileName, &job.TotalRows,
		&job.ProcessedRows, &job.SuccessRows, &job.ErrorRows, &errorsJSON,
		&startedAt, &completedAt, &job.CreatedBy, &job.CreatedAt,
	)

	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}

	if startedAt.Valid {
		job.StartedAt = startedAt.Time
	}
	if completedAt.Valid {
		job.CompletedAt = completedAt.Time
	}
	json.Unmarshal(errorsJSON, &job.Errors)

	return &job, nil
}

func (s *PostgresStore) SaveAuditLog(ctx context.Context, log AuditLogEntry) error {
	oldValuesJSON, _ := json.Marshal(log.OldValues)
	newValuesJSON, _ := json.Marshal(log.NewValues)

	query := `
		INSERT INTO audit_log (
			id, tenant_id, entity_type, entity_id, action,
			old_values, new_values, user_id, user_role, ip_address, user_agent, created_at
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
	`

	_, err := s.db.ExecContext(ctx, query,
		log.ID, log.TenantID, log.EntityType, log.EntityID, log.Action,
		oldValuesJSON, newValuesJSON, log.UserID, log.UserRole, log.IPAddress, log.UserAgent, log.CreatedAt,
	)
	return err
}

func (s *PostgresStore) ListAuditLogs(ctx context.Context, tenantID, entityType, entityID string, startDate, endDate *time.Time, limit int) ([]AuditLogEntry, error) {
	query := `
		SELECT id, tenant_id, entity_type, entity_id, action,
			old_values, new_values, user_id, user_role, ip_address, user_agent, created_at
		FROM audit_log WHERE tenant_id = $1
	`
	args := []interface{}{tenantID}
	argNum := 2

	if entityType != "" {
		query += fmt.Sprintf(" AND entity_type = $%d", argNum)
		args = append(args, entityType)
		argNum++
	}
	if entityID != "" {
		query += fmt.Sprintf(" AND entity_id = $%d", argNum)
		args = append(args, entityID)
		argNum++
	}
	if startDate != nil {
		query += fmt.Sprintf(" AND created_at >= $%d", argNum)
		args = append(args, *startDate)
		argNum++
	}
	if endDate != nil {
		query += fmt.Sprintf(" AND created_at <= $%d", argNum)
		args = append(args, *endDate)
		argNum++
	}

	query += " ORDER BY created_at DESC"

	if limit > 0 {
		query += fmt.Sprintf(" LIMIT $%d", argNum)
		args = append(args, limit)
	}

	rows, err := s.db.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var logs []AuditLogEntry
	for rows.Next() {
		var log AuditLogEntry
		var oldValuesJSON, newValuesJSON []byte

		if err := rows.Scan(
			&log.ID, &log.TenantID, &log.EntityType, &log.EntityID, &log.Action,
			&oldValuesJSON, &newValuesJSON, &log.UserID, &log.UserRole, &log.IPAddress, &log.UserAgent, &log.CreatedAt,
		); err != nil {
			return nil, err
		}

		json.Unmarshal(oldValuesJSON, &log.OldValues)
		json.Unmarshal(newValuesJSON, &log.NewValues)

		logs = append(logs, log)
	}

	return logs, rows.Err()
}

func (s *PostgresStore) ListApprovalWorkflows(ctx context.Context, tenantID string) ([]ApprovalWorkflow, error) {
	query := `
		SELECT id, tenant_id, name, entity_type, min_amount, max_amount, is_active, created_at, updated_at
		FROM approval_workflows WHERE tenant_id = $1 ORDER BY created_at DESC
	`
	rows, err := s.db.QueryContext(ctx, query, tenantID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var workflows []ApprovalWorkflow
	for rows.Next() {
		var w ApprovalWorkflow
		var minAmount, maxAmount sql.NullInt64
		if err := rows.Scan(&w.ID, &w.TenantID, &w.Name, &w.EntityType, &minAmount, &maxAmount, &w.IsActive, &w.CreatedAt, &w.UpdatedAt); err != nil {
			return nil, err
		}
		if minAmount.Valid {
			w.MinAmount = minAmount.Int64
		}
		if maxAmount.Valid {
			w.MaxAmount = maxAmount.Int64
		}
		stepsQuery := `SELECT step_order, approver_role, approver_user_id, is_mandatory FROM approval_workflow_steps WHERE workflow_id = $1 ORDER BY step_order`
		sRows, err := s.db.QueryContext(ctx, stepsQuery, w.ID)
		if err == nil {
			defer sRows.Close()
			for sRows.Next() {
				var step ApprovalWorkflowStep
				var approverUserID sql.NullString
				if err := sRows.Scan(&step.StepOrder, &step.ApproverRole, &approverUserID, &step.IsMandatory); err == nil {
					if approverUserID.Valid {
						step.ApproverUserID = approverUserID.String
					}
					w.Steps = append(w.Steps, step)
				}
			}
		}
		workflows = append(workflows, w)
	}
	return workflows, rows.Err()
}

func (s *PostgresStore) ListApprovalRequests(ctx context.Context, tenantID, entityType, status string) ([]ApprovalRequest, error) {
	query := `
		SELECT id, tenant_id, workflow_id, entity_type, entity_id, current_step, status, requested_by, requested_at, completed_at
		FROM approval_requests WHERE tenant_id = $1
	`
	args := []interface{}{tenantID}
	if entityType != "" {
		args = append(args, entityType)
		query += fmt.Sprintf(" AND entity_type = $%d", len(args))
	}
	if status != "" {
		args = append(args, status)
		query += fmt.Sprintf(" AND status = $%d", len(args))
	}
	query += " ORDER BY requested_at DESC LIMIT 100"

	rows, err := s.db.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var requests []ApprovalRequest
	for rows.Next() {
		var req ApprovalRequest
		var completedAt sql.NullTime
		if err := rows.Scan(&req.ID, &req.TenantID, &req.WorkflowID, &req.EntityType, &req.EntityID, &req.CurrentStep, &req.Status, &req.RequestedBy, &req.RequestedAt, &completedAt); err != nil {
			return nil, err
		}
		if completedAt.Valid {
			req.CompletedAt = completedAt.Time
		}
		requests = append(requests, req)
	}
	return requests, rows.Err()
}
