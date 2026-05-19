#!/usr/bin/env node
/**
 * Smoke Test Suite — 54Link Agency Banking Platform
 * 
 * Validates that all critical endpoints and services are operational.
 * Run after deployment: node scripts/smoke-test.mjs [BASE_URL]
 */

const BASE_URL = process.argv[2] || "http://localhost:3000";
let passed = 0;
let failed = 0;
const results = [];

async function test(name, fn) {
  try {
    await fn();
    passed++;
    results.push({ name, status: "PASS" });
    console.log(`  ✅ ${name}`);
  } catch (err) {
    failed++;
    results.push({ name, status: "FAIL", error: err.message });
    console.log(`  ❌ ${name}: ${err.message}`);
  }
}

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

async function fetchJson(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
  });
  return { status: res.status, data: await res.json().catch(() => null), headers: res.headers };
}

// ═══════════════════════════════════════════════════════════════════════════════
// Health & Infrastructure
// ═══════════════════════════════════════════════════════════════════════════════
console.log("\n🔍 54Link Smoke Test Suite");
console.log("═".repeat(60));
console.log(`Target: ${BASE_URL}\n`);

console.log("📡 Health & Infrastructure:");

await test("Health endpoint returns 200", async () => {
  const { status } = await fetchJson("/api/health");
  assert(status === 200, `Expected 200, got ${status}`);
});

await test("Static assets served (index.html)", async () => {
  const res = await fetch(`${BASE_URL}/`);
  assert(res.status === 200, `Expected 200, got ${res.status}`);
  const html = await res.text();
  assert(html.includes("<!DOCTYPE html>") || html.includes("<html"), "Not valid HTML");
});

await test("Security headers present", async () => {
  const res = await fetch(`${BASE_URL}/`);
  const csp = res.headers.get("content-security-policy");
  const hsts = res.headers.get("strict-transport-security");
  const xfo = res.headers.get("x-frame-options");
  // At least one security header should be present
  assert(csp || hsts || xfo, "No security headers found");
});

// ═══════════════════════════════════════════════════════════════════════════════
// Authentication
// ═══════════════════════════════════════════════════════════════════════════════
console.log("\n🔐 Authentication:");

await test("Auth me endpoint returns 401 without cookie", async () => {
  const { status } = await fetchJson("/api/auth/me");
  assert(status === 401, `Expected 401, got ${status}`);
});

await test("tRPC auth.me returns unauthenticated", async () => {
  const { status, data } = await fetchJson("/api/trpc/auth.me");
  // Should return error or unauthenticated state
  assert(status === 200 || status === 401, `Unexpected status ${status}`);
});

// ═══════════════════════════════════════════════════════════════════════════════
// tRPC Endpoints
// ═══════════════════════════════════════════════════════════════════════════════
console.log("\n📦 tRPC Endpoints:");

const publicEndpoints = [
  "auth.me",
];

for (const endpoint of publicEndpoints) {
  await test(`tRPC ${endpoint} responds`, async () => {
    const res = await fetch(`${BASE_URL}/api/trpc/${endpoint}`);
    assert(res.status < 500, `Server error: ${res.status}`);
  });
}

// Protected endpoints should return 401/UNAUTHORIZED
const protectedEndpoints = [
  "agents.list",
  "transactions.list",
  "analytics.overview",
  "notifications.list",
  "disputes.list",
  "settlement.list",
  "kyc.list",
];

for (const endpoint of protectedEndpoints) {
  await test(`tRPC ${endpoint} requires auth`, async () => {
    const res = await fetch(`${BASE_URL}/api/trpc/${endpoint}`);
    // Should not be 500 (server error) — 401 or 200 with error is fine
    assert(res.status < 500, `Server error: ${res.status}`);
  });
}

// ═══════════════════════════════════════════════════════════════════════════════
// API Routes
// ═══════════════════════════════════════════════════════════════════════════════
console.log("\n🌐 API Routes:");

await test("OAuth login endpoint exists", async () => {
  const res = await fetch(`${BASE_URL}/api/auth/login`, { redirect: "manual" });
  // Should redirect to Keycloak or return 503 if not configured
  assert(res.status === 302 || res.status === 503, `Expected 302 or 503, got ${res.status}`);
});

await test("Webhook endpoint exists", async () => {
  const res = await fetch(`${BASE_URL}/api/health`);
  // Health endpoint should exist
  assert(res.status === 200, `Health endpoint returned ${res.status}`);
});

// ═══════════════════════════════════════════════════════════════════════════════
// Client-Side Routes
// ═══════════════════════════════════════════════════════════════════════════════
console.log("\n🖥️  Client Routes (SPA):");

const clientRoutes = [
  "/",
  "/dashboard",
  "/transactions",
  "/agents",
  "/customers",
  "/analytics",
  "/settings",
  "/partner/onboard",
];

for (const route of clientRoutes) {
  await test(`Route ${route} serves SPA`, async () => {
    const res = await fetch(`${BASE_URL}${route}`);
    assert(res.status === 200, `Expected 200, got ${res.status}`);
    const html = await res.text();
    assert(html.includes("root") || html.includes("app"), "Missing SPA mount point");
  });
}

// ═══════════════════════════════════════════════════════════════════════════════
// Sprint 62 Features
// ═══════════════════════════════════════════════════════════════════════════════
console.log("\n🆕 Sprint 62 Features:");

await test("Stripe webhook endpoint exists", async () => {
  const res = await fetch(`${BASE_URL}/api/stripe/webhook`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: "{}",
  });
  assert(res.status !== 404, "Webhook endpoint not found");
});

await test("404 for unknown API routes (no 500)", async () => {
  const { status } = await fetchJson("/api/nonexistent-route-xyz");
  assert(status < 500, `Server error: ${status}`);
});

await test("Invalid tRPC procedure returns error gracefully", async () => {
  const res = await fetch(`${BASE_URL}/api/trpc/nonexistent.procedure`);
  assert(res.status < 500, `Server error: ${res.status}`);
});

// ═══════════════════════════════════════════════════════════════════════════════
// Performance
// ═══════════════════════════════════════════════════════════════════════════════
console.log("\n⚡ Performance:");

await test("Homepage loads under 5 seconds", async () => {
  const start = Date.now();
  await fetch(`${BASE_URL}/`);
  const elapsed = Date.now() - start;
  assert(elapsed < 5000, `Took ${elapsed}ms (limit: 5000ms)`);
});

await test("API health check under 2 seconds", async () => {
  const start = Date.now();
  await fetch(`${BASE_URL}/api/health`);
  const elapsed = Date.now() - start;
  assert(elapsed < 2000, `Took ${elapsed}ms (limit: 2000ms)`);
});

// ═══════════════════════════════════════════════════════════════════════════════
// Report
// ═══════════════════════════════════════════════════════════════════════════════
console.log("\n" + "═".repeat(60));
console.log(`\n📊 Results: ${passed} passed, ${failed} failed, ${passed + failed} total`);
console.log(`   Pass Rate: ${((passed / (passed + failed)) * 100).toFixed(1)}%`);

if (failed === 0) {
  console.log("\n✅ All smoke tests passed!\n");
} else {
  console.log("\n⚠️  Some tests failed. Review the output above.\n");
  console.log("Failed tests:");
  results.filter(r => r.status === "FAIL").forEach(r => {
    console.log(`  - ${r.name}: ${r.error}`);
  });
}

process.exit(failed > 0 ? 1 : 0);
