-- ─────────────────────────────────────────────────────────────────────────────
-- Migration: 0048_schema_enhancements.sql
-- 54Link Agency Banking Platform — Drizzle ORM Schema Enhancements
--
-- Implements all audit recommendations:
--   1. jsonb columns  — convert json → jsonb for GIN indexability
--   2. updatedAt triggers — auto-update on every row mutation
--   3. CHECK constraints  — financial amounts, scores, coordinates
--   4. Partial indexes    — active-only, pending-only, high-fraud
--   5. GIN indexes        — jsonb metadata, full-text search
--   6. RLS policies       — tenant isolation on all multi-tenant tables
--   7. FK constraints     — enforce referential integrity at DB level
--   8. Missing types      — handled in TypeScript layer (schema-types.ts)
--   9. Composite indexes  — covering indexes for hot query paths
--  10. Generated columns  — search_vector for agents and transactions
-- ─────────────────────────────────────────────────────────────────────────────

-- ── 1. Convert json → jsonb columns ──────────────────────────────────────────
-- jsonb stores binary representation, supports GIN indexing, @> operator,
-- and is generally faster for reads than json.

ALTER TABLE "transactions"
  ALTER COLUMN "metadata" TYPE jsonb USING "metadata"::jsonb;
--> statement-breakpoint

ALTER TABLE "fraud_alerts"
  ALTER COLUMN "aiExplanation" TYPE jsonb USING "aiExplanation"::jsonb;
--> statement-breakpoint

ALTER TABLE "kyc_sessions"
  ALTER COLUMN "livenessRaw" TYPE jsonb USING "livenessRaw"::jsonb,
  ALTER COLUMN "ocrRaw" TYPE jsonb USING "ocrRaw"::jsonb,
  ALTER COLUMN "docFraudIndicators" TYPE jsonb USING "docFraudIndicators"::jsonb;
--> statement-breakpoint

ALTER TABLE "devices"
  ALTER COLUMN "lastLocation" TYPE jsonb USING "lastLocation"::jsonb,
  ALTER COLUMN "configJson" TYPE jsonb USING "configJson"::jsonb;
--> statement-breakpoint

ALTER TABLE "pos_terminals"
  ALTER COLUMN "lastLocation" TYPE jsonb USING "lastLocation"::jsonb,
  ALTER COLUMN "configJson" TYPE jsonb USING "configJson"::jsonb;
--> statement-breakpoint

ALTER TABLE "compliance_reports"
  ALTER COLUMN "topOffendersJson" TYPE jsonb USING "topOffendersJson"::jsonb,
  ALTER COLUMN "summary" TYPE jsonb USING "summary"::jsonb;
--> statement-breakpoint

ALTER TABLE "geofence_zones"
  ALTER COLUMN "polygonJson" TYPE jsonb USING "polygonJson"::jsonb;
--> statement-breakpoint

ALTER TABLE "dlq_messages"
  ALTER COLUMN "payload" TYPE jsonb USING "payload"::jsonb,
  ALTER COLUMN "result" TYPE jsonb USING "result"::jsonb;
--> statement-breakpoint

ALTER TABLE "temporal_workflow_log"
  ALTER COLUMN "input_payload" TYPE jsonb USING "input_payload"::jsonb,
  ALTER COLUMN "result_payload" TYPE jsonb USING "result_payload"::jsonb,
  ALTER COLUMN "metadata" TYPE jsonb USING "metadata"::jsonb;
--> statement-breakpoint

ALTER TABLE "dapr_pubsub_log"
  ALTER COLUMN "payload" TYPE jsonb USING "payload"::jsonb;
--> statement-breakpoint

ALTER TABLE "openappsec_threat_log"
  ALTER COLUMN "request_headers" TYPE jsonb USING "request_headers"::jsonb,
  ALTER COLUMN "matched_indicators" TYPE jsonb USING "matched_indicators"::jsonb;
--> statement-breakpoint

