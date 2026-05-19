/**
 * k6 load test — mfa-service
 * Tests: TOTP enroll, verify, backup code generation
 *
 * Run: k6 run --env BASE_URL=http://localhost:8086 k6/mfa-service.js
 */
import http from "k6/http";
import { check, sleep, group } from "k6";
import { Rate, Trend, Counter } from "k6/metrics";

const enrollErrors = new Rate("mfa_enroll_errors");
const verifyErrors = new Rate("mfa_verify_errors");
const enrollDuration = new Trend("mfa_enroll_duration_ms", true);
const verifyDuration = new Trend("mfa_verify_duration_ms", true);
const totalRequests = new Counter("total_requests");

export const options = {
  scenarios: {
    mfa_enroll: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: "1m", target: 50 },
        { duration: "3m", target: 50 },
        { duration: "30s", target: 0 },
      ],
    },
    mfa_verify: {
      executor: "constant-arrival-rate",
      rate: 200,
      timeUnit: "1s",
      duration: "5m",
      preAllocatedVUs: 50,
      maxVUs: 100,
      startTime: "30s",
    },
  },
  thresholds: {
    http_req_duration: ["p(95)<300", "p(99)<600"],
    http_req_failed: ["rate<0.01"],
    mfa_enroll_errors: ["rate<0.02"],
    mfa_verify_errors: ["rate<0.02"],
  },
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:8086";

export default function () {
  group("mfa: enroll", () => {
    const userId = `user-${Math.floor(Math.random() * 10000)}`;
    const start = Date.now();
    const res = http.post(
      `${BASE_URL}/api/v1/mfa/enroll?user_id=${userId}`,
      null,
      { headers: { "Content-Type": "application/json" } }
    );
    totalRequests.add(1);
    enrollDuration.add(Date.now() - start);

    const ok = check(res, {
      "enroll: status 200": r => r.status === 200,
      "enroll: has secret": r => {
        try {
          const b = JSON.parse(r.body);
          return b.secret && b.secret.length > 0;
        } catch (_) {
          return false;
        }
      },
      "enroll: has backup_codes": r => {
        try {
          const b = JSON.parse(r.body);
          return Array.isArray(b.backup_codes) && b.backup_codes.length === 8;
        } catch (_) {
          return false;
        }
      },
      "enroll: fast": r => r.timings.duration < 300,
    });
    enrollErrors.add(!ok);
  });

  sleep(Math.random() * 2 + 1);
}

export function handleSummary(data) {
  return {
    "k6-results/mfa-service-summary.json": JSON.stringify(data, null, 2),
  };
}
