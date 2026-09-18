-- ─────────────────────────────────────────────────────────────────────────────
-- Migration 0057: BVN/NIN encryption at rest + blind indexes
--
-- PII audit fix: customers.bvn / customers.nin were plaintext varchar(11).
-- Application code now stores AES-256-GCM ciphertext (random IV, format
-- "v1:<iv>:<tag>:<ciphertext>", base64) which exceeds 11 chars, so the
-- columns are widened to text.
--
-- Because GCM uses a random IV, ciphertext is non-deterministic and cannot
-- be used for duplicate detection. Blind-index columns (bvnHash / ninHash)
-- hold sha256(normalized value + FIELD_ENCRYPTION_SALT) and are used for
-- equality lookups (duplicate pre-checks, verify-by-hash) instead.
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE "customers" ALTER COLUMN "bvn" TYPE text;
--> statement-breakpoint
ALTER TABLE "customers" ALTER COLUMN "nin" TYPE text;
--> statement-breakpoint
ALTER TABLE "customers" ADD COLUMN IF NOT EXISTS "bvnHash" varchar(64);
--> statement-breakpoint
ALTER TABLE "customers" ADD COLUMN IF NOT EXISTS "ninHash" varchar(64);
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "customers_bvnHash_idx" ON "customers" ("bvnHash");
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "customers_ninHash_idx" ON "customers" ("ninHash");
--> statement-breakpoint
ALTER TABLE "kyc_sessions" ALTER COLUMN "bvn" TYPE text;
--> statement-breakpoint
ALTER TABLE "kyc_sessions" ALTER COLUMN "nin" TYPE text;
--> statement-breakpoint
-- OCR-extracted ID numbers for NIN/BVN_CARD documents are also stored
-- encrypted (ciphertext exceeds varchar(256)), so widen this column too.
ALTER TABLE "kyc_sessions" ALTER COLUMN "docExtractedIdNumber" TYPE text;
--> statement-breakpoint
ALTER TABLE "kyc_sessions" ADD COLUMN IF NOT EXISTS "bvnHash" varchar(64);
--> statement-breakpoint
ALTER TABLE "kyc_sessions" ADD COLUMN IF NOT EXISTS "ninHash" varchar(64);
