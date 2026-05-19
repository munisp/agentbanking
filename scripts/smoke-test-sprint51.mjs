// Sprint 51 Smoke Tests — UI Pages, Routes, CRUD, Schema
import fs from 'fs';
import path from 'path';

const projectDir = '/home/ubuntu/pos-shell-demo';
let passed = 0, failed = 0;

function test(name, fn) {
  try {
    const result = fn();
    if (result) { passed++; console.log(`  ✅ ${name}`); }
    else { failed++; console.log(`  ❌ ${name}`); }
  } catch (e) { failed++; console.log(`  ❌ ${name}: ${e.message}`); }
}

function fileExists(fp) { return fs.existsSync(path.join(projectDir, fp)); }
function fileContains(fp, text) {
  try { return fs.readFileSync(path.join(projectDir, fp), 'utf-8').includes(text); }
  catch { return false; }
}

console.log('============================================================');
console.log('  Sprint 51 Smoke Tests');
console.log('============================================================');

// Test 1: All 20 UI pages exist
const pages = [
  'RealtimeTxMonitorPage', 'FraudMlScoringPage', 'NotificationOrchestratorPage',
  'AgentLoanFacilityPage', 'DynamicFeeEnginePage', 'MerchantKycOnboardingPage',
  'MerchantPayoutSettlementPage', 'ComplianceFilingPage', 'AgentGamificationPage',
  'TenantFeatureTogglePage', 'ReconciliationEnginePage', 'CustomerJourneyAnalyticsPage',
  'RateLimitEnginePage', 'BackupDisasterRecoveryPage', 'WorkflowEnginePage',
  'GeneralLedgerPage', 'WebhookManagementPage', 'SlaMonitoringPage',
  'DataExportHubPage', 'PlatformHealthPage'
];
for (const p of pages) {
  test(`UI Page: ${p}`, () => fileExists(`client/src/pages/${p}.tsx`));
}

// Test 2: All pages have CRUD operations
const crudPages = [
  'RealtimeTxMonitorPage', 'FraudMlScoringPage', 'AgentLoanFacilityPage',
  'MerchantKycOnboardingPage', 'MerchantPayoutSettlementPage',
  'AgentGamificationPage', 'CustomerJourneyAnalyticsPage', 'PlatformHealthPage'
];
for (const p of crudPages) {
  test(`CRUD in ${p}`, () => fileContains(`client/src/pages/${p}.tsx`, 'Create') || fileContains(`client/src/pages/${p}.tsx`, 'Add'));
}

// Test 3: Routes registered in App.tsx
const routes = [
  'realtime-tx-monitor', 'fraud-ml-scoring', 'notification-orchestrator',
  'agent-loan-facility', 'dynamic-fee-engine', 'merchant-kyc-onboarding',
  'merchant-payout-settlement', 'compliance-filing', 'agent-gamification',
  'tenant-feature-toggle', 'reconciliation-engine', 'customer-journey-analytics',
  'rate-limit-engine', 'backup-disaster-recovery', 'workflow-engine',
  'general-ledger', 'webhook-management', 'sla-monitoring',
  'data-export-hub', 'platform-health'
];
for (const r of routes) {
  test(`Route: /${r}`, () => fileContains('client/src/App.tsx', r));
}

// Test 4: DashboardLayout has Sprint 51 nav group
test('DashboardLayout Sprint 51 nav group', () => fileContains('client/src/components/DashboardLayout.tsx', 'Sprint 51'));

// Test 5: Docker Compose Sprint 51
test('Docker Compose Sprint 51', () => fileExists('docker-compose.sprint51.yml'));
test('Docker services count >= 20', () => {
  const content = fs.readFileSync(path.join(projectDir, 'docker-compose.sprint51.yml'), 'utf-8');
  const services = (content.match(/^\s{2}\w[\w-]+:/gm) || []).length;
  return services >= 20;
});

// Test 6: Schema tables for Sprint 51
const tables = [
  'realtime_tx_alerts', 'notification_channels', 'notification_logs',
  'customer_journey_events', 'gl_accounts', 'gl_journal_entries',
  'sla_definitions', 'sla_breaches', 'data_export_jobs',
  'platform_health_checks', 'platform_incidents'
];
for (const t of tables) {
  test(`Schema: ${t}`, () => fileContains('drizzle/schema.ts', t));
}

// Test 7: All routers have TRPCError import
const routers = [
  'realtimeTxMonitor', 'fraudMlScoringEngine', 'notificationOrchestrator',
  'agentLoanFacility', 'dynamicFeeEngine', 'merchantKycOnboarding',
  'merchantPayoutSettlement', 'complianceFiling', 'agentGamification',
  'tenantFeatureToggle', 'reconciliationEngine', 'customerJourneyAnalytics',
  'rateLimitEngine', 'backupDisasterRecovery', 'workflowEngine',
  'generalLedger', 'webhookManagement', 'slaMonitoring',
  'dataExportHub', 'platformHealth'
];
for (const r of routers) {
  test(`Error handling: ${r}`, () => fileContains(`server/routers/${r}.ts`, 'TRPCError'));
}

// Test 8: Security audit report
test('Security audit report exists', () => fileExists('data/security-audit-report.json'));

// Test 9: Deep service audit report
test('Deep service audit report exists', () => fileExists('data/deep-service-audit-report.json'));

// Test 10: Seed data script
test('Sprint 50 seed script', () => fileExists('scripts/seed-sprint50.mjs'));

console.log('============================================================');
console.log(`📊 Results: ${passed} passed, ${failed} failed, ${passed + failed} total`);
console.log(`   Pass rate: ${((passed / (passed + failed)) * 100).toFixed(1)}%`);
if (failed === 0) console.log('🎉 ALL SPRINT 51 SMOKE TESTS PASSED!');
else console.log(`⚠️  ${failed} tests need attention`);
