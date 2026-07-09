-- Settlement & Reconciliation Engine — PostgreSQL Persistence Tables
-- All polyglot services (Go, Rust, Python, TypeScript) auto-create tables on startup,
-- but this migration ensures schema consistency across environments.

-- Go settlement-batch-processor (port 9211)
CREATE TABLE IF NOT EXISTS "settlement_batches" (
    "batch_id" TEXT PRIMARY KEY,
    "status" TEXT NOT NULL DEFAULT 'pending',
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    "completed_at" TIMESTAMPTZ,
    "agent_count" INT NOT NULL DEFAULT 0,
    "total_volume" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "total_fees" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "total_commission" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "net_settlement" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "entries_json" JSONB NOT NULL DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS "idx_settlement_batches_status" ON "settlement_batches"("status");
CREATE INDEX IF NOT EXISTS "idx_settlement_batches_created" ON "settlement_batches"("created_at" DESC);

-- Go revenue-reconciler (port 9101)
CREATE TABLE IF NOT EXISTS "reconciliation_reports" (
    "id" BIGINT PRIMARY KEY,
    "period" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'pending',
    "projected_json" JSONB NOT NULL DEFAULT '{}',
    "actual_json" JSONB NOT NULL DEFAULT '{}',
    "revenue_variance_pct" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "volume_variance_pct" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "agent_variance_pct" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "insights_json" JSONB NOT NULL DEFAULT '[]',
    "generated_at" TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    "approved_by" TEXT,
    "approved_at" TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS "idx_recon_reports_period" ON "reconciliation_reports"("period");
CREATE INDEX IF NOT EXISTS "idx_recon_reports_status" ON "reconciliation_reports"("status");

CREATE TABLE IF NOT EXISTS "discrepancy_alerts" (
    "id" SERIAL PRIMARY KEY,
    "period" TEXT NOT NULL,
    "metric" TEXT NOT NULL,
    "projected" DOUBLE PRECISION NOT NULL,
    "actual" DOUBLE PRECISION NOT NULL,
    "variance_pct" DOUBLE PRECISION NOT NULL,
    "severity" TEXT NOT NULL DEFAULT 'warning',
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS "idx_discrepancy_severity" ON "discrepancy_alerts"("severity");

-- Rust fund-flow-settlement (port 8251)
CREATE TABLE IF NOT EXISTS "fx_rates" (
    "corridor" TEXT PRIMARY KEY,
    "from_currency" TEXT NOT NULL,
    "to_currency" TEXT NOT NULL,
    "rate" DOUBLE PRECISION NOT NULL,
    "spread_bps" INT NOT NULL,
    "effective_rate" DOUBLE PRECISION NOT NULL,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS "installment_schedules" (
    "application_id" BIGINT PRIMARY KEY,
    "schedule_json" JSONB NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS "reconciliation_results" (
    "id" UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "agent_id" BIGINT NOT NULL,
    "float_balance" DOUBLE PRECISION NOT NULL,
    "gl_net" DOUBLE PRECISION NOT NULL,
    "transaction_total" DOUBLE PRECISION NOT NULL,
    "discrepancy" DOUBLE PRECISION NOT NULL,
    "is_reconciled" BOOLEAN NOT NULL,
    "recommendations" JSONB NOT NULL DEFAULT '[]',
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS "idx_recon_results_agent" ON "reconciliation_results"("agent_id");

CREATE TABLE IF NOT EXISTS "settlement_batches_rust" (
    "batch_id" TEXT PRIMARY KEY,
    "total_settlements" INT NOT NULL DEFAULT 0,
    "total_amount" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "status" TEXT NOT NULL DEFAULT 'initiated',
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Billing projections (for revenue-reconciler real data queries)
CREATE TABLE IF NOT EXISTS "billing_projections" (
    "id" SERIAL PRIMARY KEY,
    "period" TEXT NOT NULL,
    "agent_id" BIGINT NOT NULL,
    "projected_tx_count" BIGINT NOT NULL DEFAULT 0,
    "projected_volume" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "projected_platform_revenue" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "projected_client_revenue" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS "idx_billing_projections_period" ON "billing_projections"("period");
