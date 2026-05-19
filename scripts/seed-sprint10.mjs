// SECURITY: SQL template literals in this file are for display/mock purposes only. All actual DB queries use parameterized Drizzle ORM.
#!/usr/bin/env node
/**
 * Sprint 10 Enhanced Seed Data — 54Link Agency Banking Platform
 * 
 * Seeds data for: rate alerts, email delivery logs, SMS logs,
 * notification inbox, webhook configs, preference matrices,
 * batch operations history, API keys, and security audit entries.
 */
import { randomUUID } from "crypto";

const BASE_URL = process.env.API_URL || "http://localhost:3000";

// ═══════════════════════════════════════════════════════════════════════════════
// Helpers
// ═══════════════════════════════════════════════════════════════════════════════
function uuid() { return randomUUID(); }
function randomInt(min, max) { return Math.floor(Math.random() * (max - min + 1)) + min; }
function randomChoice(arr) { return arr[Math.floor(Math.random() * arr.length)]; }
function randomDate(daysBack = 90) {
  const d = new Date();
  d.setDate(d.getDate() - randomInt(0, daysBack));
  d.setHours(randomInt(0, 23), randomInt(0, 59), randomInt(0, 59));
  return d.toISOString();
}

const CURRENCIES = ["USD", "EUR", "GBP", "KES", "NGN", "GHS", "ZAR", "TZS", "UGX", "RWF", "XOF", "XAF", "EGP", "MAD", "ETB", "MZN", "BWP", "MWK", "ZMW", "AOA"];
const CHANNELS = ["email", "sms", "push", "in_app"];
const SEVERITIES = ["info", "warning", "critical"];
const CATEGORIES = ["transaction", "fraud", "kyc", "settlement", "commission", "system", "rate_alert", "compliance"];

// ═══════════════════════════════════════════════════════════════════════════════
// 1. Rate Alert Subscriptions
// ═══════════════════════════════════════════════════════════════════════════════
function seedRateAlerts() {
  const alerts = [];
  for (let i = 0; i < 25; i++) {
    const baseCurrency = randomChoice(CURRENCIES.slice(0, 5));
    let targetCurrency;
    do { targetCurrency = randomChoice(CURRENCIES); } while (targetCurrency === baseCurrency);
    
    alerts.push({
      id: uuid(),
      userId: `user_${randomInt(1, 50)}`,
      baseCurrency,
      targetCurrency,
      targetRate: (Math.random() * 2 + 0.5).toFixed(4),
      direction: randomChoice(["above", "below"]),
      channels: JSON.stringify(CHANNELS.slice(0, randomInt(1, 3))),
      status: randomChoice(["active", "active", "active", "triggered", "paused", "expired"]),
      triggeredAt: Math.random() > 0.7 ? randomDate(30) : null,
      triggeredRate: Math.random() > 0.7 ? (Math.random() * 2 + 0.5).toFixed(4) : null,
      notificationsSent: randomInt(0, 5),
      cooldownMinutes: randomChoice([15, 30, 60, 120, 360]),
      expiresAt: new Date(Date.now() + randomInt(1, 90) * 86400000).toISOString(),
      createdAt: randomDate(60),
    });
  }
  console.log(`  ✓ ${alerts.length} rate alert subscriptions`);
  return alerts;
}

