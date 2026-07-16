/**
 * k6 Load Test: Dispute Creation Flow
 * ─────────────────────────────────────────────────────────────────────────────
 * Simulates agents raising disputes and admins resolving them under load.
 *
 * Targets:
 *  - p95 latency < 600 ms
 *  - Error rate < 1%
 *
 * Run:
 *   k6 run tests/load/dispute-creation.js \
 *     -e BASE_URL=http://localhost:3000 \
 *     -e AGENT_CODE=AGT001 \
 *     -e AGENT_PIN=1234
 */

import http from "k6/http";
import { check, sleep } from "k6";
import { Rate, Trend } from "k6/metrics";

const errorRate      = new Rate("dispute_errors");
const disputeLatency = new Trend("dispute_latency_ms", true);

export const options = {
  scenarios: {
    spike_test: {
      executor: "ramping-arrival-rate",
      startRate: 10,
      timeUnit: "1s",
      preAllocatedVUs: 50,
      maxVUs: 200,
      stages: [
        { duration: "30s", target: 10  },
        { duration: "1m",  target: 50  },
        { duration: "30s", target: 100 },
        { duration: "30s", target: 0   },
      ],
    },
  },
  thresholds: {
    http_req_duration:  ["p(95)<600"],
    dispute_errors:     ["rate<0.01"],
    dispute_latency_ms: ["p(95)<600"],
  },
};

const BASE_URL   = __ENV.BASE_URL   || "http://localhost:3000";
const AGENT_CODE = __ENV.AGENT_CODE || "AGT001";
const AGENT_PIN  = __ENV.AGENT_PIN  || "1234";

const DISPUTE_REASONS = [
  "Transaction not received by customer",
  "Duplicate charge",
  "Wrong amount debited",
  "Network timeout — customer charged but no confirmation",
  "Customer claims reversal not processed",
];

function trpcMutation(procedure, input) {
  const url     = `${BASE_URL}/api/trpc/${procedure}`;
  const payload = JSON.stringify({ json: input });
  const params  = {
    headers: { "Content-Type": "application/json" },
    tags: { name: procedure },
  };
  return http.post(url, payload, params);
}

export default function () {
  const reason = DISPUTE_REASONS[Math.floor(Math.random() * DISPUTE_REASONS.length)];
  const txRef  = `TXN${Date.now()}${Math.random().toString(36).slice(2, 6).toUpperCase()}`;

  const start = Date.now();

  const res = trpcMutation("disputes.raise", {
    agentCode:   AGENT_CODE,
    pin:         AGENT_PIN,
    txRef,
    reason,
    amount:      Math.floor(Math.random() * 50_000) + 500,
    description: `k6 load test dispute — ${reason}`,
  });

  disputeLatency.add(Date.now() - start);

  const ok = check(res, {
    "dispute status 200": (r) => r.status === 200,
    "dispute has id": (r) => {
      try {
        const body = JSON.parse(r.body);
        return typeof body.result?.data?.json?.id === "number";
      } catch {
        return false;
      }
    },
  });

  errorRate.add(!ok);

  sleep(0.2);
}
