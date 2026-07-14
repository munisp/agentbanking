/**
 * middleware-audit-schema.ts
 * ─────────────────────────────────────────────────────────────────────────────
 * Drizzle ORM table definitions for all 6 middleware integration audit tables.
 * These tables are created by migration 0047_middleware_integration_audit.sql
 * and are re-exported here for type-safe access in the application.
 *
 * Tables:
 *   1. temporalWorkflowLog   — Temporal workflow execution history
 *   2. permifyCheckLog       — Permify fine-grained authorization audit trail
 *   3. openappsecThreatLog   — OpenAppSec WAF threat events
 *   4. fluvioEventLog        — Fluvio real-time streaming event log
 *   5. lakehouseSyncLog      — Lakehouse (MinIO/Iceberg) export sync log
 *   6. daprPubsubLog         — Dapr pub/sub message audit trail
 */
import { sql } from "drizzle-orm";
import {
  bigserial,
  bigint,
  boolean,
  integer,
  jsonb,
  pgTable,
  text,
  timestamp,
  varchar,
} from "drizzle-orm/pg-core";

// ── 1. Temporal Workflow Log ──────────────────────────────────────────────────
export const temporalWorkflowLog = pgTable("temporal_workflow_log", {
  id:              bigserial("id", { mode: "number" }).primaryKey(),
  workflowId:      varchar("workflow_id", { length: 256 }).notNull(),
  workflowType:    varchar("workflow_type", { length: 128 }).notNull(),
  runId:           varchar("run_id", { length: 128 }),
  taskQueue:       varchar("task_queue", { length: 128 }).notNull().default("settlement-queue"),
  namespace:       varchar("namespace", { length: 64 }).notNull().default("default"),
  status:          varchar("status", { length: 32 }).notNull().default("running"),
  inputPayload:    jsonb("input_payload"),
  resultPayload:   jsonb("result_payload"),
  errorMessage:    text("error_message"),
  startedAt:       timestamp("started_at", { withTimezone: true }).notNull().default(sql`NOW()`),
  closedAt:        timestamp("closed_at", { withTimezone: true }),
  durationMs:      bigint("duration_ms", { mode: "number" }),
  retries:         integer("retries").notNull().default(0),
  parentWorkflowId: varchar("parent_workflow_id", { length: 256 }),
  correlationId:   varchar("correlation_id", { length: 128 }),
  tenantId:        varchar("tenant_id", { length: 64 }).notNull().default("t1"),
  agentId:         varchar("agent_id", { length: 128 }),
  txRef:           varchar("tx_ref", { length: 128 }),
  metadata:        jsonb("metadata"),
  createdAt:       timestamp("created_at", { withTimezone: true }).notNull().default(sql`NOW()`),
});

// ── 2. Permify Check Log ──────────────────────────────────────────────────────
export const permifyCheckLog = pgTable("permify_check_log", {
  id:            bigserial("id", { mode: "number" }).primaryKey(),
  tenantId:      varchar("tenant_id", { length: 64 }).notNull().default("t1"),
  subjectType:   varchar("subject_type", { length: 64 }).notNull(),
  subjectId:     varchar("subject_id", { length: 128 }).notNull(),
  entityType:    varchar("entity_type", { length: 64 }).notNull(),
  entityId:      varchar("entity_id", { length: 128 }).notNull(),
  permission:    varchar("permission", { length: 128 }).notNull(),
  result:        varchar("result", { length: 32 }).notNull(),
  schemaVersion: varchar("schema_version", { length: 64 }),
  snapToken:     varchar("snap_token", { length: 128 }),
  depth:         integer("depth").notNull().default(20),
  latencyMs:     integer("latency_ms"),
  errorMessage:  text("error_message"),
  requestId:     varchar("request_id", { length: 128 }),
  ipAddress:     varchar("ip_address", { length: 45 }),
  userAgent:     text("user_agent"),
  createdAt:     timestamp("created_at", { withTimezone: true }).notNull().default(sql`NOW()`),
});

// ── 3. OpenAppSec Threat Log ──────────────────────────────────────────────────
export const openappsecThreatLog = pgTable("openappsec_threat_log", {
  id:             bigserial("id", { mode: "number" }).primaryKey(),
  eventId:        varchar("event_id", { length: 128 }).unique(),
  timestamp:      timestamp("timestamp", { withTimezone: true }).notNull().default(sql`NOW()`),
  category:       varchar("category", { length: 64 }).notNull(),
  severity:       varchar("severity", { length: 16 }).notNull().default("medium"),
  action:         varchar("action", { length: 16 }).notNull().default("detect"),
  ipAddress:      varchar("ip_address", { length: 45 }).notNull(),
  method:         varchar("method", { length: 16 }),
  path:           text("path"),
  queryString:    text("query_string"),
  userAgent:      text("user_agent"),
  payloadSnippet: text("payload_snippet"),
  threatScore:    integer("threat_score").notNull().default(0),
  countryCode:    varchar("country_code", { length: 2 }),
  requestId:      varchar("request_id", { length: 128 }),
  agentId:        varchar("agent_id", { length: 128 }),
  policyName:     varchar("policy_name", { length: 128 }),
  ruleName:       varchar("rule_name", { length: 128 }),
  blocked:        boolean("blocked").notNull().default(false),
  responseCode:   integer("response_code"),
  metadata:       jsonb("metadata"),
  createdAt:      timestamp("created_at", { withTimezone: true }).notNull().default(sql`NOW()`),
});

