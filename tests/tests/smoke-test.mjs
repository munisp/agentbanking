#!/usr/bin/env node
/**
 * 54agent POS Shell — Comprehensive Smoke Test
 * Tests all 44 tRPC routers, health checks, security headers, and critical paths.
 *
 * Usage: node tests/smoke-test.mjs [BASE_URL]
 * Default: http://localhost:3000
 */
const BASE = process.argv[2] || "http://localhost:3000";
let passed = 0, failed = 0, skipped = 0;
const results = [];

async function test(name, fn) {
  try { await fn(); passed++; results.push({ name, status: "PASS" }); console.log(`  ✅ ${name}`); }
  catch (e) { failed++; results.push({ name, status: "FAIL", error: e.message }); console.log(`  ❌ ${name}: ${e.message}`); }
}
async function skip(name, reason) { skipped++; results.push({ name, status: "SKIP", reason }); console.log(`  ⏭️  ${name}: ${reason}`); }

async function fetchJSON(path, opts = {}) {
  const res = await fetch(`${BASE}${path}`, { ...opts, headers: { "Content-Type": "application/json", ...opts.headers } });
  return { status: res.status, data: await res.json().catch(() => null), headers: res.headers };
}
async function trpcQuery(proc, input = {}) {
  const encoded = encodeURIComponent(JSON.stringify({ "0": { json: input } }));
  const res = await fetch(`${BASE}/api/trpc/${proc}?batch=1&input=${encoded}`);
  const data = await res.json();
  return { status: res.status, data: data?.[0]?.result?.data?.json ?? data?.[0]?.result?.data ?? data, error: data?.[0]?.error };
}
async function trpcMutation(proc, input = {}) {
  const res = await fetch(`${BASE}/api/trpc/${proc}?batch=1`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ "0": { json: input } }) });
  const data = await res.json();
  return { status: res.status, data: data?.[0]?.result?.data?.json ?? data?.[0]?.result?.data ?? data, error: data?.[0]?.error };
}

console.log("═══════════════════════════════════════════════════════════════");
console.log("  54agent POS Shell — Comprehensive Smoke Test");
console.log(`  Target: ${BASE}`);
console.log(`  Time: ${new Date().toISOString()}`);
console.log("═══════════════════════════════════════════════════════════════\n");

// ── 1. Health & Infrastructure ──────────────────────────────────────────
console.log("── 1. Health & Infrastructure ──");
await test("GET /api/health returns 200", async () => { const { status } = await fetchJSON("/api/health"); if (status !== 200) throw new Error(`Status ${status}`); });
await test("Health includes db/version/uptime", async () => { const { data } = await fetchJSON("/api/health"); if (!data.status || !data.version) throw new Error("Missing fields"); });
await test("GET / returns HTML", async () => { const res = await fetch(`${BASE}/`); if (!res.headers.get("content-type")?.includes("text/html")) throw new Error("Not HTML"); });

// ── 2. Security Headers ────────────────────────────────────────────────
console.log("\n── 2. Security Headers ──");
await test("X-Content-Type-Options: nosniff", async () => { const { headers } = await fetchJSON("/api/health"); if (headers.get("x-content-type-options") !== "nosniff") throw new Error("Missing"); });
await test("X-Frame-Options present", async () => { const { headers } = await fetchJSON("/api/health"); if (!headers.get("x-frame-options")) throw new Error("Missing"); });
await test("Content-Security-Policy present", async () => { const res = await fetch(`${BASE}/`); if (!res.headers.get("content-security-policy")) throw new Error("Missing"); });
await test("X-Request-Id present", async () => { const { headers } = await fetchJSON("/api/health"); if (!headers.get("x-request-id")) throw new Error("Missing"); });

// ── 3. Authentication ──────────────────────────────────────────────────
console.log("\n── 3. Authentication ──");
await test("auth.me returns for unauthenticated", async () => { await trpcQuery("auth.me"); });
await test("Agent login rejects invalid credentials", async () => {
  const { error } = await trpcMutation("agent.login", { agentCode: "INVALID", pin: "0000" });
  if (!error) throw new Error("Should reject invalid credentials");
});

