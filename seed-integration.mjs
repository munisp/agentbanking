/**
 * seed-integration.mjs
 * Seeds customers, KYC sessions, and POS terminals for the 54Link POS Shell.
 * Run: node seed-integration.mjs
 *
 * Safe to re-run — checks for existing records before inserting.
 */

import pg from "pg";
import { randomUUID } from "crypto";

const { Pool } = pg;
const pool = new Pool({ connectionString: process.env.POSTGRES_URL });

// ── Helpers ───────────────────────────────────────────────────────────────────
const now = () => new Date();
const daysAgo = (n) => new Date(Date.now() - n * 86_400_000);

function randomPhone() {
  const prefixes = ["0803", "0806", "0813", "0816", "0703", "0706", "0813", "0901", "0905"];
  const prefix = prefixes[Math.floor(Math.random() * prefixes.length)];
  return prefix + String(Math.floor(Math.random() * 9_000_000) + 1_000_000);
}

function randomBvn() {
  // BVN is exactly 11 digits
  return String(Math.floor(Math.random() * 90_000_000_000) + 10_000_000_000).slice(0, 11);
}

function randomNin() {
  // NIN is exactly 11 digits
  return String(Math.floor(Math.random() * 90_000_000_000) + 10_000_000_000).slice(0, 11);
}

// ── Fetch existing agents ─────────────────────────────────────────────────────
const { rows: agents } = await pool.query('SELECT id, "agentCode" FROM agents LIMIT 5');
if (agents.length === 0) {
  console.error("No agents found — run the main seed script first.");
  process.exit(1);
}
console.log(`Found ${agents.length} agents: ${agents.map((a) => a.agentCode).join(", ")}`);

// ── 1. Customers ──────────────────────────────────────────────────────────────
const { rows: existingCustomers } = await pool.query("SELECT COUNT(*) FROM customers");
const customerCount = parseInt(existingCustomers[0].count, 10);

const CUSTOMER_SEED = [
  { firstName: "Amina", lastName: "Bello", email: "amina.bello@example.ng", kycLevel: 2, walletBalance: 45000, status: "active" },
  { firstName: "Chukwuemeka", lastName: "Okafor", email: "c.okafor@example.ng", kycLevel: 1, walletBalance: 12500, status: "active" },
  { firstName: "Fatima", lastName: "Musa", email: "fatima.musa@example.ng", kycLevel: 2, walletBalance: 78000, status: "active" },
  { firstName: "Taiwo", lastName: "Adeyemi", email: "taiwo.adeyemi@example.ng", kycLevel: 0, walletBalance: 0, status: "pending_kyc" },
  { firstName: "Ngozi", lastName: "Eze", email: "ngozi.eze@example.ng", kycLevel: 2, walletBalance: 125000, status: "active" },
  { firstName: "Usman", lastName: "Garba", email: "usman.garba@example.ng", kycLevel: 1, walletBalance: 8000, status: "active" },
  { firstName: "Blessing", lastName: "Nwosu", email: "blessing.nwosu@example.ng", kycLevel: 2, walletBalance: 55000, status: "active" },
  { firstName: "Ibrahim", lastName: "Suleiman", email: "ibrahim.s@example.ng", kycLevel: 0, walletBalance: 0, status: "pending_kyc" },
  { firstName: "Adaeze", lastName: "Obi", email: "adaeze.obi@example.ng", kycLevel: 2, walletBalance: 200000, status: "active" },
  { firstName: "Musa", lastName: "Aliyu", email: "musa.aliyu@example.ng", kycLevel: 1, walletBalance: 3500, status: "active" },
];

let customersInserted = 0;
const customerIds = [];

if (customerCount === 0) {
  for (const c of CUSTOMER_SEED) {
    const phone = randomPhone();
    const { rows } = await pool.query(
      `INSERT INTO customers
         ("externalId", "firstName", "lastName", email, phone, bvn, nin,
          "dateOfBirth", address, status, "kycLevel", "walletBalance",
          "dailyLimit", "monthlyLimit", "preferredAgentId", "createdAt", "updatedAt")
       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$16)
       RETURNING id`,
      [
        randomUUID(),
        c.firstName,
        c.lastName,
        c.email,
        phone,
        randomBvn(),
        randomNin(),
        new Date(1985 + Math.floor(Math.random() * 30), Math.floor(Math.random() * 12), Math.floor(Math.random() * 28) + 1).toISOString().slice(0, 10),
        `${Math.floor(Math.random() * 999) + 1} ${["Adeola Odeku", "Broad Street", "Bode Thomas", "Awolowo Road", "Marina"][Math.floor(Math.random() * 5)]}, Lagos`,
        c.status,
        c.kycLevel,
        c.walletBalance * 100, // store in kobo
        500_000 * 100,
        5_000_000 * 100,
        agents[Math.floor(Math.random() * agents.length)].id,
        daysAgo(Math.floor(Math.random() * 90)),
      ]
    );
    customerIds.push(rows[0].id);
    customersInserted++;
  }
  console.log(`✓ Inserted ${customersInserted} customers`);
} else {
  const { rows: existing } = await pool.query("SELECT id FROM customers LIMIT 10");
  existing.forEach((r) => customerIds.push(r.id));
  console.log(`  Customers already seeded (${customerCount} rows) — skipping`);
}

