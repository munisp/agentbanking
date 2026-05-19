/**
 * Sprint 50 Smoke Test — Validates all 20 new features
 * Run: node scripts/smoke-test-sprint50.mjs
 */
import pg from "pg";
const { Pool } = pg;

const pool = new Pool({
  connectionString: process.env.POSTGRES_URL || "postgresql://posadmin:posadmin123@localhost:5432/pos54link",
  ssl: false,
});

const results = [];
let passed = 0;
let failed = 0;

async function test(name, fn) {
  try {
    await fn();
    results.push({ name, status: "PASS" });
    passed++;
    console.log(`  ✅ ${name}`);
  } catch (err) {
    results.push({ name, status: "FAIL", error: err.message });
    failed++;
    console.log(`  ❌ ${name}: ${err.message}`);
  }
}

async function run() {
  const client = await pool.connect();
  console.log("🧪 Sprint 50 Smoke Tests\n");
  console.log("=" .repeat(60));

  // F01: Real-Time Transaction Monitor
  await test("F01: realtime_tx_alerts table exists with data", async () => {
    const { rows } = await client.query("SELECT COUNT(*) as cnt FROM realtime_tx_alerts");
    if (parseInt(rows[0].cnt) < 1) throw new Error("No alerts found");
  });
  await test("F01: Alert severity distribution", async () => {
    const { rows } = await client.query("SELECT severity, COUNT(*) FROM realtime_tx_alerts GROUP BY severity");
    if (rows.length < 2) throw new Error("Insufficient severity distribution");
  });

  // F02: Fraud ML Scoring
  await test("F02: fraud_ml_scores table exists with data", async () => {
    const { rows } = await client.query("SELECT COUNT(*) as cnt FROM fraud_ml_scores");
    if (parseInt(rows[0].cnt) < 1) throw new Error("No scores found");
  });
  await test("F02: ML model version consistency", async () => {
    const { rows } = await client.query("SELECT DISTINCT model_version FROM fraud_ml_scores");
    if (rows.length < 1) throw new Error("No model versions");
  });

  // F03: Notification Templates
  await test("F03: notification_templates table with channels", async () => {
    const { rows } = await client.query("SELECT DISTINCT channel FROM notification_templates");
    if (rows.length < 3) throw new Error("Need sms, email, push channels");
  });

  // F04: Agent Loans
  await test("F04: agent_loans table with status lifecycle", async () => {
    const { rows } = await client.query("SELECT DISTINCT status FROM agent_loans");
    if (rows.length < 3) throw new Error("Insufficient loan statuses");
  });
  await test("F04: Loan amounts are positive", async () => {
    const { rows } = await client.query("SELECT COUNT(*) as cnt FROM agent_loans WHERE principal_amount <= 0");
    if (parseInt(rows[0].cnt) > 0) throw new Error("Found non-positive loan amounts");
  });

  // F05: Fee Rules
  await test("F05: fee_rules table with transaction types", async () => {
    const { rows } = await client.query("SELECT COUNT(*) as cnt FROM fee_rules");
    if (parseInt(rows[0].cnt) < 5) throw new Error("Insufficient fee rules");
  });

  // F06: Merchant KYC
  await test("F06: merchant_kyc_docs with verification statuses", async () => {
    const { rows } = await client.query("SELECT DISTINCT status FROM merchant_kyc_docs");
    if (rows.length < 2) throw new Error("Need multiple KYC statuses");
  });

  // F07: Merchant Payouts
  await test("F07: merchant_payouts with settlement data", async () => {
    const { rows } = await client.query("SELECT COUNT(*) as cnt FROM merchant_payouts WHERE amount > 0");
    if (parseInt(rows[0].cnt) < 1) throw new Error("No payouts found");
  });

  // F08: Compliance Filings
  await test("F08: compliance_filings with regulatory bodies", async () => {
    const { rows } = await client.query("SELECT DISTINCT submitted_to FROM compliance_filings WHERE submitted_to IS NOT NULL");
    if (rows.length < 3) throw new Error("Need multiple regulatory bodies");
  });

  // F09: Agent Gamification
  await test("F09: agent_achievements table populated", async () => {
    const { rows } = await client.query("SELECT COUNT(*) as cnt FROM agent_achievements");
    if (parseInt(rows[0].cnt) < 50) throw new Error("Insufficient achievements");
  });
  await test("F09: agent_badges catalog exists", async () => {
    const { rows } = await client.query("SELECT COUNT(*) as cnt FROM agent_badges WHERE is_active = true");
    if (parseInt(rows[0].cnt) < 5) throw new Error("Need at least 5 active badges");
  });

  // F10: Tenant Feature Toggles
  await test("F10: tenant_feature_toggles with multi-tenant data", async () => {
    const { rows } = await client.query("SELECT COUNT(DISTINCT tenant_id) as cnt FROM tenant_feature_toggles");
    if (parseInt(rows[0].cnt) < 2) throw new Error("Need multiple tenants");
  });

  // F11: Reconciliation Engine
  await test("F11: reconciliation_batches with match statistics", async () => {
    const { rows } = await client.query("SELECT COUNT(*) as cnt FROM reconciliation_batches WHERE matched_count > 0");
    if (parseInt(rows[0].cnt) < 1) throw new Error("No matched batches");
  });

  // F12: Customer Journey Analytics
  await test("F12: customer_journey_steps with funnel stages", async () => {
    const { rows } = await client.query("SELECT DISTINCT step_type FROM customer_journey_steps");
    if (rows.length < 4) throw new Error("Insufficient journey stages");
  });

  // F13: Rate Limiting
  await test("F13: rate_limit_rules with endpoint coverage", async () => {
    const { rows } = await client.query("SELECT COUNT(*) as cnt FROM rate_limit_rules WHERE is_active = true");
    if (parseInt(rows[0].cnt) < 5) throw new Error("Insufficient rate limit rules");
  });

  // F14: Backup & DR
  await test("F14: backup_snapshots with full and incremental types", async () => {
    const { rows } = await client.query("SELECT DISTINCT snapshot_type FROM backup_snapshots");
    if (rows.length < 2) throw new Error("Need both full and incremental backups");
  });

  // F15: Workflow Engine
  await test("F15: workflow_definitions with active workflows", async () => {
    const { rows } = await client.query("SELECT COUNT(*) as cnt FROM workflow_definitions WHERE is_active = true");
    if (parseInt(rows[0].cnt) < 3) throw new Error("Need at least 3 active workflows");
  });
  await test("F15: workflow_instances running", async () => {
    const { rows } = await client.query("SELECT COUNT(*) as cnt FROM workflow_instances");
    if (parseInt(rows[0].cnt) < 1) throw new Error("No workflow instances");
  });

  // F16: General Ledger
  await test("F16: gl_entries with double-entry balancing", async () => {
    const { rows } = await client.query("SELECT SUM(CASE WHEN entry_type='debit' THEN amount ELSE -amount END) as balance FROM gl_entries");
    const balance = parseFloat(rows[0].balance);
    if (Math.abs(balance) > 0.01) throw new Error(`GL not balanced: ${balance}`);
  });

  // F17: Webhook Management
  await test("F17: webhook_subscriptions active", async () => {
    const { rows } = await client.query("SELECT COUNT(*) as cnt FROM webhook_subscriptions WHERE active = true");
    if (parseInt(rows[0].cnt) < 3) throw new Error("Need at least 3 active subscriptions");
  });
  await test("F17: webhook_delivery_logs with delivery stats", async () => {
    const { rows } = await client.query("SELECT COUNT(*) as cnt FROM webhook_delivery_logs");
    if (parseInt(rows[0].cnt) < 10) throw new Error("Insufficient delivery logs");
  });

  // F18: SLA Monitoring
  await test("F18: sla_definitions with service coverage", async () => {
    const { rows } = await client.query("SELECT COUNT(DISTINCT service_name) as cnt FROM sla_definitions");
    if (parseInt(rows[0].cnt) < 4) throw new Error("Need SLAs for at least 4 services");
  });
  await test("F18: sla_breaches tracked", async () => {
    const { rows } = await client.query("SELECT COUNT(*) as cnt FROM sla_breaches");
    if (parseInt(rows[0].cnt) < 1) throw new Error("No breaches tracked");
  });

  // F19: Data Export Hub
  await test("F19: data_export_jobs with multiple formats", async () => {
    const { rows } = await client.query("SELECT DISTINCT format FROM data_export_jobs");
    if (rows.length < 3) throw new Error("Need multiple export formats");
  });

  // F20: Platform Health
  await test("F20: platform_health_checks with service coverage", async () => {
    const { rows } = await client.query("SELECT COUNT(DISTINCT service_name) as cnt FROM platform_health_checks");
    if (parseInt(rows[0].cnt) < 5) throw new Error("Need health checks for at least 5 services");
  });
  await test("F20: platform_incidents tracked", async () => {
    const { rows } = await client.query("SELECT COUNT(*) as cnt FROM platform_incidents");
    if (parseInt(rows[0].cnt) >= 1) return;
    throw new Error("No incidents tracked");
  });

  // Schema integrity checks
  await test("Schema: All Sprint 50 tables exist", async () => {
    const tables = [
      "realtime_tx_alerts", "fraud_ml_scores", "notification_templates",
      "agent_loans", "fee_rules", "merchant_kyc_docs", "merchant_payouts",
      "compliance_filings", "agent_achievements", "agent_badges",
      "tenant_feature_toggles", "reconciliation_batches", "customer_journey_steps",
      "rate_limit_rules", "backup_snapshots", "workflow_definitions",
      "workflow_instances", "gl_entries", "webhook_subscriptions",
      "webhook_delivery_logs", "sla_definitions", "sla_breaches",
      "data_export_jobs", "platform_health_checks", "platform_incidents",
    ];
    for (const t of tables) {
      const { rows } = await client.query(`SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = $1)`, [t]);
      if (!rows[0].exists) throw new Error(`Table ${t} missing`);
    }
  });

  // Router file checks
  await test("Routers: All 20 Sprint 50 router files exist", async () => {
    const fs = await import("fs");
    const routers = [
      "realtimeTxMonitor", "fraudMlScoringEngine", "notificationOrchestrator",
      "agentLoanFacility", "dynamicFeeEngine", "merchantKycOnboarding",
      "merchantPayoutSettlement", "complianceFiling", "agentGamification",
      "tenantFeatureToggle", "reconciliationEngine", "customerJourneyAnalytics",
      "rateLimitEngine", "backupDisasterRecovery", "workflowEngine",
      "generalLedger", "webhookManagement", "slaMonitoring",
      "dataExportHub", "platformHealth",
    ];
    for (const r of routers) {
      const exists = fs.existsSync(`server/routers/${r}.ts`);
      if (!exists) throw new Error(`Router ${r}.ts missing`);
    }
  });

  client.release();
  await pool.end();

  // Summary
  console.log("\n" + "=".repeat(60));
  console.log(`\n📊 Results: ${passed} passed, ${failed} failed, ${passed + failed} total`);
  console.log(`   Pass rate: ${((passed / (passed + failed)) * 100).toFixed(1)}%`);
  
  if (failed === 0) {
    console.log("\n🎉 ALL SMOKE TESTS PASSED!");
  } else {
    console.log("\n⚠️  Some tests failed. Review output above.");
    process.exit(1);
  }
}

run().catch(err => {
  console.error("Fatal error:", err);
  process.exit(1);
});
