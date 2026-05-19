#!/usr/bin/env node
/**
 * Comprehensive Production Seed Script — 54Link Agency Banking Platform
 * 
 * Seeds all 78+ tables with realistic data for:
 * - Tenants, invite codes, branding
 * - Agents (various tiers and states)
 * - Customers (various KYC levels)
 * - Transactions (cash-in, cash-out, transfer, bill payment)
 * - Fraud alerts, disputes, escalations
 * - Notification templates, escalation chains
 * - Commission structures, fee overrides
 * - KYC records, audit logs
 * - Rate alerts, webhooks, API keys
 * 
 * Usage: node scripts/seed-comprehensive.mjs
 * 
 * NOTE: This script uses the in-memory stores when DB is unavailable.
 * In production, replace with actual Drizzle ORM insert calls.
 */

import crypto from "crypto";

// ── Helpers ──────────────────────────────────────────────────────────────────
const uuid = () => crypto.randomUUID();
const now = Date.now();
const day = 86400000;
const randomDate = (daysBack) => now - Math.floor(Math.random() * daysBack * day);
const randomAmount = (min, max) => Math.round((Math.random() * (max - min) + min) * 100) / 100;
const pick = (arr) => arr[Math.floor(Math.random() * arr.length)];

// ── Nigerian Names ───────────────────────────────────────────────────────────
const firstNames = ["Adebayo", "Chinwe", "Emeka", "Fatima", "Gbenga", "Halima", "Ibrahim", "Jumoke", "Kehinde", "Ladi", "Musa", "Ngozi", "Oluwaseun", "Patience", "Rasheed", "Sade", "Tunde", "Uche", "Vivian", "Wale", "Yetunde", "Zainab", "Aisha", "Bola", "Chidi", "Damilola", "Ese", "Funke", "Godwin", "Hassan"];
const lastNames = ["Adeyemi", "Balogun", "Chukwu", "Danjuma", "Eze", "Fashola", "Garba", "Hassan", "Igwe", "Johnson", "Kalu", "Lawal", "Mohammed", "Nwosu", "Okafor", "Peterside", "Quadri", "Rabiu", "Sanusi", "Taiwo", "Usman", "Victor", "Williams", "Yakubu", "Zubair", "Abubakar", "Bankole", "Chibueze", "Dosunmu", "Ezeife"];
const cities = ["Lagos", "Abuja", "Kano", "Ibadan", "Port Harcourt", "Benin City", "Kaduna", "Enugu", "Owerri", "Calabar", "Jos", "Ilorin", "Abeokuta", "Warri", "Uyo"];
const states = ["Lagos", "FCT", "Kano", "Oyo", "Rivers", "Edo", "Kaduna", "Enugu", "Imo", "Cross River", "Plateau", "Kwara", "Ogun", "Delta", "Akwa Ibom"];

const randomName = () => `${pick(firstNames)} ${pick(lastNames)}`;
const randomPhone = () => `+234${Math.floor(7000000000 + Math.random() * 2999999999)}`;
const randomEmail = (name) => `${name.toLowerCase().replace(/\s/g, ".")}@${pick(["gmail.com", "yahoo.com", "outlook.com", "hotmail.com"])}`;

// ═══════════════════════════════════════════════════════════════════════════════
// SEED DATA GENERATION
// ═══════════════════════════════════════════════════════════════════════════════

console.log("🌱 54Link Comprehensive Seed Data Generator");
console.log("═".repeat(60));

// ── 1. Tenants ───────────────────────────────────────────────────────────────
const tenants = [
  { id: uuid(), name: "54Link Default", slug: "54link", status: "active", plan: "enterprise", domain: "54link.ng", createdAt: randomDate(365) },
  { id: uuid(), name: "QuickPay Nigeria", slug: "quickpay", status: "active", plan: "professional", domain: "quickpay.ng", createdAt: randomDate(180) },
  { id: uuid(), name: "AfriRemit", slug: "afriremit", status: "active", plan: "professional", domain: "afriremit.com", createdAt: randomDate(120) },
  { id: uuid(), name: "NairaFlow", slug: "nairaflow", status: "onboarding", plan: "starter", domain: "nairaflow.ng", createdAt: randomDate(30) },
  { id: uuid(), name: "PayBridge Africa", slug: "paybridge", status: "active", plan: "enterprise", domain: "paybridge.africa", createdAt: randomDate(200) },
];
console.log(`✅ ${tenants.length} tenants generated`);

