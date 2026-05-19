#!/usr/bin/env node
/**
 * Seed Data Script for 54Link POS Shell
 * Generates realistic Nigerian agency banking data for all modules
 * Usage: node scripts/seed-data.mjs
 */

const SEED_CONFIG = {
  agents: 200,
  transactions: 5000,
  fraudAlerts: 150,
  commissionRules: 25,
  kycDocuments: 180,
  complianceRules: 40,
  products: 35,
  lgas: 774, // Nigerian LGAs
};

// ── Nigerian Names & Locations ──
const firstNames = ["Adebayo", "Chidinma", "Emeka", "Fatima", "Gbenga", "Halima", "Ibrahim", "Jumoke", "Kunle", "Lateef", "Maryam", "Ngozi", "Oluwaseun", "Patience", "Rasheed", "Sade", "Tunde", "Uche", "Victoria", "Wale", "Yusuf", "Zainab", "Aisha", "Bola", "Chidi", "Damilola", "Eze", "Funke", "Godwin", "Hauwa"];
const lastNames = ["Adeyemi", "Balogun", "Chukwu", "Danladi", "Eze", "Fashola", "Garba", "Hassan", "Igwe", "Johnson", "Kalu", "Lawal", "Mohammed", "Nwankwo", "Okafor", "Peters", "Quadri", "Rabiu", "Sanusi", "Taiwo", "Usman", "Victor", "Williams", "Yakubu", "Zubair"];
const states = ["Lagos", "Abuja", "Kano", "Rivers", "Oyo", "Kaduna", "Enugu", "Delta", "Ogun", "Anambra", "Imo", "Edo", "Borno", "Kwara", "Osun", "Abia", "Bauchi", "Benue", "Cross River", "Ekiti"];
const cities = ["Ikeja", "Garki", "Kano Municipal", "Port Harcourt", "Ibadan", "Kaduna Central", "Enugu East", "Warri", "Abeokuta", "Onitsha", "Owerri", "Benin City", "Maiduguri", "Ilorin", "Osogbo", "Umuahia", "Bauchi Town", "Makurdi", "Calabar", "Ado-Ekiti"];
const banks = ["Access Bank", "GTBank", "First Bank", "UBA", "Zenith Bank", "Fidelity Bank", "Sterling Bank", "Wema Bank", "Union Bank", "Stanbic IBTC"];
const terminalTypes = ["PAX S920", "Morefun A920", "Topwise MP35", "Sunmi P2", "Verifone V240m", "Ingenico Move 5000"];

function rand(min, max) { return Math.floor(Math.random() * (max - min + 1)) + min; }
function pick(arr) { return arr[rand(0, arr.length - 1)]; }
function uuid() { return `${Date.now()}-${rand(10000, 99999)}`; }
function phone() { return `+234${rand(700, 909)}${rand(1000000, 9999999)}`; }
function bvn() { return `${rand(10000000000, 99999999999)}`; }
function nin() { return `${rand(10000000000, 99999999999)}`; }

// ── Generate Agents ──
function generateAgents(count) {
  const agents = [];
  const tiers = ["super_agent", "agent", "sub_agent"];
  const statuses = ["active", "active", "active", "active", "suspended", "pending_kyc"];
  for (let i = 0; i < count; i++) {
    const firstName = pick(firstNames);
    const lastName = pick(lastNames);
    const state = states[i % states.length];
    agents.push({
      id: `AGT-${String(i + 1).padStart(5, "0")}`,
      firstName, lastName,
      fullName: `${firstName} ${lastName}`,
      email: `${firstName.toLowerCase()}.${lastName.toLowerCase()}@54link.com`,
      phone: phone(),
      bvn: bvn(), nin: nin(),
      tier: tiers[i % 3],
      status: pick(statuses),
      state, city: cities[i % cities.length],
      lga: `LGA-${rand(1, 774)}`,
      address: `${rand(1, 200)} ${pick(["Broad Street", "Marina Road", "Adeola Odeku", "Allen Avenue", "Awolowo Road"])}`,
      latitude: 6.45 + Math.random() * 3,
      longitude: 3.39 + Math.random() * 5,
      bankName: pick(banks),
      accountNumber: `${rand(1000000000, 9999999999)}`,
      terminalId: `TID-${rand(100000, 999999)}`,
      terminalType: pick(terminalTypes),
      parentAgentId: i > 50 ? `AGT-${String(rand(1, 50)).padStart(5, "0")}` : null,
      commissionRate: rand(5, 25) / 10,
      dailyLimit: [50000, 200000, 5000000][i % 3],
      kycLevel: rand(1, 3),
      onboardedAt: new Date(Date.now() - rand(30, 730) * 86400000).toISOString(),
      lastTransactionAt: new Date(Date.now() - rand(0, 48) * 3600000).toISOString(),
    });
  }
  return agents;
}

