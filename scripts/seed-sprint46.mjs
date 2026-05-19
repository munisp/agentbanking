#!/usr/bin/env node
/**
 * Sprint 46: Production Seed Data
 * Seeds realistic Nigerian banking data for all Sprint 46 features
 */
import fs from "fs";
import path from "path";

console.log("🌱 Sprint 46: Seeding production data...\n");

// ─── Payment Notification Seed Data ──────────────────────────────────────────
const paymentNotifications = Array.from({ length: 100 }, (_, i) => ({
  id: i + 1,
  type: ["payment_completed", "payment_failed", "payment_pending", "refund_initiated"][i % 4],
  channel: ["email", "sms", "push", "webhook"][i % 4],
  recipient: `agent${(i % 20) + 1}@54link.ng`,
  subject: `Transaction ${["completed", "failed", "pending", "refunded"][i % 4]} - REF-${String(i + 1).padStart(6, "0")}`,
  status: ["delivered", "delivered", "delivered", "failed"][i % 4],
  amount: Math.round((Math.random() * 500000 + 1000) * 100) / 100,
  currency: "NGN",
  createdAt: new Date(Date.now() - i * 3600000).toISOString(),
}));

// ─── Reconciliation Seed Data ────────────────────────────────────────────────
const reconciliationBatches = Array.from({ length: 30 }, (_, i) => ({
  id: `RECON-${String(i + 1).padStart(4, "0")}`,
  date: new Date(Date.now() - i * 86400000).toISOString().split("T")[0],
  totalTransactions: Math.floor(Math.random() * 5000) + 1000,
  matched: Math.floor(Math.random() * 4800) + 950,
  discrepancies: Math.floor(Math.random() * 200),
  totalAmount: Math.round((Math.random() * 1000000000 + 10000000) * 100) / 100,
  status: ["completed", "completed", "completed", "in_progress"][i % 4],
  sources: ["paystack", "flutterwave", "internal_ledger"],
}));

// ─── Compliance Reports Seed Data ────────────────────────────────────────────
const complianceReports = [
  { type: "cbn", title: "CBN Monthly Return", frequency: "monthly", lastGenerated: "2026-03-31", status: "submitted" },
  { type: "cbn", title: "CBN Quarterly Prudential Return", frequency: "quarterly", lastGenerated: "2026-03-31", status: "submitted" },
  { type: "ndpr", title: "NDPR Data Processing Report", frequency: "quarterly", lastGenerated: "2026-03-31", status: "submitted" },
  { type: "pci-dss", title: "PCI-DSS Self-Assessment Questionnaire", frequency: "annual", lastGenerated: "2026-01-15", status: "submitted" },
  { type: "aml", title: "AML Suspicious Transaction Report", frequency: "monthly", lastGenerated: "2026-03-31", status: "submitted" },
  { type: "cft", title: "CFT Counter-Terrorism Financing Report", frequency: "quarterly", lastGenerated: "2026-03-31", status: "submitted" },
];

// ─── Customer Feedback Seed Data ─────────────────────────────────────────────
const customerFeedback = Array.from({ length: 50 }, (_, i) => ({
  id: i + 1,
  agentCode: `AGT-${String((i % 20) + 1).padStart(3, "0")}`,
  rating: [5, 4, 5, 3, 4, 5, 2, 4, 5, 3][i % 10],
  comment: [
    "Excellent service, very fast transaction",
    "Good experience but had to wait a bit",
    "Agent was very helpful and professional",
    "Transaction took too long, needs improvement",
    "Great service, will come back again",
    "Best agent in the area, always reliable",
    "Poor network caused delays, not agent's fault",
    "Quick and efficient, no complaints",
    "Outstanding customer care",
    "Average experience, nothing special",
  ][i % 10],
  transactionType: ["cash_in", "cash_out", "transfer", "airtime", "bills"][i % 5],
  region: ["Lagos", "Abuja", "Kano", "Port Harcourt", "Ibadan", "Enugu"][i % 6],
  createdAt: new Date(Date.now() - i * 7200000).toISOString(),
}));

// ─── Multi-Currency Exchange Rates ───────────────────────────────────────────
const exchangeRates = [
  { pair: "NGN-USD", rate: 0.000625, bid: 0.000620, ask: 0.000630, change24h: -0.12 },
  { pair: "NGN-GBP", rate: 0.000495, bid: 0.000490, ask: 0.000500, change24h: 0.08 },
  { pair: "NGN-EUR", rate: 0.000575, bid: 0.000570, ask: 0.000580, change24h: -0.05 },
  { pair: "NGN-GHS", rate: 0.0075, bid: 0.0074, ask: 0.0076, change24h: 0.15 },
  { pair: "NGN-KES", rate: 0.0806, bid: 0.0800, ask: 0.0812, change24h: -0.22 },
  { pair: "NGN-ZAR", rate: 0.0113, bid: 0.0112, ask: 0.0114, change24h: 0.03 },
  { pair: "NGN-XOF", rate: 0.3660, bid: 0.3650, ask: 0.3670, change24h: 0.00 },
  { pair: "USD-NGN", rate: 1600.00, bid: 1598.00, ask: 1602.00, change24h: 0.12 },
  { pair: "GBP-NGN", rate: 2020.00, bid: 2018.00, ask: 2022.00, change24h: -0.08 },
  { pair: "EUR-NGN", rate: 1739.00, bid: 1737.00, ask: 1741.00, change24h: 0.05 },
];