// ═══════════════════════════════════════════════════════════════════════════════
// 2. Email Delivery Logs
// ═══════════════════════════════════════════════════════════════════════════════
function seedEmailDeliveryLogs() {
  const logs = [];
  const templates = ["rate_alert", "welcome", "password_reset", "weekly_digest", "transaction_receipt", "kyc_approved", "fraud_alert"];
  const providers = ["sendgrid", "ses"];
  const statuses = ["delivered", "delivered", "delivered", "bounced", "failed", "pending"];
  
  for (let i = 0; i < 100; i++) {
    logs.push({
      id: uuid(),
      to: `user${randomInt(1, 50)}@example.com`,
      subject: `${randomChoice(templates).replace(/_/g, " ")} notification`,
      template: randomChoice(templates),
      provider: randomChoice(providers),
      status: randomChoice(statuses),
      messageId: `msg_${uuid().slice(0, 12)}`,
      openedAt: Math.random() > 0.5 ? randomDate(7) : null,
      clickedAt: Math.random() > 0.7 ? randomDate(7) : null,
      bouncedReason: Math.random() > 0.9 ? "mailbox_full" : null,
      retryCount: randomInt(0, 3),
      sentAt: randomDate(30),
      createdAt: randomDate(30),
    });
  }
  console.log(`  ✓ ${logs.length} email delivery logs`);
  return logs;
}

// ═══════════════════════════════════════════════════════════════════════════════
// 3. SMS Delivery Logs
// ═══════════════════════════════════════════════════════════════════════════════
function seedSmsDeliveryLogs() {
  const logs = [];
  const providers = ["twilio", "africastalking", "termii"];
  const statuses = ["delivered", "delivered", "delivered", "failed", "pending", "queued"];
  const countryCodes = ["+254", "+234", "+233", "+27", "+255", "+256", "+250"];
  
  for (let i = 0; i < 80; i++) {
    const cc = randomChoice(countryCodes);
    logs.push({
      id: uuid(),
      to: `${cc}7${randomInt(10000000, 99999999)}`,
      message: `Your ${randomChoice(["OTP", "transaction", "alert", "balance"])} ${randomChoice(["code is", "of", "notification:", "update:"])} ${randomInt(1000, 9999)}`,
      provider: randomChoice(providers),
      status: randomChoice(statuses),
      messageId: `sms_${uuid().slice(0, 12)}`,
      segments: randomInt(1, 3),
      cost: (Math.random() * 0.05 + 0.01).toFixed(4),
      deliveredAt: Math.random() > 0.3 ? randomDate(7) : null,
      failureReason: Math.random() > 0.9 ? randomChoice(["invalid_number", "carrier_rejected", "timeout"]) : null,
      retryCount: randomInt(0, 2),
      sentAt: randomDate(30),
      createdAt: randomDate(30),
    });
  }
  console.log(`  ✓ ${logs.length} SMS delivery logs`);
  return logs;
}

// ═══════════════════════════════════════════════════════════════════════════════
// 4. Notification Inbox Entries
// ═══════════════════════════════════════════════════════════════════════════════
function seedNotificationInbox() {
  const entries = [];
  const types = ["transaction_complete", "fraud_alert", "kyc_status", "rate_alert_triggered", "settlement_ready", "commission_paid", "system_maintenance", "compliance_update"];
  
  for (let i = 0; i < 150; i++) {
    const type = randomChoice(types);
    const channel = randomChoice(CHANNELS);
    entries.push({
      id: uuid(),
      userId: `user_${randomInt(1, 50)}`,
      type,
      title: `${type.replace(/_/g, " ")} — ${randomChoice(["Action required", "For your information", "Urgent", "Completed"])}`,
      body: `This is a ${type.replace(/_/g, " ")} notification for ${randomChoice(["agent", "customer", "merchant"])} ${randomInt(1000, 9999)}.`,
      channel,
      severity: randomChoice(SEVERITIES),
      category: randomChoice(CATEGORIES),
      isRead: Math.random() > 0.4,
      isStarred: Math.random() > 0.8,
      isArchived: Math.random() > 0.9,
      actionUrl: Math.random() > 0.5 ? `/dashboard/${type.split("_")[0]}` : null,
      metadata: JSON.stringify({ source: randomChoice(["system", "webhook", "cron", "user_action"]) }),
      createdAt: randomDate(30),
    });
  }
  console.log(`  ✓ ${entries.length} notification inbox entries`);
  return entries;
}

