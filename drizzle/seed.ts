/**
 * Database Seeder
 * ─────────────────────────────────────────────────────────────────────────────
 * Populates the database with realistic test data for development and staging.
 *
 * Usage:
 *   npx tsx drizzle/seed.ts                    # seed all
 *   npx tsx drizzle/seed.ts --only agents      # seed only agents
 *   npx tsx drizzle/seed.ts --reset            # truncate then seed
 *
 * Safe to run multiple times (idempotent via ON CONFLICT DO NOTHING).
 */

import { drizzle } from "drizzle-orm/node-postgres";
import { Pool } from "pg";
import { sql } from "drizzle-orm";
import {
  users, agents, transactions, fraudAlerts, kycSessions,
  merchants, tenants, commissionRules, posTerminals,
  feeRules, velocityLimits, platformSettings, systemConfig,
} from "./schema";

// ─── Config ───────────────────────────────────────────────────────────────────
const DATABASE_URL =
  process.env.POSTGRES_URL ??
  process.env.DATABASE_URL ??
  "postgresql://postgres:postgres@localhost:5432/agentbanking";

const RESET = process.argv.includes("--reset");
const ONLY = process.argv.find((a) => a.startsWith("--only="))?.split("=")[1];

// ─── DB Connection ────────────────────────────────────────────────────────────
const pool = new Pool({ connectionString: DATABASE_URL, max: 5 });
const db = drizzle(pool);

// ─── Helpers ──────────────────────────────────────────────────────────────────
function randomPhone(): string {
  return `+234${Math.floor(7000000000 + Math.random() * 999999999)}`;
}

function randomAmount(min: number, max: number): string {
  return (Math.random() * (max - min) + min).toFixed(2);
}

function randomChoice<T>(arr: T[]): T {
  return arr[Math.floor(Math.random() * arr.length)];
}

function randomDate(daysBack: number): Date {
  const d = new Date();
  d.setDate(d.getDate() - Math.floor(Math.random() * daysBack));
  return d;
}

// ─── Seed Functions ───────────────────────────────────────────────────────────

async function seedTenants() {
  console.log("  Seeding tenants...");
  await db.insert(tenants).values([
    {
      name: "54Link HQ",
      subdomain: "hq",
      status: "active",
      country: "NG",
      currency: "NGN",
      createdAt: new Date(),
    },
    {
      name: "54Link Ghana",
      subdomain: "gh",
      status: "active",
      country: "GH",
      currency: "GHS",
      createdAt: new Date(),
    },
    {
      name: "54Link Kenya",
      subdomain: "ke",
      status: "active",
      country: "KE",
      currency: "KES",
      createdAt: new Date(),
    },
  ] as any).onConflictDoNothing();
  console.log("  ✓ Tenants seeded");
}

async function seedUsers() {
  console.log("  Seeding users...");
  await db.insert(users).values([
    {
      email: "admin@54link.com",
      phone: "+2348000000001",
      role: "admin",
      firstName: "Platform",
      lastName: "Admin",
      isActive: true,
      createdAt: new Date(),
    },
    {
      email: "supervisor@54link.com",
      phone: "+2348000000002",
      role: "supervisor",
      firstName: "Regional",
      lastName: "Supervisor",
      isActive: true,
      createdAt: new Date(),
    },
    {
      email: "user@54link.com",
      phone: "+2348000000003",
      role: "user",
      firstName: "Test",
      lastName: "User",
      isActive: true,
      createdAt: new Date(),
    },
  ] as any).onConflictDoNothing();
  console.log("  ✓ Users seeded");
}

async function seedAgents() {
  console.log("  Seeding agents...");
  const agentData = Array.from({ length: 20 }, (_, i) => ({
    agentCode: `AGT${String(i + 1).padStart(6, "0")}`,
    fullName: `Agent ${i + 1}`,
    phone: randomPhone(),
    email: `agent${i + 1}@54link.com`,
    tier: randomChoice(["Bronze", "Silver", "Gold", "Platinum"]),
    isActive: true,
    floatBalance: randomAmount(10000, 500000),
    floatLimit: "1000000.00",
    commissionBalance: randomAmount(0, 50000),
    tenantId: 1,
    state: randomChoice(["Lagos", "Abuja", "Kano", "Rivers", "Oyo"]),
    lga: "Test LGA",
    createdAt: randomDate(365),
  }));

  await db.insert(agents).values(agentData as any).onConflictDoNothing();
  console.log("  ✓ Agents seeded (20)");
}

async function seedTransactions() {
  console.log("  Seeding transactions...");
  const txTypes = ["Cash In", "Cash Out", "Transfer", "Airtime", "Bill Payment"];
  const txStatuses = ["completed", "completed", "completed", "failed", "pending"];

  const txData = Array.from({ length: 100 }, (_, i) => ({
    txRef: `TXN${Date.now()}${i}`,
    agentId: Math.floor(Math.random() * 20) + 1,
    type: randomChoice(txTypes),
    amount: randomAmount(100, 50000),
    fee: randomAmount(10, 500),
    commission: randomAmount(5, 250),
    status: randomChoice(txStatuses),
    channel: randomChoice(["USSD", "App", "POS", "Web"]),
    recipientPhone: randomPhone(),
    recipientName: `Recipient ${i}`,
    tenantId: 1,
    fraudScore: (Math.random() * 100).toFixed(2),
    createdAt: randomDate(90),
  }));

  await db.insert(transactions).values(txData as any).onConflictDoNothing();
  console.log("  ✓ Transactions seeded (100)");
}

