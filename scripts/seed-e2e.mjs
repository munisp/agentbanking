#!/usr/bin/env node
/**
 * seed-e2e.mjs — Minimal, schema-correct seed for Playwright E2E tests.
 *
 * Inserts the agent/admin/supervisor fixtures the E2E specs log in with
 * (AGT001 / PIN 1234, ADMIN1 / PIN 0000, SUP001 / PIN 9999). Uses the current
 * camelCase column names and bcrypt-hashed PINs so the tRPC agent.login flow
 * accepts them.
 *
 * Idempotent: re-running upserts by agentCode.
 */
import pg from "pg";
import bcrypt from "bcryptjs";

const { Pool } = pg;

const AGENTS = [
  { code: "AGT001", name: "Emeka Obi", phone: "08012345678", pin: "1234", tier: "Gold", role: "agent" },
  { code: "AGT002", name: "Fatima Yusuf", phone: "08023456789", pin: "2345", tier: "Silver", role: "agent" },
  { code: "AGT003", name: "Chidi Nwosu", phone: "08034567890", pin: "3456", tier: "Platinum", role: "agent" },
  { code: "ADMIN1", name: "Admin User", phone: "08099999999", pin: "0000", tier: "Platinum", role: "admin" },
  { code: "SUP001", name: "Supervisor Ade", phone: "08098765432", pin: "9999", tier: "Gold", role: "supervisor" },
];

async function main() {
  const connectionString =
    process.env.DATABASE_URL || process.env.POSTGRES_URL;
  if (!connectionString) {
    console.error("[seed-e2e] DATABASE_URL / POSTGRES_URL not set");
    process.exit(1);
  }
  const pool = new Pool({ connectionString });

  for (const a of AGENTS) {
    const pinHash = await bcrypt.hash(a.pin, 10);
    await pool.query(
      `INSERT INTO agents ("agentCode", name, phone, "pinHash", tier, role, "isActive", "hierarchyRole")
       VALUES ($1, $2, $3, $4, $5::agent_tier, $6, true, $6)
       ON CONFLICT ("agentCode") DO UPDATE
         SET name = EXCLUDED.name,
             phone = EXCLUDED.phone,
             "pinHash" = EXCLUDED."pinHash",
             tier = EXCLUDED.tier,
             role = EXCLUDED.role,
             "isActive" = true`,
      [a.code, a.name, a.phone, pinHash, a.tier, a.role]
    );
    console.log(`[seed-e2e] upserted ${a.code} (${a.role})`);
  }

  const { rows } = await pool.query(
    'SELECT count(*)::int AS n FROM agents'
  );
  console.log(`[seed-e2e] agents in DB: ${rows[0].n}`);
  await pool.end();
}

main().catch((err) => {
  console.error("[seed-e2e] failed:", err);
  process.exit(1);
});