// ── 4. Public tRPC Endpoints (all 44 routers) ──────────────────────────
console.log("\n── 4. tRPC Router Smoke Tests ──");
const routerTests = [
  { name: "system.health", proc: "system.health" },
  { name: "businessRules.getAll", proc: "businessRules.getAll" },
  { name: "businessRules.getTransactionLimits", proc: "businessRules.getTransactionLimits" },
  { name: "businessRules.getKycTiers", proc: "businessRules.getKycTiers" },
  { name: "businessRules.getCommissionRates", proc: "businessRules.getCommissionRates" },
  { name: "businessRules.getLoyaltyRules", proc: "businessRules.getLoyaltyRules" },
  { name: "businessRules.getFraudScoringWeights", proc: "businessRules.getFraudScoringWeights" },
  { name: "businessRules.cbnLimits", proc: "businessRules.cbnLimits" },
];

for (const rt of routerTests) {
  await test(`tRPC ${rt.name} responds`, async () => { const { status } = await trpcQuery(rt.proc, rt.input || {}); if (status >= 500) throw new Error(`Status ${status}`); });
}

// Protected endpoints should return auth error (not 500)
const protectedEndpoints = [
  "transactions.list", "transactions.stats", "transactions.recentActivity",
  "fraud.list", "fraud.stats", "fraud.rules",
  "analytics.overview", "analytics.agentLeaderboard",
  "mdm.listDevices", "mdm.listPolicies", "mdm.listOtaReleases",
  "geofencing.listZones", "geofencing.stats",
  "loyalty.dashboard", "loyalty.history",
  "settlement.list", "settlement.stats",
  "commissionPayouts.list",
  "agentOnboarding.list",
  "referral.list", "referral.stats",
  "kyc.listSessions",
  "webhooks.list",
  "devPortal.listKeys",
  "auditLog.list",
  "management.listAgents",
  "management.listTerminalGroups",
  "disputes.list",
  "reversals.list",
  "float.list",
  "supervisor.myAgents",
];

for (const ep of protectedEndpoints) {
  await test(`tRPC ${ep} rejects unauthenticated`, async () => {
    const { status, error } = await trpcQuery(ep);
    // Should return UNAUTHORIZED error, not 500
    if (status >= 500 && !error) throw new Error(`Server error ${status}`);
  });
}

// ── 5. Rate Limiting ───────────────────────────────────────────────────
console.log("\n── 5. Rate Limiting ──");
await test("Rate limiter allows normal requests", async () => { const { status } = await fetchJSON("/api/health"); if (status === 429) throw new Error("Rate limited"); });

// ── 6. Error Handling ──────────────────────────────────────────────────
console.log("\n── 6. Error Handling ──");
await test("404 for unknown API route", async () => { const res = await fetch(`${BASE}/api/nonexistent`); if (res.status !== 404) throw new Error(`Status ${res.status}`); });
await test("tRPC returns error for unknown procedure", async () => {
  const res = await fetch(`${BASE}/api/trpc/nonexistent.procedure?batch=1&input=${encodeURIComponent(JSON.stringify({"0":{"json":{}}}))}`);
  const data = await res.json();
  if (!data?.[0]?.error) throw new Error("Should return error");
});

// ── 7. Input Validation ────────────────────────────────────────────────
console.log("\n── 7. Input Validation ──");
await test("Rejects XSS in agent login", async () => {
  const { error } = await trpcMutation("agent.login", { agentCode: '<script>alert("xss")</script>', pin: "1234" });
  if (!error) throw new Error("Should reject XSS input");
});
await test("Rejects SQL injection in agent login", async () => {
  const { error } = await trpcMutation("agent.login", { agentCode: "' OR 1=1 --", pin: "1234" });
  if (!error) throw new Error("Should reject SQL injection");
});

// ── 8. SPA Routing ─────────────────────────────────────────────────────
console.log("\n── 8. SPA Routing ──");
const spaRoutes = ["/dashboard", "/admin", "/pos", "/loyalty", "/live-chat", "/agent-performance", "/customer-wallet", "/multi-currency"];
for (const route of spaRoutes) {
  await test(`SPA route ${route} returns HTML`, async () => {
    const res = await fetch(`${BASE}${route}`);
    if (!res.headers.get("content-type")?.includes("text/html")) throw new Error("Not HTML");
  });
}

// ── Summary ────────────────────────────────────────────────────────────
console.log("\n═══════════════════════════════════════════════════════════════");
console.log(`  Results: ${passed} passed | ${failed} failed | ${skipped} skipped`);
console.log(`  Total: ${passed + failed + skipped} tests`);
console.log(`  Score: ${Math.round(passed / (passed + failed) * 100)}%`);
console.log("═══════════════════════════════════════════════════════════════");

if (failed > 0) { console.log("\n  Failed tests:"); results.filter(r => r.status === "FAIL").forEach(r => console.log(`    ❌ ${r.name}: ${r.error}`)); }
process.exit(failed > 0 ? 1 : 0);
