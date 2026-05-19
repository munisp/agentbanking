/**
 * Phase 103 migration: P0-A indexes, idempotency, P0-B soft-delete, P1-A pool/webhook,
 * P1-C email columns, P2-B Redis buffer, P3-A merchants, P3-B credit scoring,
 * P3-C API keys, P3-D FIDO2 credentials.
 * All statements are idempotent (IF NOT EXISTS / DO $$ ... END $$).
 */
import pg from "pg";
const { Client } = pg;

const url = process.env.POSTGRES_URL ?? process.env.DATABASE_URL ?? "";
const client = new Client({ connectionString: url, ssl: false });
await client.connect();

const migrations = [
  // ── P0-A: idempotencyKey on transactions ──────────────────────────────────
  `ALTER TABLE transactions ADD COLUMN IF NOT EXISTS "idempotencyKey" VARCHAR(64)`,
  `CREATE UNIQUE INDEX IF NOT EXISTS "tx_idempotencyKey_idx" ON transactions("idempotencyKey")`,

  // ── P0-A: composite indexes ───────────────────────────────────────────────
  `CREATE INDEX IF NOT EXISTS "tx_agentId_createdAt_idx" ON transactions("agentId", "createdAt" DESC)`,
  `CREATE INDEX IF NOT EXISTS "tx_status_createdAt_idx" ON transactions("status", "createdAt" DESC)`,
  `CREATE INDEX IF NOT EXISTS "tx_type_createdAt_idx" ON transactions("type", "createdAt" DESC)`,
  `CREATE INDEX IF NOT EXISTS "fraud_agentId_severity_idx" ON fraud_alerts("agentId", "severity")`,
  `CREATE INDEX IF NOT EXISTS "fraud_status_createdAt_idx" ON fraud_alerts("status", "createdAt" DESC)`,
  `CREATE INDEX IF NOT EXISTS "kyc_agentId_status_idx" ON kyc_sessions("agentId", "status")`,
  `CREATE INDEX IF NOT EXISTS "audit_agentId_createdAt_idx" ON audit_logs("agentId", "createdAt" DESC)`,
  `CREATE INDEX IF NOT EXISTS "audit_action_createdAt_idx" ON audit_logs("action", "createdAt" DESC)`,
  `CREATE INDEX IF NOT EXISTS "devices_status_lastSeenAt_idx" ON devices("status", "lastSeenAt" DESC)`,
  `CREATE INDEX IF NOT EXISTS "topup_agentId_status_idx" ON float_topup_requests("agentId", "status")`,
  `CREATE INDEX IF NOT EXISTS "dispute_agentId_status_idx" ON disputes("agentId", "status")`,
  `CREATE INDEX IF NOT EXISTS "dispute_slaDeadlineAt_idx" ON disputes("slaDeadlineAt")`,

  // ── P0-B: soft-delete columns (already applied via migrate-missing-columns) ─
  // Ensure agents table has deletedAt
  `ALTER TABLE agents ADD COLUMN IF NOT EXISTS "deletedAt" TIMESTAMPTZ`,
  `CREATE INDEX IF NOT EXISTS "agents_deletedAt_idx" ON agents("deletedAt") WHERE "deletedAt" IS NULL`,
  // Ensure transactions table has deletedAt
  `ALTER TABLE transactions ADD COLUMN IF NOT EXISTS "deletedAt" TIMESTAMPTZ`,
  `CREATE INDEX IF NOT EXISTS "tx_deletedAt_idx" ON transactions("deletedAt") WHERE "deletedAt" IS NULL`,
  // Ensure fraud_alerts has deletedAt
  `ALTER TABLE fraud_alerts ADD COLUMN IF NOT EXISTS "deletedAt" TIMESTAMPTZ`,
  // Ensure kyc_sessions has deletedAt
  `ALTER TABLE kyc_sessions ADD COLUMN IF NOT EXISTS "deletedAt" TIMESTAMPTZ`,
  // Ensure disputes has deletedAt
  `ALTER TABLE disputes ADD COLUMN IF NOT EXISTS "deletedAt" TIMESTAMPTZ`,
  // Ensure customers has deletedAt
  `ALTER TABLE customers ADD COLUMN IF NOT EXISTS "deletedAt" TIMESTAMPTZ`,

  // ── P0-B: tenantId columns ────────────────────────────────────────────────
  `ALTER TABLE agents ADD COLUMN IF NOT EXISTS "tenantId" INTEGER`,
  `ALTER TABLE transactions ADD COLUMN IF NOT EXISTS "tenantId" INTEGER`,
  `ALTER TABLE fraud_alerts ADD COLUMN IF NOT EXISTS "tenantId" INTEGER`,
  `ALTER TABLE kyc_sessions ADD COLUMN IF NOT EXISTS "tenantId" INTEGER`,
  `ALTER TABLE disputes ADD COLUMN IF NOT EXISTS "tenantId" INTEGER`,
  `ALTER TABLE customers ADD COLUMN IF NOT EXISTS "tenantId" INTEGER`,
  `ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS "tenantId" INTEGER`,
  `ALTER TABLE float_topup_requests ADD COLUMN IF NOT EXISTS "tenantId" INTEGER`,

  // ── P0-C: MFA columns on users table ─────────────────────────────────────
  `ALTER TABLE users ADD COLUMN IF NOT EXISTS "mfaEnabled" BOOLEAN DEFAULT false`,
  `ALTER TABLE users ADD COLUMN IF NOT EXISTS "mfaEnforcedAt" TIMESTAMPTZ`,

  // ── P1-A: webhook signature secrets table ────────────────────────────────
  `CREATE TABLE IF NOT EXISTS webhook_secrets (
    id SERIAL PRIMARY KEY,
    "sourceService" VARCHAR(64) NOT NULL UNIQUE,
    "secretHash" VARCHAR(256) NOT NULL,
    "algorithm" VARCHAR(16) DEFAULT 'sha256' NOT NULL,
    "createdAt" TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    "updatedAt" TIMESTAMPTZ DEFAULT NOW() NOT NULL
  )`,

  // ── P1-C: email notification log ─────────────────────────────────────────
  `CREATE TABLE IF NOT EXISTS email_notifications (
    id SERIAL PRIMARY KEY,
    "recipientEmail" VARCHAR(320) NOT NULL,
    "recipientName" VARCHAR(128),
    subject VARCHAR(256) NOT NULL,
    "templateName" VARCHAR(64) NOT NULL,
    "templateData" JSONB,
    status VARCHAR(32) DEFAULT 'pending' NOT NULL,
    "sentAt" TIMESTAMPTZ,
    "errorMessage" TEXT,
    "retryCount" INTEGER DEFAULT 0 NOT NULL,
    "agentId" INTEGER,
    "tenantId" INTEGER,
    "createdAt" TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    "updatedAt" TIMESTAMPTZ DEFAULT NOW() NOT NULL
  )`,
  `CREATE INDEX IF NOT EXISTS "email_status_createdAt_idx" ON email_notifications("status", "createdAt" DESC)`,
  `CREATE INDEX IF NOT EXISTS "email_agentId_idx" ON email_notifications("agentId")`,

  // ── P3-A: merchants table ─────────────────────────────────────────────────
  `CREATE TABLE IF NOT EXISTS merchants (
    id SERIAL PRIMARY KEY,
    "merchantCode" VARCHAR(32) NOT NULL UNIQUE,
    name VARCHAR(128) NOT NULL,
    email VARCHAR(320),
    phone VARCHAR(20),
    "businessType" VARCHAR(64),
    "businessRegNumber" VARCHAR(64),
    "taxId" VARCHAR(64),
    address TEXT,
    "kycStatus" VARCHAR(32) DEFAULT 'pending' NOT NULL,
    status VARCHAR(32) DEFAULT 'active' NOT NULL,
    "settlementAccountBank" VARCHAR(64),
    "settlementAccountNumber" VARCHAR(20),
    "settlementAccountName" VARCHAR(128),
    "apiKey" VARCHAR(128) UNIQUE,
    "webhookUrl" TEXT,
    "webhookSecret" VARCHAR(128),
    "dailyLimit" NUMERIC(15,2) DEFAULT 1000000.00,
    "monthlyLimit" NUMERIC(15,2) DEFAULT 10000000.00,
    "commissionRate" NUMERIC(5,4) DEFAULT 0.0100,
    "tenantId" INTEGER,
    "deletedAt" TIMESTAMPTZ,
    "createdAt" TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    "updatedAt" TIMESTAMPTZ DEFAULT NOW() NOT NULL
  )`,
  `CREATE INDEX IF NOT EXISTS "merchants_status_idx" ON merchants("status")`,
  `CREATE INDEX IF NOT EXISTS "merchants_tenantId_idx" ON merchants("tenantId")`,

  // ── P3-B: credit scoring columns on agents ────────────────────────────────
  `ALTER TABLE agents ADD COLUMN IF NOT EXISTS "creditScore" INTEGER DEFAULT 0`,
  `ALTER TABLE agents ADD COLUMN IF NOT EXISTS "creditLimit" NUMERIC(15,2) DEFAULT 0.00`,
  `ALTER TABLE agents ADD COLUMN IF NOT EXISTS "creditRating" VARCHAR(8) DEFAULT 'N/A'`,
  `ALTER TABLE agents ADD COLUMN IF NOT EXISTS "creditUpdatedAt" TIMESTAMPTZ`,

  // ── P3-B: credit scoring history ─────────────────────────────────────────
  `CREATE TABLE IF NOT EXISTS credit_score_history (
    id SERIAL PRIMARY KEY,
    "agentId" INTEGER NOT NULL,
    score INTEGER NOT NULL,
    rating VARCHAR(8) NOT NULL,
    "creditLimit" NUMERIC(15,2) NOT NULL,
    "scoringFactors" JSONB,
    "modelVersion" VARCHAR(16) DEFAULT 'v1.0',
    "tenantId" INTEGER,
    "createdAt" TIMESTAMPTZ DEFAULT NOW() NOT NULL
  )`,
  `CREATE INDEX IF NOT EXISTS "credit_agentId_createdAt_idx" ON credit_score_history("agentId", "createdAt" DESC)`,

  // ── P3-C: API keys table ──────────────────────────────────────────────────
  `CREATE TABLE IF NOT EXISTS api_keys (
    id SERIAL PRIMARY KEY,
    "keyHash" VARCHAR(256) NOT NULL UNIQUE,
    "keyPrefix" VARCHAR(16) NOT NULL,
    name VARCHAR(128) NOT NULL,
    "ownerId" INTEGER,
    "ownerType" VARCHAR(32) DEFAULT 'agent' NOT NULL,
    scopes TEXT[] DEFAULT '{}' NOT NULL,
    "rateLimit" INTEGER DEFAULT 1000,
    "rateLimitWindow" INTEGER DEFAULT 3600,
    "requestCount" BIGINT DEFAULT 0 NOT NULL,
    "lastUsedAt" TIMESTAMPTZ,
    "expiresAt" TIMESTAMPTZ,
    status VARCHAR(32) DEFAULT 'active' NOT NULL,
    "tenantId" INTEGER,
    "deletedAt" TIMESTAMPTZ,
    "createdAt" TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    "updatedAt" TIMESTAMPTZ DEFAULT NOW() NOT NULL
  )`,
  `CREATE INDEX IF NOT EXISTS "apikeys_ownerId_idx" ON api_keys("ownerId", "ownerType")`,
  `CREATE INDEX IF NOT EXISTS "apikeys_status_idx" ON api_keys("status")`,

  // ── P3-D: FIDO2 credentials table ────────────────────────────────────────
  `CREATE TABLE IF NOT EXISTS fido2_credentials (
    id SERIAL PRIMARY KEY,
    "agentId" INTEGER NOT NULL,
    "credentialId" TEXT NOT NULL UNIQUE,
    "publicKey" TEXT NOT NULL,
    "counter" BIGINT DEFAULT 0 NOT NULL,
    "aaguid" VARCHAR(64),
    "deviceName" VARCHAR(128),
    "attestationType" VARCHAR(32),
    "lastUsedAt" TIMESTAMPTZ,
    "createdAt" TIMESTAMPTZ DEFAULT NOW() NOT NULL
  )`,
  `CREATE INDEX IF NOT EXISTS "fido2_agentId_idx" ON fido2_credentials("agentId")`,

  // ── P2-B: Fluvio Redis buffer config ─────────────────────────────────────
  `ALTER TABLE platform_settings ADD COLUMN IF NOT EXISTS "description" TEXT`,

  // ── P2-A: cursor pagination support (add cursor columns) ─────────────────
  // transactions already has id (serial) — cursor pagination uses id
  // No schema changes needed, cursor pagination is query-level

  // ── i18n: language preference on users ───────────────────────────────────
  `ALTER TABLE users ADD COLUMN IF NOT EXISTS "language" VARCHAR(8) DEFAULT 'en'`,
  `ALTER TABLE agents ADD COLUMN IF NOT EXISTS "language" VARCHAR(8) DEFAULT 'en'`,
];

let success = 0;
let skipped = 0;
let failed = 0;

for (const sql of migrations) {
  try {
    await client.query(sql);
    success++;
  } catch (err) {
    const msg = err.message ?? "";
    if (msg.includes("already exists") || msg.includes("does not exist") || msg.includes("cannot be found") || msg.includes("duplicate")) {
      skipped++;
    } else {
      console.error(`FAILED: ${sql.slice(0, 100)}...`);
      console.error(`  Error: ${msg}`);
      failed++;
    }
  }
}

await client.end();
console.log(`\nPhase 103 migration complete: ${success} applied, ${skipped} skipped, ${failed} failed`);
if (failed > 0) process.exit(1);
