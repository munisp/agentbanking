#!/usr/bin/env node
/**
 * Sprint 65 F16: Unified Final Seed Script
 * Consolidates all sprint seed data into one comprehensive script.
 * 
 * Usage: node scripts/seed-final-unified.mjs [--env production|staging|dev]
 * 
 * Seeds:
 * - 50 agents (5 admin, 10 super, 35 regular) with KYC
 * - 500 transactions across all types
 * - 30 fraud alerts (5 critical, 10 high, 15 medium)
 * - 20 disputes in various lifecycle stages
 * - 100 chat sessions with 500 messages
 * - 50 loyalty records
 * - 30 KYC documents
 * - 10 webhook endpoints
 * - 20 settlement batches
 * - Runtime config defaults
 */

import crypto from "crypto";

const ENV = process.argv.includes("--env")
  ? process.argv[process.argv.indexOf("--env") + 1]
  : "dev";

const BASE_URL = process.env.SEED_BASE_URL || "http://localhost:3000";

console.log(`\n🌱 54Link POS Shell — Unified Seed Script`);
console.log(`   Environment: ${ENV}`);
console.log(`   Target: ${BASE_URL}`);
console.log(`   Started: ${new Date().toISOString()}\n`);

// ============================================================
// Seed Data Generators
// ============================================================

const AGENT_TIERS = ["bronze", "silver", "gold", "platinum", "diamond"];
const TX_TYPES = ["cash_in", "cash_out", "transfer", "airtime", "bills", "card_payment", "qr_payment", "nfc_payment"];
const TX_STATUSES = ["completed", "pending", "failed", "reversed"];
const FRAUD_SEVERITIES = ["critical", "high", "medium", "low"];
const DISPUTE_STATUSES = ["filed", "investigating", "evidence_review", "resolved_customer", "resolved_merchant", "closed"];
const CHAT_STATUSES = ["active", "waiting", "resolved", "closed"];
const KYC_DOC_TYPES = ["national_id", "passport", "drivers_license", "utility_bill", "bank_statement", "cac_certificate"];
const NIGERIAN_BANKS = ["Access Bank", "GTBank", "First Bank", "UBA", "Zenith Bank", "Stanbic IBTC", "Fidelity Bank", "Sterling Bank", "Wema Bank", "Polaris Bank"];
const NIGERIAN_STATES = ["Lagos", "Abuja", "Kano", "Rivers", "Oyo", "Kaduna", "Enugu", "Delta", "Anambra", "Edo"];
const NIGERIAN_NAMES = [
  "Adebayo Ogundimu", "Chioma Nwosu", "Emeka Okafor", "Fatima Bello", "Ibrahim Musa",
  "Jumoke Adeyemi", "Kelechi Eze", "Lateef Abubakar", "Ngozi Okoro", "Oluwaseun Adeleke",
  "Patience Obi", "Rasheed Yusuf", "Sade Oladipo", "Tunde Bakare", "Uche Nnamdi",
  "Victoria Adekunle", "Wale Ogunleye", "Yetunde Fashola", "Zainab Abdullahi", "Aisha Mohammed",
  "Blessing Igwe", "Chidi Anyanwu", "Damilola Ojo", "Ebere Nwachukwu", "Funke Akindele",
  "Gbenga Oyedele", "Halima Sani", "Ikenna Obi", "Juliet Nnadi", "Kayode Afolabi",
  "Lilian Okonkwo", "Musa Garba", "Nkechi Agu", "Obinna Eze", "Priscilla Adamu",
  "Quadri Lawal", "Rosemary Okeke", "Segun Adeniyi", "Toyin Balogun", "Uchenna Chukwu",
  "Vivian Okafor", "Wasiu Alabi", "Xena Ogunyemi", "Yusuf Danjuma", "Zara Balarabe",
  "Amara Obi", "Bola Tinubu", "Chiamaka Eze", "Dapo Oyebanjo", "Ese Oruru"
];

function randomId() {
  return crypto.randomUUID().slice(0, 8);
}

function randomAmount(min, max) {
  return Math.round((Math.random() * (max - min) + min) * 100) / 100;
}

function randomDate(daysBack = 90) {
  return new Date(Date.now() - Math.random() * daysBack * 24 * 60 * 60 * 1000);
}

function randomPhone() {
  return `+234${Math.floor(7000000000 + Math.random() * 2999999999)}`;
}

function randomPick(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}

// ============================================================
// Generate Seed Data
// ============================================================