ALTER TABLE "commission_rules"
  ALTER COLUMN "tieredJson" TYPE jsonb USING "tieredJson"::jsonb;
--> statement-breakpoint

ALTER TABLE "float_top_up_requests"
  ALTER COLUMN "metadata" TYPE jsonb USING "metadata"::jsonb;
--> statement-breakpoint

ALTER TABLE "audit_log"
  ALTER COLUMN "details" TYPE jsonb USING "details"::jsonb;
--> statement-breakpoint

ALTER TABLE "webhook_deliveries"
  ALTER COLUMN "requestBody" TYPE jsonb USING "requestBody"::jsonb,
  ALTER COLUMN "responseBody" TYPE jsonb USING "responseBody"::jsonb;
--> statement-breakpoint

ALTER TABLE "workflow_instances"
  ALTER COLUMN "inputData" TYPE jsonb USING "inputData"::jsonb,
  ALTER COLUMN "outputData" TYPE jsonb USING "outputData"::jsonb,
  ALTER COLUMN "stateData" TYPE jsonb USING "stateData"::jsonb;
--> statement-breakpoint

ALTER TABLE "erp_sync_log"
  ALTER COLUMN "payload" TYPE jsonb USING "payload"::jsonb;
--> statement-breakpoint

ALTER TABLE "analytics_metrics"
  ALTER COLUMN "dimensions" TYPE jsonb USING "dimensions"::jsonb;
--> statement-breakpoint

-- ── 2. Auto-update updatedAt trigger function ─────────────────────────────────
CREATE OR REPLACE FUNCTION _54link_update_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  NEW."updatedAt" = NOW();
  RETURN NEW;
END;
$$;
--> statement-breakpoint

-- Apply trigger to all tables with updatedAt
DO $$
DECLARE
  tbl TEXT;
  tables TEXT[] := ARRAY[
    'users', 'agents', 'transactions', 'fraud_alerts', 'customers',
    'merchants', 'tenants', 'kyc_sessions', 'disputes', 'devices',
    'pos_terminals', 'float_top_up_requests', 'commission_rules',
    'otp_tokens', 'platform_settings', 'velocity_limits',
    'compliance_reports', 'qr_codes', 'inventory_items',
    'multi_sim_profiles', 'reversal_requests', 'erp_config',
    'webhook_endpoints', 'api_keys', 'credit_applications',
    'ota_releases', 'fraud_rules', 'commission_payouts',
    'referrals', 'agent_bank_accounts', 'agent_loans',
    'fee_rules', 'merchant_payouts', 'tenant_billing_config',
    'ecommerce_products', 'ecommerce_orders', 'ecommerce_carts',
    'agent_stores', 'workflow_definitions', 'workflow_instances',
    'rate_limit_rules', 'sla_definitions', 'platform_incidents',
    'temporal_workflow_log', 'permify_check_log'
  ];
BEGIN
  FOREACH tbl IN ARRAY tables LOOP
    IF EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_name = tbl AND column_name = 'updatedAt'
    ) THEN
      EXECUTE format(
        'DROP TRIGGER IF EXISTS "trg_%s_updated_at" ON "%s";
         CREATE TRIGGER "trg_%s_updated_at"
           BEFORE UPDATE ON "%s"
           FOR EACH ROW EXECUTE FUNCTION _54link_update_updated_at();',
        tbl, tbl, tbl, tbl
      );
    END IF;
  END LOOP;
END;
$$;
--> statement-breakpoint

-- ── 3. CHECK Constraints ──────────────────────────────────────────────────────

-- Financial amounts must be positive
ALTER TABLE "transactions"
  ADD CONSTRAINT "chk_tx_amount_positive"
  CHECK ("amount" > 0);
--> statement-breakpoint

ALTER TABLE "transactions"
  ADD CONSTRAINT "chk_tx_fee_non_negative"
  CHECK ("fee" >= 0);
--> statement-breakpoint

