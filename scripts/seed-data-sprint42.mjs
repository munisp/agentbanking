#!/usr/bin/env node
/**
 * 54Link POS Shell — Sprint 42 Seed Data Generator
 * Generates comprehensive seed data for all 42 sprints worth of features.
 * Outputs JSON files that can be imported into the database.
 */

import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const OUTPUT_DIR = path.join(__dirname, "../seed-output");
fs.mkdirSync(OUTPUT_DIR, { recursive: true });

const AGENTS = [
  { id: 1, code: "AGT-001", name: "Chioma Eze", phone: "08012345001", tier: "gold", region: "Lagos - Ikeja", role: "admin" },
  { id: 2, code: "AGT-002", name: "Emeka Obi", phone: "08012345002", tier: "silver", region: "Abuja - Wuse", role: "agent" },
  { id: 3, code: "AGT-003", name: "Fatima Bello", phone: "08012345003", tier: "platinum", region: "Kano - Nassarawa", role: "agent" },
  { id: 4, code: "AGT-004", name: "Adamu Yusuf", phone: "08012345004", tier: "bronze", region: "Port Harcourt", role: "agent" },
  { id: 5, code: "AGT-005", name: "Grace Okonkwo", phone: "08012345005", tier: "gold", region: "Enugu - New Haven", role: "agent" },
  { id: 6, code: "AGT-006", name: "Ibrahim Musa", phone: "08012345006", tier: "silver", region: "Kaduna - Barnawa", role: "agent" },
  { id: 7, code: "AGT-007", name: "Joy Nwosu", phone: "08012345007", tier: "gold", region: "Lagos - Lekki", role: "agent" },
  { id: 8, code: "AGT-008", name: "Kemi Ade", phone: "08012345008", tier: "bronze", region: "Ibadan - Bodija", role: "agent" },
  { id: 9, code: "AGT-009", name: "Ladi Bako", phone: "08012345009", tier: "silver", region: "Jos - Bukuru", role: "agent" },
  { id: 10, code: "AGT-010", name: "Musa Dan", phone: "08012345010", tier: "platinum", region: "Abuja - Garki", role: "supervisor" },
];

const TX_TYPES = ["cash_in", "cash_out", "transfer", "airtime", "bills", "card_payment", "qr_payment", "nfc_payment"];
const STATUSES = ["completed", "completed", "completed", "completed", "pending", "failed", "reversed"];
const CHANNELS = ["pos", "mobile", "ussd", "web", "api"];

function randomInt(min, max) { return Math.floor(Math.random() * (max - min + 1)) + min; }
function randomItem(arr) { return arr[randomInt(0, arr.length - 1)]; }
function randomDate(daysBack) { return new Date(Date.now() - randomInt(0, daysBack * 86400000)).toISOString(); }
function randomRef() { return `TXN-${Date.now().toString(36).toUpperCase()}-${randomInt(1000, 9999)}`; }

// Generate transactions (500 records)
const transactions = Array.from({ length: 500 }, (_, i) => ({
  id: i + 1,
  ref: randomRef(),
  type: randomItem(TX_TYPES),
  amount: randomInt(100, 500000),
  fee: randomInt(10, 500),
  commission: randomInt(5, 250),
  customer: `0${randomInt(8010000000, 8099999999)}`,
  status: randomItem(STATUSES),
  channel: randomItem(CHANNELS),
  agentId: randomInt(1, 10),
  createdAt: randomDate(90),
}));

// Generate fraud alerts (100 records)
const FRAUD_TYPES = ["velocity_breach", "geo_anomaly", "amount_spike", "duplicate_tx", "device_mismatch", "time_anomaly"];
const SEVERITIES = ["critical", "high", "medium", "low"];
const fraudAlerts = Array.from({ length: 100 }, (_, i) => ({
  id: i + 1,
  type: randomItem(FRAUD_TYPES),
  severity: randomItem(SEVERITIES),
  agentId: randomInt(1, 10),
  transactionRef: transactions[randomInt(0, 499)].ref,
  amount: randomInt(5000, 1000000),
  reason: `Automated detection: ${randomItem(FRAUD_TYPES)} pattern identified`,
  status: randomItem(["open", "investigating", "resolved", "dismissed"]),
  createdAt: randomDate(30),
}));

