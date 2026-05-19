/**
 * 54Link POS Shell — k6 Load Testing Suite
 * 
 * Covers all critical billing endpoints with realistic traffic patterns.
 * Simulates agency banking peak hours (8am-6pm WAT) with burst scenarios.
 * 
 * Run: k6 run tests/load/k6-billing-load-test.js
 * Run with cloud: k6 cloud tests/load/k6-billing-load-test.js
 */

import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';

// ─── Custom Metrics ──────────────────────────────────────────────────────────
const errorRate = new Rate('billing_errors');
const ledgerPostLatency = new Trend('ledger_post_latency', true);
const invoiceCreateLatency = new Trend('invoice_create_latency', true);
const reconciliationLatency = new Trend('reconciliation_latency', true);
const dashboardLatency = new Trend('dashboard_load_latency', true);
const transactionsProcessed = new Counter('transactions_processed');

// ─── Configuration ───────────────────────────────────────────────────────────
const BASE_URL = __ENV.BASE_URL || 'http://localhost:3000';
const AUTH_TOKEN = __ENV.AUTH_TOKEN || 'test-bearer-token';

const HEADERS = {
  'Content-Type': 'application/json',
  'Authorization': `Bearer ${AUTH_TOKEN}`,
};

// ─── Test Scenarios ──────────────────────────────────────────────────────────
export const options = {
  scenarios: {
    // Scenario 1: Normal business hours traffic
    normal_traffic: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '2m', target: 50 },   // Ramp up to 50 users
        { duration: '5m', target: 50 },   // Stay at 50 for 5 min
        { duration: '2m', target: 100 },  // Ramp to 100
        { duration: '5m', target: 100 },  // Stay at 100 for 5 min
        { duration: '2m', target: 0 },    // Ramp down
      ],
      gracefulRampDown: '30s',
    },

    // Scenario 2: Spike test (month-end invoice generation)
    month_end_spike: {
      executor: 'ramping-arrival-rate',
      startRate: 10,
      timeUnit: '1s',
      preAllocatedVUs: 200,
      maxVUs: 500,
      stages: [
        { duration: '1m', target: 10 },   // Normal rate
        { duration: '30s', target: 200 }, // Spike to 200 req/s
        { duration: '2m', target: 200 },  // Sustain spike
        { duration: '30s', target: 10 },  // Return to normal
        { duration: '1m', target: 10 },   // Cool down
      ],
      startTime: '16m', // Start after normal traffic
    },

    // Scenario 3: Soak test (sustained load)
    soak_test: {
      executor: 'constant-vus',
      vus: 30,
      duration: '30m',
      startTime: '22m', // Start after spike test
    },
  },

  thresholds: {
    http_req_duration: ['p(95)<500', 'p(99)<1000'],
    http_req_failed: ['rate<0.01'],
    billing_errors: ['rate<0.05'],
    ledger_post_latency: ['p(95)<200'],
    invoice_create_latency: ['p(95)<1000'],
    reconciliation_latency: ['p(95)<3000'],
    dashboard_load_latency: ['p(95)<500'],
  },
};

// ─── Helper Functions ────────────────────────────────────────────────────────
function trpcCall(procedure, input) {
  const payload = input !== undefined
    ? JSON.stringify({ json: input })
    : JSON.stringify({});
  
  return http.post(
    `${BASE_URL}/api/trpc/${procedure}`,
    payload,
    { headers: HEADERS, tags: { name: procedure } }
  );
}

function randomTenantId() {
  const tenants = ['TENANT_001', 'TENANT_002', 'TENANT_003', 'TENANT_004', 'TENANT_005'];
  return tenants[Math.floor(Math.random() * tenants.length)];
}

function randomAmount() {
  return Math.floor(Math.random() * 100000) / 100;
}

function randomCurrency() {
  const currencies = ['NGN', 'USD', 'GHS', 'KES', 'ZAR'];
  return currencies[Math.floor(Math.random() * currencies.length)];
}

// ─── Test Scenarios ──────────────────────────────────────────────────────────
export default function () {
  const scenario = Math.random();

  if (scenario < 0.30) {
    testLedgerOperations();
  } else if (scenario < 0.50) {
    testInvoiceOperations();
  } else if (scenario < 0.65) {
    testDashboardLoads();
  } else if (scenario < 0.75) {
    testReconciliation();
  } else if (scenario < 0.85) {
    testAuditTrail();
  } else if (scenario < 0.92) {
    testTenantOperations();
  } else {
    testRBACChecks();
  }

  sleep(Math.random() * 2 + 0.5); // 0.5-2.5s think time
}

// ─── Ledger Operations (30% of traffic) ──────────────────────────────────────
function testLedgerOperations() {
  group('Ledger Operations', () => {
    // GET ledger entries
    const getRes = trpcCall('billingLedger.getEntries', {
      tenantId: randomTenantId(),
      page: 1,
      limit: 20,
    });
    
    check(getRes, {
      'ledger entries loaded': (r) => r.status === 200,
    });
    dashboardLatency.add(getRes.timings.duration);

    // POST new ledger entry
    const postRes = trpcCall('billingLedger.postEntry', {
      tenantId: randomTenantId(),
      debitAccount: 'REVENUE_001',
      creditAccount: 'RECEIVABLES_001',
      amount: randomAmount(),
      currency: randomCurrency(),
      description: `Load test entry ${Date.now()}`,
    });

    const postSuccess = check(postRes, {
      'ledger entry posted': (r) => r.status === 200,
    });

    errorRate.add(!postSuccess);
    ledgerPostLatency.add(postRes.timings.duration);
    if (postSuccess) transactionsProcessed.add(1);
  });
}

