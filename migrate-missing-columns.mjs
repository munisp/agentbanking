/**
 * Direct SQL migration to add missing columns that the new schema requires.
 * This script is idempotent - uses ADD COLUMN IF NOT EXISTS.
 */
import pg from "pg";
const { Client } = pg;

const url = process.env.POSTGRES_URL ?? process.env.DATABASE_URL ?? "";
const client = new Client({ 
  connectionString: url,
  ssl: false
});
await client.connect();

const migrations = [
  // ── fraud_alerts: add soft-delete + tenant isolation ──────────────────────
  `ALTER TABLE fraud_alerts ADD COLUMN IF NOT EXISTS "deletedAt" TIMESTAMPTZ`,
  `ALTER TABLE fraud_alerts ADD COLUMN IF NOT EXISTS "tenantId" INTEGER`,

  // ── kyc_sessions: add liveness + OCR raw fields ───────────────────────────
  `ALTER TABLE kyc_sessions ADD COLUMN IF NOT EXISTS "livenessMethod" VARCHAR(64)`,
  `ALTER TABLE kyc_sessions ADD COLUMN IF NOT EXISTS "livenessChallenge" VARCHAR(128)`,
  `ALTER TABLE kyc_sessions ADD COLUMN IF NOT EXISTS "livenessRaw" JSONB`,
  `ALTER TABLE kyc_sessions ADD COLUMN IF NOT EXISTS "ocrRaw" JSONB`,

  // ── kyc_sessions: fix sessionRef to have a default ────────────────────────
  // Only set default if column exists and has no default yet
  `ALTER TABLE kyc_sessions ALTER COLUMN "sessionRef" SET DEFAULT gen_random_uuid()::text`,

  // ── pos_terminals: add lastCommand fields ─────────────────────────────────
  `ALTER TABLE pos_terminals ADD COLUMN IF NOT EXISTS "lastCommand" VARCHAR(64)`,
  `ALTER TABLE pos_terminals ADD COLUMN IF NOT EXISTS "lastCommandAt" TIMESTAMPTZ`,
  `ALTER TABLE pos_terminals ADD COLUMN IF NOT EXISTS "deletedAt" TIMESTAMPTZ`,
  `ALTER TABLE pos_terminals ADD COLUMN IF NOT EXISTS "tenantId" INTEGER`,

  // ── agent_geofence_zones: add assignedBy ─────────────────────────────────
  `ALTER TABLE agent_geofence_zones ADD COLUMN IF NOT EXISTS "assignedBy" VARCHAR(64)`,

  // ── compliance_reports: make reportType/period have defaults ──────────────
  `ALTER TABLE compliance_reports ALTER COLUMN "reportType" SET DEFAULT 'compliance'`,
  `ALTER TABLE compliance_reports ALTER COLUMN "period" SET DEFAULT ''`,
  `ALTER TABLE compliance_reports ADD COLUMN IF NOT EXISTS "periodStart" TIMESTAMPTZ`,
  `ALTER TABLE compliance_reports ADD COLUMN IF NOT EXISTS "periodEnd" TIMESTAMPTZ`,
  `ALTER TABLE compliance_reports ADD COLUMN IF NOT EXISTS "totalAlerts" INTEGER DEFAULT 0`,
  `ALTER TABLE compliance_reports ADD COLUMN IF NOT EXISTS "highAlerts" INTEGER DEFAULT 0`,
  `ALTER TABLE compliance_reports ADD COLUMN IF NOT EXISTS "mediumAlerts" INTEGER DEFAULT 0`,
  `ALTER TABLE compliance_reports ADD COLUMN IF NOT EXISTS "lowAlerts" INTEGER DEFAULT 0`,
  `ALTER TABLE compliance_reports ADD COLUMN IF NOT EXISTS "escalatedAlerts" INTEGER DEFAULT 0`,
  `ALTER TABLE compliance_reports ADD COLUMN IF NOT EXISTS "resolvedAlerts" INTEGER DEFAULT 0`,
  `ALTER TABLE compliance_reports ADD COLUMN IF NOT EXISTS "topOffendersJson" JSONB`,
  `ALTER TABLE compliance_reports ADD COLUMN IF NOT EXISTS "pdfUrl" TEXT`,
  `ALTER TABLE compliance_reports ADD COLUMN IF NOT EXISTS "pdfKey" VARCHAR(256)`,
  `ALTER TABLE compliance_reports ADD COLUMN IF NOT EXISTS "generatedBy" VARCHAR(64)`,
  `ALTER TABLE compliance_reports ADD COLUMN IF NOT EXISTS "tenantId" INTEGER`,

  // ── disputes: make type/description optional ──────────────────────────────
  `ALTER TABLE disputes ALTER COLUMN "type" DROP NOT NULL`,
  `ALTER TABLE disputes ALTER COLUMN "type" SET DEFAULT 'general'`,
  `ALTER TABLE disputes ALTER COLUMN "description" DROP NOT NULL`,
  `ALTER TABLE disputes ALTER COLUMN "description" SET DEFAULT ''`,
  `ALTER TABLE disputes ADD COLUMN IF NOT EXISTS "reason" VARCHAR(256)`,
  `ALTER TABLE disputes ADD COLUMN IF NOT EXISTS "evidence" TEXT`,
  `ALTER TABLE disputes ADD COLUMN IF NOT EXISTS "resolvedBy" VARCHAR(64)`,
  `ALTER TABLE disputes ADD COLUMN IF NOT EXISTS "slaDeadlineAt" TIMESTAMPTZ`,
  `ALTER TABLE disputes ADD COLUMN IF NOT EXISTS "deletedAt" TIMESTAMPTZ`,
  `ALTER TABLE disputes ADD COLUMN IF NOT EXISTS "tenantId" INTEGER`,

  // ── devices: add missing soft-delete + tenant fields ─────────────────────
  `ALTER TABLE devices ADD COLUMN IF NOT EXISTS "deletedAt" TIMESTAMPTZ`,
  `ALTER TABLE devices ADD COLUMN IF NOT EXISTS "tenantId" INTEGER`,
  `ALTER TABLE devices ADD COLUMN IF NOT EXISTS "ipAddress" VARCHAR(45)`,
  `ALTER TABLE devices ADD COLUMN IF NOT EXISTS "location" VARCHAR(128)`,
  `ALTER TABLE devices ADD COLUMN IF NOT EXISTS "enrolledAt" TIMESTAMPTZ DEFAULT NOW()`,
  `ALTER TABLE devices ADD COLUMN IF NOT EXISTS "enrollmentToken" VARCHAR(128)`,
  `ALTER TABLE devices ADD COLUMN IF NOT EXISTS "enrollmentExpiresAt" TIMESTAMPTZ`,
  `ALTER TABLE devices ADD COLUMN IF NOT EXISTS "deviceToken" VARCHAR(64)`,

  // ── kyc_sessions: add soft-delete + tenant ────────────────────────────────
  `ALTER TABLE kyc_sessions ADD COLUMN IF NOT EXISTS "deletedAt" TIMESTAMPTZ`,
  `ALTER TABLE kyc_sessions ADD COLUMN IF NOT EXISTS "tenantId" INTEGER`,

  // ── geofence_zones: add legacy columns ───────────────────────────────────
  `ALTER TABLE geofence_zones ADD COLUMN IF NOT EXISTS "latitude" NUMERIC(10,7)`,
  `ALTER TABLE geofence_zones ADD COLUMN IF NOT EXISTS "longitude" NUMERIC(10,7)`,
  `ALTER TABLE geofence_zones ADD COLUMN IF NOT EXISTS "radiusMetres" INTEGER DEFAULT 500`,
  `ALTER TABLE geofence_zones ADD COLUMN IF NOT EXISTS "createdBy" VARCHAR(64)`,

  // ── Expand enums ──────────────────────────────────────────────────────────
  // qr_code_type
  `DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'agent_id' AND enumtypid = 'qr_code_type'::regtype) THEN
      ALTER TYPE qr_code_type ADD VALUE 'agent_id';
    END IF;
  END $$`,
  `DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'product' AND enumtypid = 'qr_code_type'::regtype) THEN
      ALTER TYPE qr_code_type ADD VALUE 'product';
    END IF;
  END $$`,
  `DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'event' AND enumtypid = 'qr_code_type'::regtype) THEN
      ALTER TYPE qr_code_type ADD VALUE 'event';
    END IF;
  END $$`,
  `DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'loyalty' AND enumtypid = 'qr_code_type'::regtype) THEN
      ALTER TYPE qr_code_type ADD VALUE 'loyalty';
    END IF;
  END $$`,
  // sim_status
  `DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'standby' AND enumtypid = 'sim_status'::regtype) THEN
      ALTER TYPE sim_status ADD VALUE 'standby';
    END IF;
  END $$`,
  `DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'failed' AND enumtypid = 'sim_status'::regtype) THEN
      ALTER TYPE sim_status ADD VALUE 'failed';
    END IF;
  END $$`,
  `DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'disabled' AND enumtypid = 'sim_status'::regtype) THEN
      ALTER TYPE sim_status ADD VALUE 'disabled';
    END IF;
  END $$`,
  // reversal_status
  `DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'completed' AND enumtypid = 'reversal_status'::regtype) THEN
      ALTER TYPE reversal_status ADD VALUE 'completed';
    END IF;
  END $$`,
  `DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'failed' AND enumtypid = 'reversal_status'::regtype) THEN
      ALTER TYPE reversal_status ADD VALUE 'failed';
    END IF;
  END $$`,
  // link_type
  `DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'invoice' AND enumtypid = 'link_type'::regtype) THEN
      ALTER TYPE link_type ADD VALUE 'invoice';
    END IF;
  END $$`,
  `DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'subscription' AND enumtypid = 'link_type'::regtype) THEN
      ALTER TYPE link_type ADD VALUE 'subscription';
    END IF;
  END $$`,
  `DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'donation' AND enumtypid = 'link_type'::regtype) THEN
      ALTER TYPE link_type ADD VALUE 'donation';
    END IF;
  END $$`,
  // link_status
  `DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'used' AND enumtypid = 'link_status'::regtype) THEN
      ALTER TYPE link_status ADD VALUE 'used';
    END IF;
  END $$`,
  `DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'revoked' AND enumtypid = 'link_status'::regtype) THEN
      ALTER TYPE link_status ADD VALUE 'revoked';
    END IF;
  END $$`,
  // ad_status
  `DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'expired' AND enumtypid = 'ad_status'::regtype) THEN
      ALTER TYPE ad_status ADD VALUE 'expired';
    END IF;
  END $$`,
  `DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'rejected' AND enumtypid = 'ad_status'::regtype) THEN
      ALTER TYPE ad_status ADD VALUE 'rejected';
    END IF;
  END $$`,
];

let success = 0;
let skipped = 0;
let failed = 0;

for (const sql of migrations) {
  try {
    await client.query(sql);
    success++;
  } catch (err) {
    // Ignore "already exists" or "does not exist" errors
    const msg = err.message ?? "";
    if (msg.includes("already exists") || msg.includes("does not exist") || msg.includes("cannot be found")) {
      skipped++;
    } else {
      console.error(`FAILED: ${sql.slice(0, 80)}...`);
      console.error(`  Error: ${msg}`);
      failed++;
    }
  }
}

await client.end();
console.log(`\nMigration complete: ${success} applied, ${skipped} skipped, ${failed} failed`);
if (failed > 0) process.exit(1);
