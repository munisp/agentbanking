/**
 * k6 Smoke Test — 54Link POS Shell (Phase 164)
 * ─────────────────────────────────────────────────────────────────────────────
 * Comprehensive pre-flight check covering 40+ tRPC endpoints across all
 * feature routers. Verifies every critical endpoint is reachable and returning
 * expected HTTP status codes before running full load tests.
 *
 * Usage:
 *   k6 run tests/load/smoke-test.js -e BASE_URL=http://localhost:3000
 *
 * Expected output: all checks green, 0 failures.
 */
import http from "k6/http";
import { check, group, sleep } from "k6";

export const options = {
  vus: 1,
  iterations: 1,
  thresholds: {
    checks: ["rate==1.0"],
    http_req_failed: ["rate<0.8"],
  },
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:3000";

function trpcQuery(procedure, input = {}) {
  const qs = encodeURIComponent(JSON.stringify({ json: input }));
  return http.get(`${BASE_URL}/api/trpc/${procedure}?input=${qs}`, {
    headers: { "Content-Type": "application/json" },
    tags: { name: procedure },
  });
}

function trpcMutation(procedure, input = {}) {
  return http.post(
    `${BASE_URL}/api/trpc/${procedure}`,
    JSON.stringify({ json: input }),
    { headers: { "Content-Type": "application/json" }, tags: { name: procedure } }
  );
}

// Reachable = endpoint exists and responds (auth failures are expected)
function reachable(r) {
  return r.status === 200 || r.status === 400 || r.status === 401 || r.status === 403;
}

export default function () {

  // ── 1. Infrastructure ─────────────────────────────────────────────────────
  group("1. Infrastructure Health", () => {
    const health = http.get(`${BASE_URL}/api/health`);
    check(health, {
      "GET /api/health → 200": (r) => r.status === 200,
      "health body has status": (r) => r.body.includes("status") || r.body.includes("ok"),
    });
    const metrics = http.get(`${BASE_URL}/api/metrics`);
    check(metrics, { "GET /api/metrics reachable": (r) => r.status === 200 || r.status === 404 });
    const frontend = http.get(`${BASE_URL}/`);
    check(frontend, {
      "GET / → 200 HTML": (r) => r.status === 200,
      "frontend returns HTML": (r) => (r.headers["Content-Type"] || "").includes("text/html"),
    });
  });
  sleep(0.1);

  // ── 2. Auth ───────────────────────────────────────────────────────────────
  group("2. Auth Procedures", () => {
    const loginRes = trpcMutation("agent.login", { agentCode: "SMOKE_TEST", pin: "0000" });
    check(loginRes, { "agent.login reachable": reachable });
    const meRes = trpcQuery("auth.me");
    check(meRes, { "auth.me reachable": reachable });
  });
  sleep(0.1);

  // ── 3. Agent ──────────────────────────────────────────────────────────────
  group("3. Agent Procedures", () => {
    check(trpcQuery("agent.list", { page: 1, limit: 5 }), { "agent.list reachable": reachable });
    check(trpcQuery("agent.stats"), { "agent.stats reachable": reachable });
    check(trpcQuery("agent.cbnLimits", { id: 1 }), { "agent.cbnLimits reachable": reachable });
    check(trpcQuery("agent.get", { id: 1 }), { "agent.get reachable": reachable });
  });
  sleep(0.1);

  // ── 4. Transactions ───────────────────────────────────────────────────────
  group("4. Transaction Procedures", () => {
    check(trpcQuery("transactions.list", { limit: 5, offset: 0 }), { "transactions.list reachable": reachable });
    check(trpcQuery("transactions.summary"), { "transactions.summary reachable": reachable });
    check(trpcMutation("transactions.create", { type: "cash_in", amount: "1000", customerPhone: "08012345678" }),
      { "transactions.create reachable": reachable });
  });
  sleep(0.1);

  // ── 5. Float Top-Up ───────────────────────────────────────────────────────
  group("5. Float Top-Up Procedures", () => {
    check(trpcQuery("floatTopUp.history", { limit: 5 }), { "floatTopUp.history reachable": reachable });
    check(trpcQuery("floatTopUp.supervisorPendingTopUps"), { "floatTopUp.supervisorPendingTopUps reachable": reachable });
  });
  sleep(0.1);

  // ── 6. Fraud ──────────────────────────────────────────────────────────────
  group("6. Fraud Procedures", () => {
    check(trpcQuery("fraud.listAlerts", { limit: 5 }), { "fraud.listAlerts reachable": reachable });
    check(trpcQuery("fraud.stats"), { "fraud.stats reachable": reachable });
  });
  sleep(0.1);

  // ── 7. Loyalty ────────────────────────────────────────────────────────────
  group("7. Loyalty Procedures", () => {
    check(trpcQuery("loyalty.balance", { agentId: 1 }), { "loyalty.balance reachable": reachable });
    check(trpcQuery("loyalty.history", { agentId: 1, limit: 5 }), { "loyalty.history reachable": reachable });
    check(trpcQuery("loyalty.leaderboard", { limit: 5 }), { "loyalty.leaderboard reachable": reachable });
    check(trpcQuery("loyalty.rewardCatalog"), { "loyalty.rewardCatalog reachable": reachable });
  });
  sleep(0.1);

  // ── 8. KYC ───────────────────────────────────────────────────────────────
  group("8. KYC Procedures", () => {
    check(trpcQuery("kyc.listSessions", { limit: 5 }), { "kyc.listSessions reachable": reachable });
    check(trpcQuery("kyc.stats"), { "kyc.stats reachable": reachable });
  });
  sleep(0.1);

  // ── 9. Disputes ───────────────────────────────────────────────────────────
  group("9. Disputes Procedures", () => {
    check(trpcQuery("disputes.list", { limit: 5 }), { "disputes.list reachable": reachable });
    check(trpcQuery("disputes.stats"), { "disputes.stats reachable": reachable });
  });
  sleep(0.1);

  // ── 10. Settlement ────────────────────────────────────────────────────────
  group("10. Settlement Procedures", () => {
    check(trpcQuery("settlement.history", { limit: 5 }), { "settlement.history reachable": reachable });
    check(trpcQuery("settlement.pendingSettlements"), { "settlement.pendingSettlements reachable": reachable });
  });
  sleep(0.1);

  // ── 11. Analytics ─────────────────────────────────────────────────────────
  group("11. Analytics Procedures", () => {
    check(trpcQuery("analytics.overview", { days: 7 }), { "analytics.overview reachable": reachable });
    check(trpcQuery("analytics.transactionBreakdown", { days: 7 }), { "analytics.transactionBreakdown reachable": reachable });
    check(trpcQuery("analytics.agentLeaderboard", { days: 7, limit: 5 }), { "analytics.agentLeaderboard reachable": reachable });
    check(trpcQuery("analytics.cbnMetrics", { days: 30 }), { "analytics.cbnMetrics reachable": reachable });
  });
  sleep(0.1);

  // ── 12. Audit Log ─────────────────────────────────────────────────────────
  group("12. Audit Log Procedures", () => {
    check(trpcQuery("auditLog.list", { limit: 5 }), { "auditLog.list reachable": reachable });
  });
  sleep(0.1);

  // ── 13. Chat ──────────────────────────────────────────────────────────────
  group("13. Chat Procedures", () => {
    check(trpcQuery("chat.mySessions"), { "chat.mySessions reachable": reachable });
  });
  sleep(0.1);

  // ── 14. Supervisor ────────────────────────────────────────────────────────
  group("14. Supervisor Procedures", () => {
    check(trpcQuery("supervisor.myProfile", {}), { "supervisor.myProfile reachable": reachable });
    check(trpcQuery("supervisor.myAgents", {}), { "supervisor.myAgents reachable": reachable });
    check(trpcQuery("supervisor.myAlerts", {}), { "supervisor.myAlerts reachable": reachable });
  });
  sleep(0.1);

  // ── 15. Developer Portal ──────────────────────────────────────────────────
  group("15. Developer Portal Procedures", () => {
    check(trpcQuery("devPortal.listKeys"), { "devPortal.listKeys reachable": reachable });
    check(trpcQuery("devPortal.getScopes"), { "devPortal.getScopes reachable": reachable });
  });
  sleep(0.1);

  // ── 16. CBN Reporting ─────────────────────────────────────────────────────
  group("16. CBN Reporting Procedures", () => {
    check(trpcQuery("cbnReporting.monthlyActivityReport", { year: 2025, month: 12 }),
      { "cbnReporting.monthlyActivityReport reachable": reachable });
    check(trpcQuery("cbnReporting.quarterlyFraudReport", { year: 2025, quarter: 4 }),
      { "cbnReporting.quarterlyFraudReport reachable": reachable });
    check(trpcQuery("cbnReporting.reportStatus"), { "cbnReporting.reportStatus reachable": reachable });
  });
  sleep(0.1);

  // ── 17. Management ────────────────────────────────────────────────────────
  group("17. Management Procedures", () => {
    check(trpcQuery("management.dashboard"), { "management.dashboard reachable": reachable });
  });
  sleep(0.1);

  // ── 18. System Config ─────────────────────────────────────────────────────
  group("18. System Config Procedures", () => {
    check(trpcQuery("systemConfig.list"), { "systemConfig.list reachable": reachable });
  });
  sleep(0.1);

  // ── 19. Merchant ──────────────────────────────────────────────────────────
  group("19. Merchant Procedures", () => {
    check(trpcQuery("merchant.profile"), { "merchant.profile reachable": reachable });
  });
  sleep(0.1);

  // ── 20. Customer ──────────────────────────────────────────────────────────
  group("20. Customer Procedures", () => {
    check(trpcQuery("customer.search", { query: "test", limit: 5 }), { "customer.search reachable": reachable });
  });
  sleep(0.1);

  // ── 21. Export ────────────────────────────────────────────────────────────
  group("21. Export Procedures", () => {
    check(trpcMutation("export.exportTransactionsCsv", {
      fromMs: Date.now() - 7 * 24 * 60 * 60 * 1000,
      toMs: Date.now(),
    }), { "export.exportTransactionsCsv reachable": reachable });
  });
  sleep(0.1);

  // ── 22. Geofencing ────────────────────────────────────────────────────────
  group("22. Geofencing Procedures", () => {
    check(trpcQuery("geofencing.listZones"), { "geofencing.listZones reachable": reachable });
  });
  sleep(0.1);

  // ── 23. MDM ───────────────────────────────────────────────────────────────
  group("23. MDM Procedures", () => {
    check(trpcQuery("mdm.listDevices", { limit: 5 }), { "mdm.listDevices reachable": reachable });
  });
  sleep(0.1);

  // ── 24. PIN Reset ─────────────────────────────────────────────────────────
  group("24. PIN Reset Procedures", () => {
    check(trpcMutation("pinReset.requestReset", { agentCode: "SMOKE_TEST", phone: "08012345678" }),
      { "pinReset.requestReset reachable": reachable });
  });
  sleep(0.1);

  // ── 25. v1 tRPC alias ────────────────────────────────────────────────────
  group("25. v1 tRPC Alias", () => {
    const v1Res = http.post(
      `${BASE_URL}/api/v1/trpc/agent.login`,
      JSON.stringify({ json: { agentCode: "SMOKE_TEST", pin: "0000" } }),
      { headers: { "Content-Type": "application/json" } }
    );
    check(v1Res, { "v1 alias reachable": reachable });
  });
}

// ── Lakehouse / Sedona / DataFusion ───────────────────────────────────────────
group("Lakehouse: listSnapshots", () => {
  const r = http.post(`${BASE}/api/trpc/lakehouse.listSnapshots`, JSON.stringify({
    json: { bucket: "transactions", datePrefix: "2026-04" },
  }), HEADERS);
  check(r, { "lakehouse.listSnapshots 200": (res) => res.status === 200 });
  sleep(0.3);
});

group("Lakehouse: goldLayerSummary", () => {
  const r = http.post(`${BASE}/api/trpc/lakehouse.goldLayerSummary`, JSON.stringify({
    json: { date: "2026-04-14" },
  }), HEADERS);
  check(r, { "lakehouse.goldLayerSummary 200": (res) => res.status === 200 });
  sleep(0.3);
});

group("Lakehouse: transactionHeatmap", () => {
  const r = http.post(`${BASE}/api/trpc/lakehouse.transactionHeatmap`, JSON.stringify({
    json: { days: 7, cellDeg: 0.1 },
  }), HEADERS);
  check(r, { "lakehouse.transactionHeatmap 200": (res) => res.status === 200 });
  sleep(0.3);
});

group("Lakehouse: agentDensityGrid", () => {
  const r = http.post(`${BASE}/api/trpc/lakehouse.agentDensityGrid`, JSON.stringify({
    json: { cellDeg: 0.5 },
  }), HEADERS);
  check(r, { "lakehouse.agentDensityGrid 200": (res) => res.status === 200 });
  sleep(0.3);
});

group("Lakehouse: nearbyAgents", () => {
  const r = http.post(`${BASE}/api/trpc/lakehouse.nearbyAgents`, JSON.stringify({
    json: { lat: 6.5244, lon: 3.3792, radiusKm: 5, limit: 10 },
  }), HEADERS);
  check(r, { "lakehouse.nearbyAgents 200": (res) => res.status === 200 });
  sleep(0.3);
});

group("Lakehouse: lakehouseQuery (DataFusion)", () => {
  const r = http.post(`${BASE}/api/trpc/lakehouse.lakehouseQuery`, JSON.stringify({
    json: { sql: "SELECT agent_code, count(*) FROM 54link.silver.transactions GROUP BY agent_code LIMIT 10", limit: 10 },
  }), HEADERS);
  check(r, { "lakehouse.lakehouseQuery 200": (res) => res.status === 200 });
  sleep(0.3);
});

group("CBN: dailySummary", () => {
  const r = http.post(`${BASE}/api/trpc/cbnReporting.dailySummary`, JSON.stringify({
    json: { date: "2026-04-14" },
  }), HEADERS);
  check(r, { "cbnReporting.dailySummary 200": (res) => res.status === 200 });
  sleep(0.3);
});

group("CBN: complianceMetrics", () => {
  const r = http.post(`${BASE}/api/trpc/cbnReporting.complianceMetrics`, JSON.stringify({
    json: {},
  }), HEADERS);
  check(r, { "cbnReporting.complianceMetrics 200": (res) => res.status === 200 });
  sleep(0.3);
});

group("BusinessRules: checkTransactionLimits", () => {
  const r = http.post(`${BASE}/api/trpc/businessRules.checkTransactionLimits`, JSON.stringify({
    json: { agentId: 1, amount: 5000, txType: "cash_in" },
  }), HEADERS);
  check(r, { "businessRules.checkTransactionLimits 200": (res) => res.status === 200 });
  sleep(0.3);
});

group("BusinessRules: calculateCommission", () => {
  const r = http.post(`${BASE}/api/trpc/businessRules.calculateCommission`, JSON.stringify({
    json: { agentId: 1, amount: 10000, txType: "cash_in" },
  }), HEADERS);
  check(r, { "businessRules.calculateCommission 200": (res) => res.status === 200 });
  sleep(0.3);
});