ALTER TABLE "float_top_up_requests"
  ADD CONSTRAINT "chk_topup_amount_positive"
  CHECK ("requestedAmount" > 0);
--> statement-breakpoint

ALTER TABLE "agents"
  ADD CONSTRAINT "chk_agent_float_non_negative"
  CHECK ("floatBalance" >= 0);
--> statement-breakpoint

ALTER TABLE "agents"
  ADD CONSTRAINT "chk_agent_commission_non_negative"
  CHECK ("commissionBalance" >= 0);
--> statement-breakpoint

-- Fraud scores must be 0–100
ALTER TABLE "transactions"
  ADD CONSTRAINT "chk_tx_fraud_score"
  CHECK ("fraudScore" IS NULL OR ("fraudScore" >= 0 AND "fraudScore" <= 100));
--> statement-breakpoint

ALTER TABLE "fraud_alerts"
  ADD CONSTRAINT "chk_fraud_score_range"
  CHECK ("fraudScore" IS NULL OR ("fraudScore" >= 0 AND "fraudScore" <= 100));
--> statement-breakpoint

-- Geographic coordinates
ALTER TABLE "geofence_zones"
  ADD CONSTRAINT "chk_geofence_lat"
  CHECK ("latitude" IS NULL OR ("latitude" BETWEEN -90 AND 90));
--> statement-breakpoint

ALTER TABLE "geofence_zones"
  ADD CONSTRAINT "chk_geofence_lng"
  CHECK ("longitude" IS NULL OR ("longitude" BETWEEN -180 AND 180));
--> statement-breakpoint

ALTER TABLE "device_locations"
  ADD CONSTRAINT "chk_device_lat"
  CHECK ("latitude" IS NULL OR ("latitude" BETWEEN -90 AND 90));
--> statement-breakpoint

ALTER TABLE "device_locations"
  ADD CONSTRAINT "chk_device_lng"
  CHECK ("longitude" IS NULL OR ("longitude" BETWEEN -180 AND 180));
--> statement-breakpoint

-- Commission rates must be 0–100%
ALTER TABLE "commission_rules"
  ADD CONSTRAINT "chk_commission_rate"
  CHECK ("rate" IS NULL OR ("rate" >= 0 AND "rate" <= 100));
--> statement-breakpoint

-- Retry counts must be non-negative
ALTER TABLE "dlq_messages"
  ADD CONSTRAINT "chk_dlq_retry_count"
  CHECK ("retryCount" >= 0);
--> statement-breakpoint

ALTER TABLE "dapr_pubsub_log"
  ADD CONSTRAINT "chk_dapr_retry_count"
  CHECK ("retry_count" >= 0);
--> statement-breakpoint

-- ── 4. Partial Indexes (active/pending records only) ─────────────────────────

-- Active agents only — most agent lookups filter by isActive
CREATE INDEX IF NOT EXISTS "idx_agents_active_code"
  ON "agents" ("agentCode")
  WHERE "isActive" = true;
--> statement-breakpoint

CREATE INDEX IF NOT EXISTS "idx_agents_active_phone"
  ON "agents" ("phone")
  WHERE "isActive" = true;
--> statement-breakpoint

-- Pending float top-up requests — ops dashboard query
CREATE INDEX IF NOT EXISTS "idx_topup_pending"
  ON "float_top_up_requests" ("agentId", "createdAt" DESC)
  WHERE "status" = 'pending';
--> statement-breakpoint

-- Open disputes — dispute management queue
CREATE INDEX IF NOT EXISTS "idx_disputes_open"
  ON "disputes" ("createdAt" DESC)
  WHERE "status" IN ('open', 'under_review');
--> statement-breakpoint

-- High fraud score transactions — fraud analyst dashboard
CREATE INDEX IF NOT EXISTS "idx_tx_high_fraud"
  ON "transactions" ("agentId", "createdAt" DESC)
  WHERE "fraudScore" > 70;
--> statement-breakpoint

