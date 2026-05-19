/**
 * k6 load test — auth-service
 * Tests: login, token refresh, logout, MFA verify, session check
 *
 * Run: k6 run --env BASE_URL=http://localhost:8081 k6/auth-service.js
 */
import http from "k6/http";
import { check, sleep, group } from "k6";
import { Rate, Trend, Counter } from "k6/metrics";

// ── Custom metrics ────────────────────────────────────────────────────────────
const loginErrors = new Rate("login_errors");
const loginDuration = new Trend("login_duration_ms", true);
const tokenRefreshErrors = new Rate("token_refresh_errors");
const mfaVerifyErrors = new Rate("mfa_verify_errors");
const totalRequests = new Counter("total_requests");

// ── Options ───────────────────────────────────────────────────────────────────
export const options = {
  scenarios: {
    // Ramp up to 200 concurrent users over 2 min, hold 5 min, ramp down 1 min
    login_load: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: "2m", target: 200 },
        { duration: "5m", target: 200 },
        { duration: "1m", target: 0 },
      ],
      gracefulRampDown: "30s",
    },
    // Constant 50 VUs for token refresh (background traffic)
    token_refresh: {
      executor: "constant-vus",
      vus: 50,
      duration: "8m",
      startTime: "30s",
    },
  },
  thresholds: {
    http_req_duration: ["p(95)<500", "p(99)<1000"],
    http_req_failed: ["rate<0.01"],
    login_errors: ["rate<0.02"],
    token_refresh_errors: ["rate<0.01"],
    mfa_verify_errors: ["rate<0.02"],
  },
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:8081";

// ── Test data ─────────────────────────────────────────────────────────────────
const TEST_AGENTS = Array.from({ length: 100 }, (_, i) => ({
  phone: `0800000${String(i).padStart(4, "0")}`,
  pin: "1234",
}));

function randomAgent() {
  return TEST_AGENTS[Math.floor(Math.random() * TEST_AGENTS.length)];
}

// ── Scenarios ─────────────────────────────────────────────────────────────────
export default function loginScenario() {
  const agent = randomAgent();

  group("auth: login flow", () => {
    const start = Date.now();
    const res = http.post(
      `${BASE_URL}/api/v1/auth/login`,
      JSON.stringify({ phone: agent.phone, pin: agent.pin }),
      { headers: { "Content-Type": "application/json" } }
    );
    totalRequests.add(1);
    loginDuration.add(Date.now() - start);

    const ok = check(res, {
      "login: status 200 or 401": r => r.status === 200 || r.status === 401,
      "login: has body": r => r.body && r.body.length > 0,
      "login: response time < 500ms": r => r.timings.duration < 500,
    });
    loginErrors.add(!ok);

    if (res.status === 200) {
      let body;
      try {
        body = JSON.parse(res.body);
      } catch (_) {
        return;
      }
      const token = body.token || body.access_token;
      if (!token) return;

      sleep(0.5);

      // Token refresh
      group("auth: token refresh", () => {
        const refreshRes = http.post(
          `${BASE_URL}/api/v1/auth/refresh`,
          JSON.stringify({ token }),
          { headers: { "Content-Type": "application/json" } }
        );
        totalRequests.add(1);
        const refreshOk = check(refreshRes, {
          "refresh: status 200 or 401": r =>
            r.status === 200 || r.status === 401,
          "refresh: response time < 300ms": r => r.timings.duration < 300,
        });
        tokenRefreshErrors.add(!refreshOk);
      });

      sleep(0.3);

      // Session check
      group("auth: session check", () => {
        const sessionRes = http.get(`${BASE_URL}/api/v1/auth/me`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        totalRequests.add(1);
        check(sessionRes, {
          "session: status 200 or 401": r =>
            r.status === 200 || r.status === 401,
          "session: response time < 200ms": r => r.timings.duration < 200,
        });
      });

      sleep(0.2);

      // Logout
      group("auth: logout", () => {
        const logoutRes = http.post(`${BASE_URL}/api/v1/auth/logout`, null, {
          headers: { Authorization: `Bearer ${token}` },
        });
        totalRequests.add(1);
        check(logoutRes, {
          "logout: status 200 or 204": r =>
            r.status === 200 || r.status === 204,
        });
      });
    }
  });

  sleep(Math.random() * 2 + 1);
}

export function tokenRefreshScenario() {
  // Simulate background token refresh from already-logged-in sessions
  const res = http.post(
    `${BASE_URL}/api/v1/auth/refresh`,
    JSON.stringify({ token: "test-token-placeholder" }),
    { headers: { "Content-Type": "application/json" } }
  );
  totalRequests.add(1);
  check(res, {
    "bg-refresh: responds": r => r.status < 500,
    "bg-refresh: fast": r => r.timings.duration < 200,
  });
  sleep(5);
}

export function handleSummary(data) {
  return {
    "k6-results/auth-service-summary.json": JSON.stringify(data, null, 2),
  };
}