// Generate disputes (80 records)
const DISPUTE_CATEGORIES = ["unauthorized_tx", "wrong_amount", "service_not_received", "duplicate_charge", "fraud", "technical_error"];
const disputes = Array.from({ length: 80 }, (_, i) => ({
  id: i + 1,
  ref: `DSP-${String(i + 1).padStart(4, "0")}`,
  category: randomItem(DISPUTE_CATEGORIES),
  amount: randomInt(500, 200000),
  status: randomItem(["open", "under_review", "escalated", "resolved", "closed"]),
  priority: randomItem(["critical", "high", "medium", "low"]),
  agentId: randomInt(1, 10),
  customerPhone: `0${randomInt(8010000000, 8099999999)}`,
  description: `Customer reported ${randomItem(DISPUTE_CATEGORIES)} on transaction`,
  slaDeadline: new Date(Date.now() + randomInt(1, 168) * 3600000).toISOString(),
  createdAt: randomDate(60),
}));

// Generate refunds (40 records)
const refunds = Array.from({ length: 40 }, (_, i) => ({
  id: i + 1,
  ref: `RFD-${String(i + 1).padStart(4, "0")}`,
  disputeId: randomInt(1, 80),
  amount: randomInt(500, 100000),
  status: randomItem(["pending", "approved", "processing", "completed", "rejected"]),
  method: randomItem(["original_method", "bank_transfer", "wallet_credit", "cash"]),
  approvedBy: randomItem(AGENTS).name,
  processedAt: randomDate(30),
  createdAt: randomDate(45),
}));

// Generate settlements (60 records)
const settlements = Array.from({ length: 60 }, (_, i) => ({
  id: i + 1,
  batchRef: `STL-${String(i + 1).padStart(4, "0")}`,
  agentId: randomInt(1, 10),
  txCount: randomInt(10, 200),
  totalVolume: randomInt(50000, 5000000),
  totalCommission: randomInt(2000, 100000),
  status: randomItem(["pending", "processing", "completed", "failed"]),
  settledAt: randomDate(30),
  createdAt: randomDate(45),
}));

// Generate audit logs (200 records)
const ACTIONS = ["login", "logout", "transaction_create", "fraud_review", "dispute_create", "refund_approve", "settlement_run", "agent_suspend", "config_change", "report_export"];
const auditLogs = Array.from({ length: 200 }, (_, i) => ({
  id: i + 1,
  actor: randomItem(AGENTS).name,
  actorId: randomInt(1, 10),
  action: randomItem(ACTIONS),
  resource: randomItem(["transaction", "agent", "dispute", "refund", "settlement", "config"]),
  details: `Action performed on ${randomItem(["transaction", "agent", "dispute"])} record`,
  ipAddress: `192.168.${randomInt(1, 254)}.${randomInt(1, 254)}`,
  createdAt: randomDate(30),
}));

// Generate loyalty records (50 records)
const loyaltyRecords = Array.from({ length: 50 }, (_, i) => ({
  id: i + 1,
  agentId: randomInt(1, 10),
  points: randomInt(100, 50000),
  tier: randomItem(["bronze", "silver", "gold", "platinum"]),
  action: randomItem(["earn", "redeem", "bonus", "tier_upgrade"]),
  description: `${randomItem(["Transaction bonus", "Referral reward", "Monthly target", "Tier upgrade bonus"])}`,
  balanceAfter: randomInt(1000, 100000),
  createdAt: randomDate(90),
}));

// Generate customer surveys (100 records)
const surveys = Array.from({ length: 100 }, (_, i) => ({
  id: i + 1,
  customerId: `0${randomInt(8010000000, 8099999999)}`,
  agentId: randomInt(1, 10),
  transactionRef: transactions[randomInt(0, 499)].ref,
  nps: randomInt(0, 10),
  csat: randomInt(1, 5),
  feedback: randomItem([
    "Great service, very fast",
    "Agent was helpful and professional",
    "Transaction took too long",
    "Need better receipt options",
    "Excellent experience overall",
    "Could improve waiting time",
    "Very satisfied with the service",
    "Agent needs more training",
  ]),
  createdAt: randomDate(30),
}));

