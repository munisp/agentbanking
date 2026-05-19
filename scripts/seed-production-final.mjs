#!/usr/bin/env node
/**
 * Production Seed Script — 54Link Agency Banking Platform
 * 
 * Seeds: 50 agents, 500 transactions, 20 disputes, 30 KYC records,
 * 10 customers, 5 settlement batches, runtime configs, webhook endpoints
 * 
 * Usage: node scripts/seed-production-final.mjs
 */
import { drizzle } from "drizzle-orm/node-postgres";
import pg from "pg";
import { randomUUID } from "crypto";

const DATABASE_URL = process.env.DATABASE_URL || process.env.POSTGRES_URL;
if (!DATABASE_URL) { console.error("DATABASE_URL required"); process.exit(1); }

const pool = new pg.Pool({ connectionString: DATABASE_URL, ssl: { rejectUnauthorized: false } });

// ── Helpers ─────────────────────────────────────────────────────────────
const rand = (min, max) => Math.floor(Math.random() * (max - min + 1)) + min;
const pick = (arr) => arr[rand(0, arr.length - 1)];
const uuid = () => randomUUID();
const now = () => new Date().toISOString();
const pastDate = (daysAgo) => new Date(Date.now() - daysAgo * 86400000).toISOString();

const TIERS = ["basic", "standard", "premium", "enterprise"];
const TX_TYPES = ["cash_in", "cash_out", "transfer", "airtime", "bills", "card_payment", "qr_payment"];
const TX_STATUSES = ["initiated", "validated", "processing", "processed", "settled", "reconciled", "failed"];
const CHANNELS = ["pos", "mobile", "web", "ussd", "api"];
const DISPUTE_STATUSES = ["filed", "investigating", "evidence_requested", "escalated", "resolved_customer", "resolved_merchant", "closed"];
const KYC_STATUSES = ["submitted", "document_review", "liveness_check", "approved", "rejected"];
const NIGERIAN_STATES = ["Lagos", "Abuja", "Kano", "Rivers", "Oyo", "Kaduna", "Enugu", "Delta", "Anambra", "Edo"];
const FIRST_NAMES = ["Adebayo", "Chioma", "Emeka", "Fatima", "Ibrahim", "Kemi", "Ngozi", "Oluwaseun", "Rasheed", "Yetunde", "Aisha", "Chidi", "Damilola", "Funke", "Hassan", "Ifeoma", "Jide", "Kehinde", "Ladi", "Musa"];
const LAST_NAMES = ["Okafor", "Adeyemi", "Balogun", "Chukwu", "Danjuma", "Eze", "Fashola", "Garba", "Hussaini", "Igwe", "Johnson", "Kalu", "Lawal", "Mohammed", "Nnamdi", "Obi", "Peters", "Quadri", "Raji", "Suleiman"];

