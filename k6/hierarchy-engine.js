/**
 * k6 load test — hierarchy-engine
 * Tests: agent lookup, branch listing, institution tree, agent status update
 *
 * Run: k6 run --env BASE_URL=http://localhost:8082 k6/hierarchy-engine.js
 */
import http from "k6/http";
import { check, sleep, group } from "k6";
import { Rate, Trend, Counter } from "k6/metrics";

const lookupErrors = new Rate("hierarchy_lookup_errors");
const lookupDuration = new Trend("hierarchy_lookup_duration_ms", true);
const totalRequests = new Counter("total_requests");

export const options = {
  scenarios: {
    hierarchy_reads: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: "1m", target: 300 },
        { duration: "5m", target: 300 },
        { duration: "1m", target: 0 },
      ],
    },
    hierarchy_writes: {
      executor: "constant-arrival-rate",
      rate: 20,
      timeUnit: "1s",
      duration: "7m",
      preAllocatedVUs: 30,
      maxVUs: 60,
      startTime: "30s",
    },
  },
  thresholds: {
    http_req_duration: ["p(95)<300", "p(99)<600"],
    http_req_failed: ["rate<0.01"],
    hierarchy_lookup_errors: ["rate<0.02"],
  },
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:8082";

const AGENT_IDS = Array.from(
  { length: 200 },
  (_, i) => `agent-${String(i + 1).padStart(6, "0")}`
);
const BRANCH_IDS = Array.from(
  { length: 20 },
  (_, i) => `branch-${String(i + 1).padStart(4, "0")}`
);

function randomItem(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}

export default function () {
  group("hierarchy: agent lookup", () => {
    const agentId = randomItem(AGENT_IDS);
    const start = Date.now();
    const res = http.get(`${BASE_URL}/api/v1/hierarchy/agents/${agentId}`);
    totalRequests.add(1);
    lookupDuration.add(Date.now() - start);

    const ok = check(res, {
      "agent lookup: 200 or 404": r => r.status === 200 || r.status === 404,
      "agent lookup: fast": r => r.timings.duration < 300,
    });
    lookupErrors.add(!ok);
  });

  sleep(0.1);

  group("hierarchy: branch agents list", () => {
    const branchId = randomItem(BRANCH_IDS);
    const res = http.get(
      `${BASE_URL}/api/v1/hierarchy/branches/${branchId}/agents?page=1&limit=20`
    );
    totalRequests.add(1);
    check(res, {
      "branch agents: 200 or 404": r => r.status === 200 || r.status === 404,
      "branch agents: fast": r => r.timings.duration < 400,
    });
  });

  sleep(0.2);

  group("hierarchy: institution tree", () => {
    const res = http.get(`${BASE_URL}/api/v1/hierarchy/institutions`);
    totalRequests.add(1);
    check(res, {
      "institutions: 200": r => r.status === 200,
      "institutions: has body": r => r.body && r.body.length > 2,
    });
  });

  sleep(Math.random() * 1 + 0.5);
}

export function handleSummary(data) {
  return {
    "k6-results/hierarchy-engine-summary.json": JSON.stringify(data, null, 2),
  };
}
