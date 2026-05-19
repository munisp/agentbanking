/**
 * Sprint 52 Smoke Tests
 * Tests all 20 Sprint 52 features: middleware, RBAC, health, API versioning,
 * executive dashboard, audit log, system settings, leaderboard, float mgmt,
 * dispute resolution, error boundary, loading skeletons, keyboard shortcuts,
 * bulk operations, theme persistence, mobile responsive
 */
import fs from "fs";
import path from "path";

let passed = 0, failed = 0;
const results = [];

function test(name, fn) {
  try {
    fn();
    passed++;
    results.push({ name, status: "PASS" });
  } catch (e) {
    failed++;
    results.push({ name, status: "FAIL", error: e.message });
    console.log(`  ❌ ${name}: ${e.message}`);
  }
}

function exists(p) {
  if (!fs.existsSync(p)) throw new Error(`File not found: ${p}`);
}

function contains(p, text) {
  const content = fs.readFileSync(p, "utf8");
  if (!content.includes(text)) throw new Error(`"${text}" not found in ${path.basename(p)}`);
}

function minLines(p, min) {
  const lines = fs.readFileSync(p, "utf8").split("\n").length;
  if (lines < min) throw new Error(`${path.basename(p)} has ${lines} lines, expected >= ${min}`);
}

const root = path.resolve(".");

console.log("============================================================");
console.log("SPRINT 52 SMOKE TESTS");
console.log("============================================================");

// F01: Health Endpoint
console.log("\n=== F01: Health Endpoint ===");
test("Health endpoint middleware exists", () => exists(`${root}/server/middleware/index.ts`));
test("Health middleware has rate limiting", () => contains(`${root}/server/middleware/index.ts`, "rateLimit"));
test("Health middleware has request logging", () => contains(`${root}/server/middleware/index.ts`, "requestLog"));
test("Health middleware has request ID", () => contains(`${root}/server/middleware/index.ts`, "requestId"));

// F02: Executive Command Center
console.log("\n=== F02: Executive Command Center ===");
test("Executive Command Center page exists", () => exists(`${root}/client/src/pages/ExecutiveCommandCenterPage.tsx`));
test("Executive page has KPI cards", () => contains(`${root}/client/src/pages/ExecutiveCommandCenterPage.tsx`, "KPI"));
test("Executive page is substantial", () => minLines(`${root}/client/src/pages/ExecutiveCommandCenterPage.tsx`, 100));

// F03: Server Middleware
console.log("\n=== F03: Server Middleware ===");
test("Middleware directory exists", () => exists(`${root}/server/middleware`));
test("Middleware index has exports", () => contains(`${root}/server/middleware/index.ts`, "export"));

// F04: Activity Audit Log
console.log("\n=== F04: Activity Audit Log ===");
test("Activity Audit Log page exists", () => exists(`${root}/client/src/pages/ActivityAuditLogPage.tsx`));
test("Audit log page has search", () => contains(`${root}/client/src/pages/ActivityAuditLogPage.tsx`, "search"));
test("Audit log page is substantial", () => minLines(`${root}/client/src/pages/ActivityAuditLogPage.tsx`, 100));

// F05: Production Defaults
console.log("\n=== F05: Production Defaults ===");
test("Production defaults file exists", () => exists(`${root}/shared/production-defaults.ts`));
test("Defaults has API URLs", () => contains(`${root}/shared/production-defaults.ts`, "API"));
test("Defaults has timeout values", () => contains(`${root}/shared/production-defaults.ts`, "timeout"));

// F06: RBAC Hardening
console.log("\n=== F06: RBAC Hardening ===");
test("RBAC middleware exists", () => exists(`${root}/server/middleware/rbac.ts`));
test("RBAC has role checks", () => contains(`${root}/server/middleware/rbac.ts`, "role"));
test("RBAC has admin check", () => contains(`${root}/server/middleware/rbac.ts`, "admin"));

// F07: System Settings
console.log("\n=== F07: System Settings ===");
test("System Settings page exists", () => exists(`${root}/client/src/pages/SystemSettingsPage.tsx`));
test("System Settings is substantial", () => minLines(`${root}/client/src/pages/SystemSettingsPage.tsx`, 100));

// F08: API Versioning
console.log("\n=== F08: API Versioning ===");
test("API versioning middleware exists", () => exists(`${root}/server/middleware/apiVersioning.ts`));
test("API versioning has version header", () => contains(`${root}/server/middleware/apiVersioning.ts`, "version"));

// F09: Agent Performance Leaderboard
console.log("\n=== F09: Agent Performance Leaderboard ===");
test("Leaderboard page exists", () => exists(`${root}/client/src/pages/AgentPerformanceLeaderboardPage.tsx`));
test("Leaderboard page is substantial", () => minLines(`${root}/client/src/pages/AgentPerformanceLeaderboardPage.tsx`, 100));

// F10: Float Management
console.log("\n=== F10: Float Management ===");
test("Float Management page exists", () => exists(`${root}/client/src/pages/FloatManagementPage.tsx`));
test("Float Management is substantial", () => minLines(`${root}/client/src/pages/FloatManagementPage.tsx`, 100));

