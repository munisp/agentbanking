/**
 * 54Link POS Shell — Database Seed Script
 * Run: POSTGRES_URL=... node scripts/seed.mjs
 */
import pg from "pg";
import bcrypt from "bcryptjs";

const { Pool } = pg;

const POSTGRES_URL =
  process.env.POSTGRES_URL ?? "postgresql://posadmin:pos54link2026@localhost:5432/pos54link";

const pool = new Pool({ connectionString: POSTGRES_URL, ssl: false });

const AGENTS = [
  { code: "AGT001", name: "Emeka Obi", phone: "08012345678", pin: "1234", tier: "Gold", location: "Lagos Island, Lagos", float: "850000.00", commission: "24500.00", loyalty: 18750, streak: 12, rank: 3 },
  { code: "AGT002", name: "Fatima Yusuf", phone: "08023456789", pin: "2345", tier: "Silver", location: "Kano Central, Kano", float: "420000.00", commission: "8900.00", loyalty: 7200, streak: 5, rank: 18 },
  { code: "AGT003", name: "Chidi Nwosu", phone: "08034567890", pin: "3456", tier: "Platinum", location: "Onitsha, Anambra", float: "1500000.00", commission: "67800.00", loyalty: 62400, streak: 30, rank: 1 },
  { code: "AGT004", name: "Amaka Eze", phone: "08045678901", pin: "4567", tier: "Bronze", location: "Enugu North, Enugu", float: "120000.00", commission: "2100.00", loyalty: 1850, streak: 2, rank: 87 },
  { code: "ADMIN1", name: "Admin User", phone: "08099999999", pin: "0000", tier: "Platinum", location: "Head Office, Lagos", float: "5000000.00", commission: "0.00", loyalty: 0, streak: 0, rank: null },
];

const TX_TYPES = ["Cash In", "Cash Out", "Transfer", "Airtime", "Bill Payment", "Card Payment"];
const TX_CHANNELS = ["Cash", "Card", "USSD", "QR", "NFC", "App"];
const CUSTOMER_NAMES = ["Biodun Adeyemi", "Ngozi Okafor", "Musa Ibrahim", "Chioma Obi", "Suleiman Bello", "Adaeze Nwosu"];

async function seed() {
  const client = await pool.connect();
  try {
    console.log("🌱 Seeding 54Link POS database...\n");

    // Seed agents
    for (const a of AGENTS) {
      const pinHash = await bcrypt.hash(a.pin, 10);
      await client.query(
        `INSERT INTO agents ("agentCode", name, phone, tier, "pinHash", "floatBalance", "commissionBalance", "loyaltyPoints", streak, rank, location, "terminalModel", "terminalSerial", "isActive")
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, 'PAX A920 MAX', $12, true)
         ON CONFLICT ("agentCode") DO UPDATE SET "pinHash" = $5, "floatBalance" = $6, "commissionBalance" = $7, "loyaltyPoints" = $8, streak = $9, rank = $10`,
        [a.code, a.name, a.phone, a.tier, pinHash, a.float, a.commission, a.loyalty, a.streak, a.rank, a.location, `SN${a.code}2026`]
      );
      console.log(`  ✅ Agent: ${a.code} — ${a.name} (PIN: ${a.pin})`);
    }

    // Get agent IDs
    const agentRows = await client.query(`SELECT id, "agentCode" FROM agents`);
    const agentMap = Object.fromEntries(agentRows.rows.map((r) => [r.agentCode, r.id]));

    // Seed 50 transactions for AGT001
    const agentId = agentMap["AGT001"];
    console.log("\n  Seeding transactions for AGT001...");
    for (let i = 0; i < 50; i++) {
      const type = TX_TYPES[Math.floor(Math.random() * TX_TYPES.length)];
      const amount = (Math.floor(Math.random() * 95000 + 5000)).toFixed(2);
      const channel = TX_CHANNELS[Math.floor(Math.random() * TX_CHANNELS.length)];
      const customer = CUSTOMER_NAMES[Math.floor(Math.random() * CUSTOMER_NAMES.length)];
      const ref = `TXN${Date.now().toString(36).toUpperCase()}${Math.random().toString(36).slice(2, 5).toUpperCase()}`;
      const daysAgo = Math.floor(Math.random() * 30);
      const createdAt = new Date(Date.now() - daysAgo * 86400000);
      await client.query(
        `INSERT INTO transactions (ref, "agentId", type, amount, channel, status, "customerName", "fraudScore", "createdAt", "updatedAt")
         VALUES ($1, $2, $3, $4, $5, 'success', $6, '0.00', $7, $7)`,
        [ref, agentId, type, amount, channel, customer, createdAt]
      );
    }
    console.log("  ✅ 50 transactions seeded for AGT001");

    // Seed fraud alerts
    console.log("\n  Seeding fraud alerts...");
    const fraudTypes = [
      { severity: "critical", type: "Structuring Pattern", reason: "Multiple sub-threshold transactions detected within 10 minutes", score: "0.92" },
      { severity: "high", type: "Velocity Anomaly", reason: "Transaction rate 4× above 30-day baseline", score: "0.78" },
      { severity: "high", type: "Large Cash Out", reason: "Single cash-out of ₦950,000 exceeds daily threshold", score: "0.71" },
      { severity: "medium", type: "Unusual Geography", reason: "Transaction origin 120km from registered agent zone", score: "0.55" },
      { severity: "low", type: "Duplicate Transaction", reason: "Same amount and recipient within 3 minutes", score: "0.32" },
    ];
    for (const f of fraudTypes) {
      await client.query(
        `INSERT INTO fraud_alerts (severity, type, reason, "fraudScore", status, "customerName", amount, "createdAt", "updatedAt")
         VALUES ($1, $2, $3, $4, 'open', 'Suspicious Customer', '150000.00', NOW(), NOW())`,
        [f.severity, f.type, f.reason, f.score]
      );
    }
    console.log("  ✅ 5 fraud alerts seeded");

    // Seed loyalty history for AGT001
    console.log("\n  Seeding loyalty history for AGT001...");
    const loyaltyEntries = [
      { type: "earned", points: 450, desc: "Cash In — ₦450,000", balance: 18750 },
      { type: "earned", points: 200, desc: "Transfer — ₦100,000", balance: 18300 },
      { type: "bonus", points: 500, desc: "Weekly challenge: 50 transactions", balance: 18100 },
      { type: "redeemed", points: -1000, desc: "Redeemed: ₦500 Cash Bonus", balance: 17600 },
      { type: "earned", points: 100, desc: "Airtime — ₦20,000", balance: 18600 },
    ];
    for (const l of loyaltyEntries) {
      await client.query(
        `INSERT INTO loyalty_history ("agentId", type, points, description, "balanceAfter", "createdAt")
         VALUES ($1, $2, $3, $4, $5, NOW())`,
        [agentId, l.type, l.points, l.desc, l.balance]
      );
    }
    console.log("  ✅ Loyalty history seeded for AGT001");

    console.log("\n✅ Seed complete!\n");
    console.log("[REDACTED sensitive data]");
    for (const a of AGENTS) {
      console.log(`  ${a.code.padEnd(8)} PIN: ${a.pin}  (${a.name})`);
    }
  } finally {
    client.release();
    await pool.end();
  }
}

seed().catch((err) => {
  console.error("❌ Seed failed:", err);
  process.exit(1);
});
