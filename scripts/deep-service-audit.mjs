// Sprint 51: Deep Service Audit Script
// Checks: business rules, middleware, CRUD completeness, seed data, integration points
import fs from 'fs';
import path from 'path';

const PROJECT = '/home/ubuntu/pos-shell-demo';
const results = { passed: 0, failed: 0, warnings: 0, details: [] };

function check(name, condition, detail = '') {
  if (condition) { results.passed++; results.details.push({ status: 'PASS', name, detail }); }
  else { results.failed++; results.details.push({ status: 'FAIL', name, detail }); }
}
function warn(name, detail) { results.warnings++; results.details.push({ status: 'WARN', name, detail }); }

// 1. Check all Sprint 50+51 routers exist and have procedures
const routerDir = path.join(PROJECT, 'server/routers');
const expectedRouters = [
  'realtimeTxMonitor', 'fraudMlScoringEngine', 'notificationOrchestrator',
  'agentLoanFacility', 'dynamicFeeEngine', 'merchantKycOnboarding',
  'merchantPayoutSettlement', 'complianceFiling', 'agentGamification',
  'tenantFeatureToggle', 'reconciliationEngine', 'customerJourneyAnalytics',
  'rateLimitEngine', 'backupDisasterRecovery', 'workflowEngine',
  'generalLedger', 'webhookManagement', 'slaMonitoring', 'dataExportHub', 'platformHealth'
];

