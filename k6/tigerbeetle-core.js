/**
 * k6 load test — tigerbeetle-core (ledger operations)
 * Tests: account balance lookup, transfer creation, batch transfers
 *
 * Run: k6 run --env BASE_URL=http://localhost:8083 k6/tigerbeetle-core.js
 */
import http from "k6/http";
import { check, sleep, group } from "k6";
import { Rate, Trend, Counter } from "k6/metrics";

const balanceErrors = new Rate("balance_lookup_errors");
const transferErrors = new Rate("transfer_errors");
const balanceDuration = new Trend("balance_lookup_duration_ms", true);
const transferDuration = new Trend("transfer_duration_ms", true);
const totalRequests = new Counter("total_requests");

export const options = {
  scenarios: {
    // Balance lookups — very high read throughput
    balance_reads: {
      executor: "constant-arrival-rate",
      rate: 500,
      timeUnit: "1s",
      duration: "8m",
      preAllocatedVUs: 100,
      maxVUs: 300,
    },
    // Transfer writes — lower rate, higher latency tolerance
    transfers: {
      executor: "ramping-arrival-rate",
      startRate: 10,
      timeUnit: "1s",
      stages: [
        { duration: "2m", target: 100 },
        { duration: "4m", target: 100 },
        { duration: "1m", target: 0 },
      ],
      preAllocatedVUs: 50,
      maxVUs: 150,
      startTime: "30s",
    },
  },
  thresholds: {
    http_req_duration: ["p(95)<200", "p(99)<500"],
    http_req_failed: ["rate<0.005"],
    balance_lookup_errors: ["rate<0.005"],
    transfer_errors: ["rate<0.01"],
  },
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:8083";

const ACCOUNT_IDS = Array.from({ length: 1000 }, (_, i) => i + 1);

function randomAccountId() {
  return ACCOUNT_IDS[Math.floor(Math.random() * ACCOUNT_IDS.length)];
}

function randomAmount() {
  // 100 to 50,000 NGN in kobo
  return Math.floor(Math.random() * 4999900 + 10000);
}

export default function () {
  group("ledger: balance lookup", () => {
    const accountId = randomAccountId();
    const start = Date.now();
    const res = http.get(`${BASE_URL}/api/v1/accounts/${accountId}/balance`);
    totalRequests.add(1);
    balanceDuration.add(Date.now() - start);

    const ok = check(res, {
      "balance: 200 or 404": r => r.status === 200 || r.status === 404,
      "balance: fast": r => r.timings.duration < 200,
    });
    balanceErrors.add(!ok);
  });

  sleep(0.05);

  group("ledger: transfer", () => {
    const debitId = randomAccountId();
    let creditId = randomAccountId();
    while (creditId === debitId) creditId = randomAccountId();

    const start = Date.now();
    const res = http.post(
      `${BASE_URL}/api/v1/transfers`,
      JSON.stringify({
        debit_account_id: debitId,
        credit_account_id: creditId,
        amount: randomAmount(),
        currency: "NGN",
        reference: `k6-${Date.now()}-${Math.random().toString(36).slice(2)}`,
        narration: "k6 load test transfer",
      }),
      { headers: { "Content-Type": "application/json" } }
    );
    totalRequests.add(1);
    transferDuration.add(Date.now() - start);

    const ok = check(res, {
      "transfer: 200, 201, 400, or 422": r =>
        [200, 201, 400, 422].includes(r.status),
      "transfer: has body": r => r.body && r.body.length > 2,
      "transfer: < 500ms": r => r.timings.duration < 500,
    });
    transferErrors.add(!ok);
  });

  sleep(Math.random() * 0.5 + 0.1);
}

export function handleSummary(data) {
  return {
    "k6-results/tigerbeetle-core-summary.json": JSON.stringify(data, null, 2),
  };
}
