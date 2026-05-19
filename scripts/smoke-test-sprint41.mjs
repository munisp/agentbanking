#!/usr/bin/env node
/**
 * Sprint 41 Smoke Test — 54Link POS Shell
 * Validates all Sprint 41 endpoints are operational.
 * Usage: node scripts/smoke-test-sprint41.mjs [BASE_URL]
 */
const BASE_URL = process.argv[2] || "http://localhost:3000";
let passed = 0, failed = 0;
const results = [];

async function test(name, fn) {
  try { await fn(); passed++; results.push({ name, status: "PASS" }); console.log(`  ✅ ${name}`); }
  catch (err) { failed++; results.push({ name, status: "FAIL", error: err.message }); console.log(`  ❌ ${name}: ${err.message}`); }
}

async function fetchTrpc(procedure) {
  const url = `${BASE_URL}/api/trpc/${procedure}?input={}`;
  const res = await fetch(url, { headers: { "Content-Type": "application/json" } });
  return { status: res.status, data: await res.json().catch(() => null) };
}

console.log(`\n🔥 Sprint 41 Smoke Tests — ${BASE_URL}\n`);

const sprint41Procedures = [
  "agentKycDocVault.getStats", "realtimePnlDashboard.getStats", "autoReconciliationEngine.getStats",
  "agentTerritoryOptimizer.getStats", "paymentDisputeArbitration.getStats", "regulatoryReportGenerator.getStats",
  "agentTrainingAcademy.getStats", "dynamicFeeCalculator.getStats", "customerOnboardingPipeline.getStats",
  "merchantSettlementDashboard.getStats", "agentFloatInsuranceClaims.getStats", "platformSlaMonitor.getStats",
  "bulkDisbursementEngine.getStats", "transactionReversalManager.getStats", "agentLoanOrigination.getStats",
  "multiChannelNotificationHub.getStats", "complianceTrainingTracker.getStats", "platformMigrationToolkit.getStats",
  "agentPerformanceIncentives.getStats", "executiveCommandCenter.getStats",
];

for (const proc of sprint41Procedures) {
  await test(`tRPC: ${proc}`, async () => {
    const { status } = await fetchTrpc(proc);
    // 401 is expected for protected procedures without auth — that's correct behavior
    if (status !== 200 && status !== 401) throw new Error(`HTTP ${status}`);
  });
}

const sprint41Routes = [
  "/agent-kyc-vault", "/realtime-pnl", "/auto-reconciliation", "/territory-optimizer",
  "/dispute-arbitration", "/regulatory-reports", "/training-academy", "/fee-calculator",
  "/customer-onboarding", "/merchant-settlement", "/insurance-claims", "/sla-monitor",
  "/bulk-disbursement", "/reversal-manager", "/loan-origination", "/notification-hub",
  "/compliance-training", "/migration-toolkit", "/performance-incentives", "/executive-command",
];

for (const route of sprint41Routes) {
  await test(`Route: ${route}`, async () => {
    const res = await fetch(`${BASE_URL}${route}`);
    if (res.status !== 200) throw new Error(`HTTP ${res.status}`);
  });
}

console.log(`\n${"═".repeat(60)}`);
console.log(`  Results: ${passed} passed, ${failed} failed, ${passed + failed} total`);
console.log(`${"═".repeat(60)}\n`);
process.exit(failed > 0 ? 1 : 0);
