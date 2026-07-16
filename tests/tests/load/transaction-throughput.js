/**
 * k6 Load Test: Transaction Throughput
 * ─────────────────────────────────────────────────────────────────────────────
 * Simulates concurrent agents submitting Cash In / Cash Out transactions.
 *
 * Targets:
 *  - p95 latency < 500 ms
 *  - Error rate < 1%
 *  - Sustained 200 RPS for 2 minutes
 *
 * Run:
 *   k6 run tests/load/transaction-throughput.js \
 *     -e BASE_URL=http://localhost:3000 \
 *     -e AGENT_CODE=AGT001 \
 *     -e AGENT_PIN=1234
 */

import http from "k6/http";
import { check, sleep } from "k6";
import { Rate, Trend } from "k6/metrics";

// ── Custom metrics ────────────────────────────────────────────────────────────
const errorRate   = new Rate("transaction_errors");
const txLatency   = new Trend("transaction_latency_ms", true);

// ── Test configuration ────────────────────────────────────────────────────────
export const options = {
  scenarios: {
    ramp_up: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: "30s", target: 50  },  // Ramp to 50 VUs
        { duration: "2m",  target: 200 },  // Sustain 200 VUs
        { duration: "30s", target: 0   },  // Ramp down
      ],
    },
  },
  thresholds: {
    http_req_duration:    ["p(95)<500"],   // 95th percentile < 500 ms
    transaction_errors:   ["rate<0.01"],   // Error rate < 1%
    transaction_latency_ms: ["p(95)<500"],
  },
};

const BASE_URL   = __ENV.BASE_URL   || "http://localhost:3000";
const AGENT_CODE = __ENV.AGENT_CODE || "AGT001";
const AGENT_PIN  = __ENV.AGENT_PIN  || "1234";

const TX_TYPES = ["Cash In", "Cash Out", "Transfer", "Airtime"];

function randomAmount() {
  return Math.floor(Math.random() * 49_000) + 1_000; // ₦1,000 – ₦50,000
}

function randomRef() {
  return `TXN${Date.now()}${Math.random().toString(36).slice(2, 8).toUpperCase()}`;
}

// ── tRPC batch helper ─────────────────────────────────────────────────────────
function trpcMutation(procedure, input) {
  const url = `${BASE_URL}/api/trpc/${procedure}`;
  const payload = JSON.stringify({ json: input });
  const params = {
    headers: { "Content-Type": "application/json" },
    tags: { name: procedure },
  };
  return http.post(url, payload, params);
}

// ── Main VU function ──────────────────────────────────────────────────────────
export default function () {
  const txType = TX_TYPES[Math.floor(Math.random() * TX_TYPES.length)];
  const amount = randomAmount();
  const ref    = randomRef();

  const start = Date.now();
  const res = trpcMutation("transactions.create", {
    agentCode:       AGENT_CODE,
    pin:             AGENT_PIN,
    type:            txType,
    amount,
    ref,
    customerName:    "Test Customer",
    customerPhone:   "08012345678",
    paymentMethod:   "Cash",
    narration:       `k6 load test — ${txType}`,
  });
  const elapsed = Date.now() - start;

  txLatency.add(elapsed);

  const ok = check(res, {
    "status 200":       (r) => r.status === 200,
    "has result":       (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.result?.data?.json?.ref !== undefined;
      } catch {
        return false;
      }
    },
  });

  errorRate.add(!ok);

  sleep(0.1); // 100 ms think time between requests
}
