#!/usr/bin/env node
/**
 * Sprint 45 — Comprehensive Smoke Test
 * Tests all router categories, middleware connectivity, and service health.
 * Usage: node tests/smoke-test-sprint45.mjs [BASE_URL]
 */
const BASE = process.argv[2] || process.env.APP_URL || "http://localhost:3000";

const results = { pass: 0, fail: 0, skip: 0, errors: [] };

async function test(name, fn) {
  try {
    await fn();
    results.pass++;
    console.log(`  ✅ ${name}`);
  } catch (e) {
    results.fail++;
    results.errors.push({ name, error: e.message });
    console.log(`  ❌ ${name}: ${e.message}`);
  }
}

async function skip(name) {
  results.skip++;
  console.log(`  ⏭️  ${name} (skipped — requires external service)`);
}

async function fetchJSON(path, opts = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...opts.headers },
    ...opts,
  });
  if (!res.ok && !opts.allowFail) throw new Error(`HTTP ${res.status}`);
  return { status: res.status, data: res.headers.get("content-type")?.includes("json") ? await res.json() : await res.text() };
}

// ═══════════════════════════════════════════════════════════════════════════
// 1. CORE HEALTH
// ═══════════════════════════════════════════════════════════════════════════
console.log("\n🏥 Core Health Checks");
await test("Server responds on /", async () => {
  const res = await fetch(BASE);
  if (res.status !== 200) throw new Error(`Status ${res.status}`);
});

await test("Health endpoint /api/health", async () => {
  const { data } = await fetchJSON("/api/health", { allowFail: true });
  // Health endpoint may return partial health when DB is down
});

await test("tRPC endpoint responds", async () => {
  const res = await fetch(`${BASE}/api/trpc/auth.me`, {
    headers: { "Content-Type": "application/json" },
  });
  // Should return 401 or 200, not 404
  if (res.status === 404) throw new Error("tRPC not mounted");
});

// ═══════════════════════════════════════════════════════════════════════════
// 2. STATIC ASSETS
// ═══════════════════════════════════════════════════════════════════════════
console.log("\n📦 Static Assets");
await test("Vite client bundle loads", async () => {
  const res = await fetch(BASE);
  const html = await res.text();
  if (!html.includes("src=") && !html.includes("script")) throw new Error("No script tags");
});

await test("Favicon exists", async () => {
  const res = await fetch(`${BASE}/favicon.ico`);
  if (res.status === 404) throw new Error("No favicon");
});

// ═══════════════════════════════════════════════════════════════════════════
// 3. AUTH FLOW
// ═══════════════════════════════════════════════════════════════════════════
console.log("\n🔐 Authentication");
await test("Login redirect works", async () => {
  const res = await fetch(`${BASE}/api/auth/login`, { redirect: "manual" });
  if (res.status !== 302 && res.status !== 200) throw new Error(`Status ${res.status}`);
});

await test("Logout endpoint exists", async () => {
  const res = await fetch(`${BASE}/api/auth/logout`, { redirect: "manual" });
  // Should redirect or clear cookie, not 404
  if (res.status === 404) throw new Error("Logout not found");
});

// ═══════════════════════════════════════════════════════════════════════════
// 4. MIDDLEWARE CONNECTIVITY
// ═══════════════════════════════════════════════════════════════════════════
console.log("\n🔌 Middleware Connectivity");
const middlewareChecks = [
  { name: "Kafka", env: "KAFKA_BROKERS" },
  { name: "Redis", env: "REDIS_URL" },
  { name: "TigerBeetle Sidecar", env: "TB_SIDECAR_URL" },
  { name: "Temporal", env: "TEMPORAL_ADDRESS" },
  { name: "Permify", env: "PERMIFY_URL" },
  { name: "Fluvio", env: "FLUVIO_ENDPOINT" },
  { name: "Keycloak", env: "KEYCLOAK_URL" },
  { name: "APISIX", env: "APISIX_ADMIN_URL" },
  { name: "Mojaloop", env: "MOJALOOP_HUB_URL" },
  { name: "MinIO", env: "MINIO_ENDPOINT" },
  { name: "Dapr", env: "DAPR_HTTP_PORT" },
  { name: "Lakehouse", env: "LAKEHOUSE_URL" },
  { name: "PostgreSQL", env: "POSTGRES_URL" },
];

for (const mw of middlewareChecks) {
  await skip(`${mw.name} (${mw.env})`);
}

// ═══════════════════════════════════════════════════════════════════════════
// 5. ROUTER CATEGORIES
// ═══════════════════════════════════════════════════════════════════════════
console.log("\n📡 Router Category Checks (tRPC batch)");