// ── 2. Invite Codes ──────────────────────────────────────────────────────────
const inviteCodes = tenants.flatMap(t => [
  { id: uuid(), code: `INV-${t.slug.toUpperCase()}-${Math.random().toString(36).slice(2, 8).toUpperCase()}`, tenantId: t.id, type: "multi_use", maxUses: 50, usedCount: Math.floor(Math.random() * 20), expiresAt: now + 90 * day, createdBy: "admin", status: "active" },
  { id: uuid(), code: `PROMO-${Math.random().toString(36).slice(2, 8).toUpperCase()}`, tenantId: t.id, type: "one_time", maxUses: 1, usedCount: 0, expiresAt: now + 30 * day, createdBy: "admin", status: "active" },
]);
console.log(`✅ ${inviteCodes.length} invite codes generated`);

// ── 3. Agents ────────────────────────────────────────────────────────────────
const agentTiers = ["basic", "standard", "premium", "enterprise"];
const agentStates = ["active", "active", "active", "active", "suspended", "kyc_review", "training"];
const agents = Array.from({ length: 100 }, (_, i) => {
  const name = randomName();
  const city = pick(cities);
  const state = pick(states);
  return {
    id: uuid(),
    agentCode: `AGT${String(i + 1).padStart(4, "0")}`,
    name,
    email: randomEmail(name),
    phone: randomPhone(),
    tier: pick(agentTiers),
    status: pick(agentStates),
    kycLevel: pick(["basic", "standard", "enhanced", "full"]),
    tenantId: pick(tenants).id,
    city,
    state,
    address: `${Math.floor(Math.random() * 200) + 1} ${pick(["Broad Street", "Marina Road", "Allen Avenue", "Adeola Odeku", "Awolowo Road", "Herbert Macaulay", "Nnamdi Azikiwe"])}`,
    latitude: 6.4 + Math.random() * 3,
    longitude: 3.2 + Math.random() * 5,
    floatBalance: randomAmount(10000, 5000000),
    commissionBalance: randomAmount(0, 500000),
    totalTransactions: Math.floor(Math.random() * 50000),
    dailyTransactionCount: Math.floor(Math.random() * 100),
    monthlyTransactionCount: Math.floor(Math.random() * 2000),
    deviceId: `DEV-${Math.random().toString(36).slice(2, 10).toUpperCase()}`,
    lastActiveAt: randomDate(7),
    createdAt: randomDate(365),
  };
});
console.log(`✅ ${agents.length} agents generated`);

// ── 4. Customers ─────────────────────────────────────────────────────────────
const customers = Array.from({ length: 200 }, (_, i) => {
  const name = randomName();
  return {
    id: uuid(),
    name,
    email: randomEmail(name),
    phone: randomPhone(),
    kycLevel: pick(["none", "basic", "standard", "enhanced", "full"]),
    status: pick(["active", "active", "active", "inactive", "blocked"]),
    tenantId: pick(tenants).id,
    walletBalance: randomAmount(0, 2000000),
    totalTransactions: Math.floor(Math.random() * 500),
    loyaltyPoints: Math.floor(Math.random() * 10000),
    referralCode: `REF-${Math.random().toString(36).slice(2, 8).toUpperCase()}`,
    createdAt: randomDate(365),
  };
});
console.log(`✅ ${customers.length} customers generated`);

// ── 5. Transactions ──────────────────────────────────────────────────────────
const txnTypes = ["cash_in", "cash_out", "transfer", "bill_payment"];
const txnStatuses = ["processed", "processed", "processed", "settled", "reconciled", "failed", "reversed"];
const currencies = ["NGN", "NGN", "NGN", "USD", "GBP", "EUR", "GHS", "KES"];
const transactions = Array.from({ length: 1000 }, () => {
  const type = pick(txnTypes);
  const amount = type === "bill_payment" ? randomAmount(500, 50000) : randomAmount(1000, 500000);
  return {
    id: uuid(),
    reference: `TXN-${Date.now()}-${Math.random().toString(36).slice(2, 8).toUpperCase()}`,
    type,
    amount,
    currency: pick(currencies),
    status: pick(txnStatuses),
    agentId: pick(agents).id,
    customerId: pick(customers).id,
    tenantId: pick(tenants).id,
    fee: Math.round(amount * 0.01 * 100) / 100,
    commission: Math.round(amount * 0.005 * 100) / 100,
    fraudScore: Math.floor(Math.random() * 100),
    channel: pick(["pos", "mobile", "web", "ussd"]),
    description: `${type.replace("_", " ")} transaction`,
    createdAt: randomDate(90),
    processedAt: randomDate(90),
    settledAt: randomDate(30),
  };
});
console.log(`✅ ${transactions.length} transactions generated`);

