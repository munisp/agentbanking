/**
 * k6 load test — CBN reporting engine
 * Tests: report generation, status check, submission
 *
 * Run: k6 run --env BASE_URL=http://localhost:8090 k6/cbn-reporting.js
 */
import http from "k6/http";
import { check, sleep, group } from "k6";
import { Rate, Trend, Counter } from "k6/metrics";

const reportErrors = new Rate("report_errors");
const reportDuration = new Trend("report_duration_ms", true);
const totalRequests = new Counter("total_requests");

export const options = {
  scenarios: {
    report_status_reads: {
      executor: "constant-arrival-rate",
      rate: 50,
      timeUnit: "1s",
      duration: "5m",
      preAllocatedVUs: 20,
      maxVUs: 50,
    },
    report_generation: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: "1m", target: 10 },
        { duration: "3m", target: 10 },
        { duration: "30s", target: 0 },
      ],
      startTime: "30s",
    },
  },
  thresholds: {
    http_req_duration: ["p(95)<2000", "p(99)<5000"], // Reports can be slow
    http_req_failed: ["rate<0.02"],
    report_errors: ["rate<0.05"],
  },
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:8090";

const REPORT_TYPES = [
  "daily_transaction",
  "weekly_summary",
  "monthly_cbn",
  "quarterly_audit",
];
const INSTITUTIONS = Array.from(
  { length: 10 },
  (_, i) => `INST-${String(i + 1).padStart(4, "0")}`
);

function randomItem(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}

export default function () {
  group("cbn: report status", () => {
    const res = http.get(`${BASE_URL}/api/v1/reports/status`);
    totalRequests.add(1);
    check(res, {
      "status: 200": r => r.status === 200,
      "status: fast": r => r.timings.duration < 500,
    });
  });

  sleep(0.5);

  group("cbn: generate report", () => {
    const today = new Date().toISOString().split("T")[0];
    const yesterday = new Date(Date.now() - 86400000)
      .toISOString()
      .split("T")[0];

    const start = Date.now();
    const res = http.post(
      `${BASE_URL}/api/v1/reports/generate`,
      JSON.stringify({
        report_type: randomItem(REPORT_TYPES),
        institution_id: randomItem(INSTITUTIONS),
        start_date: yesterday,
        end_date: today,
        format: "json",
      }),
      {
        headers: { "Content-Type": "application/json" },
        timeout: "30s",
      }
    );
    totalRequests.add(1);
    reportDuration.add(Date.now() - start);

    const ok = check(res, {
      "generate: 200, 201, or 202": r => [200, 201, 202].includes(r.status),
      "generate: has report_id or data": r => {
        try {
          const b = JSON.parse(r.body);
          return b.report_id || b.data || b.status;
        } catch (_) {
          return false;
        }
      },
    });
    reportErrors.add(!ok);
  });

  sleep(Math.random() * 3 + 2);
}

export function handleSummary(data) {
  return {
    "k6-results/cbn-reporting-summary.json": JSON.stringify(data, null, 2),
  };
}
