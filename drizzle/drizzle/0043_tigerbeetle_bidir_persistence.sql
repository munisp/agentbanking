-- TigerBeetle Bi-Directional Persistence Migration
-- Adds all PostgreSQL tables needed for TB<->PG bi-directional sync

-- Go tigerbeetle-core: accounts + transfers
CREATE TABLE IF NOT EXISTS "tb_accounts" (
  "id" BIGINT PRIMARY KEY,
  "user_data" BIGINT NOT NULL DEFAULT 0,
  "ledger" INT NOT NULL DEFAULT 0,
  "code" SMALLINT NOT NULL DEFAULT 0,
  "flags" SMALLINT NOT NULL DEFAULT 0,
  "debits_pending" BIGINT NOT NULL DEFAULT 0,
  "debits_posted" BIGINT NOT NULL DEFAULT 0,
  "credits_pending" BIGINT NOT NULL DEFAULT 0,
  "credits_posted" BIGINT NOT NULL DEFAULT 0,
  "created_at" TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  "updated_at" TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "idx_tb_accounts_ledger" ON "tb_accounts"("ledger");
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "idx_tb_accounts_code" ON "tb_accounts"("code");
--> statement-breakpoint

CREATE TABLE IF NOT EXISTS "tb_transfers" (
  "id" BIGINT PRIMARY KEY,
  "debit_account_id" BIGINT NOT NULL,
  "credit_account_id" BIGINT NOT NULL,
  "amount" BIGINT NOT NULL DEFAULT 0,
  "user_data" BIGINT NOT NULL DEFAULT 0,
  "ledger" INT NOT NULL DEFAULT 0,
  "code" SMALLINT NOT NULL DEFAULT 0,
  "flags" SMALLINT NOT NULL DEFAULT 0,
  "timestamp" BIGINT NOT NULL DEFAULT 0,
  "created_at" TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "idx_tb_transfers_debit" ON "tb_transfers"("debit_account_id");
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "idx_tb_transfers_credit" ON "tb_transfers"("credit_account_id");
--> statement-breakpoint

-- Go tigerbeetle-edge: offline-first edge transfers
CREATE TABLE IF NOT EXISTS "edge_transfers" (
  "id" BIGINT PRIMARY KEY,
  "debit_account_id" BIGINT NOT NULL,
  "credit_account_id" BIGINT NOT NULL,
  "amount" BIGINT NOT NULL DEFAULT 0,
  "ledger" INT NOT NULL DEFAULT 0,
  "code" SMALLINT NOT NULL DEFAULT 0,
  "agent_code" TEXT,
  "reference" TEXT,
  "sync_status" TEXT NOT NULL DEFAULT 'pending',
  "created_at" TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  "synced_at" TIMESTAMPTZ
);
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "idx_edge_transfers_sync" ON "edge_transfers"("sync_status");
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "idx_edge_transfers_agent" ON "edge_transfers"("agent_code");
--> statement-breakpoint

-- Go tigerbeetle-integrated (sidecar): transfer metadata write-back
CREATE TABLE IF NOT EXISTS "tb_transfer_metadata" (
  "id" SERIAL PRIMARY KEY,
  "transfer_ref" TEXT UNIQUE NOT NULL,
  "debit_account" TEXT NOT NULL,
  "credit_account" TEXT NOT NULL,
  "amount" BIGINT NOT NULL,
  "ledger" INT NOT NULL DEFAULT 0,
  "code" INT NOT NULL DEFAULT 0,
  "agent_code" TEXT,
  "tx_type" TEXT,
  "reference" TEXT,
  "tb_committed" BOOLEAN NOT NULL DEFAULT false,
  "pg_written" BOOLEAN NOT NULL DEFAULT true,
  "created_at" TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "idx_tb_meta_agent" ON "tb_transfer_metadata"("agent_code");
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "idx_tb_meta_committed" ON "tb_transfer_metadata"("tb_committed");
--> statement-breakpoint

CREATE TABLE IF NOT EXISTS "tb_agent_accounts" (
  "agent_code" TEXT PRIMARY KEY,
  "tb_account_id" TEXT NOT NULL,
  "created_at" TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
--> statement-breakpoint

-- Rust bridge: transfer persistence + metrics
CREATE TABLE IF NOT EXISTS "tb_bridge_transfers" (
  "id" TEXT PRIMARY KEY,
  "debit_account_id" TEXT NOT NULL,
  "credit_account_id" TEXT NOT NULL,
  "amount" BIGINT NOT NULL,
  "currency" TEXT NOT NULL DEFAULT 'NGN',
  "ledger" INT NOT NULL DEFAULT 0,
  "code" SMALLINT NOT NULL DEFAULT 0,
  "reference" TEXT,
  "agent_code" TEXT,
  "tx_type" TEXT,
  "metadata" JSONB,
  "kafka_published" BOOLEAN NOT NULL DEFAULT false,
  "redis_cached" BOOLEAN NOT NULL DEFAULT false,
  "opensearch_indexed" BOOLEAN NOT NULL DEFAULT false,
  "lakehouse_exported" BOOLEAN NOT NULL DEFAULT false,
  "created_at" TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "idx_tbt_agent" ON "tb_bridge_transfers"("agent_code");
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "idx_tbt_created" ON "tb_bridge_transfers"("created_at");
--> statement-breakpoint

CREATE TABLE IF NOT EXISTS "tb_bridge_metrics_log" (
  "id" SERIAL PRIMARY KEY,
  "transfers_processed" BIGINT NOT NULL DEFAULT 0,
  "kafka_produced" BIGINT NOT NULL DEFAULT 0,
  "redis_updates" BIGINT NOT NULL DEFAULT 0,
  "opensearch_indexed" BIGINT NOT NULL DEFAULT 0,
  "pg_persisted" BIGINT NOT NULL DEFAULT 0,
  "recorded_at" TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
--> statement-breakpoint

-- Python tigerbeetle-zig: account mapping + balance tracking
CREATE TABLE IF NOT EXISTS "tb_zig_account_map" (
  "user_id" TEXT PRIMARY KEY,
  "account_id" TEXT NOT NULL,
  "account_type" TEXT NOT NULL,
  "created_at" TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
--> statement-breakpoint

CREATE TABLE IF NOT EXISTS "tb_zig_accounts" (
  "account_id" TEXT PRIMARY KEY,
  "user_id" TEXT NOT NULL,
  "account_type" TEXT NOT NULL,
  "ledger" INT NOT NULL DEFAULT 1,
  "code" INT NOT NULL DEFAULT 1,
  "flags" INT NOT NULL DEFAULT 0,
  "initial_balance_kobo" BIGINT NOT NULL DEFAULT 0,
  "credits_posted" BIGINT NOT NULL DEFAULT 0,
  "debits_posted" BIGINT NOT NULL DEFAULT 0,
  "credits_pending" BIGINT NOT NULL DEFAULT 0,
  "debits_pending" BIGINT NOT NULL DEFAULT 0,
  "created_at" TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  "updated_at" TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
--> statement-breakpoint

CREATE TABLE IF NOT EXISTS "tb_zig_transfers" (
  "transfer_id" TEXT PRIMARY KEY,
  "from_account_id" TEXT NOT NULL,
  "to_account_id" TEXT NOT NULL,
  "amount_kobo" BIGINT NOT NULL,
  "transfer_code" INT NOT NULL,
  "description" TEXT,
  "status" TEXT NOT NULL DEFAULT 'completed',
  "idempotency_key" TEXT,
  "created_at" TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "idx_tzx_from" ON "tb_zig_transfers"("from_account_id");
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "idx_tzx_to" ON "tb_zig_transfers"("to_account_id");
--> statement-breakpoint

-- Go settlement-ledger-sync: billing entries + settlement batches
CREATE TABLE IF NOT EXISTS "billing_ledger_entries" (
  "id" SERIAL PRIMARY KEY,
  "transaction_id" TEXT UNIQUE NOT NULL,
  "agent_id" TEXT NOT NULL,
  "client_id" TEXT NOT NULL,
  "transaction_type" TEXT NOT NULL,
  "gross_amount" BIGINT NOT NULL,
  "gross_fee" BIGINT NOT NULL DEFAULT 0,
  "platform_share" BIGINT NOT NULL DEFAULT 0,
  "client_share" BIGINT NOT NULL DEFAULT 0,
  "agent_commission" BIGINT NOT NULL DEFAULT 0,
  "currency" TEXT NOT NULL DEFAULT 'NGN',
  "billing_model" TEXT NOT NULL DEFAULT 'revenue_share',
  "sync_status" TEXT NOT NULL DEFAULT 'pending',
  "processed_at" TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  "synced_at" TIMESTAMPTZ
);
--> statement-breakpoint

-- Go CDC: watermarks + event log
CREATE TABLE IF NOT EXISTS "cdc_watermarks" (
  "table_name" TEXT PRIMARY KEY,
  "last_processed_at" TIMESTAMPTZ NOT NULL DEFAULT '1970-01-01',
  "events_emitted" BIGINT NOT NULL DEFAULT 0,
  "updated_at" TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
--> statement-breakpoint

CREATE TABLE IF NOT EXISTS "cdc_event_log" (
  "id" SERIAL PRIMARY KEY,
  "source_table" TEXT NOT NULL,
  "source_key" TEXT NOT NULL,
  "operation" TEXT NOT NULL,
  "published" BOOLEAN NOT NULL DEFAULT false,
  "created_at" TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "idx_cdc_log_created" ON "cdc_event_log"("created_at");
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "idx_cdc_log_published" ON "cdc_event_log"("published");