async function seedCommissionRules() {
  console.log("  Seeding commission rules...");
  await db.insert(commissionRules).values([
    {
      name: "Standard Cash In",
      type: "flat",
      rate: "0.50",
      minAmount: "100",
      maxAmount: "999999",
      txType: "Cash In",
      tenantId: 1,
      isActive: true,
      createdAt: new Date(),
    },
    {
      name: "Standard Cash Out",
      type: "percentage",
      rate: "0.75",
      minAmount: "100",
      maxAmount: "999999",
      txType: "Cash Out",
      tenantId: 1,
      isActive: true,
      createdAt: new Date(),
    },
    {
      name: "Transfer Commission",
      type: "percentage",
      rate: "0.30",
      minAmount: "100",
      maxAmount: "999999",
      txType: "Transfer",
      tenantId: 1,
      isActive: true,
      createdAt: new Date(),
    },
  ] as any).onConflictDoNothing();
  console.log("  ✓ Commission rules seeded");
}

async function seedFeeRules() {
  console.log("  Seeding fee rules...");
  await db.insert(feeRules).values([
    {
      name: "Cash In Fee",
      txType: "Cash In",
      feeType: "flat",
      amount: "50.00",
      tenantId: 1,
      isActive: true,
      createdAt: new Date(),
    },
    {
      name: "Cash Out Fee",
      txType: "Cash Out",
      feeType: "percentage",
      amount: "1.00",
      tenantId: 1,
      isActive: true,
      createdAt: new Date(),
    },
  ] as any).onConflictDoNothing();
  console.log("  ✓ Fee rules seeded");
}

async function seedVelocityLimits() {
  console.log("  Seeding velocity limits...");
  await db.insert(velocityLimits).values([
    {
      tier: "Bronze",
      maxDailyTxCount: 50,
      maxDailyVolume: "500000.00",
      maxSingleTxAmount: "50000.00",
      dailyTxLimit: "500000.00",
      singleTxLimit: "50000.00",
      tenantId: 1,
      createdAt: new Date(),
    },
    {
      tier: "Silver",
      maxDailyTxCount: 100,
      maxDailyVolume: "1000000.00",
      maxSingleTxAmount: "100000.00",
      dailyTxLimit: "1000000.00",
      singleTxLimit: "100000.00",
      tenantId: 1,
      createdAt: new Date(),
    },
    {
      tier: "Gold",
      maxDailyTxCount: 200,
      maxDailyVolume: "5000000.00",
      maxSingleTxAmount: "500000.00",
      dailyTxLimit: "5000000.00",
      singleTxLimit: "500000.00",
      tenantId: 1,
      createdAt: new Date(),
    },
    {
      tier: "Platinum",
      maxDailyTxCount: 500,
      maxDailyVolume: "20000000.00",
      maxSingleTxAmount: "2000000.00",
      dailyTxLimit: "20000000.00",
      singleTxLimit: "2000000.00",
      tenantId: 1,
      createdAt: new Date(),
    },
  ] as any).onConflictDoNothing();
  console.log("  ✓ Velocity limits seeded");
}

async function seedPlatformSettings() {
  console.log("  Seeding platform settings...");
  await db.insert(platformSettings).values([
    { key: "maintenance_mode", value: "false", description: "Enable maintenance mode", createdAt: new Date() },
    { key: "max_login_attempts", value: "5", description: "Max failed login attempts before lockout", createdAt: new Date() },
    { key: "otp_expiry_minutes", value: "10", description: "OTP expiry in minutes", createdAt: new Date() },
    { key: "session_timeout_hours", value: "24", description: "Session timeout in hours", createdAt: new Date() },
    { key: "fraud_score_threshold", value: "75", description: "Fraud score threshold for auto-block", createdAt: new Date() },
    { key: "min_float_balance", value: "1000", description: "Minimum float balance before alert", createdAt: new Date() },
  ] as any).onConflictDoNothing();
  console.log("  ✓ Platform settings seeded");
}

// ─── Reset Helper ─────────────────────────────────────────────────────────────
async function resetDatabase() {
  console.log("  Resetting database (truncating seed tables)...");
  await db.execute(sql`
    TRUNCATE TABLE
      "platform_settings",
      "velocity_limits",
      "fee_rules",
      "commission_rules",
      "transactions",
      "agents",
      "users",
      "tenants"
    RESTART IDENTITY CASCADE
  `);
  console.log("  ✓ Database reset");
}

// ─── Main ─────────────────────────────────────────────────────────────────────
async function main() {
  console.log("🌱 Starting database seed...\n");

  try {
    if (RESET) {
      await resetDatabase();
    }

    const seeders: Record<string, () => Promise<void>> = {
      tenants: seedTenants,
      users: seedUsers,
      agents: seedAgents,
      transactions: seedTransactions,
      commissionRules: seedCommissionRules,
      feeRules: seedFeeRules,
      velocityLimits: seedVelocityLimits,
      platformSettings: seedPlatformSettings,
    };

    if (ONLY) {
      if (!seeders[ONLY]) {
        console.error(`Unknown seeder: ${ONLY}. Available: ${Object.keys(seeders).join(", ")}`);
        process.exit(1);
      }
      await seeders[ONLY]();
    } else {
      // Run in dependency order
      for (const seeder of Object.values(seeders)) {
        await seeder();
      }
    }

    console.log("\n✅ Database seed complete!");
  } catch (err) {
    console.error("\n❌ Seed failed:", err);
    process.exit(1);
  } finally {
    await pool.end();
  }
}

main();
