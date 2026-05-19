#!/usr/bin/env node
/**
 * Database backup automation script.
 * Exports PostgreSQL database to a timestamped SQL dump.
 * Usage: node scripts/db-backup.mjs
 */
import { execSync } from "child_process";
import { existsSync, mkdirSync } from "fs";
import path from "path";

const BACKUP_DIR = process.env.BACKUP_DIR ?? "./backups";
const DB_URL = process.env.DATABASE_URL ?? process.env.POSTGRES_URL;

if (!DB_URL) {
  console.error("[Backup] DATABASE_URL not set — cannot create backup");
  process.exit(1);
}

// Ensure backup directory exists
if (!existsSync(BACKUP_DIR)) {
  mkdirSync(BACKUP_DIR, { recursive: true });
}

const timestamp = new Date().toISOString().replace(/[:.]/g, "-").substring(0, 19);
const filename = `backup-${timestamp}.sql.gz`;
const filepath = path.join(BACKUP_DIR, filename);

console.log(`[Backup] Starting database backup to ${filepath}...`);

try {
  execSync(`pg_dump "${DB_URL}" | gzip > "${filepath}"`, { stdio: "inherit" });
  console.log(`[Backup] ✓ Backup complete: ${filepath}`);
  
  // Clean up old backups (keep last 7)
  const { readdirSync, unlinkSync } = await import("fs");
  const backups = readdirSync(BACKUP_DIR)
    .filter(f => f.startsWith("backup-") && f.endsWith(".sql.gz"))
    .sort()
    .reverse();
  
  if (backups.length > 7) {
    for (const old of backups.slice(7)) {
      unlinkSync(path.join(BACKUP_DIR, old));
      console.log(`[Backup] Removed old backup: ${old}`);
    }
  }
} catch (err) {
  console.error("[Backup] Failed:", err.message);
  process.exit(1);
}