// ─── Invoice Operations (20% of traffic) ─────────────────────────────────────
function testInvoiceOperations() {
  group('Invoice Operations', () => {
    // List invoices
    const listRes = trpcCall('billingInvoice.listInvoices', {
      tenantId: randomTenantId(),
      page: 1,
      limit: 10,
    });

    check(listRes, {
      'invoices listed': (r) => r.status === 200,
    });

    // Create invoice
    const createRes = trpcCall('billingInvoice.createInvoice', {
      tenantId: randomTenantId(),
      lineItems: [
        { description: 'Transaction fees', amount: randomAmount(), quantity: 1 },
        { description: 'Platform fee', amount: randomAmount(), quantity: 1 },
      ],
      currency: 'NGN',
    });

    const createSuccess = check(createRes, {
      'invoice created': (r) => r.status === 200,
    });

    errorRate.add(!createSuccess);
    invoiceCreateLatency.add(createRes.timings.duration);
  });
}

// ─── Dashboard Loads (15% of traffic) ────────────────────────────────────────
function testDashboardLoads() {
  group('Dashboard Loads', () => {
    // Live billing metrics
    const metricsRes = trpcCall('liveBillingDashboard.getMetrics', undefined);
    check(metricsRes, {
      'metrics loaded': (r) => r.status === 200,
    });
    dashboardLatency.add(metricsRes.timings.duration);

    // Billing analytics
    const analyticsRes = trpcCall('billingAnalytics.getSummary', {
      tenantId: randomTenantId(),
    });
    check(analyticsRes, {
      'analytics loaded': (r) => r.status === 200,
    });
    dashboardLatency.add(analyticsRes.timings.duration);
  });
}

// ─── Reconciliation (10% of traffic) ─────────────────────────────────────────
function testReconciliation() {
  group('Reconciliation', () => {
    const res = trpcCall('revenueReconciliation.runReconciliation', {
      tenantId: randomTenantId(),
      startDate: '2025-01-01',
      endDate: '2025-01-31',
    });

    const success = check(res, {
      'reconciliation completed': (r) => r.status === 200,
    });

    errorRate.add(!success);
    reconciliationLatency.add(res.timings.duration);
  });
}

// ─── Audit Trail (10% of traffic) ────────────────────────────────────────────
function testAuditTrail() {
  group('Audit Trail', () => {
    const res = trpcCall('billingAudit.getAuditLog', {
      page: 1,
      limit: 50,
    });

    check(res, {
      'audit log loaded': (r) => r.status === 200,
    });
  });
}

// ─── Tenant Operations (7% of traffic) ───────────────────────────────────────
function testTenantOperations() {
  group('Tenant Operations', () => {
    // Get tenant billing config
    const configRes = trpcCall('billingLedger.getClientBillingConfig', {
      tenantId: randomTenantId(),
      clientId: 'XMTS',
    });

    check(configRes, {
      'tenant config loaded': (r) => r.status === 200,
    });
  });
}

// ─── RBAC Checks (8% of traffic) ─────────────────────────────────────────────
function testRBACChecks() {
  group('RBAC Permission Checks', () => {
    const permissions = [
      'billing:view', 'billing:create_invoice', 'billing:approve_refund',
      'billing:manage_rates', 'billing:run_reconciliation',
    ];
    const perm = permissions[Math.floor(Math.random() * permissions.length)];

    const res = trpcCall('billingRbac.checkPermission', {
      userId: Math.floor(Math.random() * 100) + 1,
      permission: perm,
    });

    check(res, {
      'permission check completed': (r) => r.status === 200,
    });
  });
}

// ─── Teardown ────────────────────────────────────────────────────────────────
export function handleSummary(data) {
  return {
    'tests/load/k6-results.json': JSON.stringify(data, null, 2),
    stdout: textSummary(data, { indent: ' ', enableColors: true }),
  };
}

function textSummary(data, opts) {
  const metrics = data.metrics;
  let output = '\n=== 54Link Billing Load Test Results ===\n\n';
  
  output += `Total Requests: ${metrics.http_reqs?.values?.count || 0}\n`;
  output += `Failed Requests: ${metrics.http_req_failed?.values?.rate?.toFixed(4) || 0}\n`;
  output += `Avg Response Time: ${metrics.http_req_duration?.values?.avg?.toFixed(2) || 0}ms\n`;
  output += `P95 Response Time: ${metrics.http_req_duration?.values?.['p(95)']?.toFixed(2) || 0}ms\n`;
  output += `P99 Response Time: ${metrics.http_req_duration?.values?.['p(99)']?.toFixed(2) || 0}ms\n`;
  output += `Billing Error Rate: ${metrics.billing_errors?.values?.rate?.toFixed(4) || 0}\n`;
  output += `Transactions Processed: ${metrics.transactions_processed?.values?.count || 0}\n`;
  
  return output;
}
