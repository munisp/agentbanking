-- ─────────────────────────────────────────────────────────────────────────────
-- Migration 0056: tamper-evident hash chain for audit_log
--
-- Adds prevHash / entryHash columns so every audit row commits to the hash
-- of the previous row (sha256 over prevHash + canonical row JSON). Deleting
-- or modifying a historical row breaks the chain and is detectable.
-- Nullable + IF NOT EXISTS: existing rows simply have no chain links.
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE "audit_log" ADD COLUMN IF NOT EXISTS "prevHash" varchar(64);
--> statement-breakpoint
ALTER TABLE "audit_log" ADD COLUMN IF NOT EXISTS "entryHash" varchar(64);
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "audit_log_entryHash_idx" ON "audit_log" ("entryHash");