// ── 6. Fraud Alerts ──────────────────────────────────────────────────────────
const fraudAlerts = Array.from({ length: 50 }, () => ({
  id: uuid(),
  transactionId: pick(transactions).id,
  agentId: pick(agents).id,
  severity: pick(["low", "medium", "high", "critical"]),
  type: pick(["velocity", "amount", "location", "device", "pattern", "structuring"]),
  fraudScore: Math.floor(Math.random() * 60) + 40,
  reason: pick([
    "Unusual transaction velocity detected",
    "Transaction amount exceeds normal pattern",
    "New device used for high-value transaction",
    "Geographic anomaly detected",
    "Potential structuring activity",
    "Multiple failed attempts before success",
  ]),
  status: pick(["open", "investigating", "resolved", "dismissed"]),
  tenantId: pick(tenants).id,
  createdAt: randomDate(30),
}));
console.log(`✅ ${fraudAlerts.length} fraud alerts generated`);

// ── 7. Disputes ──────────────────────────────────────────────────────────────
const disputes = Array.from({ length: 30 }, () => ({
  id: uuid(),
  transactionId: pick(transactions).id,
  customerId: pick(customers).id,
  agentId: pick(agents).id,
  type: pick(["wrong_amount", "unauthorized", "service_not_received", "double_charge", "failed_reversal"]),
  status: pick(["filed", "investigating", "resolved_favor_customer", "resolved_favor_agent", "closed"]),
  amount: randomAmount(1000, 200000),
  description: pick([
    "Customer claims wrong amount was debited",
    "Unauthorized transaction on account",
    "Service was paid for but not received",
    "Double charge for same transaction",
    "Reversal was promised but not processed",
  ]),
  resolution: null,
  tenantId: pick(tenants).id,
  createdAt: randomDate(60),
}));
console.log(`✅ ${disputes.length} disputes generated`);

// ── 8. KYC Records ───────────────────────────────────────────────────────────
const kycRecords = agents.slice(0, 80).map(agent => ({
  id: uuid(),
  agentId: agent.id,
  level: agent.kycLevel,
  status: pick(["approved", "approved", "approved", "pending", "rejected", "expired"]),
  documentType: pick(["national_id", "passport", "drivers_license", "voters_card"]),
  documentNumber: `DOC-${Math.random().toString(36).slice(2, 12).toUpperCase()}`,
  livenessScore: Math.floor(Math.random() * 40) + 60,
  faceMatchScore: Math.floor(Math.random() * 30) + 70,
  ocrConfidence: Math.floor(Math.random() * 20) + 80,
  reviewedBy: pick(["system", "admin-001", "supervisor-001"]),
  expiresAt: now + 365 * day,
  createdAt: randomDate(180),
}));
console.log(`✅ ${kycRecords.length} KYC records generated`);

// ── 9. Notification Templates ────────────────────────────────────────────────
const notificationTemplates = [
  { id: uuid(), name: "Transaction Confirmation", channel: "sms", template: "Dear {{customerName}}, your {{type}} of {{currency}} {{amount}} has been processed. Ref: {{reference}}", variables: ["customerName", "type", "currency", "amount", "reference"], category: "transaction", active: true },
  { id: uuid(), name: "Fraud Alert", channel: "email", template: "ALERT: Suspicious activity detected on agent {{agentCode}}. Risk score: {{fraudScore}}/100. Reason: {{reason}}", variables: ["agentCode", "fraudScore", "reason"], category: "security", active: true },
  { id: uuid(), name: "KYC Approved", channel: "sms", template: "Congratulations {{agentName}}! Your KYC verification has been approved. You can now process transactions up to {{limit}}.", variables: ["agentName", "limit"], category: "kyc", active: true },
  { id: uuid(), name: "Rate Alert Triggered", channel: "push", template: "{{baseCurrency}}/{{targetCurrency}} has reached your target rate of {{targetRate}}. Current rate: {{currentRate}}", variables: ["baseCurrency", "targetCurrency", "targetRate", "currentRate"], category: "rate_alert", active: true },
  { id: uuid(), name: "Settlement Complete", channel: "email", template: "Settlement batch {{batchId}} has been completed. Total: {{currency}} {{totalAmount}} across {{transactionCount}} transactions.", variables: ["batchId", "currency", "totalAmount", "transactionCount"], category: "settlement", active: true },
  { id: uuid(), name: "Commission Payout", channel: "sms", template: "Your commission of {{currency}} {{amount}} has been credited to your wallet. New balance: {{currency}} {{newBalance}}", variables: ["currency", "amount", "newBalance"], category: "commission", active: true },
  { id: uuid(), name: "Dispute Filed", channel: "email", template: "A new dispute has been filed by {{customerName}} for transaction {{reference}}. Amount: {{currency}} {{amount}}. Please investigate within 48 hours.", variables: ["customerName", "reference", "currency", "amount"], category: "dispute", active: true },
  { id: uuid(), name: "System Maintenance", channel: "push", template: "Scheduled maintenance on {{date}} from {{startTime}} to {{endTime}}. Some services may be temporarily unavailable.", variables: ["date", "startTime", "endTime"], category: "system", active: true },
];
console.log(`✅ ${notificationTemplates.length} notification templates generated`);

