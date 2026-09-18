-- 0060_kyb_results.sql
-- Persistent store for KYB verification results produced by the Go kyb-engine.
-- The engine historically kept all verification state in an in-memory map, so
-- restarts lost verification results and approvals. This table is the durable
-- system of record for verification outcomes.

CREATE TABLE IF NOT EXISTS kyb_verification_results (
    id                  TEXT PRIMARY KEY,              -- engine verification id (kyb-<ts>)
    business_name       TEXT NOT NULL,
    registration_number TEXT,
    tax_id              TEXT,
    status              VARCHAR(32) NOT NULL DEFAULT 'pending',
    risk_score          DOUBLE PRECISION,
    risk_level          VARCHAR(16),
    approved_by         TEXT,                          -- admin actor id (never 'system')
    approved_at         TIMESTAMPTZ,
    rejected_by         TEXT,
    rejection_reason    TEXT,
    payload             JSONB NOT NULL DEFAULT '{}',   -- full verification snapshot
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS kyb_results_status_idx
    ON kyb_verification_results (status);

CREATE INDEX IF NOT EXISTS kyb_results_reg_number_idx
    ON kyb_verification_results (registration_number);

-- Guard: approved rows must carry a real actor id.
ALTER TABLE kyb_verification_results
    DROP CONSTRAINT IF EXISTS kyb_results_approved_actor_chk;
ALTER TABLE kyb_verification_results
    ADD CONSTRAINT kyb_results_approved_actor_chk
    CHECK (status <> 'approved' OR (approved_by IS NOT NULL AND approved_by <> '' AND approved_by <> 'system'));
