/**
 * 54Link POS Shell — Stryker Mutation Testing Configuration
 * 
 * Mutation testing validates test suite quality by introducing small code changes
 * (mutants) and verifying that tests detect them. A high mutation score (>80%)
 * indicates robust test coverage.
 * 
 * Run: npx stryker run
 * Run specific files: npx stryker run --mutate "server/routers/billing*.ts"
 */

/** @type {import('@stryker-mutator/api/core').PartialStrykerOptions} */
const config = {
  packageManager: 'pnpm',
  
  // ─── Test Runner ─────────────────────────────────────────────────────────
  testRunner: 'vitest',
  vitest: {
    configFile: 'vitest.config.ts',
  },

  // ─── Mutation Targets ────────────────────────────────────────────────────
  // Focus on business-critical billing logic
  mutate: [
    'server/routers/billingLedger.ts',
    'server/routers/billingInvoice.ts',
    'server/routers/billingRbac.ts',
    'server/routers/billingAudit.ts',
    'server/routers/billingProduction.ts',
    'server/routers/revenueReconciliation.ts',
    'server/routers/tenantBillingOnboarding.ts',
    'server/routers/liveBillingDashboard.ts',
    'server/db.ts',
    'shared/const.ts',
    '!**/*.test.ts',
    '!**/*.spec.ts',
    '!**/node_modules/**',
    '!**/dist/**',
  ],

  // ─── Mutators ────────────────────────────────────────────────────────────
  // Enable all relevant mutator types for financial code
  mutator: {
    excludedMutations: [
      'StringLiteral',      // Skip string mutations (log messages, etc.)
      'ObjectLiteral',      // Skip object literal mutations
    ],
  },

  // ─── Thresholds ──────────────────────────────────────────────────────────
  // Financial code requires high mutation scores
  thresholds: {
    high: 90,    // Green: mutation score >= 90%
    low: 70,     // Red: mutation score < 70%
    break: 60,   // Fail CI if mutation score < 60%
  },

  // ─── Reporters ───────────────────────────────────────────────────────────
  reporters: [
    'html',           // Interactive HTML report
    'clear-text',     // Console output
    'progress',       // Progress bar
    'json',           // Machine-readable JSON
    'dashboard',      // Stryker dashboard integration
  ],

  htmlReporter: {
    fileName: 'reports/mutation/index.html',
  },

  jsonReporter: {
    fileName: 'reports/mutation/mutation-report.json',
  },

  // ─── Performance ─────────────────────────────────────────────────────────
  concurrency: 4,                    // Parallel test runners
  timeoutMS: 30000,                  // 30s timeout per mutant
  timeoutFactor: 2.5,               // Timeout multiplier for slow tests
  
  // ─── Incremental Mode ────────────────────────────────────────────────────
  // Only test mutants in changed files (for CI)
  incremental: true,
  incrementalFile: '.stryker-cache/incremental.json',

  // ─── Coverage Analysis ───────────────────────────────────────────────────
  coverageAnalysis: 'perTest',       // Map mutants to specific tests
  
  // ─── Ignore Patterns ─────────────────────────────────────────────────────
  // Skip mutations in non-critical code paths
  ignorers: [],
  
  // ─── Dashboard ───────────────────────────────────────────────────────────
  dashboard: {
    project: '54link/pos-shell-demo',
    version: 'main',
    module: 'billing-engine',
  },
};

export default config;
