/**
 * k6 load test — rbac-service
 * Tests: permission checks at high concurrency (critical path for every API call)
 *
 * Run: k6 run --env BASE_URL=http://localhost:8087 k6/rbac-service.js
 */
import http from "k6/http";
import { check, sleep } from "k6";
import { Rate, Trend, Counter } from "k6/metrics";

const checkErrors = new Rate("rbac_check_errors");
const checkDuration = new Trend("rbac_check_duration_ms", true);
const totalRequests = new Counter("total_requests");

export const options = {
  scenarios: {
    // RBAC is called on every API request — must handle 1000 rps
    high_concurrency: {
      executor: "constant-arrival-rate",
      rate: 1000,
      timeUnit: "1s",
      duration: "5m",
      preAllocatedVUs: 200,
      maxVUs: 500,
    },
  },
  thresholds: {
    http_req_duration: ["p(95)<50", "p(99)<100"], // RBAC must be very fast
    http_req_failed: ["rate<0.001"],
    rbac_check_errors: ["rate<0.001"],
  },
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:8087";

const ROLES = [
  "super_admin",
  "bank_admin",
  "branch_manager",
  "agent",
  "auditor",
  "compliance",
  "customer",
];
const PERMISSIONS = [
  "transactions:create",
  "transactions:read",
  "agents:read",
  "agents:write",
  "reports:read",
  "kyc:approve",
  "float:approve",
  "cbn:submit",
  "profile:read:own",
  "profile:write:own",
];

function randomItem(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}

export default function () {
  const start = Date.now();
  const res = http.post(
    `${BASE_URL}/api/v1/rbac/check`,
    JSON.stringify({
      role: randomItem(ROLES),
      permission: randomItem(PERMISSIONS),
    }),
    { headers: { "Content-Type": "application/json" } }
  );
  totalRequests.add(1);
  checkDuration.add(Date.now() - start);

  const ok = check(res, {
    "rbac check: status 200": r => r.status === 200,
    "rbac check: has allowed field": r => {
      try {
        const body = JSON.parse(r.body);
        return typeof body.allowed === "boolean";
      } catch (_) {
        return false;
      }
    },
    "rbac check: p95 < 50ms": r => r.timings.duration < 50,
  });
  checkErrors.add(!ok);
}

export function handleSummary(data) {
  return {
    "k6-results/rbac-service-summary.json": JSON.stringify(data, null, 2),
  };
}