// ═══════════════════════════════════════════════════════════════════════════════
// 5. Webhook Configurations
// ═══════════════════════════════════════════════════════════════════════════════
function seedWebhookConfigs() {
  const configs = [];
  const events = ["transaction.completed", "transaction.failed", "kyc.approved", "kyc.rejected", "fraud.detected", "settlement.ready", "agent.onboarded", "commission.paid"];
  
  for (let i = 0; i < 15; i++) {
    const selectedEvents = events.slice(0, randomInt(2, events.length));
    configs.push({
      id: uuid(),
      name: `Webhook ${i + 1} — ${randomChoice(["Payment Gateway", "CRM", "Analytics", "ERP", "Compliance", "Audit"])}`,
      url: `https://hooks.example.com/webhook/${uuid().slice(0, 8)}`,
      secret: `whsec_${uuid().replace(/-/g, "").slice(0, 32)}`,
      events: JSON.stringify(selectedEvents),
      isActive: Math.random() > 0.2,
      retryPolicy: JSON.stringify({ maxRetries: randomChoice([3, 5, 10]), backoffMs: randomChoice([1000, 5000, 10000]) }),
      headers: JSON.stringify({ "X-Custom-Header": `value_${randomInt(1, 100)}` }),
      lastDeliveryAt: Math.random() > 0.3 ? randomDate(7) : null,
      lastDeliveryStatus: randomChoice(["success", "success", "success", "failed", "timeout"]),
      totalDeliveries: randomInt(0, 500),
      failedDeliveries: randomInt(0, 20),
      createdAt: randomDate(90),
    });
  }
  console.log(`  ✓ ${configs.length} webhook configurations`);
  return configs;
}

// ═══════════════════════════════════════════════════════════════════════════════
// 6. Notification Preference Matrices
// ═══════════════════════════════════════════════════════════════════════════════
function seedPreferenceMatrices() {
  const matrices = [];
  
  for (let userId = 1; userId <= 30; userId++) {
    for (const category of CATEGORIES) {
      const prefs = {};
      for (const channel of CHANNELS) {
        prefs[channel] = Math.random() > 0.3;
      }
      matrices.push({
        id: uuid(),
        userId: `user_${userId}`,
        category,
        preferences: JSON.stringify(prefs),
        quietHoursStart: randomChoice(["22:00", "23:00", "00:00", null]),
        quietHoursEnd: randomChoice(["06:00", "07:00", "08:00", null]),
        timezone: randomChoice(["Africa/Nairobi", "Africa/Lagos", "Africa/Accra", "Africa/Johannesburg", "UTC"]),
        updatedAt: randomDate(30),
      });
    }
  }
  console.log(`  ✓ ${matrices.length} notification preference matrix entries`);
  return matrices;
}

// ═══════════════════════════════════════════════════════════════════════════════
// 7. Batch Operation History
// ═══════════════════════════════════════════════════════════════════════════════
function seedBatchOperations() {
  const ops = [];
  const types = ["bulk_sms", "bulk_email", "mass_payout", "batch_kyc_review", "agent_status_update", "commission_calculation", "settlement_batch", "data_export"];
  
  for (let i = 0; i < 40; i++) {
    const total = randomInt(10, 5000);
    const succeeded = randomInt(Math.floor(total * 0.8), total);
    const failed = total - succeeded;
    ops.push({
      id: uuid(),
      type: randomChoice(types),
      initiatedBy: `user_${randomInt(1, 10)}`,
      status: randomChoice(["completed", "completed", "completed", "in_progress", "failed", "cancelled"]),
      totalItems: total,
      succeededItems: succeeded,
      failedItems: failed,
      progressPercent: succeeded === total ? 100 : randomInt(50, 99),
      inputFile: Math.random() > 0.5 ? `uploads/batch_${uuid().slice(0, 8)}.csv` : null,
      outputFile: Math.random() > 0.3 ? `exports/result_${uuid().slice(0, 8)}.csv` : null,
      errorLog: failed > 0 ? JSON.stringify(Array.from({ length: Math.min(failed, 5) }, (_, j) => ({ row: randomInt(1, total), error: "Validation failed" }))) : null,
      startedAt: randomDate(30),
      completedAt: Math.random() > 0.2 ? randomDate(30) : null,
      duration: `${randomInt(5, 3600)}s`,
      createdAt: randomDate(30),
    });
  }
  console.log(`  ✓ ${ops.length} batch operation records`);
  return ops;
}

