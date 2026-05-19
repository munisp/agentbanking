import pg from "pg";
import { readFileSync } from "fs";

// Load DATABASE_URL from .env manually (dotenv not available as ESM here)
let dbUrl = process.env.DATABASE_URL;
if (!dbUrl) {
  try {
    const env = readFileSync(".env", "utf8");
    const match = env.match(/DATABASE_URL=(.+)/);
    if (match) dbUrl = match[1].trim().replace(/^["']|["']$/g, "");
  } catch {}
}

if (!dbUrl) {
  console.error("DATABASE_URL not found");
  process.exit(1);
}

const pool = new pg.Pool({ connectionString: dbUrl, ssl: false });

async function run() {
  const client = await pool.connect();
  try {
    await client.query(`
      ALTER TABLE float_topup_requests
        ADD COLUMN IF NOT EXISTS "supervisorApprovalRequired" boolean DEFAULT false NOT NULL
    `);
    await client.query(`
      ALTER TABLE float_topup_requests
        ADD COLUMN IF NOT EXISTS "supervisorApprovedBy" varchar(64)
    `);
    await client.query(`
      ALTER TABLE float_topup_requests
        ADD COLUMN IF NOT EXISTS "supervisorApprovedAt" timestamp
    `);
    console.log("Migration applied: supervisorApprovalRequired, supervisorApprovedBy, supervisorApprovedAt");
  } finally {
    client.release();
    await pool.end();
  }
}

run().catch((e) => { console.error(e.message); process.exit(1); });
