/**
 * k6 Load Test: Transaction Throughput
 * ─────────────────────────────────────────────────────────────────────────────
 * Tests the core transaction path (cash-in / cash-out / transfer) under load.
 *
 * Usage:
 *   k6 run k6/transaction-throughput.js
 *   k6 run --vus 50 --duration 2m k6/transaction-throughput.js
 *   BASE_URL=https://your-app.manus.space k6 run k6/transaction-throughput.js
 *
 * Environment variables:
 *   BASE_URL      Target base URL (default: http://localhost:3000)
 *   AGENT_TOKEN   Pre-authenticated agent JWT cookie value
 */
import http from "k6/http";
import { check, sleep } from "k6";
import { Counter, Rate, Trend } from "k6/metrics";

// ── Custom metrics ────────────────────────────────────────────────────────────
const txSuccessRate = new Rate("tx_success_rate");
const txDuration = new Trend("tx_duration_ms", true);
const txErrors = new Counter("tx_errors");

// ── Test configuration ────────────────────────────────────────────────────────
export const options = {
  stages: [
    { duration: "30s", target: 10 }, // Ramp up to 10 VUs
    { duration: "1m", target: 50 }, // Hold at 50 VUs
    { duration: "30s", target: 100 }, // Spike to 100 VUs
    { duration: "1m", target: 50 }, // Back to 50 VUs
    { duration: "30s", target: 0 }, // Ramp down
  ],
  thresholds: {
    // 95th percentile response time under 500ms
    tx_duration_ms: ["p(95)<500"],
    // At least 99% of transactions succeed
    tx_success_rate: ["rate>0.99"],
    // HTTP error rate below 1%
    http_req_failed: ["rate<0.01"],
  },
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:3000";
const AGENT_TOKEN = __ENV.AGENT_TOKEN || "";

// ── Helpers ───────────────────────────────────────────────────────────────────
function randomAmount(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

function randomPhone() {
  return `0${Math.floor(Math.random() * 9000000000) + 1000000000}`;
}

function trpcMutation(procedure, input) {
  const url = `${BASE_URL}/api/trpc/${procedure}`;
  const payload = JSON.stringify({ json: input });
  const headers = {
    "Content-Type": "application/json",
    Accept: "application/json",
  };
  if (AGENT_TOKEN) {
    headers["Cookie"] = `agent_session=${AGENT_TOKEN}`;
  }
  return http.post(url, payload, { headers, timeout: "10s" });
}

// ── Main test function ────────────────────────────────────────────────────────
export default function () {
  const txType = ["cash_in", "cash_out", "transfer"][
    Math.floor(Math.random() * 3)
  ];
  const amount = randomAmount(100, 50000);

  const input = {
    type: txType,
    amount,
    customer: randomPhone(),
    channel: "pos",
    note: `k6 load test — ${txType}`,
  };

  const start = Date.now();
  const res = trpcMutation("transactions.create", input);
  const elapsed = Date.now() - start;

  txDuration.add(elapsed);

  const ok = check(res, {
    "status is 200": r => r.status === 200,
    "no tRPC error": r => {
      try {
        const body = JSON.parse(r.body);
        return !body.error && body.result?.data?.json?.ref;
      } catch {
        return false;
      }
    },
    "response time < 500ms": () => elapsed < 500,
  });

  txSuccessRate.add(ok);
  if (!ok) txErrors.add(1);

  sleep(Math.random() * 0.5 + 0.1); // 100–600ms think time
}

// ── Setup: authenticate one agent and share the token ────────────────────────
export function setup() {
  const res = http.post(
    `${BASE_URL}/api/trpc/agent.login`,
    JSON.stringify({ json: { agentCode: "AGT001", pin: "123456" } }),
    { headers: { "Content-Type": "application/json" } }
  );

  if (res.status !== 200) {
    console.warn(
      `Setup login failed (status ${res.status}) — tests will run without auth`
    );
    return { token: "" };
  }

  const cookie = res.headers["Set-Cookie"] || "";
  const match = cookie.match(/agent_session=([^;]+)/);
  return { token: match ? match[1] : "" };
}

export function handleSummary(data) {
  return {
    "k6/results/transaction-throughput.json": JSON.stringify(data, null, 2),
    stdout: textSummary(data, { indent: " ", enableColors: true }),
  };
}

// Inline text summary helper (avoids external import requirement)
function textSummary(data, opts = {}) {
  const indent = opts.indent || "";
  const lines = [`\n${indent}=== Transaction Throughput Summary ===`];
  const m = data.metrics;
  if (m.tx_duration_ms)
    lines.push(
      `${indent}  p50 latency:    ${m.tx_duration_ms.values.med?.toFixed(0)}ms`
    );
  if (m.tx_duration_ms)
    lines.push(
      `${indent}  p95 latency:    ${m.tx_duration_ms.values["p(95)"]?.toFixed(0)}ms`
    );
  if (m.tx_success_rate)
    lines.push(
      `${indent}  success rate:   ${(m.tx_success_rate.values.rate * 100).toFixed(2)}%`
    );
  if (m.tx_errors)
    lines.push(`${indent}  total errors:   ${m.tx_errors.values.count}`);
  if (m.iterations)
    lines.push(`${indent}  total requests: ${m.iterations.values.count}`);
  return lines.join("\n");
}