// ═══════════════════════════════════════════════════════════════════════════════
// 8. API Key Records
// ═══════════════════════════════════════════════════════════════════════════════
function seedApiKeys() {
  const keys = [];
  const scopes = ["read:transactions", "write:transactions", "read:agents", "write:agents", "read:customers", "write:customers", "read:analytics", "admin:all"];
  
  for (let i = 0; i < 20; i++) {
    const selectedScopes = scopes.slice(0, randomInt(1, scopes.length));
    keys.push({
      id: uuid(),
      name: `API Key — ${randomChoice(["Mobile App", "Web Dashboard", "Partner Integration", "Analytics Service", "Webhook Service", "CI/CD Pipeline"])} ${i + 1}`,
      keyPrefix: `pk_${randomChoice(["live", "test"])}_${uuid().slice(0, 8)}`,
      keyHash: `sha256:${uuid().replace(/-/g, "")}${uuid().replace(/-/g, "")}`,
      scopes: JSON.stringify(selectedScopes),
      ownerId: `user_${randomInt(1, 10)}`,
      isActive: Math.random() > 0.15,
      lastUsedAt: Math.random() > 0.3 ? randomDate(7) : null,
      lastUsedIp: Math.random() > 0.3 ? `${randomInt(10, 200)}.${randomInt(0, 255)}.${randomInt(0, 255)}.${randomInt(1, 254)}` : null,
      requestCount: randomInt(0, 50000),
      rateLimit: randomChoice([100, 500, 1000, 5000]),
      expiresAt: Math.random() > 0.5 ? new Date(Date.now() + randomInt(30, 365) * 86400000).toISOString() : null,
      createdAt: randomDate(180),
    });
  }
  console.log("[REDACTED sensitive data]");
  return keys;
}

// ═══════════════════════════════════════════════════════════════════════════════
// 9. Security Audit Entries
// ═══════════════════════════════════════════════════════════════════════════════
function seedSecurityAuditEntries() {
  const entries = [];
  const actions = ["login_success", "login_failed", "password_change", "role_change", "api_key_created", "api_key_revoked", "webhook_created", "data_export", "bulk_operation", "permission_denied", "rate_limit_exceeded", "suspicious_activity"];
  
  for (let i = 0; i < 200; i++) {
    const action = randomChoice(actions);
    entries.push({
      id: uuid(),
      action,
      userId: `user_${randomInt(1, 50)}`,
      ipAddress: `${randomInt(10, 200)}.${randomInt(0, 255)}.${randomInt(0, 255)}.${randomInt(1, 254)}`,
      userAgent: randomChoice([
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36",
        "54Link-Mobile/2.1.0 (iOS 17.4)",
        "54Link-Mobile/2.1.0 (Android 14)",
      ]),
      resource: randomChoice(["transactions", "agents", "customers", "settings", "api_keys", "webhooks"]),
      details: JSON.stringify({
        method: randomChoice(["GET", "POST", "PUT", "DELETE"]),
        path: `/api/${randomChoice(["transactions", "agents", "customers", "settings"])}`,
        statusCode: randomChoice([200, 201, 400, 401, 403, 404, 429, 500]),
      }),
      severity: action.includes("failed") || action.includes("denied") || action.includes("suspicious") ? "warning" : "info",
      createdAt: randomDate(30),
    });
  }
  console.log(`  ✓ ${entries.length} security audit entries`);
  return entries;
}