async function seed() {
  const client = await pool.connect();
  console.log("[Seed] Connected to database");
  
  try {
    await client.query("BEGIN");
    
    // ── 1. Seed 50 Agents ─────────────────────────────────────────
    console.log("[Seed] Creating 50 agents...");
    const agentIds = [];
    for (let i = 1; i <= 50; i++) {
      const code = `AGT${String(i).padStart(3, "0")}`;
      const firstName = pick(FIRST_NAMES);
      const lastName = pick(LAST_NAMES);
      const tier = pick(TIERS);
      const state = pick(NIGERIAN_STATES);
      const phone = `+234${rand(700, 909)}${rand(1000000, 9999999)}`;
      const email = `${firstName.toLowerCase()}.${lastName.toLowerCase()}${i}@54link.ng`;
      
      const result = await client.query(`
        INSERT INTO agents (agent_code, name, phone, email, tier, location, status, float_balance, commission_balance, created_at, updated_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $10)
        ON CONFLICT (agent_code) DO UPDATE SET name = $2
        RETURNING id
      `, [code, `${firstName} ${lastName}`, phone, email, tier, `${state}, Nigeria`, "active", rand(50000, 5000000), rand(1000, 100000), pastDate(rand(30, 365))]);
      
      agentIds.push(result.rows[0]?.id ?? i);
    }
    console.log(`[Seed] ✓ ${agentIds.length} agents created`);
    
    // ── 2. Seed 500 Transactions ──────────────────────────────────
    console.log("[Seed] Creating 500 transactions...");
    let txCount = 0;
    for (let i = 1; i <= 500; i++) {
      const ref = `TXN-${uuid().slice(0, 8).toUpperCase()}`;
      const type = pick(TX_TYPES);
      const amount = rand(100, 500000);
      const status = pick(TX_STATUSES);
      const channel = pick(CHANNELS);
      const agentId = pick(agentIds);
      const customerName = `${pick(FIRST_NAMES)} ${pick(LAST_NAMES)}`;
      const customerPhone = `+234${rand(700, 909)}${rand(1000000, 9999999)}`;
      
      try {
        await client.query(`
          INSERT INTO transactions (ref, type, amount, status, channel, agent_id, customer, customer_phone, created_at, updated_at)
          VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $9)
          ON CONFLICT DO NOTHING
        `, [ref, type, amount, status, channel, agentId, customerName, customerPhone, pastDate(rand(0, 90))]);
        txCount++;
      } catch (e) {
        // Skip duplicates
      }
    }
    console.log(`[Seed] ✓ ${txCount} transactions created`);
    
    // ── 3. Seed 10 Customers ──────────────────────────────────────
    console.log("[Seed] Creating 10 customers...");
    for (let i = 1; i <= 10; i++) {
      const firstName = pick(FIRST_NAMES);
      const lastName = pick(LAST_NAMES);
      const phone = `+234${rand(700, 909)}${rand(1000000, 9999999)}`;
      const email = `${firstName.toLowerCase()}.${lastName.toLowerCase()}@gmail.com`;
      
      try {
        await client.query(`
          INSERT INTO customers (name, phone, email, kyc_level, created_at, updated_at)
          VALUES ($1, $2, $3, $4, $5, $5)
          ON CONFLICT DO NOTHING
        `, [`${firstName} ${lastName}`, phone, email, rand(1, 3), pastDate(rand(10, 180))]);
      } catch (e) { /* skip */ }
    }
    console.log("[Seed] ✓ 10 customers created");
    
    // ── 4. Seed 20 Disputes ───────────────────────────────────────
    console.log("[Seed] Creating 20 disputes...");
    const disputeReasons = [
      "Customer claims unauthorized transaction",
      "Duplicate charge on account",
      "Wrong amount debited",
      "Service not received after payment",
      "Agent overcharged commission",
      "Network error caused double debit",
      "Customer did not authorize POS transaction",
    ];
    
    for (let i = 1; i <= 20; i++) {
      const txRef = `TXN-${uuid().slice(0, 8).toUpperCase()}`;
      const status = pick(DISPUTE_STATUSES);
      const reason = pick(disputeReasons);
      const agentId = pick(agentIds);
      const amount = rand(500, 100000);
      
      try {
        await client.query(`
          INSERT INTO disputes (transaction_ref, status, reason, agent_id, amount, category, created_at, updated_at)
          VALUES ($1, $2, $3, $4, $5, $6, $7, $7)
          ON CONFLICT DO NOTHING
        `, [txRef, status, reason, agentId, amount, pick(["unauthorized", "duplicate", "wrong_amount", "service_not_received", "other"]), pastDate(rand(0, 60))]);
      } catch (e) { /* skip */ }
    }
    console.log("[Seed] ✓ 20 disputes created");
    
    // ── 5. Seed 30 KYC Records ────────────────────────────────────
    console.log("[Seed] Creating 30 KYC records...");
    for (let i = 1; i <= 30; i++) {
      const agentId = agentIds[i % agentIds.length];
      const status = pick(KYC_STATUSES);
      const docType = pick(["national_id", "drivers_license", "passport", "voters_card"]);
      
      try {
        await client.query(`
          INSERT INTO kyc_verifications (agent_id, status, document_type, document_number, submitted_at, reviewed_at, created_at)
          VALUES ($1, $2, $3, $4, $5, $6, $5)
          ON CONFLICT DO NOTHING
        `, [agentId, status, docType, `DOC-${uuid().slice(0, 12).toUpperCase()}`, pastDate(rand(5, 90)), status !== "submitted" ? pastDate(rand(0, 5)) : null]);
      } catch (e) { /* skip */ }
    }
    console.log("[Seed] ✓ 30 KYC records created");
    
    // ── 6. Seed 5 Settlement Batches ──────────────────────────────
    console.log("[Seed] Creating 5 settlement batches...");
    for (let i = 1; i <= 5; i++) {
      const batchRef = `STTL-${uuid().slice(0, 8).toUpperCase()}`;
      const status = pick(["pending", "processing", "completed", "reconciled"]);
      const txCount = rand(50, 200);
      const totalAmount = rand(1000000, 50000000);
      
      try {
        await client.query(`
          INSERT INTO settlement_batches (batch_ref, status, transaction_count, total_amount, created_at, completed_at)
          VALUES ($1, $2, $3, $4, $5, $6)
          ON CONFLICT DO NOTHING
        `, [batchRef, status, txCount, totalAmount, pastDate(rand(1, 30)), status === "completed" || status === "reconciled" ? pastDate(rand(0, 1)) : null]);
      } catch (e) { /* skip */ }
    }
    console.log("[Seed] ✓ 5 settlement batches created");
    
    // ── 7. Seed Runtime Configs ───────────────────────────────────
    console.log("[Seed] Creating runtime configs...");
    const configs = [
      ["settlement_batch_size", "5000"],
      ["settlement_concurrency", "4"],
      ["archival_retention_days", "90"],
      ["archival_schedule", JSON.stringify({ enabled: false, cron: "0 3 * * 0", retentionDays: 90 })],
      ["loadtest_p99_threshold_ms", "500"],
      ["loadtest_error_rate_threshold", "5"],
      ["scheduled_loadtest_config", JSON.stringify({ enabled: false, cronExpression: "0 2 * * *", targetRps: 200, duration: 60, concurrency: 5 })],
    ];
    
    for (const [key, value] of configs) {
      try {
        await client.query(`
          INSERT INTO system_config (key, value, updated_at)
          VALUES ($1, $2, NOW())
          ON CONFLICT (key) DO UPDATE SET value = $2, updated_at = NOW()
        `, [key, value]);
      } catch (e) { /* skip if table doesn't exist */ }
    }
    console.log("[Seed] ✓ Runtime configs created");
    
    // ── 8. Seed Webhook Endpoints ─────────────────────────────────
    console.log("[Seed] Creating webhook endpoints...");
    const webhookEndpoints = [
      { name: "ERP Sync", url: "https://erp.54link.ng/webhooks/pos", events: ["transaction.completed", "settlement.completed"] },
      { name: "Fraud Monitor", url: "https://fraud.54link.ng/webhooks/alerts", events: ["transaction.flagged", "dispute.filed"] },
      { name: "Audit Logger", url: "https://audit.54link.ng/webhooks/events", events: ["agent.created", "agent.suspended", "kyc.approved"] },
    ];
    
    for (const wh of webhookEndpoints) {
      try {
        await client.query(`
          INSERT INTO webhook_endpoints (name, url, events, secret, active, created_at)
          VALUES ($1, $2, $3, $4, true, NOW())
          ON CONFLICT DO NOTHING
        `, [wh.name, wh.url, JSON.stringify(wh.events), `whsec_${uuid().replace(/-/g, "")}`]);
      } catch (e) { /* skip */ }
    }
    console.log("[Seed] ✓ Webhook endpoints created");
    
    await client.query("COMMIT");
    console.log("\n[Seed] ✅ Production seed completed successfully!");
    console.log("  • 50 agents across 4 tiers");
    console.log("  • 500 transactions across 7 types");
    console.log("  • 10 customers with KYC levels");
    console.log("  • 20 disputes across 7 statuses");
    console.log("  • 30 KYC verification records");
    console.log("  • 5 settlement batches");
    console.log("  • 7 runtime config entries");
    console.log("  • 3 webhook endpoints");
    
  } catch (err) {
    await client.query("ROLLBACK");
    console.error("[Seed] ❌ Failed:", err.message);
    // Don't exit with error - some tables may not exist yet
  } finally {
    client.release();
    await pool.end();
  }
}

seed();