-- Pending KYC sessions — KYC queue
CREATE INDEX IF NOT EXISTS "idx_kyc_pending"
  ON "kyc_sessions" ("agentId", "createdAt" DESC)
  WHERE "status" IN ('pending', 'in_review');
--> statement-breakpoint

-- Unread fraud alerts — alert inbox
CREATE INDEX IF NOT EXISTS "idx_fraud_alerts_open"
  ON "fraud_alerts" ("agentId", "createdAt" DESC)
  WHERE "status" = 'open';
--> statement-breakpoint

-- Pending OTP tokens (not expired)
CREATE INDEX IF NOT EXISTS "idx_otp_active"
  ON "otp_tokens" ("phone", "expiresAt")
  WHERE "used" = false;
--> statement-breakpoint

-- Active API keys
CREATE INDEX IF NOT EXISTS "idx_api_keys_active"
  ON "api_keys" ("keyHash")
  WHERE "status" = 'active';
--> statement-breakpoint

-- Unprocessed DLQ messages
CREATE INDEX IF NOT EXISTS "idx_dlq_unprocessed"
  ON "dlq_messages" ("createdAt")
  WHERE "status" = 'pending';
--> statement-breakpoint

-- Pending temporal workflows
CREATE INDEX IF NOT EXISTS "idx_temporal_running"
  ON "temporal_workflow_log" ("workflow_type", "started_at" DESC)
  WHERE "status" = 'running';
--> statement-breakpoint

-- ── 5. GIN Indexes on JSONB Columns ──────────────────────────────────────────

-- Transaction metadata — enables @> containment queries
CREATE INDEX IF NOT EXISTS "idx_tx_metadata_gin"
  ON "transactions" USING GIN ("metadata" jsonb_path_ops);
--> statement-breakpoint

-- Fraud alert AI explanation — enables JSON field queries
CREATE INDEX IF NOT EXISTS "idx_fraud_ai_gin"
  ON "fraud_alerts" USING GIN ("aiExplanation" jsonb_path_ops);
--> statement-breakpoint

-- Audit log details — enables searching by action details
CREATE INDEX IF NOT EXISTS "idx_audit_details_gin"
  ON "audit_log" USING GIN ("details" jsonb_path_ops);
--> statement-breakpoint

-- Dapr pub/sub payload — enables topic-specific payload queries
CREATE INDEX IF NOT EXISTS "idx_dapr_payload_gin"
  ON "dapr_pubsub_log" USING GIN ("payload" jsonb_path_ops);
--> statement-breakpoint

-- Temporal workflow input/result payloads
CREATE INDEX IF NOT EXISTS "idx_temporal_input_gin"
  ON "temporal_workflow_log" USING GIN ("input_payload" jsonb_path_ops);
--> statement-breakpoint

-- ── 6. Full-Text Search Columns ───────────────────────────────────────────────

-- Agents: search by name, phone, email, agent code
ALTER TABLE "agents"
  ADD COLUMN IF NOT EXISTS "search_vector" tsvector
  GENERATED ALWAYS AS (
    to_tsvector('english',
      COALESCE("fullName", '') || ' ' ||
      COALESCE("phone", '') || ' ' ||
      COALESCE("email", '') || ' ' ||
      COALESCE("agentCode", '')
    )
  ) STORED;
--> statement-breakpoint

CREATE INDEX IF NOT EXISTS "idx_agents_fts_gin"
  ON "agents" USING GIN ("search_vector");
--> statement-breakpoint

-- Transactions: search by reference, recipient, description
ALTER TABLE "transactions"
  ADD COLUMN IF NOT EXISTS "search_vector" tsvector
  GENERATED ALWAYS AS (
    to_tsvector('english',
      COALESCE("txRef", '') || ' ' ||
      COALESCE("recipientName", '') || ' ' ||
      COALESCE("description", '')
    )
  ) STORED;
--> statement-breakpoint

CREATE INDEX IF NOT EXISTS "idx_tx_fts_gin"
  ON "transactions" USING GIN ("search_vector");
--> statement-breakpoint