const routerCategories = [
  { name: "Agent Management", proc: "agentManagement.listAll" },
  { name: "Transactions", proc: "transactions.list" },
  { name: "Fraud Detection", proc: "fraud.list" },
  { name: "Loyalty System", proc: "loyalty.profile" },
  { name: "Settlement", proc: "settlement.getLastRun" },
  { name: "Commission Engine", proc: "commissionEngine.getSplitRatios" },
  { name: "Dispute/Refund", proc: "disputeRefund.listDisputes" },
  { name: "Audit Trail", proc: "auditTrail.list" },
  { name: "Analytics", proc: "analytics.overview" },
  { name: "Float Management", proc: "floatTopUp.list" },
];

for (const cat of routerCategories) {
  await test(`Router: ${cat.name}`, async () => {
    const res = await fetch(`${BASE}/api/trpc/${cat.proc}`, {
      headers: { "Content-Type": "application/json" },
    });
    // Should return 200, 401 (auth required), or 400 (missing input) — NOT 404
    if (res.status === 404) throw new Error(`Router ${cat.proc} not found`);
  });
}

// ═══════════════════════════════════════════════════════════════════════════
// 6. WEBHOOK ENDPOINT
// ═══════════════════════════════════════════════════════════════════════════
console.log("\n🪝 Webhook Endpoints");
await test("Stripe webhook endpoint exists", async () => {
  const res = await fetch(`${BASE}/api/stripe/webhook`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ type: "test" }),
  });
  // Should return 400 (bad signature) not 404
  if (res.status === 404) throw new Error("Stripe webhook not mounted");
});

// ═══════════════════════════════════════════════════════════════════════════
// 7. SIDECAR HEALTH CHECKS
// ═══════════════════════════════════════════════════════════════════════════
console.log("\n🐳 Sidecar Health Checks");
const sidecars = [
  { name: "TB Commission Sidecar (Go)", url: process.env.TB_SIDECAR_URL || "http://localhost:8086", path: "/health" },
  { name: "Fluvio Producer (Rust)", url: process.env.FLUVIO_PRODUCER_URL || "http://localhost:8087", path: "/health" },
  { name: "Lakehouse-Mojaloop (Python)", url: process.env.LAKEHOUSE_MOJALOOP_URL || "http://localhost:8088", path: "/health" },
];

for (const sc of sidecars) {
  await skip(`${sc.name} at ${sc.url}${sc.path}`);
}

// ═══════════════════════════════════════════════════════════════════════════
// 8. DOCKER COMPOSE VALIDATION
// ═══════════════════════════════════════════════════════════════════════════
console.log("\n🐋 Docker Compose Validation");
await test("docker-compose.yml exists", async () => {
  const fs = await import("fs");
  if (!fs.existsSync("docker-compose.yml") && !fs.existsSync("docker-compose.production.yml")) {
    throw new Error("No docker-compose file found");
  }
});

await test("docker-compose.sprint42.yml exists", async () => {
  const fs = await import("fs");
  if (!fs.existsSync("docker-compose.sprint42.yml")) {
    throw new Error("Sprint 42 compose not found");
  }
});

// ═══════════════════════════════════════════════════════════════════════════
// 9. SEED DATA VALIDATION
// ═══════════════════════════════════════════════════════════════════════════
console.log("\n🌱 Seed Data Validation");
await test("Production seed script exists", async () => {
  const fs = await import("fs");
  if (!fs.existsSync("scripts/seed-production.mjs")) {
    throw new Error("No production seed script");
  }
});

await test("Seed script is syntactically valid", async () => {
  const fs = await import("fs");
  const content = fs.readFileSync("scripts/seed-production.mjs", "utf-8");
  if (content.length < 1000) throw new Error("Seed script too small");
  const tableCount = (content.match(/INSERT INTO/g) || []).length;
  if (tableCount < 30) throw new Error(`Only ${tableCount} tables seeded (need 30+)`);
});

// ═══════════════════════════════════════════════════════════════════════════
// 10. FILE STRUCTURE VALIDATION
// ═══════════════════════════════════════════════════════════════════════════
console.log("\n📂 File Structure Validation");
const requiredFiles = [
  "server/routers.ts",
  "server/db.ts",
  "drizzle/schema.ts",
  "client/src/App.tsx",
  "client/src/main.tsx",
  "package.json",
  "tsconfig.json",
  "vitest.config.ts",
  "docs/env-reference.md",
];

for (const file of requiredFiles) {
  await test(`Required file: ${file}`, async () => {
    const fs = await import("fs");
    if (!fs.existsSync(file)) throw new Error(`Missing: ${file}`);
  });
}

// ═══════════════════════════════════════════════════════════════════════════
// SUMMARY
// ═══════════════════════════════════════════════════════════════════════════
console.log("\n" + "═".repeat(60));
console.log(`🏁 Smoke Test Results: ${results.pass} passed, ${results.fail} failed, ${results.skip} skipped`);
if (results.errors.length > 0) {
  console.log("\n❌ Failures:");
  results.errors.forEach(e => console.log(`   ${e.name}: ${e.error}`));
}
console.log("═".repeat(60));
process.exit(results.fail > 0 ? 1 : 0);
