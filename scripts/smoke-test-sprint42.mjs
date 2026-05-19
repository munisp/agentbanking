#!/usr/bin/env node
/**
 * 54Link POS Shell — Sprint 42 Smoke Test Suite
 * Tests all Sprint 42 endpoints and page routes.
 */

const BASE = process.env.BASE_URL || "http://localhost:3000";
let passed = 0, failed = 0, total = 0;

async function test(name, fn) {
  total++;
  try {
    await fn();
    passed++;
    console.log(`  ✅ ${name}`);
  } catch (e) {
    failed++;
    console.log(`  ❌ ${name}: ${e.message}`);
  }
}

async function checkRoute(path, expectedStatus = 200) {
  const res = await fetch(`${BASE}${path}`, { redirect: "manual" });
  if (res.status !== expectedStatus && res.status !== 302 && res.status !== 200) {
    throw new Error(`Expected ${expectedStatus}, got ${res.status}`);
  }
}

async function checkTrpc(procedure) {
  const res = await fetch(`${BASE}/api/trpc/${procedure}?input={}`, { redirect: "manual" });
  if (res.status !== 200 && res.status !== 401 && res.status !== 400) {
    throw new Error(`tRPC ${procedure}: Expected 200/401/400, got ${res.status}`);
  }
}

console.log("🔥 Sprint 42 Smoke Tests");
console.log("========================\n");

// Page route tests
console.log("📄 Page Routes:");
const routes = [
  "/dispute-notifications", "/dispute-analytics-dashboard", "/agent-benchmarking",
  "/tx-velocity-monitor", "/customer-surveys", "/agent-territory-heatmap",
  "/report-scheduler", "/gateway-health-monitor", "/agent-loan-origination-v2",
  "/mfa-manager", "/data-retention-policy", "/incident-playbook",
  "/device-fleet-manager", "/revenue-leakage-detector", "/customer-journey-mapper",
  "/compliance-cert-manager", "/platform-health-scorecard", "/training-certification",
  "/bulk-transaction-processor", "/system-config-manager",
];

for (const route of routes) {
  await test(`GET ${route}`, () => checkRoute(route));
}

// tRPC endpoint tests — using actual procedure names from routers
console.log("\n🔌 tRPC Endpoints:");
const procedures = [
  "disputeNotifications.listNotifications",
  "disputeAnalytics.getResolutionMetrics",
  "agentBenchmarking.getBenchmarks",
  "txVelocityMonitor.getCurrentTps",
  "customerSurveys.listSurveys",
  "agentTerritoryHeatmap.getHeatmapData",
  "reportScheduler.listSchedules",
  "gatewayHealthMonitor.getGatewayStatus",
  "agentLoanOrigination2.listApplications",
  "mfaManager.getMfaStatus",
  "dataRetentionPolicy.listPolicies",
  "incidentPlaybook.listPlaybooks",
  "deviceFleetManager.listDevices",
  "revenueLeakageDetector.getLeakageReport",
  "customerJourneyMapper.listJourneys",
  "complianceCertManager.listCertificates",
  "platformHealthScorecard.getOverallScore",
  "trainingCertification.listCourses",
  "bulkTransactionProcessor.listBatches",
  "systemConfigManager.listConfigs",
];

for (const proc of procedures) {
  await test(`tRPC ${proc}`, () => checkTrpc(proc));
}

// Server health
console.log("\n🏥 Server Health:");
await test("Server responds", async () => {
  const res = await fetch(`${BASE}/`);
  if (!res.ok) throw new Error(`Server returned ${res.status}`);
});

console.log(`\n${"=".repeat(40)}`);
console.log(`Results: ${passed}/${total} passed, ${failed} failed`);
console.log(`Score: ${((passed / total) * 100).toFixed(1)}%`);
process.exit(failed > 0 ? 1 : 0);