// ── Generate Transactions ──
function generateTransactions(count, agents) {
  const txns = [];
  const types = ["cash_withdrawal", "cash_deposit", "transfer", "bill_payment", "airtime_purchase", "fund_transfer", "balance_inquiry"];
  const statuses = ["completed", "completed", "completed", "completed", "pending", "failed", "reversed"];
  const channels = ["pos_terminal", "ussd", "mobile_app", "whatsapp"];
  for (let i = 0; i < count; i++) {
    const agent = pick(agents);
    const type = pick(types);
    const amount = type === "balance_inquiry" ? 0 : rand(100, 500000);
    txns.push({
      id: `TXN-${String(i + 1).padStart(8, "0")}`,
      agentId: agent.id,
      type,
      amount,
      fee: Math.floor(amount * 0.01),
      commission: Math.floor(amount * agent.commissionRate / 100),
      currency: "NGN",
      status: pick(statuses),
      channel: pick(channels),
      customerPhone: phone(),
      customerName: `${pick(firstNames)} ${pick(lastNames)}`,
      reference: `REF-${Date.now()}-${rand(1000, 9999)}`,
      terminalId: agent.terminalId,
      state: agent.state,
      city: agent.city,
      latitude: agent.latitude + (Math.random() - 0.5) * 0.01,
      longitude: agent.longitude + (Math.random() - 0.5) * 0.01,
      riskScore: rand(0, 100),
      createdAt: new Date(Date.now() - rand(0, 90) * 86400000).toISOString(),
      completedAt: new Date(Date.now() - rand(0, 90) * 86400000 + rand(1000, 60000)).toISOString(),
    });
  }
  return txns;
}

// ── Generate Fraud Alerts ──
function generateFraudAlerts(count, transactions) {
  const alerts = [];
  const categories = ["velocity_breach", "geo_anomaly", "amount_spike", "device_change", "sim_swap", "account_takeover", "card_skimming", "identity_fraud"];
  const severities = ["critical", "high", "medium", "low"];
  for (let i = 0; i < count; i++) {
    const txn = transactions[rand(0, transactions.length - 1)];
    alerts.push({
      id: `FRD-${String(i + 1).padStart(6, "0")}`,
      transactionId: txn.id,
      agentId: txn.agentId,
      category: pick(categories),
      severity: severities[i % 4],
      riskScore: rand(60, 100),
      description: `Suspicious activity detected: ${pick(categories).replace("_", " ")} on transaction ${txn.id}`,
      mlModelUsed: pick(["XGBoost", "Autoencoder", "GNN", "Ensemble"]),
      mlConfidence: rand(70, 99) / 100,
      status: pick(["open", "investigating", "confirmed_fraud", "false_positive", "resolved"]),
      assignedTo: `${pick(firstNames)} ${pick(lastNames)}`,
      createdAt: new Date(Date.now() - rand(0, 30) * 86400000).toISOString(),
      resolvedAt: i % 3 === 0 ? new Date(Date.now() - rand(0, 15) * 86400000).toISOString() : null,
    });
  }
  return alerts;
}