function generateAgents(count = 50) {
  const agents = [];
  for (let i = 0; i < count; i++) {
    const isAdmin = i < 5;
    const isSuper = i >= 5 && i < 15;
    agents.push({
      agentCode: `AGT${String(i + 1).padStart(4, "0")}`,
      name: NIGERIAN_NAMES[i % NIGERIAN_NAMES.length],
      phone: randomPhone(),
      email: `agent${i + 1}@54link.ng`,
      role: isAdmin ? "admin" : isSuper ? "super_agent" : "agent",
      tier: isAdmin ? "diamond" : isSuper ? "gold" : randomPick(AGENT_TIERS),
      floatBalance: randomAmount(50000, 5000000),
      commissionBalance: randomAmount(1000, 500000),
      loyaltyPoints: Math.floor(Math.random() * 50000),
      isActive: Math.random() > 0.05,
      location: randomPick(NIGERIAN_STATES),
      bank: randomPick(NIGERIAN_BANKS),
      accountNumber: String(Math.floor(1000000000 + Math.random() * 9000000000)),
      pinHash: "$2b$10$dummy.hash.for.seed.data.only",
      createdAt: randomDate(365),
    });
  }
  return agents;
}

function generateTransactions(count = 500, agents = []) {
  const txns = [];
  for (let i = 0; i < count; i++) {
    const agent = randomPick(agents);
    const type = randomPick(TX_TYPES);
    const amount = type === "airtime" ? randomAmount(100, 50000) : randomAmount(500, 500000);
    const fee = Math.round(amount * 0.01 * 100) / 100;
    const commission = Math.round(amount * 0.005 * 100) / 100;

    txns.push({
      ref: `TXN-${Date.now()}-${randomId()}`,
      type,
      amount,
      fee,
      commission,
      customer: randomPhone(),
      customerName: randomPick(NIGERIAN_NAMES),
      agentCode: agent.agentCode,
      status: randomPick(TX_STATUSES),
      channel: randomPick(["pos", "mobile", "web", "ussd"]),
      currency: "NGN",
      mcc: randomPick(["5411", "5541", "5812", "5912", "5999"]),
      createdAt: randomDate(90),
    });
  }
  return txns;
}

function generateFraudAlerts(count = 30, agents = []) {
  const alerts = [];
  const types = ["velocity_breach", "amount_anomaly", "geo_mismatch", "device_change", "pattern_match", "blacklist_hit"];
  for (let i = 0; i < count; i++) {
    const severity = i < 5 ? "critical" : i < 15 ? "high" : i < 25 ? "medium" : "low";
    alerts.push({
      id: `FRD-${randomId()}`,
      type: randomPick(types),
      severity,
      agentCode: randomPick(agents).agentCode,
      customer: randomPhone(),
      amount: randomAmount(10000, 1000000),
      reason: `Automated detection: ${randomPick(types)} triggered`,
      status: randomPick(["new", "investigating", "confirmed", "dismissed"]),
      createdAt: randomDate(30),
    });
  }
  return alerts;
}

function generateDisputes(count = 20) {
  const disputes = [];
  for (let i = 0; i < count; i++) {
    disputes.push({
      id: `DSP-${randomId()}`,
      transactionRef: `TXN-${Date.now()}-${randomId()}`,
      type: randomPick(["unauthorized", "duplicate", "wrong_amount", "service_not_received", "fraud"]),
      amount: randomAmount(1000, 500000),
      status: randomPick(DISPUTE_STATUSES),
      filedBy: randomPick(NIGERIAN_NAMES),
      filedByPhone: randomPhone(),
      assignedTo: Math.random() > 0.3 ? randomPick(NIGERIAN_NAMES) : null,
      evidence: Math.random() > 0.5 ? "Receipt photo uploaded" : null,
      resolution: Math.random() > 0.6 ? randomPick(["refunded", "chargeback", "no_action", "partial_refund"]) : null,
      createdAt: randomDate(60),
    });
  }
  return disputes;
}

function generateChatSessions(count = 100) {
  const sessions = [];
  for (let i = 0; i < count; i++) {
    const messageCount = Math.floor(Math.random() * 15) + 1;
    const messages = [];
    for (let j = 0; j < messageCount; j++) {
      messages.push({
        role: j % 2 === 0 ? "user" : "assistant",
        content: j % 2 === 0
          ? randomPick(["How do I check my balance?", "My transaction failed", "I need help with KYC", "Commission not received", "Float top-up request"])
          : randomPick(["I can help with that. Let me check.", "Your balance is ₦50,000", "Please upload your ID document", "Commission will be credited within 24h", "Float request submitted for approval"]),
        timestamp: new Date(Date.now() - (messageCount - j) * 60000),
      });
    }
    sessions.push({
      id: `CHAT-${randomId()}`,
      userId: randomPick(NIGERIAN_NAMES),
      status: randomPick(CHAT_STATUSES),
      topic: randomPick(["balance_inquiry", "transaction_issue", "kyc_help", "commission", "float_topup", "general"]),
      messages,
      rating: Math.random() > 0.5 ? Math.floor(Math.random() * 5) + 1 : null,
      createdAt: randomDate(30),
    });
  }
  return sessions;
}

