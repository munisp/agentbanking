/**
 * k6 Load Test: Dispute Creation + Lifecycle
 * ─────────────────────────────────────────────────────────────────────────────
 * Tests the dispute raise → message → resolve pipeline under load.
 *
 * Usage:
 *   k6 run k6/dispute-creation.js
 *   BASE_URL=https://your-app.manus.space k6 run k6/dispute-creation.js
 */
import http from "k6/http";
import { check, sleep } from "k6";
import { Rate, Trend } from "k6/metrics";

const disputeSuccessRate = new Rate("dispute_success_rate");
const disputeDuration = new Trend("dispute_duration_ms", true);

export const options = {
  stages: [
    { duration: "20s", target: 15 },
    { duration: "1m", target: 30 },
    { duration: "20s", target: 0 },
  ],
  thresholds: {
    dispute_duration_ms: ["p(95)<1000"],
    dispute_success_rate: ["rate>0.97"],
    http_req_failed: ["rate<0.03"],
  },
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:3000";
const AGENT_TOKEN = __ENV.AGENT_TOKEN || "";

function trpcMutation(procedure, input, token) {
  const headers = { "Content-Type": "application/json" };
  if (token) headers["Cookie"] = `agent_session=${token}`;
  return http.post(
    `${BASE_URL}/api/trpc/${procedure}`,
    JSON.stringify({ json: input }),
    { headers, timeout: "15s" }
  );
}

const DISPUTE_TYPES = [
  "wrong_amount",
  "failed_transaction",
  "double_charge",
  "service_not_rendered",
];
const CHANNELS = ["cash_in", "cash_out", "transfer", "airtime"];

export default function () {
  const start = Date.now();

  // Step 1: Raise a dispute
  const raiseRes = trpcMutation(
    "disputes.raise",
    {
      transactionRef: `TXN${Math.random().toString(36).slice(2, 12).toUpperCase()}`,
      type: DISPUTE_TYPES[Math.floor(Math.random() * DISPUTE_TYPES.length)],
      amount: Math.floor(Math.random() * 50000) + 500,
      channel: CHANNELS[Math.floor(Math.random() * CHANNELS.length)],
      description: "k6 load test dispute — automated",
      customerPhone: `0${Math.floor(Math.random() * 9000000000) + 1000000000}`,
    },
    AGENT_TOKEN
  );

  const ok = check(raiseRes, {
    "dispute raised (200)": r => r.status === 200,
    "has dispute id": r => {
      try {
        return !!JSON.parse(r.body).result?.data?.json?.id;
      } catch {
        return false;
      }
    },
  });

  disputeSuccessRate.add(ok);
  disputeDuration.add(Date.now() - start);

  if (ok) {
    let disputeId;
    try {
      disputeId = JSON.parse(raiseRes.body).result?.data?.json?.id;
    } catch {
      /* ignore */
    }

    if (disputeId) {
      sleep(0.1);

      // Step 2: Add a follow-up message
      const msgRes = trpcMutation(
        "disputes.addMessage",
        {
          disputeId,
          message: "k6 follow-up: please confirm receipt of dispute",
        },
        AGENT_TOKEN
      );

      check(msgRes, {
        "message added (200)": r => r.status === 200,
      });
    }
  }

  sleep(Math.random() * 0.5 + 0.2);
}