// ═══════════════════════════════════════════════════════════════════════════════
// 10. Multi-Currency Exchange Rate History
// ═══════════════════════════════════════════════════════════════════════════════
function seedExchangeRateHistory() {
  const records = [];
  const pairs = [
    ["USD", "KES"], ["USD", "NGN"], ["USD", "GHS"], ["USD", "ZAR"],
    ["EUR", "KES"], ["EUR", "NGN"], ["GBP", "KES"], ["GBP", "NGN"],
    ["KES", "UGX"], ["KES", "TZS"], ["NGN", "GHS"], ["ZAR", "BWP"],
  ];
  const baseRates = {
    "USD-KES": 129.5, "USD-NGN": 1550, "USD-GHS": 14.8, "USD-ZAR": 18.2,
    "EUR-KES": 141.3, "EUR-NGN": 1690, "GBP-KES": 164.7, "GBP-NGN": 1970,
    "KES-UGX": 28.9, "KES-TZS": 19.4, "NGN-GHS": 0.0095, "ZAR-BWP": 0.75,
  };

  for (const [base, target] of pairs) {
    const baseRate = baseRates[`${base}-${target}`] || 1;
    for (let day = 0; day < 365; day++) {
      const date = new Date();
      date.setDate(date.getDate() - day);
      // Add realistic daily fluctuation (±2%)
      const fluctuation = 1 + (Math.random() - 0.5) * 0.04;
      // Add trend (slight appreciation/depreciation over time)
      const trend = 1 + (day / 365) * (Math.random() > 0.5 ? 0.05 : -0.03);
      records.push({
        id: uuid(),
        baseCurrency: base,
        targetCurrency: target,
        rate: (baseRate * fluctuation * trend).toFixed(6),
        source: randomChoice(["ecb", "frankfurter", "openexchangerates"]),
        date: date.toISOString().split("T")[0],
        createdAt: date.toISOString(),
      });
    }
  }
  console.log(`  ✓ ${records.length} exchange rate history records (${pairs.length} pairs × 365 days)`);
  return records;
}

// ═══════════════════════════════════════════════════════════════════════════════
// Main
// ═══════════════════════════════════════════════════════════════════════════════
async function main() {
  console.log("═══════════════════════════════════════════════════════");
  console.log("  54Link Sprint 10 Seed Data Generator");
  console.log("═══════════════════════════════════════════════════════\n");

  const data = {
    rateAlerts: seedRateAlerts(),
    emailLogs: seedEmailDeliveryLogs(),
    smsLogs: seedSmsDeliveryLogs(),
    inboxEntries: seedNotificationInbox(),
    webhookConfigs: seedWebhookConfigs(),
    preferenceMatrices: seedPreferenceMatrices(),
    batchOperations: seedBatchOperations(),
    apiKeys: seedApiKeys(),
    securityAudit: seedSecurityAuditEntries(),
    exchangeRateHistory: seedExchangeRateHistory(),
  };

  const totalRecords = Object.values(data).reduce((sum, arr) => sum + arr.length, 0);
  
  console.log(`\n═══════════════════════════════════════════════════════`);
  console.log(`  Total: ${totalRecords.toLocaleString()} seed records generated`);
  console.log("[REDACTED sensitive data]").length}`);
  console.log(`═══════════════════════════════════════════════════════`);

  // Write to JSON for import
  const { writeFileSync } = await import("fs");
  const outputPath = new URL("../data/seed-sprint10.json", import.meta.url).pathname;
  const { mkdirSync } = await import("fs");
  try { mkdirSync(new URL("../data", import.meta.url).pathname, { recursive: true }); } catch {}
  writeFileSync(outputPath, JSON.stringify(data, null, 2));
  console.log(`\n  📁 Written to: ${outputPath}`);
}

main().catch(console.error);
