-- ─────────────────────────────────────────────────────────────────────────────
-- Migration: 0047_middleware_integration_audit.sql
-- 54Link Agency Banking Platform — Middleware Integration Audit Tables
--
-- Adds dedicated audit/log tables for all integrated middleware services:
--   1. temporal_workflow_log    — Temporal workflow execution history
--   2. permify_check_log        — Permify fine-grained authorization audit trail
--   3. openappsec_threat_log    — OpenAppSec WAF threat events
--   4. fluvio_event_log         — Fluvio real-time streaming event log
--   5. lakehouse_sync_log       — Lakehouse (MinIO/Iceberg) export sync log
--   6. dapr_pubsub_log          — Dapr pub/sub message audit trail
-- ─────────────────────────────────────────────────────────────────────────────

-- ── 1. Temporal Workflow Log ──────────────────────────────────────────────────
-- Tracks the execution history of all Temporal workflows for audit and replay.
CREATE TABLE IF NOT EXISTS "temporal_workflow_log" (
  "id"                  BIGSERIAL PRIMARY KEY,
  "workflow_id"         VARCHAR(256) NOT NULL,
  "workflow_type"       VARCHAR(128) NOT NULL,
  "run_id"              VARCHAR(128),
  "task_queue"          VARCHAR(128) NOT NULL DEFAULT 'settlement-queue',
  "namespace"           VARCHAR(64)  NOT NULL DEFAULT 'default',
  "status"              VARCHAR(32)  NOT NULL DEFAULT 'running',
    -- 'running' | 'completed' | 'failed' | 'cancelled' | 'timed_out' | 'terminated'
  "input_payload"       JSONB,
  "result_payload"      JSONB,
  "error_message"       TEXT,
  "started_at"          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  "closed_at"           TIMESTAMPTZ,
  "duration_ms"         BIGINT,
  "triggered_by"        VARCHAR(128),  -- 'cron' | 'manual' | agentCode | userId
  "agent_code"          VARCHAR(32),
  "tenant_id"           INTEGER,
  "metadata"            JSONB,
  "created_at"          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  "updated_at"          TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "twl_workflow_id_idx"   ON "temporal_workflow_log"("workflow_id");
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "twl_workflow_type_idx" ON "temporal_workflow_log"("workflow_type");
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "twl_status_idx"        ON "temporal_workflow_log"("status");
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "twl_agent_idx"         ON "temporal_workflow_log"("agent_code");
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "twl_started_at_idx"    ON "temporal_workflow_log"("started_at");
--> statement-breakpoint

-- ── 2. Permify Check Log ──────────────────────────────────────────────────────
-- Maintains an audit trail of all fine-grained authorization decisions.
CREATE TABLE IF NOT EXISTS "permify_check_log" (
  "id"              BIGSERIAL PRIMARY KEY,
  "tenant_id"       VARCHAR(64)  NOT NULL DEFAULT 't1',
  "subject_type"    VARCHAR(64)  NOT NULL,
  "subject_id"      VARCHAR(128) NOT NULL,
  "entity_type"     VARCHAR(64)  NOT NULL,
  "entity_id"       VARCHAR(128) NOT NULL,
  "permission"      VARCHAR(128) NOT NULL,
  "result"          VARCHAR(32)  NOT NULL,  -- 'allowed' | 'denied' | 'error' | 'fallback_open'
  "schema_version"  VARCHAR(64),
  "snap_token"      VARCHAR(128),
  "depth"           INTEGER      NOT NULL DEFAULT 20,
  "latency_ms"      INTEGER,
  "error_message"   TEXT,
  "request_id"      VARCHAR(128),
  "ip_address"      VARCHAR(45),
  "user_agent"      TEXT,
  "created_at"      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "pcl_subject_idx"    ON "permify_check_log"("subject_type", "subject_id");
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "pcl_entity_idx"     ON "permify_check_log"("entity_type", "entity_id");
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "pcl_permission_idx" ON "permify_check_log"("permission");
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "pcl_result_idx"     ON "permify_check_log"("result");
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "pcl_created_at_idx" ON "permify_check_log"("created_at");
--> statement-breakpoint

-- ── 3. OpenAppSec Threat Log ──────────────────────────────────────────────────
-- Persists WAF threat events detected and/or blocked by the OpenAppSec agent.
CREATE TABLE IF NOT EXISTS "openappsec_threat_log" (
  "id"               BIGSERIAL PRIMARY KEY,
  "event_id"         VARCHAR(128) UNIQUE,
  "timestamp"        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  "category"         VARCHAR(64)  NOT NULL,
    -- 'sql_injection' | 'xss' | 'path_traversal' | 'command_injection'
    -- 'file_inclusion' | 'ssrf' | 'xxe' | 'deserialization' | 'bot'
    -- 'scanner' | 'credential_stuffing' | 'api_abuse' | 'geo_blocked'
  "severity"         VARCHAR(16)  NOT NULL DEFAULT 'medium',
    -- 'critical' | 'high' | 'medium' | 'low'
  "action"           VARCHAR(16)  NOT NULL DEFAULT 'detect',
    -- 'block' | 'detect' | 'allow'
  "ip_address"       VARCHAR(45)  NOT NULL,
  "method"           VARCHAR(16),
  "path"             TEXT,
  "query_string"     TEXT,
  "user_agent"       TEXT,
  "payload_snippet"  TEXT,
  "threat_score"     INTEGER      NOT NULL DEFAULT 0,
  "country_code"     VARCHAR(2),
  "request_id"       VARCHAR(128),
  "agent_id"         VARCHAR(128),
  "policy_name"      VARCHAR(128),
  "rule_name"        VARCHAR(128),
  "blocked"          BOOLEAN      NOT NULL DEFAULT FALSE,
  "response_code"    INTEGER,
  "metadata"         JSONB,
  "created_at"       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "oatl_category_idx"   ON "openappsec_threat_log"("category");
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "oatl_severity_idx"   ON "openappsec_threat_log"("severity");
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "oatl_ip_idx"         ON "openappsec_threat_log"("ip_address");
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "oatl_blocked_idx"    ON "openappsec_threat_log"("blocked");
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "oatl_timestamp_idx"  ON "openappsec_threat_log"("timestamp");
--> statement-breakpoint

-- ── 4. Fluvio Event Log ───────────────────────────────────────────────────────
-- Records critical events streamed through Fluvio for reconciliation and replay.
CREATE TABLE IF NOT EXISTS "fluvio_event_log" (
  "id"              BIGSERIAL PRIMARY KEY,
  "topic"           VARCHAR(128) NOT NULL,
  "partition"       INTEGER      NOT NULL DEFAULT 0,
  "offset"          BIGINT,
  "key"             VARCHAR(256),
  "payload"         JSONB        NOT NULL,
  "event_type"      VARCHAR(64),
    -- 'tx.created' | 'fraud.alert' | 'mdm.heartbeat' | 'settlement.event'
  "agent_code"      VARCHAR(32),
  "tx_ref"          VARCHAR(128),
  "status"          VARCHAR(32)  NOT NULL DEFAULT 'produced',
    -- 'produced' | 'consumed' | 'failed' | 'dead_letter'
  "error_message"   TEXT,
  "retry_count"     INTEGER      NOT NULL DEFAULT 0,
  "produced_at"     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  "consumed_at"     TIMESTAMPTZ,
  "created_at"      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "fel_topic_idx"      ON "fluvio_event_log"("topic");
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "fel_event_type_idx" ON "fluvio_event_log"("event_type");
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "fel_agent_idx"      ON "fluvio_event_log"("agent_code");
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "fel_tx_ref_idx"     ON "fluvio_event_log"("tx_ref");
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "fel_status_idx"     ON "fluvio_event_log"("status");
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "fel_produced_at_idx" ON "fluvio_event_log"("produced_at");
--> statement-breakpoint

-- ── 5. Lakehouse Sync Log ─────────────────────────────────────────────────────
-- Tracks the status of batch exports from PostgreSQL to MinIO/Iceberg lakehouse.
CREATE TABLE IF NOT EXISTS "lakehouse_sync_log" (
  "id"              BIGSERIAL PRIMARY KEY,
  "job_id"          VARCHAR(128) UNIQUE NOT NULL,
  "bucket"          VARCHAR(128) NOT NULL,
  "object_key"      TEXT         NOT NULL,
  "format"          VARCHAR(16)  NOT NULL DEFAULT 'parquet',
    -- 'parquet' | 'json' | 'csv' | 'avro'
  "table_source"    VARCHAR(128) NOT NULL,
    -- Source PostgreSQL table name
  "record_count"    BIGINT       NOT NULL DEFAULT 0,
  "size_bytes"      BIGINT       NOT NULL DEFAULT 0,
  "status"          VARCHAR(32)  NOT NULL DEFAULT 'pending',
    -- 'pending' | 'running' | 'completed' | 'failed' | 'skipped'
  "error_message"   TEXT,
  "checksum"        VARCHAR(128),
  "partition_date"  DATE,
  "started_at"      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  "completed_at"    TIMESTAMPTZ,
  "duration_ms"     BIGINT,
  "triggered_by"    VARCHAR(64)  DEFAULT 'cron',
    -- 'cron' | 'manual' | 'event'
  "metadata"        JSONB,
  "created_at"      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "lsl_bucket_idx"        ON "lakehouse_sync_log"("bucket");
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "lsl_table_source_idx"  ON "lakehouse_sync_log"("table_source");
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "lsl_status_idx"        ON "lakehouse_sync_log"("status");
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "lsl_partition_idx"     ON "lakehouse_sync_log"("partition_date");
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "lsl_started_at_idx"    ON "lakehouse_sync_log"("started_at");
--> statement-breakpoint

-- ── 6. Dapr Pub/Sub Log ───────────────────────────────────────────────────────
-- Tracks messages published and consumed via Dapr for debugging and DLQ analysis.
CREATE TABLE IF NOT EXISTS "dapr_pubsub_log" (
  "id"              BIGSERIAL PRIMARY KEY,
  "message_id"      VARCHAR(256) UNIQUE,
  "pubsub_name"     VARCHAR(128) NOT NULL DEFAULT '54link-pubsub',
  "topic"           VARCHAR(128) NOT NULL,
  "direction"       VARCHAR(16)  NOT NULL DEFAULT 'publish',
    -- 'publish' | 'subscribe'
  "app_id"          VARCHAR(128) NOT NULL DEFAULT 'pos-shell',
  "payload"         JSONB        NOT NULL,
  "status"          VARCHAR(32)  NOT NULL DEFAULT 'published',
    -- 'published' | 'consumed' | 'failed' | 'dead_letter' | 'dropped'
  "error_message"   TEXT,
  "retry_count"     INTEGER      NOT NULL DEFAULT 0,
  "correlation_id"  VARCHAR(256),
  "trace_id"        VARCHAR(128),
  "agent_code"      VARCHAR(32),
  "tx_ref"          VARCHAR(128),
  "published_at"    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  "consumed_at"     TIMESTAMPTZ,
  "created_at"      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "dpl_topic_idx"         ON "dapr_pubsub_log"("topic");
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "dpl_app_id_idx"        ON "dapr_pubsub_log"("app_id");
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "dpl_status_idx"        ON "dapr_pubsub_log"("status");
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "dpl_agent_idx"         ON "dapr_pubsub_log"("agent_code");
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "dpl_tx_ref_idx"        ON "dapr_pubsub_log"("tx_ref");
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "dpl_published_at_idx"  ON "dapr_pubsub_log"("published_at");
--> statement-breakpoint

-- ── Cleanup: Partition maintenance functions ──────────────────────────────────
-- Auto-cleanup for high-volume log tables (retain 90 days)
CREATE OR REPLACE FUNCTION cleanup_middleware_logs(retention_days INTEGER DEFAULT 90)
RETURNS TABLE(table_name TEXT, rows_deleted BIGINT) AS $$
DECLARE
  cutoff TIMESTAMPTZ := NOW() - (retention_days || ' days')::INTERVAL;
  deleted BIGINT;
BEGIN
  DELETE FROM temporal_workflow_log WHERE created_at < cutoff;
  GET DIAGNOSTICS deleted = ROW_COUNT;
  RETURN QUERY SELECT 'temporal_workflow_log'::TEXT, deleted;

  DELETE FROM permify_check_log WHERE created_at < cutoff;
  GET DIAGNOSTICS deleted = ROW_COUNT;
  RETURN QUERY SELECT 'permify_check_log'::TEXT, deleted;

  DELETE FROM openappsec_threat_log WHERE created_at < cutoff;
  GET DIAGNOSTICS deleted = ROW_COUNT;
  RETURN QUERY SELECT 'openappsec_threat_log'::TEXT, deleted;

  DELETE FROM fluvio_event_log WHERE created_at < cutoff AND status IN ('consumed', 'dead_letter');
  GET DIAGNOSTICS deleted = ROW_COUNT;
  RETURN QUERY SELECT 'fluvio_event_log'::TEXT, deleted;

  DELETE FROM lakehouse_sync_log WHERE created_at < cutoff AND status IN ('completed', 'skipped');
  GET DIAGNOSTICS deleted = ROW_COUNT;
  RETURN QUERY SELECT 'lakehouse_sync_log'::TEXT, deleted;

  DELETE FROM dapr_pubsub_log WHERE created_at < cutoff AND status IN ('consumed', 'dead_letter', 'dropped');
  GET DIAGNOSTICS deleted = ROW_COUNT;
  RETURN QUERY SELECT 'dapr_pubsub_log'::TEXT, deleted;
END;
$$ LANGUAGE plpgsql;