// ── Generate Commission Rules ──
function generateCommissionRules() {
  const rules = [
    { id: "CR-001", name: "Cash Withdrawal Base", transactionType: "cash_withdrawal", tierRates: { super_agent: 1.5, agent: 1.0, sub_agent: 0.5 }, minAmount: 100, maxAmount: 500000, flatFee: 0, capPerTransaction: 2500, dailyCap: 50000, status: "active" },
    { id: "CR-002", name: "Cash Deposit Base", transactionType: "cash_deposit", tierRates: { super_agent: 1.2, agent: 0.8, sub_agent: 0.4 }, minAmount: 100, maxAmount: 1000000, flatFee: 0, capPerTransaction: 3000, dailyCap: 75000, status: "active" },
    { id: "CR-003", name: "Transfer Commission", transactionType: "transfer", tierRates: { super_agent: 0.8, agent: 0.5, sub_agent: 0.3 }, minAmount: 100, maxAmount: 5000000, flatFee: 50, capPerTransaction: 5000, dailyCap: 100000, status: "active" },
    { id: "CR-004", name: "Bill Payment", transactionType: "bill_payment", tierRates: { super_agent: 2.0, agent: 1.5, sub_agent: 1.0 }, minAmount: 500, maxAmount: 200000, flatFee: 0, capPerTransaction: 1000, dailyCap: 25000, status: "active" },
    { id: "CR-005", name: "Airtime Sales", transactionType: "airtime_purchase", tierRates: { super_agent: 3.0, agent: 2.5, sub_agent: 2.0 }, minAmount: 50, maxAmount: 50000, flatFee: 0, capPerTransaction: 500, dailyCap: 10000, status: "active" },
    { id: "CR-006", name: "Weekend Bonus", transactionType: "all", tierRates: { super_agent: 0.5, agent: 0.3, sub_agent: 0.2 }, minAmount: 0, maxAmount: 999999999, flatFee: 0, capPerTransaction: 1000, dailyCap: 20000, status: "active" },
  ];
  return rules;
}

// ── Generate Compliance Rules ──
function generateComplianceRules() {
  return [
    { id: "COMP-001", name: "CBN Daily Transaction Limit - Tier 1", category: "transaction_limit", rule: "Max ₦50,000 daily for Tier 1 agents", threshold: 50000, action: "block_transaction", severity: "high", status: "active" },
    { id: "COMP-002", name: "CBN Daily Transaction Limit - Tier 2", category: "transaction_limit", rule: "Max ₦200,000 daily for Tier 2 agents", threshold: 200000, action: "block_transaction", severity: "high", status: "active" },
    { id: "COMP-003", name: "CBN Daily Transaction Limit - Tier 3", category: "transaction_limit", rule: "Max ₦5,000,000 daily for Tier 3 agents", threshold: 5000000, action: "block_transaction", severity: "high", status: "active" },
    { id: "COMP-004", name: "KYC Document Expiry", category: "kyc", rule: "Agent KYC documents must be renewed annually", threshold: 365, action: "suspend_agent", severity: "critical", status: "active" },
    { id: "COMP-005", name: "AML Suspicious Transaction", category: "aml", rule: "Flag transactions > ₦1,000,000 for AML review", threshold: 1000000, action: "flag_for_review", severity: "high", status: "active" },
    { id: "COMP-006", name: "Velocity Check", category: "fraud_prevention", rule: "Max 10 transactions per agent per hour", threshold: 10, action: "temporary_block", severity: "medium", status: "active" },
    { id: "COMP-007", name: "Geo-fencing", category: "fraud_prevention", rule: "Block transactions outside agent's registered LGA", threshold: 0, action: "block_transaction", severity: "high", status: "active" },
    { id: "COMP-008", name: "CBN Monthly Reporting", category: "reporting", rule: "Submit monthly transaction report to CBN by 5th", threshold: 5, action: "alert_compliance_officer", severity: "critical", status: "active" },
    { id: "COMP-009", name: "PCI DSS Compliance", category: "security", rule: "All card data must be encrypted at rest and in transit", threshold: 0, action: "system_audit", severity: "critical", status: "active" },
    { id: "COMP-010", name: "Agent Dormancy", category: "agent_management", rule: "Flag agents with no transactions for 30 days", threshold: 30, action: "flag_for_review", severity: "low", status: "active" },
  ];
}