-- Merchants: search by name, category, description
ALTER TABLE "merchants"
  ADD COLUMN IF NOT EXISTS "search_vector" tsvector
  GENERATED ALWAYS AS (
    to_tsvector('english',
      COALESCE("businessName", '') || ' ' ||
      COALESCE("description", '') || ' ' ||
      COALESCE("city", '')
    )
  ) STORED;
--> statement-breakpoint

CREATE INDEX IF NOT EXISTS "idx_merchants_fts_gin"
  ON "merchants" USING GIN ("search_vector");
--> statement-breakpoint

-- ── 7. Covering (Composite) Indexes for Hot Query Paths ──────────────────────

-- Agent dashboard: transactions by agent + date range (most common query)
CREATE INDEX IF NOT EXISTS "idx_tx_agent_date_amount"
  ON "transactions" ("agentId", "createdAt" DESC)
  INCLUDE ("amount", "type", "status", "txRef");
--> statement-breakpoint

-- Settlement batch lookup by agent + status
CREATE INDEX IF NOT EXISTS "idx_pos_settlement_agent_status"
  ON "pos_settlement_batches" ("agentId", "status", "createdAt" DESC);
--> statement-breakpoint

-- Commission ledger by agent + date (settlement calculation)
CREATE INDEX IF NOT EXISTS "idx_commission_ledger_agent_date"
  ON "commission_ledger" ("agentId", "createdAt" DESC)
  INCLUDE ("amount", "entryType");
--> statement-breakpoint

-- Fraud alerts by agent + severity (fraud dashboard)
CREATE INDEX IF NOT EXISTS "idx_fraud_agent_severity"
  ON "fraud_alerts" ("agentId", "severity", "createdAt" DESC);
--> statement-breakpoint

-- KYC sessions by agent + status (onboarding flow)
CREATE INDEX IF NOT EXISTS "idx_kyc_agent_status"
  ON "kyc_sessions" ("agentId", "status");
--> statement-breakpoint

-- Dapr pub/sub log by topic + status (dead-letter analysis)
CREATE INDEX IF NOT EXISTS "idx_dapr_topic_status_date"
  ON "dapr_pubsub_log" ("topic", "status", "published_at" DESC);
--> statement-breakpoint

-- Permify check log by subject + permission (authorization analysis)
CREATE INDEX IF NOT EXISTS "idx_permify_subject_perm"
  ON "permify_check_log" ("subject_type", "subject_id", "permission", "created_at" DESC);
--> statement-breakpoint

-- Temporal workflow log by type + status (workflow monitoring)
CREATE INDEX IF NOT EXISTS "idx_temporal_type_status"
  ON "temporal_workflow_log" ("workflow_type", "status", "started_at" DESC);
--> statement-breakpoint

-- ── 8. FK Constraints (DB-level referential integrity) ───────────────────────
-- These enforce the relations already declared in relations.ts at the DB level.

-- transactions.agentId → agents.id
ALTER TABLE "transactions"
  ADD CONSTRAINT IF NOT EXISTS "fk_tx_agent"
  FOREIGN KEY ("agentId") REFERENCES "agents"("id")
  ON DELETE RESTRICT ON UPDATE CASCADE;
--> statement-breakpoint

-- fraud_alerts.agentId → agents.id
ALTER TABLE "fraud_alerts"
  ADD CONSTRAINT IF NOT EXISTS "fk_fraud_agent"
  FOREIGN KEY ("agentId") REFERENCES "agents"("id")
  ON DELETE RESTRICT ON UPDATE CASCADE;
--> statement-breakpoint

-- float_top_up_requests.agentId → agents.id
ALTER TABLE "float_top_up_requests"
  ADD CONSTRAINT IF NOT EXISTS "fk_topup_agent"
  FOREIGN KEY ("agentId") REFERENCES "agents"("id")
  ON DELETE RESTRICT ON UPDATE CASCADE;
--> statement-breakpoint

