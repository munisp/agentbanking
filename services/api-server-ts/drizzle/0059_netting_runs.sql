-- ─────────────────────────────────────────────────────────────────────────────
-- Migration 0059: Settlement netting run persistence
-- settlementNettingEngine.createSession previously computed netting results
-- in-memory and returned a fabricated NET-<timestamp> id with no database
-- row, so settleSession could never settle a created session. These tables
-- persist each netting run and its per-party items; createSession writes here
-- inside withTransaction and settleSession transitions the run row
-- ('calculating' → 'settled') atomically.
-- ─────────────────────────────────────────────────────────────────────────────

-- 1. Netting runs (one per createSession call)
CREATE TABLE IF NOT EXISTS netting_runs (
  id               BIGSERIAL PRIMARY KEY,
  type             VARCHAR(32) NOT NULL DEFAULT 'bilateral',
  parties          JSONB NOT NULL DEFAULT '[]'::jsonb,
  gross_amount     NUMERIC(20, 2) NOT NULL DEFAULT 0,
  fee_amount       NUMERIC(20, 2) NOT NULL DEFAULT 0,
  tax_amount       NUMERIC(20, 2) NOT NULL DEFAULT 0,
  net_amount       NUMERIC(20, 2) NOT NULL DEFAULT 0,
  savings          NUMERIC(20, 2) NOT NULL DEFAULT 0,
  status           VARCHAR(32) NOT NULL DEFAULT 'calculating', -- calculating, settled, failed, cancelled
  confirmation_ref VARCHAR(64),
  created_by       VARCHAR(128),
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  settled_at       TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_netting_runs_status ON netting_runs (status);
CREATE INDEX IF NOT EXISTS idx_netting_runs_created ON netting_runs (created_at DESC);

-- 2. Per-party netting items belonging to a run
CREATE TABLE IF NOT EXISTS netting_run_items (
  id           BIGSERIAL PRIMARY KEY,
  run_id       BIGINT NOT NULL REFERENCES netting_runs(id) ON DELETE CASCADE,
  party        VARCHAR(128) NOT NULL,
  gross_amount NUMERIC(20, 2) NOT NULL DEFAULT 0,
  fee_amount   NUMERIC(20, 2) NOT NULL DEFAULT 0,
  net_amount   NUMERIC(20, 2) NOT NULL DEFAULT 0,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_netting_run_items_run ON netting_run_items (run_id);