// ── Generate Products ──
function generateProducts() {
  return [
    { id: "PROD-001", name: "Cash Withdrawal", category: "banking", fee: "1% (min ₦100)", description: "POS cash withdrawal service", status: "active" },
    { id: "PROD-002", name: "Cash Deposit", category: "banking", fee: "Free", description: "Cash deposit to bank account", status: "active" },
    { id: "PROD-003", name: "Fund Transfer", category: "banking", fee: "₦50 flat", description: "Inter-bank fund transfer", status: "active" },
    { id: "PROD-004", name: "MTN Airtime", category: "airtime", fee: "3% commission", description: "MTN airtime vending", status: "active" },
    { id: "PROD-005", name: "Glo Airtime", category: "airtime", fee: "3% commission", description: "Glo airtime vending", status: "active" },
    { id: "PROD-006", name: "Airtel Airtime", category: "airtime", fee: "3% commission", description: "Airtel airtime vending", status: "active" },
    { id: "PROD-007", name: "9mobile Airtime", category: "airtime", fee: "3% commission", description: "9mobile airtime vending", status: "active" },
    { id: "PROD-008", name: "DSTV Payment", category: "bills", fee: "₦100 flat", description: "DSTV subscription payment", status: "active" },
    { id: "PROD-009", name: "GOTV Payment", category: "bills", fee: "₦100 flat", description: "GOTV subscription payment", status: "active" },
    { id: "PROD-010", name: "PHCN Electricity", category: "bills", fee: "₦100 flat", description: "Electricity bill payment", status: "active" },
    { id: "PROD-011", name: "LIRS Tax Payment", category: "tax", fee: "Free", description: "Lagos state tax collection", status: "active" },
    { id: "PROD-012", name: "Pension Collection", category: "pension", fee: "Free", description: "Pension contribution collection", status: "active" },
    { id: "PROD-013", name: "Insurance Premium", category: "insurance", fee: "2% commission", description: "Insurance premium collection", status: "active" },
    { id: "PROD-014", name: "Savings Account", category: "savings", fee: "Free", description: "Agent-assisted savings account", status: "active" },
    { id: "PROD-015", name: "Micro Loan", category: "lending", fee: "Processing fee", description: "Micro loan disbursement", status: "active" },
  ];
}

// ── Main ──
async function main() {
  console.log("🌱 54Link POS Shell — Seed Data Generator");
  console.log("==========================================\n");

  const agents = generateAgents(SEED_CONFIG.agents);
  console.log(`✅ Generated ${agents.length} agents`);

  const transactions = generateTransactions(SEED_CONFIG.transactions, agents);
  console.log(`✅ Generated ${transactions.length} transactions`);

  const fraudAlerts = generateFraudAlerts(SEED_CONFIG.fraudAlerts, transactions);
  console.log(`✅ Generated ${fraudAlerts.length} fraud alerts`);

  const commissionRules = generateCommissionRules();
  console.log(`✅ Generated ${commissionRules.length} commission rules`);

  const complianceRules = generateComplianceRules();
  console.log(`✅ Generated ${complianceRules.length} compliance rules`);

  const products = generateProducts();
  console.log(`✅ Generated ${products.length} products`);

  // Write seed data to JSON files
  const seedData = { agents, transactions, fraudAlerts, commissionRules, complianceRules, products, generatedAt: new Date().toISOString(), config: SEED_CONFIG };

  const fs = await import("fs");
  const path = await import("path");
  const outDir = path.join(process.cwd(), "scripts", "seed-output");
  fs.mkdirSync(outDir, { recursive: true });

  fs.writeFileSync(path.join(outDir, "agents.json"), JSON.stringify(agents, null, 2));
  fs.writeFileSync(path.join(outDir, "transactions.json"), JSON.stringify(transactions, null, 2));
  fs.writeFileSync(path.join(outDir, "fraud-alerts.json"), JSON.stringify(fraudAlerts, null, 2));
  fs.writeFileSync(path.join(outDir, "commission-rules.json"), JSON.stringify(commissionRules, null, 2));
  fs.writeFileSync(path.join(outDir, "compliance-rules.json"), JSON.stringify(complianceRules, null, 2));
  fs.writeFileSync(path.join(outDir, "products.json"), JSON.stringify(products, null, 2));
  fs.writeFileSync(path.join(outDir, "seed-manifest.json"), JSON.stringify(seedData, null, 2));

  console.log(`\n📁 Seed data written to ${outDir}/`);
  console.log(`   Total records: ${agents.length + transactions.length + fraudAlerts.length + commissionRules.length + complianceRules.length + products.length}`);
  console.log("\n✅ Seed data generation complete!");
}

main().catch(console.error);