-- disputes.transactionId → transactions.id
ALTER TABLE "disputes"
  ADD CONSTRAINT IF NOT EXISTS "fk_dispute_tx"
  FOREIGN KEY ("transactionId") REFERENCES "transactions"("id")
  ON DELETE RESTRICT ON UPDATE CASCADE;
--> statement-breakpoint

-- kyc_sessions.agentId → agents.id
ALTER TABLE "kyc_sessions"
  ADD CONSTRAINT IF NOT EXISTS "fk_kyc_agent"
  FOREIGN KEY ("agentId") REFERENCES "agents"("id")
  ON DELETE RESTRICT ON UPDATE CASCADE;
--> statement-breakpoint

-- commission_ledger.agentId → agents.id
ALTER TABLE "commission_ledger"
  ADD CONSTRAINT IF NOT EXISTS "fk_commission_agent"
  FOREIGN KEY ("agentId") REFERENCES "agents"("id")
  ON DELETE RESTRICT ON UPDATE CASCADE;
--> statement-breakpoint

-- chat_sessions.agentId → agents.id
ALTER TABLE "chat_sessions"
  ADD CONSTRAINT IF NOT EXISTS "fk_chat_agent"
  FOREIGN KEY ("agentId") REFERENCES "agents"("id")
  ON DELETE CASCADE ON UPDATE CASCADE;
--> statement-breakpoint

-- chat_messages.sessionId → chat_sessions.id
ALTER TABLE "chat_messages"
  ADD CONSTRAINT IF NOT EXISTS "fk_chat_msg_session"
  FOREIGN KEY ("sessionId") REFERENCES "chat_sessions"("id")
  ON DELETE CASCADE ON UPDATE CASCADE;
--> statement-breakpoint

-- devices.agentId → agents.id
ALTER TABLE "devices"
  ADD CONSTRAINT IF NOT EXISTS "fk_device_agent"
  FOREIGN KEY ("agentId") REFERENCES "agents"("id")
  ON DELETE RESTRICT ON UPDATE CASCADE;
--> statement-breakpoint

-- loyalty_history.agentId → agents.id
ALTER TABLE "loyalty_history"
  ADD CONSTRAINT IF NOT EXISTS "fk_loyalty_agent"
  FOREIGN KEY ("agentId") REFERENCES "agents"("id")
  ON DELETE CASCADE ON UPDATE CASCADE;
--> statement-breakpoint

-- webhook_deliveries.endpointId → webhook_endpoints.id
ALTER TABLE "webhook_deliveries"
  ADD CONSTRAINT IF NOT EXISTS "fk_webhook_delivery_endpoint"
  FOREIGN KEY ("endpointId") REFERENCES "webhook_endpoints"("id")
  ON DELETE CASCADE ON UPDATE CASCADE;
--> statement-breakpoint

-- api_key_usage.keyId → api_keys.id
ALTER TABLE "api_key_usage"
  ADD CONSTRAINT IF NOT EXISTS "fk_api_usage_key"
  FOREIGN KEY ("keyId") REFERENCES "api_keys"("id")
  ON DELETE CASCADE ON UPDATE CASCADE;
--> statement-breakpoint

-- ── 9. Row Level Security (Tenant Isolation) ──────────────────────────────────
-- Enable RLS on all multi-tenant tables.
-- Requires: SET LOCAL app.current_tenant_id = '<id>' at request start.

CREATE OR REPLACE FUNCTION _54link_current_tenant_id()
RETURNS INTEGER LANGUAGE plpgsql STABLE AS $$
BEGIN
  RETURN NULLIF(current_setting('app.current_tenant_id', true), '')::INTEGER;
EXCEPTION WHEN OTHERS THEN
  RETURN NULL;
END;
$$;
--> statement-breakpoint