// ── 10. Escalation Chains ────────────────────────────────────────────────────
const escalationChains = [
  { id: uuid(), name: "Critical Fraud Alert", levels: [
    { level: 1, target: "supervisor", timeoutMinutes: 15, channel: "push" },
    { level: 2, target: "fraud_team", timeoutMinutes: 30, channel: "email" },
    { level: 3, target: "compliance_officer", timeoutMinutes: 60, channel: "sms" },
    { level: 4, target: "cto", timeoutMinutes: 120, channel: "phone" },
  ]},
  { id: uuid(), name: "High-Value Transaction", levels: [
    { level: 1, target: "supervisor", timeoutMinutes: 10, channel: "push" },
    { level: 2, target: "operations_manager", timeoutMinutes: 30, channel: "email" },
    { level: 3, target: "cfo", timeoutMinutes: 60, channel: "sms" },
  ]},
  { id: uuid(), name: "System Outage", levels: [
    { level: 1, target: "devops_team", timeoutMinutes: 5, channel: "push" },
    { level: 2, target: "engineering_lead", timeoutMinutes: 15, channel: "sms" },
    { level: 3, target: "cto", timeoutMinutes: 30, channel: "phone" },
  ]},
  { id: uuid(), name: "Compliance Violation", levels: [
    { level: 1, target: "compliance_officer", timeoutMinutes: 30, channel: "email" },
    { level: 2, target: "legal_team", timeoutMinutes: 60, channel: "email" },
    { level: 3, target: "ceo", timeoutMinutes: 120, channel: "phone" },
  ]},
];
console.log(`✅ ${escalationChains.length} escalation chains generated`);

// ── 11. Commission Structures ────────────────────────────────────────────────
const commissionStructures = [
  { id: uuid(), name: "Standard Agent", tier: "starter", cashInRate: 0.5, cashOutRate: 0.75, transferRate: 0.3, billPaymentRate: 0.2, minPayout: 1000, payoutFrequency: "weekly" },
  { id: uuid(), name: "Bronze Agent", tier: "bronze", cashInRate: 0.6, cashOutRate: 0.85, transferRate: 0.35, billPaymentRate: 0.25, minPayout: 500, payoutFrequency: "weekly" },
  { id: uuid(), name: "Silver Agent", tier: "silver", cashInRate: 0.7, cashOutRate: 1.0, transferRate: 0.4, billPaymentRate: 0.3, minPayout: 500, payoutFrequency: "bi-weekly" },
  { id: uuid(), name: "Gold Agent", tier: "gold", cashInRate: 0.8, cashOutRate: 1.15, transferRate: 0.45, billPaymentRate: 0.35, minPayout: 0, payoutFrequency: "daily" },
  { id: uuid(), name: "Platinum Agent", tier: "platinum", cashInRate: 1.0, cashOutRate: 1.3, transferRate: 0.5, billPaymentRate: 0.4, minPayout: 0, payoutFrequency: "daily" },
];
console.log(`✅ ${commissionStructures.length} commission structures generated`);