// Generate device fleet (30 records)
const DEVICE_MODELS = ["PAX A920", "Verifone V240m", "Ingenico Move 5000", "Sunmi P2", "Newland N910"];
const devices = Array.from({ length: 30 }, (_, i) => ({
  id: i + 1,
  serial: `DEV-${String(i + 1).padStart(5, "0")}`,
  model: randomItem(DEVICE_MODELS),
  agentId: randomInt(1, 10),
  firmwareVersion: `v${randomInt(2, 4)}.${randomInt(0, 9)}.${randomInt(0, 99)}`,
  status: randomItem(["active", "active", "active", "needs_update", "decommissioned"]),
  lastSeen: randomDate(7),
  assignedAt: randomDate(365),
}));

// Generate compliance certificates (40 records)
const CERT_TYPES = ["KYC_LEVEL_1", "KYC_LEVEL_2", "KYC_LEVEL_3", "AML_BASIC", "AML_ENHANCED", "PCI_DSS", "CBN_LICENSE"];
const complianceCerts = Array.from({ length: 40 }, (_, i) => ({
  id: i + 1,
  agentId: randomInt(1, 10),
  certType: randomItem(CERT_TYPES),
  status: randomItem(["active", "active", "active", "expiring_soon", "expired", "revoked"]),
  issuedAt: randomDate(365),
  expiresAt: new Date(Date.now() + randomInt(-30, 365) * 86400000).toISOString(),
}));

// Generate training records (60 records)
const COURSES = ["POS Operations 101", "Fraud Prevention", "Customer Service Excellence", "AML Compliance", "Digital Payments", "Cash Management"];
const trainingRecords = Array.from({ length: 60 }, (_, i) => ({
  id: i + 1,
  agentId: randomInt(1, 10),
  course: randomItem(COURSES),
  progress: randomInt(0, 100),
  score: randomInt(50, 100),
  badge: randomItem(["none", "bronze", "silver", "gold"]),
  completedAt: randomInt(0, 1) ? randomDate(90) : null,
  enrolledAt: randomDate(120),
}));

// Generate incident playbooks (15 records)
const INCIDENT_TYPES = ["data_breach", "ddos_attack", "fraud_ring", "system_outage", "api_failure", "payment_gateway_down"];
const incidents = Array.from({ length: 15 }, (_, i) => ({
  id: i + 1,
  type: randomItem(INCIDENT_TYPES),
  severity: randomItem(["P1", "P2", "P3", "P4"]),
  status: randomItem(["active", "mitigating", "resolved", "post_mortem"]),
  playbook: `Playbook for ${randomItem(INCIDENT_TYPES)}`,
  mttr: randomInt(5, 480),
  assignedTo: randomItem(AGENTS).name,
  createdAt: randomDate(30),
}));

// Generate report schedules (20 records)
const REPORT_TYPES = ["daily_settlement", "weekly_fraud", "monthly_revenue", "agent_performance", "compliance_audit", "transaction_summary"];
const reportSchedules = Array.from({ length: 20 }, (_, i) => ({
  id: i + 1,
  name: `${randomItem(REPORT_TYPES)} Report`,
  schedule: randomItem(["0 6 * * *", "0 0 * * 1", "0 0 1 * *", "0 18 * * *"]),
  lastRun: randomDate(7),
  status: randomItem(["active", "active", "active", "paused"]),
  recipients: randomInt(1, 15),
  format: randomItem(["pdf", "csv", "xlsx"]),
}));

// Summary
const seedData = {
  agents: AGENTS,
  transactions,
  fraudAlerts,
  disputes,
  refunds,
  settlements,
  auditLogs,
  loyaltyRecords,
  surveys,
  devices,
  complianceCerts,
  trainingRecords,
  incidents,
  reportSchedules,
};

let totalRecords = 0;
for (const [key, data] of Object.entries(seedData)) {
  const filePath = path.join(OUTPUT_DIR, `${key}.json`);
  fs.writeFileSync(filePath, JSON.stringify(data, null, 2));
  totalRecords += data.length;
  console.log(`  ${key}: ${data.length} records → ${filePath}`);
}

console.log(`\n✅ Total: ${totalRecords} seed records across ${Object.keys(seedData).length} entities`);
console.log(`📁 Output: ${OUTPUT_DIR}`);