// ─── Training Courses Seed Data ──────────────────────────────────────────────
const trainingCourses = [
  { id: 1, title: "Agent Onboarding Fundamentals", category: "mandatory", modules: 8, duration: "4 hours", passingScore: 70 },
  { id: 2, title: "AML/CFT Compliance Training", category: "compliance", modules: 6, duration: "3 hours", passingScore: 80 },
  { id: 3, title: "POS Terminal Operations", category: "technical", modules: 10, duration: "5 hours", passingScore: 75 },
  { id: 4, title: "Customer Service Excellence", category: "soft_skills", modules: 5, duration: "2.5 hours", passingScore: 70 },
  { id: 5, title: "Fraud Detection & Prevention", category: "compliance", modules: 7, duration: "3.5 hours", passingScore: 85 },
  { id: 6, title: "Float Management Best Practices", category: "operations", modules: 4, duration: "2 hours", passingScore: 75 },
  { id: 7, title: "NDPR Data Privacy Awareness", category: "compliance", modules: 3, duration: "1.5 hours", passingScore: 80 },
  { id: 8, title: "Mobile Money Operations", category: "technical", modules: 6, duration: "3 hours", passingScore: 75 },
  { id: 9, title: "CBN Regulatory Requirements", category: "compliance", modules: 5, duration: "2.5 hours", passingScore: 85 },
  { id: 10, title: "Advanced Commission Optimization", category: "business", modules: 4, duration: "2 hours", passingScore: 70 },
];

// ─── Agent Hierarchy Seed Data ───────────────────────────────────────────────
const territories = [
  { id: "TER-001", name: "Lagos Island", region: "Lagos", lga: "Lagos Island", agentCount: 45 },
  { id: "TER-002", name: "Lagos Mainland", region: "Lagos", lga: "Surulere", agentCount: 38 },
  { id: "TER-003", name: "Ikeja", region: "Lagos", lga: "Ikeja", agentCount: 52 },
  { id: "TER-004", name: "Abuja Central", region: "Abuja", lga: "AMAC", agentCount: 34 },
  { id: "TER-005", name: "Garki", region: "Abuja", lga: "Garki", agentCount: 28 },
  { id: "TER-006", name: "Kano Municipal", region: "Kano", lga: "Kano Municipal", agentCount: 41 },
  { id: "TER-007", name: "Port Harcourt", region: "Rivers", lga: "Port Harcourt", agentCount: 36 },
  { id: "TER-008", name: "Ibadan North", region: "Oyo", lga: "Ibadan North", agentCount: 29 },
  { id: "TER-009", name: "Enugu", region: "Enugu", lga: "Enugu South", agentCount: 22 },
  { id: "TER-010", name: "Kaduna", region: "Kaduna", lga: "Kaduna North", agentCount: 31 },
];

// ─── Feature Flags Seed Data ─────────────────────────────────────────────────
const featureFlags = [
  { id: "ff_biometric_auth", name: "Biometric Authentication", enabled: true, category: "security" },
  { id: "ff_nfc_payments", name: "NFC Contactless Payments", enabled: true, category: "payments" },
  { id: "ff_multi_currency", name: "Multi-Currency Exchange", enabled: true, category: "payments" },
  { id: "ff_ai_fraud_detection", name: "AI-Powered Fraud Detection", enabled: true, category: "security" },
  { id: "ff_offline_mode", name: "Offline Transaction Mode", enabled: true, category: "resilience" },
  { id: "ff_ussd_fallback", name: "USSD Fallback Channel", enabled: true, category: "resilience" },
  { id: "ff_whatsapp_channel", name: "WhatsApp Business Channel", enabled: false, category: "channels" },
  { id: "ff_crypto_payments", name: "Cryptocurrency Payments", enabled: false, category: "payments" },
  { id: "ff_voice_commands", name: "Voice Command Interface", enabled: false, category: "accessibility" },
  { id: "ff_dark_mode", name: "Dark Mode Theme", enabled: true, category: "ui" },
];

// ─── Write seed data to JSON files ───────────────────────────────────────────
const seedDir = path.resolve("scripts/seed-data");
if (!fs.existsSync(seedDir)) fs.mkdirSync(seedDir, { recursive: true });

const seedFiles = {
  "payment-notifications.json": paymentNotifications,
  "reconciliation-batches.json": reconciliationBatches,
  "compliance-reports.json": complianceReports,
  "customer-feedback.json": customerFeedback,
  "exchange-rates.json": exchangeRates,
  "training-courses.json": trainingCourses,
  "territories.json": territories,
  "feature-flags.json": featureFlags,
};

for (const [file, data] of Object.entries(seedFiles)) {
  fs.writeFileSync(path.join(seedDir, file), JSON.stringify(data, null, 2));
  console.log(`  ✓ ${file} (${Array.isArray(data) ? data.length : Object.keys(data).length} records)`);
}

console.log(`\n✅ Sprint 46 seed data generated: ${Object.keys(seedFiles).length} files`);
console.log(`📁 Location: scripts/seed-data/`);