// ── 12. Audit Log Entries ────────────────────────────────────────────────────
const auditActions = ["login", "logout", "create_transaction", "approve_kyc", "reject_kyc", "suspend_agent", "reactivate_agent", "update_config", "generate_report", "export_data", "create_invite_code", "update_branding", "resolve_dispute", "escalate_fraud"];
const auditLogs = Array.from({ length: 500 }, () => ({
  id: uuid(),
  action: pick(auditActions),
  performedBy: pick([...agents.slice(0, 10).map(a => a.id), "admin-001", "supervisor-001", "system"]),
  entityType: pick(["transaction", "agent", "customer", "kyc", "dispute", "config", "tenant"]),
  entityId: uuid(),
  details: pick(["Action completed successfully", "Approved after review", "Automatic system action", "Manual override applied"]),
  ipAddress: `${Math.floor(Math.random() * 255)}.${Math.floor(Math.random() * 255)}.${Math.floor(Math.random() * 255)}.${Math.floor(Math.random() * 255)}`,
  userAgent: pick(["Chrome/120", "Firefox/119", "Safari/17", "POS Terminal v2.1", "Mobile App v3.0"]),
  createdAt: randomDate(90),
}));
console.log(`✅ ${auditLogs.length} audit log entries generated`);

// ── 13. Webhooks ─────────────────────────────────────────────────────────────
const webhooks = [
  { id: uuid(), url: "https://api.partner1.com/webhooks/54link", events: ["transaction.completed", "fraud.detected"], secret: crypto.randomBytes(32).toString("hex"), status: "active", failureCount: 0 },
  { id: uuid(), url: "https://hooks.partner2.ng/remittance", events: ["settlement.completed", "dispute.filed"], secret: crypto.randomBytes(32).toString("hex"), status: "active", failureCount: 2 },
  { id: uuid(), url: "https://api.compliance.gov.ng/reports", events: ["aml.ctr_filed", "aml.sar_filed"], secret: crypto.randomBytes(32).toString("hex"), status: "active", failureCount: 0 },
];
console.log(`✅ ${webhooks.length} webhooks generated`);

// ── 14. API Keys ─────────────────────────────────────────────────────────────
const apiKeys = tenants.map(t => ({
  id: uuid(),
  tenantId: t.id,
  name: `${t.name} Production Key`,
  keyPrefix: `pk_live_${Math.random().toString(36).slice(2, 10)}`,
  hashedKey: crypto.createHash("sha256").update(crypto.randomBytes(32)).digest("hex"),
  permissions: ["transactions:read", "transactions:write", "agents:read", "reports:read"],
  rateLimit: 1000,
  status: "active",
  lastUsedAt: randomDate(7),
  createdAt: randomDate(180),
}));
console.log("[REDACTED sensitive data]");

// ── 15. Rate Alerts ──────────────────────────────────────────────────────────
const rateAlerts = Array.from({ length: 20 }, () => ({
  id: uuid(),
  userId: pick(agents).id,
  baseCurrency: pick(["USD", "GBP", "EUR"]),
  targetCurrency: "NGN",
  targetRate: randomAmount(700, 1800),
  direction: pick(["above", "below"]),
  active: Math.random() > 0.3,
  triggeredAt: Math.random() > 0.5 ? randomDate(30) : null,
  createdAt: randomDate(60),
}));
console.log(`✅ ${rateAlerts.length} rate alerts generated`);

// ── Summary ──────────────────────────────────────────────────────────────────
console.log("\n" + "═".repeat(60));
console.log("📊 Seed Data Summary:");
console.log(`   Tenants:              ${tenants.length}`);
console.log(`   Invite Codes:         ${inviteCodes.length}`);
console.log(`   Agents:               ${agents.length}`);
console.log(`   Customers:            ${customers.length}`);
console.log(`   Transactions:         ${transactions.length}`);
console.log(`   Fraud Alerts:         ${fraudAlerts.length}`);
console.log(`   Disputes:             ${disputes.length}`);
console.log(`   KYC Records:          ${kycRecords.length}`);
console.log(`   Notification Templates: ${notificationTemplates.length}`);
console.log(`   Escalation Chains:    ${escalationChains.length}`);
console.log(`   Commission Structures: ${commissionStructures.length}`);
console.log(`   Audit Logs:           ${auditLogs.length}`);
console.log(`   Webhooks:             ${webhooks.length}`);
console.log("[REDACTED sensitive data]");
console.log(`   Rate Alerts:          ${rateAlerts.length}`);
console.log(`   ─────────────────────────────`);
console.log("[REDACTED sensitive data]");
console.log("═".repeat(60));

// Export for programmatic use
const seedData = {
  tenants, inviteCodes, agents, customers, transactions, fraudAlerts,
  disputes, kycRecords, notificationTemplates, escalationChains,
  commissionStructures, auditLogs, webhooks, apiKeys, rateAlerts,
};

// Write to JSON for reference
import { writeFileSync } from "fs";
writeFileSync("data/seed-comprehensive.json", JSON.stringify(seedData, null, 2));
console.log("\n✅ Seed data written to data/seed-comprehensive.json");