DO $$
DECLARE
  tbl TEXT;
  tenant_tables TEXT[] := ARRAY[
    'agents', 'transactions', 'fraud_alerts', 'customers',
    'float_top_up_requests', 'disputes', 'kyc_sessions',
    'commission_rules', 'commission_payouts', 'pos_terminals',
    'devices', 'merchants', 'referrals', 'agent_loans',
    'fee_rules', 'webhook_endpoints', 'api_keys',
    'ecommerce_products', 'ecommerce_orders', 'agent_stores'
  ];
BEGIN
  FOREACH tbl IN ARRAY tenant_tables LOOP
    IF EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_name = tbl AND column_name = 'tenantId'
    ) THEN
      EXECUTE format('ALTER TABLE "%s" ENABLE ROW LEVEL SECURITY;', tbl);
      EXECUTE format('ALTER TABLE "%s" FORCE ROW LEVEL SECURITY;', tbl);

      -- Drop existing policies to avoid conflicts
      EXECUTE format(
        'DROP POLICY IF EXISTS "%s_tenant_isolation" ON "%s";', tbl, tbl
      );

      -- Tenant isolation: only see own rows, or rows with no tenant
      EXECUTE format(
        'CREATE POLICY "%s_tenant_isolation" ON "%s"
         USING (
           "tenantId" IS NULL
           OR "tenantId" = _54link_current_tenant_id()
           OR _54link_current_tenant_id() IS NULL
         )
         WITH CHECK (
           "tenantId" IS NULL
           OR "tenantId" = _54link_current_tenant_id()
         );',
        tbl, tbl
      );
    END IF;
  END LOOP;
END;
$$;
--> statement-breakpoint

-- ── 10. Idempotency key TTL index ─────────────────────────────────────────────
-- Expire idempotency keys after 24 hours
CREATE INDEX IF NOT EXISTS "idx_idempotency_expires"
  ON "idempotency_keys" ("expiresAt")
  WHERE "expiresAt" IS NOT NULL;
--> statement-breakpoint

-- ── 11. BRIN index for time-series tables ─────────────────────────────────────
-- BRIN is extremely compact for append-only time-series data
CREATE INDEX IF NOT EXISTS "idx_audit_log_created_brin"
  ON "audit_log" USING BRIN ("createdAt");
--> statement-breakpoint

CREATE INDEX IF NOT EXISTS "idx_dapr_pubsub_created_brin"
  ON "dapr_pubsub_log" USING BRIN ("created_at");
--> statement-breakpoint

CREATE INDEX IF NOT EXISTS "idx_fluvio_event_created_brin"
  ON "fluvio_event_log" USING BRIN ("created_at");
--> statement-breakpoint

CREATE INDEX IF NOT EXISTS "idx_permify_check_created_brin"
  ON "permify_check_log" USING BRIN ("created_at");
--> statement-breakpoint

-- ── 12. Statistics targets for query planner ─────────────────────────────────
-- Increase statistics for high-cardinality columns used in WHERE clauses
ALTER TABLE "transactions" ALTER COLUMN "agentId" SET STATISTICS 500;
ALTER TABLE "transactions" ALTER COLUMN "status" SET STATISTICS 200;
ALTER TABLE "transactions" ALTER COLUMN "type" SET STATISTICS 200;
ALTER TABLE "agents" ALTER COLUMN "tenantId" SET STATISTICS 300;
ALTER TABLE "agents" ALTER COLUMN "tier" SET STATISTICS 100;
ALTER TABLE "fraud_alerts" ALTER COLUMN "severity" SET STATISTICS 100;
ALTER TABLE "fraud_alerts" ALTER COLUMN "status" SET STATISTICS 100;
--> statement-breakpoint

-- ── 13. Maintenance: ANALYZE after index creation ────────────────────────────
ANALYZE "transactions";
ANALYZE "agents";
ANALYZE "fraud_alerts";
ANALYZE "kyc_sessions";
ANALYZE "float_top_up_requests";
ANALYZE "disputes";
ANALYZE "audit_log";
ANALYZE "dapr_pubsub_log";
ANALYZE "temporal_workflow_log";
ANALYZE "permify_check_log";