// F11: Dispute Resolution
console.log("\n=== F11: Dispute Resolution ===");
test("Dispute Resolution page exists", () => exists(`${root}/client/src/pages/DisputeResolutionPage.tsx`));

// F12: Cursor-based Pagination
console.log("\n=== F12: Cursor-based Pagination ===");
test("Pagination helper in apiVersioning", () => contains(`${root}/server/middleware/apiVersioning.ts`, "cursor"));

// F13: Error Boundary
console.log("\n=== F13: Error Boundary ===");
test("Error Boundary component exists", () => exists(`${root}/client/src/components/ErrorBoundary.tsx`));
test("Error Boundary has fallback UI", () => contains(`${root}/client/src/components/ErrorBoundary.tsx`, "fallback"));

// F14: Loading Skeletons
console.log("\n=== F14: Loading Skeletons ===");
test("Loading Skeleton component exists", () => exists(`${root}/client/src/components/LoadingSkeleton.tsx`));
test("Loading Skeleton has variants", () => contains(`${root}/client/src/components/LoadingSkeleton.tsx`, "Skeleton"));

// F15: Toast Notification System
console.log("\n=== F15: Toast/Keyboard Shortcuts ===");
test("Keyboard shortcuts hook exists", () => exists(`${root}/client/src/hooks/useKeyboardShortcuts.ts`));

// F16: Keyboard Shortcuts
test("Keyboard shortcuts has key bindings", () => contains(`${root}/client/src/hooks/useKeyboardShortcuts.ts`, "key"));

// F17: Bulk Operations
console.log("\n=== F17: Bulk Operations ===");
test("Bulk operations hook exists", () => exists(`${root}/client/src/hooks/useBulkOperations.ts`));
test("Bulk operations has select all", () => contains(`${root}/client/src/hooks/useBulkOperations.ts`, "select"));

// F18: CSV/PDF Export
test("Export utilities exist", () => contains(`${root}/client/src/hooks/useBulkOperations.ts`, "export"));

// F19: Theme Persistence
console.log("\n=== F19: Theme Persistence ===");
test("Theme persistence hook exists", () => exists(`${root}/client/src/hooks/useThemePersistence.ts`));
test("Theme persistence uses localStorage", () => contains(`${root}/client/src/hooks/useThemePersistence.ts`, "localStorage"));

// F20: Mobile Responsive
test("Mobile responsive utilities exist", () => contains(`${root}/client/src/hooks/useThemePersistence.ts`, "mobile"));

// Docker
console.log("\n=== Docker ===");
test("Sprint 52 Docker Compose exists", () => exists(`${root}/docker-compose.sprint52.yml`));
test("Docker Compose has all services", () => {
  const dc = fs.readFileSync(`${root}/docker-compose.sprint52.yml`, "utf8");
  for (const svc of ["pos-shell-app", "postgres", "redis", "middleware-proxy", "rbac-service", "health-aggregator"]) {
    if (!dc.includes(svc)) throw new Error(`Missing service: ${svc}`);
  }
});

// Routes
console.log("\n=== Route Registration ===");
test("Executive Command Center route registered", () => contains(`${root}/client/src/App.tsx`, "/executive-command-center"));
test("Activity Audit Log route registered", () => contains(`${root}/client/src/App.tsx`, "/activity-audit-log"));
test("System Settings route registered", () => contains(`${root}/client/src/App.tsx`, "/system-settings"));
test("Float Management route registered", () => contains(`${root}/client/src/App.tsx`, "/float-management"));

// Sidebar Nav
console.log("\n=== Sidebar Navigation ===");
test("Sprint 52 nav group in sidebar", () => contains(`${root}/client/src/components/DashboardLayout.tsx`, "Sprint 52"));

// Previous Sprint Tests
console.log("\n=== Previous Sprint Compatibility ===");
test("Sprint 50 seed script", () => exists(`${root}/scripts/seed-sprint50.mjs`));
test("Sprint 50 smoke test", () => exists(`${root}/scripts/smoke-test-sprint50.mjs`));
test("Sprint 51 smoke test", () => exists(`${root}/scripts/smoke-test-sprint51.mjs`));
test("Sprint 50 Docker Compose", () => exists(`${root}/docker-compose.sprint50.yml`));
test("Sprint 51 Docker Compose", () => exists(`${root}/docker-compose.sprint51.yml`));

console.log("\n============================================================");
console.log(`📊 Results: ${passed} passed, ${failed} failed, ${passed + failed} total`);
console.log(`   Pass rate: ${((passed / (passed + failed)) * 100).toFixed(1)}%`);
if (failed === 0) console.log("🎉 ALL SPRINT 52 SMOKE TESTS PASSED!");
else console.log(`⚠️  ${failed} tests failed`);
console.log("============================================================");

fs.writeFileSync(`${root}/data/smoke-test-sprint52.json`, JSON.stringify({ passed, failed, total: passed + failed, results }, null, 2));
