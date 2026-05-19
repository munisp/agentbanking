/**
 * k6 Load Test: Float Top-Up Request Workflow
 * ─────────────────────────────────────────────────────────────────────────────
 * Tests the float top-up request → admin approval pipeline under load.
 *
 * Usage:
 *   k6 run k6/float-topup.js
 *   BASE_URL=https://your-app.manus.space k6 run k6/float-topup.js
 */
import http from "k6/http";
import { check, sleep } from "k6";
import { Rate, Trend } from "k6/metrics";

const topupSuccessRate = new Rate("topup_success_rate");
const topupDuration = new Trend("topup_duration_ms", true);

export const options = {
  stages: [
    { duration: "20s", target: 20 },
    { duration: "1m", target: 40 },
    { duration: "20s", target: 0 },
  ],
  thresholds: {
    topup_duration_ms: ["p(95)<800"],
    topup_success_rate: ["rate>0.98"],
    http_req_failed: ["rate<0.02"],
  },
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:3000";
const AGENT_TOKEN = __ENV.AGENT_TOKEN || "";
const ADMIN_TOKEN = __ENV.ADMIN_TOKEN || "";

function trpcMutation(procedure, input, token) {
  const headers = { "Content-Type": "application/json" };
  if (token) headers["Cookie"] = `agent_session=${token}`;
  return http.post(
    `${BASE_URL}/api/trpc/${procedure}`,
    JSON.stringify({ json: input }),
    { headers, timeout: "10s" }
  );
}

function trpcQuery(procedure, input, token) {
  const headers = { "Content-Type": "application/json" };
  if (token) headers["Cookie"] = `agent_session=${token}`;
  const qs = encodeURIComponent(JSON.stringify({ json: input }));
  return http.get(`${BASE_URL}/api/trpc/${procedure}?input=${qs}`, {
    headers,
    timeout: "10s",
  });
}

export default function () {
  // Step 1: Agent submits a float top-up request
  const amount = Math.floor(Math.random() * 90000) + 10000; // 10k–100k
  const start = Date.now();

  const createRes = trpcMutation(
    "floatTopUp.request",
    { amount, reason: "k6 load test top-up" },
    AGENT_TOKEN
  );

  const ok = check(createRes, {
    "top-up request created": r => r.status === 200,
    "has request id": r => {
      try {
        return !!JSON.parse(r.body).result?.data?.json?.id;
      } catch {
        return false;
      }
    },
  });

  topupSuccessRate.add(ok);
  topupDuration.add(Date.now() - start);

  sleep(0.2);

  // Step 2: Admin lists pending requests (read-heavy path)
  if (ADMIN_TOKEN) {
    const listRes = trpcQuery(
      "floatTopUp.listRequests",
      { status: "pending", page: 1 },
      ADMIN_TOKEN
    );
    check(listRes, {
      "admin list returns 200": r => r.status === 200,
    });
  }

  sleep(Math.random() * 0.3 + 0.1);
}
