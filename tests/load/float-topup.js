/**
 * k6 Load Test: Float Top-Up Flow
 * ─────────────────────────────────────────────────────────────────────────────
 * Simulates agents requesting float top-ups and supervisors approving them.
 *
 * Targets:
 *  - p95 latency < 800 ms
 *  - Error rate < 1%
 *
 * Run:
 *   k6 run tests/load/float-topup.js \
 *     -e BASE_URL=http://localhost:3000 \
 *     -e AGENT_CODE=AGT001 \
 *     -e AGENT_PIN=1234
 */

import http from "k6/http";
import { check, sleep } from "k6";
import { Rate, Trend } from "k6/metrics";

const errorRate  = new Rate("float_topup_errors");
const reqLatency = new Trend("float_topup_latency_ms", true);

export const options = {
  scenarios: {
    steady_load: {
      executor: "constant-vus",
      vus: 50,
      duration: "2m",
    },
  },
  thresholds: {
    http_req_duration:       ["p(95)<800"],
    float_topup_errors:      ["rate<0.01"],
    float_topup_latency_ms:  ["p(95)<800"],
  },
};

const BASE_URL   = __ENV.BASE_URL   || "http://localhost:3000";
const AGENT_CODE = __ENV.AGENT_CODE || "AGT001";
const AGENT_PIN  = __ENV.AGENT_PIN  || "1234";

function trpcMutation(procedure, input) {
  const url     = `${BASE_URL}/api/trpc/${procedure}`;
  const payload = JSON.stringify({ json: input });
  const params  = {
    headers: { "Content-Type": "application/json" },
    tags: { name: procedure },
  };
  return http.post(url, payload, params);
}

function trpcQuery(procedure, input) {
  const url    = `${BASE_URL}/api/trpc/${procedure}?input=${encodeURIComponent(JSON.stringify({ json: input }))}`;
  const params = { tags: { name: procedure } };
  return http.get(url, params);
}

export default function () {
  // Step 1: Request float top-up
  const amount = Math.floor(Math.random() * 90_000) + 10_000; // ₦10k – ₦100k
  const start  = Date.now();

  const topUpRes = trpcMutation("floatTopUp.request", {
    agentCode: AGENT_CODE,
    pin:       AGENT_PIN,
    amount,
    channel:   "bank_transfer",
    notes:     "k6 load test top-up",
  });

  reqLatency.add(Date.now() - start);

  const ok = check(topUpRes, {
    "topup status 200": (r) => r.status === 200,
    "topup has id": (r) => {
      try {
        const body = JSON.parse(r.body);
        return typeof body.result?.data?.json?.id === "number";
      } catch {
        return false;
      }
    },
  });

  errorRate.add(!ok);

  // Step 2: Check balance (read path)
  const balRes = trpcQuery("transactions.getFloatBalance", { agentCode: AGENT_CODE });
  check(balRes, {
    "balance status 200": (r) => r.status === 200,
  });

  sleep(0.5);
}
