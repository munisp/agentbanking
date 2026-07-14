-- ─────────────────────────────────────────────────────────────────────────────
-- Migration 0049: Stakeholder-dedicated tables
-- Adds first-class tables for every stakeholder workflow that previously
-- relied on aliased or shared tables.
-- ─────────────────────────────────────────────────────────────────────────────

-- 1. ENUMS
DO $$ BEGIN
  CREATE TYPE role_type AS ENUM (
    'super_admin','tenant_owner','tenant_admin','supervisor','agent',
    'customer','merchant','developer','regulator','compliance_officer',
    'auditor','support'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE float_account_status AS ENUM ('active','suspended','closed','overdrawn');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE float_insurance_claim_status AS ENUM (
    'submitted','under_review','approved','rejected','paid'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE tb_account_type AS ENUM (
    'agent_float','customer_wallet','merchant_settlement',
    'fee_collection','suspense','nostro','vostro'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE bnpl_status AS ENUM (
    'initiated','approved','active','partially_repaid','fully_repaid',
    'overdue','defaulted','cancelled'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE loan_application_status AS ENUM (
    'draft','submitted','under_review','credit_check',
    'approved','rejected','disbursed','cancelled'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE settlement_status AS ENUM (
    'pending','processing','completed','failed','reversed'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE aml_risk_level AS ENUM ('low','medium','high','critical');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE notif_inbox_status AS ENUM ('unread','read','archived','deleted');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- 2. ROLES
CREATE TABLE IF NOT EXISTS roles (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       UUID NOT NULL,
  name            TEXT NOT NULL,
  type            role_type NOT NULL,
  description     TEXT,
  permissions     JSONB NOT NULL DEFAULT '[]',
  is_system       BOOLEAN NOT NULL DEFAULT FALSE,
  is_active       BOOLEAN NOT NULL DEFAULT TRUE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS roles_tenant_idx ON roles(tenant_id);
CREATE UNIQUE INDEX IF NOT EXISTS roles_tenant_name_uidx ON roles(tenant_id, name);

-- 3. AGENT FLOAT ACCOUNTS
CREATE TABLE IF NOT EXISTS agent_float_accounts (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id           UUID NOT NULL,
  agent_id            UUID NOT NULL,
  currency            TEXT NOT NULL DEFAULT 'NGN',
  balance             NUMERIC(20,4) NOT NULL DEFAULT 0
                        CONSTRAINT afa_balance_non_negative CHECK (balance >= 0),
  reserved_balance    NUMERIC(20,4) NOT NULL DEFAULT 0
                        CONSTRAINT afa_reserved_non_negative CHECK (reserved_balance >= 0),
  credit_limit        NUMERIC(20,4) NOT NULL DEFAULT 0,
  status              float_account_status NOT NULL DEFAULT 'active',
  tb_account_id       TEXT,
  last_reconciled_at  TIMESTAMPTZ,
  metadata            JSONB DEFAULT '{}',
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS afa_tenant_idx ON agent_float_accounts(tenant_id);
CREATE INDEX IF NOT EXISTS afa_agent_idx ON agent_float_accounts(agent_id);
CREATE UNIQUE INDEX IF NOT EXISTS afa_agent_tenant_currency_uidx ON agent_float_accounts(agent_id, tenant_id, currency);

-- 4. AGENT FLOAT INSURANCE CLAIMS
CREATE TABLE IF NOT EXISTS agent_float_insurance_claims (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       UUID NOT NULL,
  agent_id        UUID NOT NULL,
  float_account_id UUID NOT NULL,
  claim_amount    NUMERIC(20,4) NOT NULL CONSTRAINT afic_claim_positive CHECK (claim_amount > 0),
  approved_amount NUMERIC(20,4),
  status          float_insurance_claim_status NOT NULL DEFAULT 'submitted',
  incident_date   TIMESTAMPTZ NOT NULL,
  description     TEXT NOT NULL,
  evidence_urls   JSONB DEFAULT '[]',
  reviewed_by     UUID,
  review_notes    TEXT,
  paid_at         TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS afic_tenant_idx ON agent_float_insurance_claims(tenant_id);
CREATE INDEX IF NOT EXISTS afic_agent_idx ON agent_float_insurance_claims(agent_id);
CREATE INDEX IF NOT EXISTS afic_status_idx ON agent_float_insurance_claims(status);

-- 5. AGENT CLUSTERS
CREATE TABLE IF NOT EXISTS agent_clusters (
  id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id                 UUID NOT NULL,
  supervisor_id             UUID NOT NULL,
  name                      TEXT NOT NULL,
  description               TEXT,
  region                    TEXT,
  state                     TEXT,
  lga                       TEXT,
  target_tx_volume          NUMERIC(20,4),
  target_agent_count        INTEGER,
  is_active                 BOOLEAN NOT NULL DEFAULT TRUE,
  metadata                  JSONB DEFAULT '{}',
  created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at                TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ac_tenant_idx ON agent_clusters(tenant_id);
CREATE INDEX IF NOT EXISTS ac_supervisor_idx ON agent_clusters(supervisor_id);

CREATE TABLE IF NOT EXISTS agent_cluster_members (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  cluster_id  UUID NOT NULL,
  agent_id    UUID NOT NULL,
  joined_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  is_active   BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE INDEX IF NOT EXISTS acm_cluster_idx ON agent_cluster_members(cluster_id);
CREATE INDEX IF NOT EXISTS acm_agent_idx ON agent_cluster_members(agent_id);
CREATE UNIQUE INDEX IF NOT EXISTS acm_unique_uidx ON agent_cluster_members(cluster_id, agent_id);

-- 6. AGENT GAMIFICATION
CREATE TABLE IF NOT EXISTS agent_gamification (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id           UUID NOT NULL,
  agent_id            UUID NOT NULL,
  total_points        INTEGER NOT NULL DEFAULT 0 CONSTRAINT ag_points_non_neg CHECK (total_points >= 0),
  level               INTEGER NOT NULL DEFAULT 1,
  level_name          TEXT NOT NULL DEFAULT 'Bronze',
  current_streak      INTEGER NOT NULL DEFAULT 0,
  longest_streak      INTEGER NOT NULL DEFAULT 0,
  last_activity_date  TIMESTAMPTZ,
  monthly_points      INTEGER NOT NULL DEFAULT 0,
  weekly_points       INTEGER NOT NULL DEFAULT 0,
  leaderboard_rank    INTEGER,
  badges              JSONB NOT NULL DEFAULT '[]',
  metadata            JSONB DEFAULT '{}',
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ag_tenant_idx ON agent_gamification(tenant_id);
CREATE UNIQUE INDEX IF NOT EXISTS ag_agent_tenant_uidx ON agent_gamification(agent_id, tenant_id);
CREATE INDEX IF NOT EXISTS ag_points_idx ON agent_gamification(total_points DESC);

-- 7. AGENT HIERARCHY
CREATE TABLE IF NOT EXISTS agent_hierarchy (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       UUID NOT NULL,
  agent_id        UUID NOT NULL,
  parent_agent_id UUID,
  supervisor_id   UUID,
  cluster_id      UUID,
  depth           INTEGER NOT NULL DEFAULT 0,
  path            TEXT NOT NULL DEFAULT '',
  is_active       BOOLEAN NOT NULL DEFAULT TRUE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ah_tenant_idx ON agent_hierarchy(tenant_id);
CREATE UNIQUE INDEX IF NOT EXISTS ah_agent_tenant_uidx ON agent_hierarchy(agent_id, tenant_id);
CREATE INDEX IF NOT EXISTS ah_parent_idx ON agent_hierarchy(parent_agent_id);
CREATE INDEX IF NOT EXISTS ah_supervisor_idx ON agent_hierarchy(supervisor_id);

-- 8. TIGERBEETLE ACCOUNTS
CREATE TABLE IF NOT EXISTS tb_accounts (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       UUID NOT NULL,
  tb_account_id   TEXT NOT NULL,
  ledger          INTEGER NOT NULL,
  code            INTEGER NOT NULL,
  account_type    tb_account_type NOT NULL,
  owner_id        UUID NOT NULL,
  owner_type      TEXT NOT NULL,
  currency        TEXT NOT NULL DEFAULT 'NGN',
  credits_pending NUMERIC(20,4) NOT NULL DEFAULT 0,
  credits_posted  NUMERIC(20,4) NOT NULL DEFAULT 0,
  debits_pending  NUMERIC(20,4) NOT NULL DEFAULT 0,
  debits_posted   NUMERIC(20,4) NOT NULL DEFAULT 0,
  flags           INTEGER NOT NULL DEFAULT 0,
  is_active       BOOLEAN NOT NULL DEFAULT TRUE,
  last_synced_at  TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS tba_tenant_idx ON tb_accounts(tenant_id);
CREATE UNIQUE INDEX IF NOT EXISTS tba_tb_id_uidx ON tb_accounts(tb_account_id);
CREATE INDEX IF NOT EXISTS tba_owner_idx ON tb_accounts(owner_id, owner_type);

-- 9. BNPL TRANSACTIONS
CREATE TABLE IF NOT EXISTS bnpl_transactions (
  id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id                   UUID NOT NULL,
  customer_id                 UUID NOT NULL,
  merchant_id                 UUID NOT NULL,
  original_transaction_id     UUID,
  principal_amount            NUMERIC(20,4) NOT NULL CONSTRAINT bnpl_principal_pos CHECK (principal_amount > 0),
  total_repayable_amount      NUMERIC(20,4) NOT NULL,
  outstanding_balance         NUMERIC(20,4) NOT NULL,
  interest_rate               NUMERIC(8,4) NOT NULL DEFAULT 0,
  tenor_days                  INTEGER NOT NULL,
  installment_count           INTEGER NOT NULL DEFAULT 1,
  installment_amount          NUMERIC(20,4) NOT NULL,
  status                      bnpl_status NOT NULL DEFAULT 'initiated',
  approved_at                 TIMESTAMPTZ,
  first_installment_due_date  TIMESTAMPTZ,
  last_installment_due_date   TIMESTAMPTZ,
  defaulted_at                TIMESTAMPTZ,
  tb_debit_account_id         TEXT,
  tb_credit_account_id        TEXT,
  metadata                    JSONB DEFAULT '{}',
  created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS bnpl_tenant_idx ON bnpl_transactions(tenant_id);
CREATE INDEX IF NOT EXISTS bnpl_customer_idx ON bnpl_transactions(customer_id);
CREATE INDEX IF NOT EXISTS bnpl_merchant_idx ON bnpl_transactions(merchant_id);
CREATE INDEX IF NOT EXISTS bnpl_status_idx ON bnpl_transactions(status);

CREATE TABLE IF NOT EXISTS bnpl_repayments (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  bnpl_transaction_id   UUID NOT NULL,
  installment_number    INTEGER NOT NULL,
  due_date              TIMESTAMPTZ NOT NULL,
  due_amount            NUMERIC(20,4) NOT NULL,
  paid_amount           NUMERIC(20,4) NOT NULL DEFAULT 0,
  paid_at               TIMESTAMPTZ,
  is_paid               BOOLEAN NOT NULL DEFAULT FALSE,
  penalty_amount        NUMERIC(20,4) NOT NULL DEFAULT 0,
  transaction_ref       TEXT,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS bnplr_bnpl_idx ON bnpl_repayments(bnpl_transaction_id);
CREATE INDEX IF NOT EXISTS bnplr_due_date_idx ON bnpl_repayments(due_date);

-- 10. LOAN APPLICATIONS
CREATE TABLE IF NOT EXISTS loan_applications (
  id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id                   UUID NOT NULL,
  applicant_id                UUID NOT NULL,
  applicant_type              TEXT NOT NULL DEFAULT 'customer',
  requested_amount            NUMERIC(20,4) NOT NULL CONSTRAINT la_req_amount_pos CHECK (requested_amount > 0),
  approved_amount             NUMERIC(20,4),
  currency                    TEXT NOT NULL DEFAULT 'NGN',
  purpose                     TEXT NOT NULL,
  tenor_months                INTEGER NOT NULL,
  interest_rate               NUMERIC(8,4),
  status                      loan_application_status NOT NULL DEFAULT 'draft',
  credit_score                INTEGER,
  credit_score_source         TEXT,
  collateral_description      TEXT,
  collateral_value            NUMERIC(20,4),
  reviewed_by                 UUID,
  review_notes                TEXT,
  rejection_reason            TEXT,
  submitted_at                TIMESTAMPTZ,
  approved_at                 TIMESTAMPTZ,
  disbursed_at                TIMESTAMPTZ,
  disbursement_transaction_id UUID,
  documents                   JSONB DEFAULT '[]',
  metadata                    JSONB DEFAULT '{}',
  created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS la_tenant_idx ON loan_applications(tenant_id);
CREATE INDEX IF NOT EXISTS la_applicant_idx ON loan_applications(applicant_id);
CREATE INDEX IF NOT EXISTS la_status_idx ON loan_applications(status);

-- 11. SETTLEMENTS
CREATE TABLE IF NOT EXISTS settlements (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id           UUID NOT NULL,
  batch_id            TEXT NOT NULL,
  settlement_type     TEXT NOT NULL,
  recipient_id        UUID NOT NULL,
  recipient_type      TEXT NOT NULL,
  gross_amount        NUMERIC(20,4) NOT NULL CONSTRAINT s_gross_pos CHECK (gross_amount > 0),
  fee_amount          NUMERIC(20,4) NOT NULL DEFAULT 0,
  tax_amount          NUMERIC(20,4) NOT NULL DEFAULT 0,
  net_amount          NUMERIC(20,4) NOT NULL,
  currency            TEXT NOT NULL DEFAULT 'NGN',
  status              settlement_status NOT NULL DEFAULT 'pending',
  bank_account_number TEXT,
  bank_code           TEXT,
  bank_name           TEXT,
  payment_reference   TEXT,
  settlement_date     TIMESTAMPTZ,
  processed_at        TIMESTAMPTZ,
  failure_reason      TEXT,
  tb_transfer_id      TEXT,
  metadata            JSONB DEFAULT '{}',
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS s_tenant_idx ON settlements(tenant_id);
CREATE INDEX IF NOT EXISTS s_batch_idx ON settlements(batch_id);
CREATE INDEX IF NOT EXISTS s_recipient_idx ON settlements(recipient_id);
CREATE INDEX IF NOT EXISTS s_status_idx ON settlements(status);
CREATE INDEX IF NOT EXISTS s_date_idx ON settlements(settlement_date);

-- 12. AML SCREENING RESULTS
CREATE TABLE IF NOT EXISTS aml_screening_results (
  id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id               UUID NOT NULL,
  screening_id            UUID NOT NULL,
  entity_id               UUID NOT NULL,
  entity_type             TEXT NOT NULL,
  risk_level              aml_risk_level NOT NULL,
  risk_score              NUMERIC(5,2) NOT NULL,
  matched_watchlists      JSONB DEFAULT '[]',
  matched_patterns        JSONB DEFAULT '[]',
  sanctions_hit           BOOLEAN NOT NULL DEFAULT FALSE,
  pep_hit                 BOOLEAN NOT NULL DEFAULT FALSE,
  adverse_media_hit       BOOLEAN NOT NULL DEFAULT FALSE,
  requires_manual_review  BOOLEAN NOT NULL DEFAULT FALSE,
  reviewed_by             UUID,
  review_decision         TEXT,
  review_notes            TEXT,
  reviewed_at             TIMESTAMPTZ,
  raw_response            JSONB DEFAULT '{}',
  created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS asr_tenant_idx ON aml_screening_results(tenant_id);
CREATE INDEX IF NOT EXISTS asr_entity_idx ON aml_screening_results(entity_id, entity_type);
CREATE INDEX IF NOT EXISTS asr_risk_idx ON aml_screening_results(risk_level);
CREATE INDEX IF NOT EXISTS asr_sanctions_idx ON aml_screening_results(sanctions_hit) WHERE sanctions_hit = TRUE;

-- 13. COMMISSION STRUCTURES
CREATE TABLE IF NOT EXISTS commission_structures (
  id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id               UUID NOT NULL,
  name                    TEXT NOT NULL,
  description             TEXT,
  transaction_type        TEXT NOT NULL,
  agent_share             NUMERIC(8,4) NOT NULL,
  supervisor_share        NUMERIC(8,4) NOT NULL DEFAULT 0,
  tenant_share            NUMERIC(8,4) NOT NULL DEFAULT 0,
  platform_share          NUMERIC(8,4) NOT NULL DEFAULT 0,
  min_transaction_amount  NUMERIC(20,4),
  max_transaction_amount  NUMERIC(20,4),
  effective_from          TIMESTAMPTZ NOT NULL DEFAULT now(),
  effective_to            TIMESTAMPTZ,
  is_active               BOOLEAN NOT NULL DEFAULT TRUE,
  metadata                JSONB DEFAULT '{}',
  created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT cs_shares_sum CHECK (
    agent_share + supervisor_share + tenant_share + platform_share <= 100
  )
);
CREATE INDEX IF NOT EXISTS cs_tenant_idx ON commission_structures(tenant_id);
CREATE INDEX IF NOT EXISTS cs_tx_type_idx ON commission_structures(transaction_type);
CREATE INDEX IF NOT EXISTS cs_active_idx ON commission_structures(is_active) WHERE is_active = TRUE;

-- 14. USER NOTIFICATION PREFERENCES
CREATE TABLE IF NOT EXISTS user_notif_preferences (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id             UUID NOT NULL,
  user_id               UUID NOT NULL,
  email_enabled         BOOLEAN NOT NULL DEFAULT TRUE,
  sms_enabled           BOOLEAN NOT NULL DEFAULT TRUE,
  push_enabled          BOOLEAN NOT NULL DEFAULT TRUE,
  in_app_enabled        BOOLEAN NOT NULL DEFAULT TRUE,
  whatsapp_enabled      BOOLEAN NOT NULL DEFAULT FALSE,
  transaction_alerts    BOOLEAN NOT NULL DEFAULT TRUE,
  security_alerts       BOOLEAN NOT NULL DEFAULT TRUE,
  marketing_messages    BOOLEAN NOT NULL DEFAULT FALSE,
  report_digests        BOOLEAN NOT NULL DEFAULT TRUE,
  quiet_hours_start     TEXT,
  quiet_hours_end       TEXT,
  timezone              TEXT NOT NULL DEFAULT 'Africa/Lagos',
  language              TEXT NOT NULL DEFAULT 'en',
  custom_preferences    JSONB DEFAULT '{}',
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS unp_tenant_idx ON user_notif_preferences(tenant_id);
CREATE UNIQUE INDEX IF NOT EXISTS unp_user_tenant_uidx ON user_notif_preferences(user_id, tenant_id);

-- 15. NOTIFICATION INBOX
CREATE TABLE IF NOT EXISTS notification_inbox (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id   UUID NOT NULL,
  user_id     UUID NOT NULL,
  title       TEXT NOT NULL,
  body        TEXT NOT NULL,
  category    TEXT NOT NULL DEFAULT 'general',
  action_url  TEXT,
  icon_url    TEXT,
  status      notif_inbox_status NOT NULL DEFAULT 'unread',
  read_at     TIMESTAMPTZ,
  archived_at TIMESTAMPTZ,
  expires_at  TIMESTAMPTZ,
  metadata    JSONB DEFAULT '{}',
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ni_tenant_idx ON notification_inbox(tenant_id);
CREATE INDEX IF NOT EXISTS ni_user_idx ON notification_inbox(user_id);
CREATE INDEX IF NOT EXISTS ni_status_idx ON notification_inbox(status);
CREATE INDEX IF NOT EXISTS ni_user_status_idx ON notification_inbox(user_id, status);

-- 16. SYSTEM SETTINGS
CREATE TABLE IF NOT EXISTS system_settings (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  key               TEXT NOT NULL,
  value             JSONB NOT NULL,
  description       TEXT,
  is_secret         BOOLEAN NOT NULL DEFAULT FALSE,
  is_editable       BOOLEAN NOT NULL DEFAULT TRUE,
  category          TEXT NOT NULL DEFAULT 'general',
  last_modified_by  UUID,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS ss_key_uidx ON system_settings(key);
CREATE INDEX IF NOT EXISTS ss_category_idx ON system_settings(category);

-- 17. TENANT SETTINGS
CREATE TABLE IF NOT EXISTS tenant_settings (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id         UUID NOT NULL,
  key               TEXT NOT NULL,
  value             JSONB NOT NULL,
  description       TEXT,
  is_secret         BOOLEAN NOT NULL DEFAULT FALSE,
  category          TEXT NOT NULL DEFAULT 'general',
  last_modified_by  UUID,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ts_tenant_idx ON tenant_settings(tenant_id);
CREATE UNIQUE INDEX IF NOT EXISTS ts_tenant_key_uidx ON tenant_settings(tenant_id, key);

-- 18. AUDIT LOGS (canonical)
CREATE TABLE IF NOT EXISTS audit_logs (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id   UUID NOT NULL,
  actor_id    UUID,
  actor_type  TEXT,
  action      TEXT NOT NULL,
  resource    TEXT NOT NULL,
  resource_id TEXT,
  outcome     TEXT NOT NULL DEFAULT 'success',
  ip_address  TEXT,
  user_agent  TEXT,
  request_id  TEXT,
  session_id  TEXT,
  before      JSONB,
  after       JSONB,
  diff        JSONB,
  metadata    JSONB DEFAULT '{}',
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS al_tenant_idx ON audit_logs(tenant_id);
CREATE INDEX IF NOT EXISTS al_actor_idx ON audit_logs(actor_id);
CREATE INDEX IF NOT EXISTS al_resource_idx ON audit_logs(resource, resource_id);
CREATE INDEX IF NOT EXISTS al_action_idx ON audit_logs(action);
CREATE INDEX IF NOT EXISTS al_created_at_idx ON audit_logs(created_at DESC);

-- ─── Updated_at triggers for all new tables ───────────────────────────────────
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

DO $$ DECLARE
  tbl TEXT;
BEGIN
  FOREACH tbl IN ARRAY ARRAY[
    'roles','agent_float_accounts','agent_float_insurance_claims',
    'agent_clusters','agent_cluster_members','agent_gamification',
    'agent_hierarchy','tb_accounts','bnpl_transactions','bnpl_repayments',
    'loan_applications','settlements','aml_screening_results',
    'commission_structures','user_notif_preferences','notification_inbox',
    'system_settings','tenant_settings'
  ] LOOP
    EXECUTE format(
      'DROP TRIGGER IF EXISTS trg_%s_updated_at ON %I;
       CREATE TRIGGER trg_%s_updated_at
       BEFORE UPDATE ON %I
       FOR EACH ROW EXECUTE FUNCTION set_updated_at();',
      tbl, tbl, tbl, tbl
    );
  END LOOP;
END $$;
