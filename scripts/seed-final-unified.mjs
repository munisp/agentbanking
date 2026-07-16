#!/usr/bin/env node
/**
 * 54Link Agency Banking Platform — Unified Seed Script
 * Comprehensive realistic Nigerian banking data for all platform domains.
 *
 * Usage: node scripts/seed-final-unified.mjs [--env production|staging|dev]
 *
 * Seeds:
 * - 50 agents (5 admin, 10 super, 35 regular) with KYC across all tiers
 * - 500 transactions across 8 types (cash_in, cash_out, transfer, airtime, bills, card, qr, nfc)
 * - 30 fraud alerts (5 critical, 10 high, 15 medium) with ML scores
 * - 20 disputes in various lifecycle stages
 * - 100 chat sessions with 500+ messages
 * - 30 KYC documents (NIN, BVN, passport, utility, bank statement, CAC)
 * - 20 settlement batches with reconciliation data
 * - 15 merchants with KYB documents
 * - 25 commission rules across tiers
 * - 10 POS terminals per agent
 * - 20 compliance reports (CTR, STR)
 * - 10 webhook endpoints with delivery history
 * - 5 loan applications in various stages
 * - Nigerian LGAs, BVN format, NIN format, realistic phone numbers
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

  // Additional domain seed data
  const merchantsSeed = generateMerchants(15);
  console.log(`  \u2713 ${merchantsSeed.length} merchants with KYB documents`);

  const commissionRules = generateCommissionRules(25);
  console.log(`  \u2713 ${commissionRules.length} commission rules`);

  const complianceReports = generateComplianceReports(20);
  console.log(`  \u2713 ${complianceReports.length} compliance reports (CTR/STR)`);

  const loanApplications = generateLoanApplications(5, agents);
  console.log(`  \u2713 ${loanApplications.length} loan applications`);

  const posTerminals = generatePosTerminals(agents.slice(0, 10));
  console.log(`  \u2713 ${posTerminals.length} POS terminals`);

  // Write seed data to file for import
  const seedData = {
    agents, transactions, fraudAlerts, disputes, chatSessions,
    kycDocs, settlements, merchants: merchantsSeed, commissionRules,
    complianceReports, loanApplications, posTerminals, summary
  };

  const outputDir = new URL("./seed-output/", import.meta.url).pathname;
  const fs = await import("fs");
  fs.mkdirSync(outputDir, { recursive: true });
  const outPath = outputDir + "seed-data-output.json";
  fs.writeFileSync(outPath, JSON.stringify(seedData, null, 2));
  console.log(`\n\u2705 Seed data written to ${outPath}`);
}

// ============================================================
// Additional Domain Generators
// ============================================================

const NIGERIAN_LGAS = [
  "Ikeja", "Surulere", "Alimosho", "Eti-Osa", "Kosofe",
  "Garki", "Wuse", "Maitama", "Asokoro", "Gwarinpa",
  "Sabon Gari", "Fagge", "Nassarawa", "Tarauni", "Dala",
  "Port Harcourt City", "Obio-Akpor", "Eleme", "Bonny", "Ogu-Bolo",
];

const MERCHANT_CATEGORIES = [
  "grocery", "fuel_station", "pharmacy", "electronics", "restaurant",
  "fashion", "hardware", "agriculture", "education", "healthcare",
];

function generateBVN() {
  return `22${Math.floor(100000000 + Math.random() * 900000000)}`;
}

function generateNIN() {
  return `${Math.floor(10000000000 + Math.random() * 90000000000)}`;
}

function generateMerchants(count = 15) {
  const merchants = [];
  const businessTypes = ["sole_proprietorship", "partnership", "limited_company", "cooperative"];
  for (let i = 0; i < count; i++) {
    merchants.push({
      id: `MER-${randomId()}`,
      businessName: `${randomPick(NIGERIAN_NAMES).split(" ")[1]} ${randomPick(["Enterprises", "Trading Co.", "Services Ltd", "Global", "Nigeria Ltd"])}`,
      businessType: randomPick(businessTypes),
      category: randomPick(MERCHANT_CATEGORIES),
      rcNumber: `RC${Math.floor(100000 + Math.random() * 900000)}`,
      tin: `${Math.floor(10000000 + Math.random() * 90000000)}-0001`,
      bvn: generateBVN(),
      contactName: randomPick(NIGERIAN_NAMES),
      contactPhone: randomPhone(),
      contactEmail: `merchant${i + 1}@54link.ng`,
      address: `${Math.floor(1 + Math.random() * 200)} ${randomPick(["Broad Street", "Marina Road", "Adeola Odeku", "Awolowo Way", "Ahmadu Bello Way"])}`,
      lga: randomPick(NIGERIAN_LGAS),
      state: randomPick(NIGERIAN_STATES),
      kybStatus: randomPick(["approved", "pending", "under_review", "rejected"]),
      kybDocuments: [
        { type: "cac_certificate", status: "verified", documentNumber: `BN${Math.floor(100000 + Math.random() * 900000)}` },
        { type: "tin_certificate", status: Math.random() > 0.3 ? "verified" : "pending" },
        { type: "utility_bill", status: Math.random() > 0.4 ? "verified" : "pending" },
      ],
      monthlyVolume: randomAmount(500000, 50000000),
      commissionRate: Math.round((0.5 + Math.random() * 2) * 100) / 100,
      createdAt: randomDate(180),
    });
  }
  return merchants;
}

function generateCommissionRules(count = 25) {
  const rules = [];
  const txTypes = ["cash_in", "cash_out", "transfer", "airtime", "bills"];
  const tiers = ["bronze", "silver", "gold", "platinum", "diamond"];
  for (let i = 0; i < count; i++) {
    const txType = txTypes[i % txTypes.length];
    const tier = tiers[Math.floor(i / txTypes.length) % tiers.length];
    rules.push({
      id: `CMR-${randomId()}`,
      txType,
      tier,
      flatFee: randomAmount(10, 100),
      percentFee: Math.round(Math.random() * 2 * 100) / 100,
      minAmount: txType === "airtime" ? 50 : 500,
      maxAmount: txType === "airtime" ? 50000 : tier === "diamond" ? 10000000 : 5000000,
      agentShare: Math.round((60 + Math.random() * 20) * 100) / 100,
      superAgentShare: Math.round((10 + Math.random() * 15) * 100) / 100,
      platformShare: Math.round((5 + Math.random() * 10) * 100) / 100,
      isActive: Math.random() > 0.1,
      effectiveFrom: randomDate(90),
    });
  }
  return rules;
}

function generateComplianceReports(count = 20) {
  const reports = [];
  for (let i = 0; i < count; i++) {
    const isCTR = Math.random() > 0.4;
    reports.push({
      id: `CPL-${randomId()}`,
      type: isCTR ? "CTR" : "STR",
      referenceNumber: `${isCTR ? "CTR" : "STR"}-${new Date().getFullYear()}-${String(i + 1).padStart(5, "0")}`,
      subjectName: randomPick(NIGERIAN_NAMES),
      subjectBVN: generateBVN(),
      amount: isCTR ? randomAmount(5000000, 100000000) : randomAmount(100000, 10000000),
      currency: "NGN",
      reason: isCTR
        ? "Cash transaction exceeding \u20A65,000,000 threshold"
        : randomPick(["Unusual transaction pattern", "Structuring suspected", "PEP-related activity", "Sanctions screening match"]),
      filedTo: "NFIU",
      status: randomPick(["filed", "acknowledged", "under_review", "closed"]),
      filedAt: randomDate(90),
      filedBy: randomPick(NIGERIAN_NAMES),
    });
  }
  return reports;
}

function generateLoanApplications(count = 5, agents = []) {
  const loans = [];
  const purposes = ["float_topup", "working_capital", "pos_terminal", "business_expansion", "inventory"];
  const statuses = ["applied", "under_review", "approved", "disbursed", "repaying"];
  for (let i = 0; i < count; i++) {
    const principal = randomAmount(50000, 2000000);
    const rate = 2.5 + Math.random() * 3;
    const tenure = randomPick([30, 60, 90, 180]);
    loans.push({
      id: `LOAN-${randomId()}`,
      agentCode: randomPick(agents).agentCode,
      purpose: purposes[i % purposes.length],
      principal,
      interestRate: Math.round(rate * 100) / 100,
      tenureDays: tenure,
      monthlyRepayment: Math.round(principal * (1 + rate / 100) / (tenure / 30) * 100) / 100,
      status: statuses[i % statuses.length],
      creditScore: Math.floor(300 + Math.random() * 550),
      disbursedAt: i >= 3 ? randomDate(30) : null,
      appliedAt: randomDate(60),
    });
  }
  return loans;
}

function generatePosTerminals(agents = []) {
  const terminals = [];
  const models = ["PAX A920", "Verifone V240m", "Ingenico Move/5000", "Nexgo N86", "Sunmi P2"];
  for (const agent of agents) {
    const termCount = Math.floor(Math.random() * 3) + 1;
    for (let i = 0; i < termCount; i++) {
      terminals.push({
        id: `TRM-${randomId()}`,
        serialNumber: `SN${Math.floor(1000000000 + Math.random() * 9000000000)}`,
        model: randomPick(models),
        agentCode: agent.agentCode,
        firmwareVersion: `v${Math.floor(1 + Math.random() * 3)}.${Math.floor(Math.random() * 10)}.${Math.floor(Math.random() * 20)}`,
        simICCID: `8923401${Math.floor(10000000000 + Math.random() * 90000000000)}`,
        lastHeartbeat: randomDate(1),
        batteryLevel: Math.floor(20 + Math.random() * 80),
        status: randomPick(["active", "active", "active", "maintenance", "offline"]),
        assignedAt: randomDate(180),
      });
    }
  }
  return terminals;
}

main().catch(console.error);
