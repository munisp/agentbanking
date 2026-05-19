/**
 * migrate-keycloak-sub.mjs
 * Migrates the users table from Manus openId to Keycloak keycloakSub.
 * Safe to run multiple times (idempotent).
 */
import "dotenv/config";
import pg from "pg";
const { Pool } = pg;

const pool = new Pool({
  connectionString: process.env.POSTGRES_URL,
  ssl: false,
});

async function migrate() {
  const client = await pool.connect();
  try {
    await client.query("BEGIN");

    // Check current columns
    const cols = await client.query(
      `SELECT column_name FROM information_schema.columns WHERE table_name = 'users'`
    );
    const colNames = cols.rows.map((r) => r.column_name);
    console.log("Current users columns:", colNames.join(", "));

    const hasOpenId = colNames.includes("openId");
    const hasKeycloakSub = colNames.includes("keycloakSub");

    // Step 1: Add keycloakSub column if missing
    if (!hasKeycloakSub) {
      await client.query(`ALTER TABLE users ADD COLUMN "keycloakSub" VARCHAR(128)`);
      console.log("[REDACTED sensitive data]");
    } else {
      console.log("[REDACTED sensitive data]");
    }

    // Step 2: Copy openId → keycloakSub
    if (hasOpenId) {
      await client.query(
        `UPDATE users SET "keycloakSub" = "openId" WHERE "keycloakSub" IS NULL`
      );
      console.log("[REDACTED sensitive data]");
    }

    // Step 3: Fill any remaining NULLs with a placeholder
    await client.query(
      `UPDATE users SET "keycloakSub" = 'migrated-' || id::text WHERE "keycloakSub" IS NULL`
    );

    // Step 4: Set NOT NULL
    await client.query(`ALTER TABLE users ALTER COLUMN "keycloakSub" SET NOT NULL`);
    console.log("[REDACTED sensitive data]");

    // Step 5: Add unique constraint if missing
    const constraints = await client.query(
      `SELECT conname FROM pg_constraint WHERE conrelid = 'users'::regclass AND conname = 'users_keycloakSub_unique'`
    );
    if (constraints.rows.length === 0) {
      await client.query(
        `ALTER TABLE users ADD CONSTRAINT users_keycloakSub_unique UNIQUE ("keycloakSub")`
      );
      console.log("[REDACTED sensitive data]");
    } else {
      console.log("  Unique constraint already exists");
    }

    // Step 6: Drop old openId column
    if (hasOpenId) {
      await client.query(`ALTER TABLE users DROP COLUMN "openId"`);
      console.log("✓ Dropped openId column");
    } else {
      console.log("  openId column already removed");
    }

    await client.query("COMMIT");
    console.log("[REDACTED sensitive data]");
  } catch (e) {
    await client.query("ROLLBACK");
    console.error("❌ Migration failed:", e.message);
    process.exit(1);
  } finally {
    client.release();
    await pool.end();
  }
}

migrate();
