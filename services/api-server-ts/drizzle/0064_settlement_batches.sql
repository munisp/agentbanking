-- Settlement batch integrity (audit fix):
-- durable batch records for services/settlement-batch-processor, and the
-- per-row settlement lifecycle columns its claiming UPDATE relies on.

-- Per-batch durable record (replaces the processor's in-memory-only map).
CREATE TABLE IF NOT EXISTS settlement_batches (
  batch_id         TEXT PRIMARY KEY,
  status           TEXT NOT NULL DEFAULT 'processing'
                   CONSTRAINT settlement_batches_status_chk
                   CHECK (status IN ('pending','processing','completed','failed')),
  agent_count      INTEGER NOT NULL DEFAULT 0,
  total_volume     NUMERIC(20,2) NOT NULL DEFAULT 0,
  total_fees       NUMERIC(20,2) NOT NULL DEFAULT 0,
  total_commission NUMERIC(20,2) NOT NULL DEFAULT 0,
  net_settlement   NUMERIC(20,2) NOT NULL DEFAULT 0,
  entries          JSONB NOT NULL DEFAULT '[]',
  error            TEXT,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at     TIMESTAMPTZ
);

--> statement-breakpoint

-- Per-row settlement lifecycle on the billing ledger used by the batch
-- processor: pending -> processing (claimed) -> settled (posted).
ALTER TABLE platform_billing_ledger
  ADD COLUMN IF NOT EXISTS settlement_status TEXT NOT NULL DEFAULT 'pending';

--> statement-breakpoint

ALTER TABLE platform_billing_ledger
  ADD COLUMN IF NOT EXISTS settlement_batch_id TEXT;

--> statement-breakpoint

ALTER TABLE platform_billing_ledger
  ADD COLUMN IF NOT EXISTS settled_at TIMESTAMPTZ;

--> statement-breakpoint

CREATE INDEX IF NOT EXISTS pbl_settlement_status_idx
  ON platform_billing_ledger (settlement_status);

--> statement-breakpoint

CREATE INDEX IF NOT EXISTS pbl_settlement_batch_idx
  ON platform_billing_ledger (settlement_batch_id);
