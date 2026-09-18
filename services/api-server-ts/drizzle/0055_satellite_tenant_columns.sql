-- ─────────────────────────────────────────────────────────────────────────────
-- Migration 0055: tenantId on satellite money-adjacent tables
--
-- Tenancy audit fix: commission_payouts, merchant_payouts, agent_loans,
-- fee_rules, velocity_limits and transaction_limits lacked a tenantId column,
-- so rows could not be attributed to (or isolated by) tenant. This migration
-- adds a nullable "tenantId" column plus a lookup index to each table.
--
-- Nullable + IF NOT EXISTS: safe to apply on live tables with existing rows;
-- backfill of historical rows is a separate operational task.
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE "commission_payouts" ADD COLUMN IF NOT EXISTS "tenantId" integer;
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "commission_payouts_tenantId_idx" ON "commission_payouts" ("tenantId");
--> statement-breakpoint
ALTER TABLE "merchant_payouts" ADD COLUMN IF NOT EXISTS "tenantId" integer;
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "merchant_payouts_tenantId_idx" ON "merchant_payouts" ("tenantId");
--> statement-breakpoint
ALTER TABLE "agent_loans" ADD COLUMN IF NOT EXISTS "tenantId" integer;
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "agent_loans_tenantId_idx" ON "agent_loans" ("tenantId");
--> statement-breakpoint
ALTER TABLE "fee_rules" ADD COLUMN IF NOT EXISTS "tenantId" integer;
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "fee_rules_tenantId_idx" ON "fee_rules" ("tenantId");
--> statement-breakpoint
ALTER TABLE "velocity_limits" ADD COLUMN IF NOT EXISTS "tenantId" integer;
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "velocity_limits_tenantId_idx" ON "velocity_limits" ("tenantId");
--> statement-breakpoint
ALTER TABLE "transaction_limits" ADD COLUMN IF NOT EXISTS "tenantId" integer;
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "transaction_limits_tenantId_idx" ON "transaction_limits" ("tenantId");
