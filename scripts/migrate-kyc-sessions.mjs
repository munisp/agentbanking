/**
 * Migration: create kyc_sessions table and related enums
 * Run: node scripts/migrate-kyc-sessions.mjs
 */
import pg from "pg";
import dotenv from "dotenv";
dotenv.config();

const { Client } = pg;
const client = new Client({ connectionString: process.env.POSTGRES_URL });

async function run() {
  await client.connect();
  console.log("Connected to PostgreSQL");

  // Create enums (ignore if already exists)
  await client.query(`
    DO $$ BEGIN
      CREATE TYPE kyc_status AS ENUM (
        'pending', 'liveness_passed', 'liveness_failed',
        'document_passed', 'document_failed', 'completed', 'rejected'
      );
    EXCEPTION WHEN duplicate_object THEN NULL;
    END $$;
  `);
  console.log("kyc_status enum ready");

  await client.query(`
    DO $$ BEGIN
      CREATE TYPE kyc_doc_type AS ENUM (
        'NIN', 'BVN_CARD', 'PASSPORT', 'DRIVERS_LICENCE', 'VOTER_CARD'
      );
    EXCEPTION WHEN duplicate_object THEN NULL;
    END $$;
  `);
  console.log("kyc_doc_type enum ready");

  // Create kyc_sessions table
  await client.query(`
    CREATE TABLE IF NOT EXISTS kyc_sessions (
      id                    SERIAL PRIMARY KEY,
      "agentId"             INTEGER NOT NULL,
      status                kyc_status NOT NULL DEFAULT 'pending',
      "livenessScore"       NUMERIC(5,4),
      "livenessMethod"      VARCHAR(64),
      "livenessChallenge"   VARCHAR(128),
      "livenessPassed"      BOOLEAN,
      "docType"             kyc_doc_type,
      "docExtractedName"    VARCHAR(256),
      "docExtractedDob"     VARCHAR(32),
      "docExtractedIdNumber" VARCHAR(64),
      "docConfidence"       NUMERIC(5,4),
      "docFraudIndicators"  JSON,
      "livenessRaw"         JSON,
      "ocrRaw"              JSON,
      "complianceRecordId"  VARCHAR(64),
      "rejectionReason"     TEXT,
      "createdAt"           TIMESTAMP NOT NULL DEFAULT NOW(),
      "updatedAt"           TIMESTAMP NOT NULL DEFAULT NOW()
    );
  `);
  console.log("kyc_sessions table ready");

  // Index on agentId for fast lookups
  await client.query(`
    CREATE INDEX IF NOT EXISTS idx_kyc_sessions_agent_id ON kyc_sessions ("agentId");
  `);
  console.log("Index on agentId created");

  await client.end();
  console.log("Migration complete");
}

run().catch(err => {
  console.error("Migration failed:", err);
  process.exit(1);
});