// ── 4. Fluvio Event Log ───────────────────────────────────────────────────────
export const fluvioEventLog = pgTable("fluvio_event_log", {
  id:           bigserial("id", { mode: "number" }).primaryKey(),
  topic:        varchar("topic", { length: 128 }).notNull(),
  partition:    integer("partition").notNull().default(0),
  offset:       bigint("offset", { mode: "number" }),
  key:          varchar("key", { length: 256 }),
  payload:      jsonb("payload").notNull(),
  eventType:    varchar("event_type", { length: 64 }),
  agentCode:    varchar("agent_code", { length: 32 }),
  txRef:        varchar("tx_ref", { length: 128 }),
  status:       varchar("status", { length: 32 }).notNull().default("produced"),
  errorMessage: text("error_message"),
  retryCount:   integer("retry_count").notNull().default(0),
  producedAt:   timestamp("produced_at", { withTimezone: true }).notNull().default(sql`NOW()`),
  consumedAt:   timestamp("consumed_at", { withTimezone: true }),
  createdAt:    timestamp("created_at", { withTimezone: true }).notNull().default(sql`NOW()`),
});

// ── 5. Lakehouse Sync Log ─────────────────────────────────────────────────────
export const lakehouseSyncLog = pgTable("lakehouse_sync_log", {
  id:            bigserial("id", { mode: "number" }).primaryKey(),
  syncId:        varchar("sync_id", { length: 128 }).unique(),
  tableName:     varchar("table_name", { length: 128 }).notNull(),
  exportFormat:  varchar("export_format", { length: 32 }).notNull().default("parquet"),
  status:        varchar("status", { length: 32 }).notNull().default("pending"),
  rowsExported:  bigint("rows_exported", { mode: "number" }),
  bytesWritten:  bigint("bytes_written", { mode: "number" }),
  s3Path:        text("s3_path"),
  partitionKey:  varchar("partition_key", { length: 128 }),
  checksum:      varchar("checksum", { length: 64 }),
  errorMessage:  text("error_message"),
  startedAt:     timestamp("started_at", { withTimezone: true }).notNull().default(sql`NOW()`),
  completedAt:   timestamp("completed_at", { withTimezone: true }),
  durationMs:    bigint("duration_ms", { mode: "number" }),
  tenantId:      varchar("tenant_id", { length: 64 }).notNull().default("t1"),
  triggeredBy:   varchar("triggered_by", { length: 64 }).notNull().default("cron"),
  metadata:      jsonb("metadata"),
  createdAt:     timestamp("created_at", { withTimezone: true }).notNull().default(sql`NOW()`),
});

// ── 6. Dapr Pub/Sub Log ───────────────────────────────────────────────────────
export const daprPubsubLog = pgTable("dapr_pubsub_log", {
  id:            bigserial("id", { mode: "number" }).primaryKey(),
  messageId:     varchar("message_id", { length: 128 }).unique(),
  pubsubName:    varchar("pubsub_name", { length: 64 }).notNull().default("agentbanking-pubsub"),
  topic:         varchar("topic", { length: 128 }).notNull(),
  direction:     varchar("direction", { length: 8 }).notNull().default("publish"),
  appId:         varchar("app_id", { length: 64 }),
  data:          jsonb("data").notNull(),
  contentType:   varchar("content_type", { length: 64 }).notNull().default("application/json"),
  status:        varchar("status", { length: 32 }).notNull().default("published"),
  errorMessage:  text("error_message"),
  retryCount:    integer("retry_count").notNull().default(0),
  correlationId: varchar("correlation_id", { length: 128 }),
  traceId:       varchar("trace_id", { length: 128 }),
  tenantId:      varchar("tenant_id", { length: 64 }).notNull().default("t1"),
  agentId:       varchar("agent_id", { length: 128 }),
  txRef:         varchar("tx_ref", { length: 128 }),
  publishedAt:   timestamp("published_at", { withTimezone: true }).notNull().default(sql`NOW()`),
  processedAt:   timestamp("processed_at", { withTimezone: true }),
  createdAt:     timestamp("created_at", { withTimezone: true }).notNull().default(sql`NOW()`),
});

// ── TypeScript type exports ───────────────────────────────────────────────────
export type TemporalWorkflowLog         = typeof temporalWorkflowLog.$inferSelect;
export type InsertTemporalWorkflowLog   = typeof temporalWorkflowLog.$inferInsert;
export type PermifyCheckLog             = typeof permifyCheckLog.$inferSelect;
export type InsertPermifyCheckLog       = typeof permifyCheckLog.$inferInsert;
export type OpenappsecThreatLog         = typeof openappsecThreatLog.$inferSelect;
export type InsertOpenappsecThreatLog   = typeof openappsecThreatLog.$inferInsert;
export type FluvioEventLog              = typeof fluvioEventLog.$inferSelect;
export type InsertFluvioEventLog        = typeof fluvioEventLog.$inferInsert;
export type LakehouseSyncLog            = typeof lakehouseSyncLog.$inferSelect;
export type InsertLakehouseSyncLog      = typeof lakehouseSyncLog.$inferInsert;
export type DaprPubsubLog               = typeof daprPubsubLog.$inferSelect;
export type InsertDaprPubsubLog         = typeof daprPubsubLog.$inferInsert;