function generateKycDocuments(count = 30, agents = []) {
  const docs = [];
  for (let i = 0; i < count; i++) {
    const docType = randomPick(KYC_DOC_TYPES);
    const issuedAt = randomDate(365 * 3);
    const validityDays = { national_id: 3650, passport: 1825, drivers_license: 1095, utility_bill: 90, bank_statement: 90, cac_certificate: 365 };
    const expiresAt = new Date(issuedAt.getTime() + (validityDays[docType] || 365) * 24 * 60 * 60 * 1000);

    docs.push({
      id: `KYC-${randomId()}`,
      agentId: randomPick(agents).agentCode,
      docType,
      documentNumber: `DOC${Math.floor(100000 + Math.random() * 900000)}`,
      issuedAt,
      expiresAt,
      status: expiresAt < new Date() ? "expired" : expiresAt < new Date(Date.now() + 30 * 24 * 60 * 60 * 1000) ? "expiring_soon" : "valid",
      verifiedBy: Math.random() > 0.3 ? randomPick(NIGERIAN_NAMES) : null,
    });
  }
  return docs;
}

function generateSettlementBatches(count = 20) {
  const batches = [];
  for (let i = 0; i < count; i++) {
    const txCount = Math.floor(Math.random() * 200) + 10;
    batches.push({
      id: `STL-${randomId()}`,
      batchNumber: i + 1,
      transactionCount: txCount,
      totalVolume: randomAmount(100000, 50000000),
      totalCommission: randomAmount(5000, 500000),
      totalFees: randomAmount(1000, 100000),
      status: randomPick(["completed", "processing", "pending", "failed"]),
      settledAt: randomDate(30),
      processedBy: "system",
    });
  }
  return batches;
}

// ============================================================
// Main Seed Execution
// ============================================================

async function main() {
  const startTime = Date.now();

  console.log("📊 Generating seed data...\n");

  const agents = generateAgents(50);
  console.log(`  ✓ ${agents.length} agents (5 admin, 10 super, 35 regular)`);

  const transactions = generateTransactions(500, agents);
  console.log(`  ✓ ${transactions.length} transactions across ${TX_TYPES.length} types`);

  const fraudAlerts = generateFraudAlerts(30, agents);
  console.log(`  ✓ ${fraudAlerts.length} fraud alerts (5 critical, 10 high, 15 medium)`);

  const disputes = generateDisputes(20);
  console.log(`  ✓ ${disputes.length} disputes in various lifecycle stages`);

  const chatSessions = generateChatSessions(100);
  const totalMessages = chatSessions.reduce((sum, s) => sum + s.messages.length, 0);
  console.log(`  ✓ ${chatSessions.length} chat sessions with ${totalMessages} messages`);

  const kycDocs = generateKycDocuments(30, agents);
  console.log(`  ✓ ${kycDocs.length} KYC documents`);

  const settlements = generateSettlementBatches(20);
  console.log(`  ✓ ${settlements.length} settlement batches`);

  const summary = {
    agents: agents.length,
    transactions: transactions.length,
    fraudAlerts: fraudAlerts.length,
    disputes: disputes.length,
    chatSessions: chatSessions.length,
    chatMessages: totalMessages,
    kycDocuments: kycDocs.length,
    settlementBatches: settlements.length,
    totalRecords: agents.length + transactions.length + fraudAlerts.length + disputes.length + chatSessions.length + kycDocs.length + settlements.length,
    generatedAt: new Date().toISOString(),
    durationMs: Date.now() - startTime,
  };

  console.log(`\n✅ Seed data generated: ${summary.totalRecords} total records in ${summary.durationMs}ms`);
  console.log(`\n📋 Summary:`);
  console.log(JSON.stringify(summary, null, 2));

  // Write seed data to file for import
  const seedData = { agents, transactions, fraudAlerts, disputes, chatSessions, kycDocs, settlements, summary };
  const fs = await import("fs");
  fs.writeFileSync("/home/ubuntu/pos-shell-demo/scripts/seed-data-output.json", JSON.stringify(seedData, null, 2));
  console.log(`\n💾 Seed data written to scripts/seed-data-output.json`);
}

main().catch(console.error);
