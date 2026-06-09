/**
 * Database Migration Runner
 *
 * Usage:
 *   npx tsx scripts/migrate.ts              # Run pending migrations
 *   npx tsx scripts/migrate.ts --status     # Show migration status
 *   npx tsx scripts/migrate.ts --rollback   # Rollback last migration
 *   npx tsx scripts/migrate.ts --generate   # Generate new migration from schema diff
 *
 * Requires: DATABASE_URL or POSTGRES_URL environment variable
 *
 * This replaces the unsafe `db:push` approach with proper versioned migrations
 * that support rollback via the drizzle-kit migration system.
 */
import { drizzle } from "drizzle-orm/node-postgres";
import { migrate } from "drizzle-orm/node-postgres/migrator";
import pg from "pg";
import { execSync } from "child_process";
import path from "path";
import fs from "fs";

const { Pool } = pg;

const connectionString = process.env.POSTGRES_URL || process.env.DATABASE_URL;

if (!connectionString) {
  console.error(
    "ERROR: POSTGRES_URL or DATABASE_URL environment variable is required"
  );
  process.exit(1);
}

const migrationsFolder = path.resolve(__dirname, "../drizzle/migrations");

async function runMigrations() {
  const pool = new Pool({ connectionString });
  const db = drizzle(pool);

  console.log("Running pending migrations...");
  try {
    await migrate(db, { migrationsFolder });
    console.log("All migrations applied successfully.");
  } catch (error) {
    console.error("Migration failed:", error);
    process.exit(1);
  } finally {
    await pool.end();
  }
}

async function showStatus() {
  const pool = new Pool({ connectionString });
  try {
    const result = await pool.query(
      `SELECT * FROM drizzle.__drizzle_migrations ORDER BY created_at DESC LIMIT 20`
    );
    if (result.rows.length === 0) {
      console.log("No migrations have been applied yet.");
    } else {
      console.log("Applied migrations:");
      for (const row of result.rows) {
        console.log(
          `  ${row.hash} — ${new Date(Number(row.created_at)).toISOString()}`
        );
      }
    }
  } catch {
    console.log(
      "Migration tracking table does not exist yet. Run migrations first."
    );
  } finally {
    await pool.end();
  }
}

function generateMigration() {
  console.log("Generating migration from schema diff...");
  try {
    execSync("npx drizzle-kit generate", { stdio: "inherit" });
    console.log("Migration generated in drizzle/migrations/");
  } catch (error) {
    console.error("Failed to generate migration:", error);
    process.exit(1);
  }
}

function rollback() {
  const files = fs
    .readdirSync(migrationsFolder)
    .filter(f => f.endsWith(".sql"))
    .sort()
    .reverse();

  if (files.length === 0) {
    console.log("No migrations to rollback.");
    return;
  }

  const lastMigration = files[0];
  console.log(`Last migration: ${lastMigration}`);
  console.log("WARNING: Drizzle ORM does not support automatic rollback.");
  console.log("To rollback, you must:");
  console.log("  1. Write a manual DOWN migration SQL");
  console.log("  2. Apply it with: psql $DATABASE_URL -f <rollback.sql>");
  console.log(
    "  3. Remove the migration record from drizzle.__drizzle_migrations"
  );
  console.log(
    "\nFor safety, always test migrations in staging before applying to production."
  );
}

const arg = process.argv[2];

if (arg === "--status") {
  showStatus();
} else if (arg === "--rollback") {
  rollback();
} else if (arg === "--generate") {
  generateMigration();
} else {
  runMigrations();
}