// ── 2. KYC Sessions ───────────────────────────────────────────────────────────
const { rows: existingKyc } = await pool.query("SELECT COUNT(*) FROM kyc_sessions");
const kycCount = parseInt(existingKyc[0].count, 10);

if (kycCount === 0 && customerIds.length > 0) {
  const kycStatuses = ["completed", "completed", "completed", "pending", "rejected"];
  const docTypes = ["NIN", "BVN_CARD", "PASSPORT", "DRIVERS_LICENCE", "VOTER_CARD"];
  let kycInserted = 0;

  for (let i = 0; i < Math.min(customerIds.length, 8); i++) {
    const status = kycStatuses[i % kycStatuses.length];
    const agentId = agents[i % agents.length].id;
    const docType = docTypes[i % docTypes.length];
    const passed = status === "approved";

    await pool.query(
      `INSERT INTO kyc_sessions
         ("agentId", status, "livenessScore", "livenessMethod", "livenessPassed",
          "docType", "docExtractedName", "docExtractedDob", "docExtractedIdNumber",
          "docConfidence", "rejectionReason", "createdAt", "updatedAt")
       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$12)`,
      [
        agentId,
        status,
        passed ? (0.85 + Math.random() * 0.14).toFixed(3) : (0.4 + Math.random() * 0.3).toFixed(3),
        null,
        passed,
        docType,
        `${CUSTOMER_SEED[i]?.firstName ?? "Test"} ${CUSTOMER_SEED[i]?.lastName ?? "User"}`,
        new Date(1985 + i * 2, i % 12, (i % 28) + 1),
        `NG-${docType.toUpperCase().slice(0, 2)}-${String(Math.floor(Math.random() * 9_000_000) + 1_000_000)}`,
        passed ? (0.88 + Math.random() * 0.11).toFixed(3) : (0.5 + Math.random() * 0.2).toFixed(3),
        status === "rejected" ? "Document image quality too low" : null,
        daysAgo(Math.floor(Math.random() * 60)),
      ]
    );
    kycInserted++;
  }
  console.log(`✓ Inserted ${kycInserted} KYC sessions`);
} else {
  console.log(`  KYC sessions already seeded (${kycCount} rows) — skipping`);
}

// ── 3. POS Terminals ─────────────────────────────────────────────────────────
const { rows: existingTerminals } = await pool.query("SELECT COUNT(*) FROM pos_terminals");
const terminalCount = parseInt(existingTerminals[0].count, 10);

const TERMINAL_MODELS = ["PAX A920", "Ingenico Move 5000", "Verifone V240m", "PAX S920", "Sunmi P2"];
const FIRMWARE_VERSIONS = ["2.1.4", "3.0.1", "2.8.7", "3.2.0", "2.5.3"];
const TERMINAL_STATUSES = ["active", "active", "active", "inactive", "maintenance"];
const LAGOS_COORDS = [
  [6.4541, 3.3947], [6.5244, 3.3792], [6.4698, 3.5852],
  [6.6018, 3.3515], [6.4355, 3.4197], [6.5227, 3.6145],
];

if (terminalCount === 0) {
  let terminalsInserted = 0;
  for (let i = 0; i < agents.length; i++) {
    const agent = agents[i];
    const coords = LAGOS_COORDS[i % LAGOS_COORDS.length];
    const status = TERMINAL_STATUSES[i % TERMINAL_STATUSES.length];

    await pool.query(
      `INSERT INTO pos_terminals
         ("serialNumber", model, "firmwareVersion", "appVersion", "agentId",
          status, "lastHeartbeatAt", "configJson", "locationLat", "locationLng",
          notes, "createdAt", "updatedAt")
       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$12)`,
      [
        `54L-${agent.agentCode}-${String(i + 1).padStart(3, "0")}`,
        TERMINAL_MODELS[i % TERMINAL_MODELS.length],
        FIRMWARE_VERSIONS[i % FIRMWARE_VERSIONS.length],
        "1.4.2",
        agent.id,
        status,
        status === "online" ? daysAgo(0) : daysAgo(Math.floor(Math.random() * 7) + 1),
        JSON.stringify({
          maxTxAmount: 500_000,
          allowedTxTypes: ["cash_in", "cash_out", "transfer", "airtime", "bills"],
          receiptPrinter: true,
          nfcEnabled: true,
          qrEnabled: true,
        }),
        coords[0],
        coords[1],
        `Terminal assigned to agent ${agent.agentCode}`,
        daysAgo(Math.floor(Math.random() * 180) + 30),
      ]
    );
    terminalsInserted++;
  }
  console.log(`✓ Inserted ${terminalsInserted} POS terminals`);
} else {
  console.log(`  POS terminals already seeded (${terminalCount} rows) — skipping`);
}

// ── Summary ───────────────────────────────────────────────────────────────────
const counts = await Promise.all(
  ["agents", "transactions", "customers", "kyc_sessions", "fraud_alerts", "pos_terminals"].map((t) =>
    pool.query("SELECT COUNT(*) FROM " + t).then((r) => `${t}: ${r.rows[0].count}`)
  )
);
console.log("\n=== Database Summary ===");
counts.forEach((c) => console.log(" ", c));
console.log("\nSeed complete ✓");

await pool.end();
