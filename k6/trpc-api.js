/**
 * k6 load test — main tRPC API (Node.js server)
 * Tests: all major tRPC procedures under realistic mixed load
 *
 * Run: k6 run --env BASE_URL=http://localhost:3000 k6/trpc-api.js
 */
import http from "k6/http";
import { check, sleep, group } from "k6";
import { Rate, Trend, Counter } from "k6/metrics";

const apiErrors = new Rate("trpc_api_errors");
const apiDuration = new Trend("trpc_api_duration_ms", true);
const totalRequests = new Counter("total_requests");

export const options = {
  scenarios: {
    // Mixed realistic traffic
    mixed_load: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: "2m", target: 100 },
        { duration: "8m", target: 100 },
        { duration: "2m", target: 200 },
        { duration: "3m", target: 200 },
        { duration: "1m", target: 0 },
      ],
      gracefulRampDown: "30s",
    },
    // Spike test
    spike: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: "30s", target: 500 },
        { duration: "1m", target: 500 },
        { duration: "30s", target: 0 },
      ],
      startTime: "10m",
    },
  },
  thresholds: {
    http_req_duration: ["p(95)<800", "p(99)<2000"],
    http_req_failed: ["rate<0.02"],
    trpc_api_errors: ["rate<0.03"],
  },
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:3000";

// tRPC batch request helper
function trpcQuery(procedure, input = {}) {
  const url = `${BASE_URL}/api/trpc/${procedure}?batch=1&input=${encodeURIComponent(
    JSON.stringify({ 0: { json: input } })
  )}`;
  return http.get(url, {
    headers: { "Content-Type": "application/json" },
  });
}

function trpcMutation(procedure, input = {}) {
  return http.post(
    `${BASE_URL}/api/trpc/${procedure}?batch=1`,
    JSON.stringify({ 0: { json: input } }),
    { headers: { "Content-Type": "application/json" } }
  );
}

export default function () {
  // 40% — transaction queries (most common)
  if (Math.random() < 0.4) {
    group("trpc: transactions list", () => {
      const start = Date.now();
      const res = trpcQuery("transactions.list", { page: 1, limit: 20 });
      totalRequests.add(1);
      apiDuration.add(Date.now() - start);
      const ok = check(res, {
        "tx list: 200": r => r.status === 200,
        "tx list: fast": r => r.timings.duration < 800,
      });
      apiErrors.add(!ok);
    });
  }

  sleep(0.1);

  // 25% — agent management queries
  if (Math.random() < 0.25) {
    group("trpc: agent management", () => {
      const start = Date.now();
      const res = trpcQuery("agentManagement.listAgents", {
        page: 1,
        limit: 10,
      });
      totalRequests.add(1);
      apiDuration.add(Date.now() - start);
      const ok = check(res, {
        "agents: 200": r => r.status === 200,
        "agents: fast": r => r.timings.duration < 600,
      });
      apiErrors.add(!ok);
    });
  }

  sleep(0.1);

  // 20% — float management
  if (Math.random() < 0.2) {
    group("trpc: float balance", () => {
      const start = Date.now();
      const res = trpcQuery("float.getBalance", {});
      totalRequests.add(1);
      apiDuration.add(Date.now() - start);
      const ok = check(res, {
        "float: 200 or 401": r => r.status === 200 || r.status === 401,
        "float: fast": r => r.timings.duration < 400,
      });
      apiErrors.add(!ok);
    });
  }

  sleep(0.1);

  // 10% — fraud alerts
  if (Math.random() < 0.1) {
    group("trpc: fraud alerts", () => {
      const start = Date.now();
      const res = trpcQuery("fraud.getAlerts", { status: "open", limit: 10 });
      totalRequests.add(1);
      apiDuration.add(Date.now() - start);
      const ok = check(res, {
        "fraud: 200 or 401": r => r.status === 200 || r.status === 401,
        "fraud: fast": r => r.timings.duration < 500,
      });
      apiErrors.add(!ok);
    });
  }

  sleep(0.1);

  // 5% — health check
  if (Math.random() < 0.05) {
    group("trpc: health", () => {
      const res = http.get(`${BASE_URL}/api/health`);
      totalRequests.add(1);
      check(res, {
        "health: 200": r => r.status === 200,
        "health: very fast": r => r.timings.duration < 100,
      });
    });
  }

  sleep(Math.random() * 1 + 0.5);
}

export function handleSummary(data) {
  return {
    "k6-results/trpc-api-summary.json": JSON.stringify(data, null, 2),
  };
}