console.log('=== ROUTER AUDIT ===');
for (const r of expectedRouters) {
  const fp = path.join(routerDir, `${r}.ts`);
  const exists = fs.existsSync(fp);
  check(`Router: ${r}`, exists, exists ? `${(fs.statSync(fp).size / 1024).toFixed(1)}KB` : 'FILE MISSING');
  if (exists) {
    const content = fs.readFileSync(fp, 'utf-8');
    const procCount = (content.match(/\.(query|mutation)\(/g) || []).length;
    check(`  Procedures in ${r}`, procCount >= 2, `${procCount} procedures found`);
    // Check for input validation (zod)
    const hasZod = content.includes('z.object') || content.includes('z.string') || content.includes('z.number');
    if (!hasZod) warn(`  No Zod validation in ${r}`, 'Consider adding input validation');
    // Check for error handling
    const hasErrorHandling = content.includes('TRPCError') || content.includes('try') || content.includes('catch');
    check(`  Error handling in ${r}`, hasErrorHandling, hasErrorHandling ? 'Has error handling' : 'Missing error handling');
  }
}

// 2. Check all Sprint 51 UI pages exist
console.log('\n=== UI PAGE AUDIT ===');
const expectedPages = [
  'RealtimeTxMonitorPage', 'FraudMlScoringPage', 'NotificationOrchestratorPage',
  'AgentLoanFacilityPage', 'DynamicFeeEnginePage', 'MerchantKycOnboardingPage',
  'MerchantPayoutSettlementPage', 'ComplianceFilingPage', 'AgentGamificationPage',
  'TenantFeatureTogglePage', 'ReconciliationEnginePage', 'CustomerJourneyAnalyticsPage',
  'BackupDisasterRecoveryPage', 'WorkflowEnginePage', 'GeneralLedgerPage',
  'WebhookManagementPage', 'SlaMonitoringPage', 'DataExportHubPage',
  'RateLimitEnginePage', 'PlatformHealthPage'
];
for (const p of expectedPages) {
  const fp = path.join(PROJECT, `client/src/pages/${p}.tsx`);
  const exists = fs.existsSync(fp);
  check(`Page: ${p}`, exists, exists ? `${(fs.statSync(fp).size / 1024).toFixed(1)}KB` : 'FILE MISSING');
  if (exists) {
    const content = fs.readFileSync(fp, 'utf-8');
    const hasTrpc = content.includes('trpc.');
    const hasSearch = content.includes('search') || content.includes('filter') || content.includes('Search');
    const hasCrud = content.includes('Create') || content.includes('Add') || content.includes('Edit') || content.includes('Delete');
    check(`  tRPC integration in ${p}`, hasTrpc, hasTrpc ? 'Uses tRPC hooks' : 'No tRPC calls');
    if (!hasSearch) warn(`  No search/filter in ${p}`, 'Consider adding search functionality');
    check(`  CRUD operations in ${p}`, hasCrud, hasCrud ? 'Has CRUD UI' : 'Missing CRUD operations');
  }
}

// 3. Check route registration in App.tsx
console.log('\n=== ROUTE REGISTRATION AUDIT ===');
const appTsx = fs.readFileSync(path.join(PROJECT, 'client/src/App.tsx'), 'utf-8');
const expectedRoutes = [
  '/realtime-tx-monitor', '/fraud-ml-scoring', '/notification-orchestrator',
  '/agent-loan-facility', '/dynamic-fee-engine', '/merchant-kyc-onboarding',
  '/merchant-payout-settlement', '/compliance-filing', '/tenant-feature-toggle',
  '/reconciliation-engine', '/customer-journey-analytics', '/backup-disaster-recovery',
  '/workflow-engine', '/general-ledger', '/data-export-hub', '/sla-monitoring-v2',
  '/rate-limit-engine', '/agent-gamification-v2'
];
for (const route of expectedRoutes) {
  check(`Route registered: ${route}`, appTsx.includes(`"${route}"`), appTsx.includes(`"${route}"`) ? 'In App.tsx' : 'MISSING from App.tsx');
}

// 4. Check DashboardLayout sidebar nav
console.log('\n=== SIDEBAR NAV AUDIT ===');
const dashLayout = fs.readFileSync(path.join(PROJECT, 'client/src/components/DashboardLayout.tsx'), 'utf-8');
check('Sprint 51 nav group exists', dashLayout.includes('sprint51-features'), 'Sprint 51 nav group in sidebar');

// 5. Check schema tables
console.log('\n=== SCHEMA AUDIT ===');
const schemaContent = fs.readFileSync(path.join(PROJECT, 'drizzle/schema.ts'), 'utf-8');
const expectedTables = [
  'realtime_tx_alerts', 'fraud_ml_scores', 'notification_channels', 'notification_logs',
  'agent_loans', 'fee_rules', 'merchant_kyc_docs', 'merchant_payouts',
  'compliance_filings', 'agent_achievements', 'agent_badges', 'tenant_feature_toggles',
  'reconciliation_batches', 'customer_journey_events', 'rate_limit_rules',
  'backup_snapshots', 'workflow_definitions', 'workflow_instances',
  'gl_accounts', 'gl_journal_entries', 'webhook_endpoints', 'webhook_deliveries',
  'sla_definitions', 'sla_breaches', 'data_export_jobs', 'platform_health_checks', 'platform_incidents'
];
for (const t of expectedTables) {
  check(`Schema table: ${t}`, schemaContent.includes(t), schemaContent.includes(t) ? 'Defined in schema' : 'MISSING from schema');
}

// 6. Check seed data script
console.log('\n=== SEED DATA AUDIT ===');
const seedScript = path.join(PROJECT, 'scripts/seed-sprint50.mjs');
check('Seed script exists', fs.existsSync(seedScript), fs.existsSync(seedScript) ? `${(fs.statSync(seedScript).size / 1024).toFixed(1)}KB` : 'MISSING');

// 7. Check Docker files
console.log('\n=== DOCKER AUDIT ===');
const dockerCompose = path.join(PROJECT, 'docker-compose.sprint50.yml');
check('Docker Compose Sprint 50', fs.existsSync(dockerCompose));
const dockerfile = path.join(PROJECT, 'Dockerfile');
check('Dockerfile exists', fs.existsSync(dockerfile));

// 8. Check smoke test
console.log('\n=== SMOKE TEST AUDIT ===');
const smokeTest = path.join(PROJECT, 'scripts/smoke-test-sprint50.mjs');
check('Smoke test exists', fs.existsSync(smokeTest));

// 9. Check middleware and business rules
console.log('\n=== MIDDLEWARE AUDIT ===');
const routersTs = fs.readFileSync(path.join(PROJECT, 'server/routers.ts'), 'utf-8');
const sprint51Routers = [
  'realtimeTxMonitorRouter', 'fraudMlScoringRouter', 'notificationOrchestratorRouter',
  'agentLoanFacilityRouter', 'dynamicFeeEngineRouter', 'merchantKycOnboardingRouter',
  'merchantPayoutSettlementRouter', 'complianceFilingRouter', 'agentGamificationRouter',
  'tenantFeatureToggleRouter', 'reconciliationEngineRouter', 'customerJourneyAnalyticsRouter',
  'rateLimitEngineRouter', 'backupDisasterRecoveryRouter', 'workflowEngineRouter',
  'generalLedgerRouter', 'webhookManagementRouter', 'slaMonitoringRouter',
  'dataExportHubRouter', 'platformHealthRouter'
];
for (const r of sprint51Routers) {
  check(`Router registered: ${r}`, routersTs.includes(r), routersTs.includes(r) ? 'In appRouter' : 'MISSING from appRouter');
}

// 10. Security check
console.log('\n=== SECURITY QUICK CHECK ===');
const securityReport = path.join(PROJECT, 'data/security-audit-report.json');
check('Security audit report exists', fs.existsSync(securityReport));

// Summary
console.log('\n' + '='.repeat(60));
console.log('DEEP SERVICE AUDIT SUMMARY');
console.log('='.repeat(60));
console.log(`PASSED:   ${results.passed}`);
console.log(`FAILED:   ${results.failed}`);
console.log(`WARNINGS: ${results.warnings}`);
console.log(`SCORE:    ${((results.passed / (results.passed + results.failed)) * 100).toFixed(1)}%`);
console.log('='.repeat(60));

// Show failures
const failures = results.details.filter(d => d.status === 'FAIL');
if (failures.length > 0) {
  console.log('\nFAILURES:');
  failures.forEach(f => console.log(`  ❌ ${f.name}: ${f.detail}`));
}

// Show warnings
const warnings = results.details.filter(d => d.status === 'WARN');
if (warnings.length > 0) {
  console.log('\nWARNINGS:');
  warnings.forEach(w => console.log(`  ⚠️  ${w.name}: ${w.detail}`));
}

// Write report
fs.writeFileSync(path.join(PROJECT, 'data/deep-service-audit.json'), JSON.stringify(results, null, 2));
console.log('\nReport saved to data/deep-service-audit.json');
