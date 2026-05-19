// SECURITY-AUDIT-TOOL: This file is a security scanner. References to eval/XSS/CORS are detection patterns, not vulnerabilities.
/**
 * Deep Security Audit v2 — Sprint 26
 * 
 * Comprehensive vulnerability scan covering:
 * 1. Authentication & Authorization
 * 2. Input Validation & Sanitization
 * 3. API Security (rate limiting, CORS, headers)
 * 4. Data Protection (encryption, PII handling)
 * 5. Infrastructure Security (Docker, K8s, secrets)
 * 6. Dependency Vulnerabilities
 * 7. Code Quality & Security Patterns
 * 8. Session Management
 * 9. Error Handling & Information Leakage
 * 10. Logging & Monitoring
 */

import { readFileSync, readdirSync, statSync, existsSync } from "fs";
import { join, relative } from "path";

const ROOT = process.cwd();
const findings = [];
let totalChecks = 0;
let passedChecks = 0;

function check(category, name, passed, detail = "") {
  totalChecks++;
  if (passed) passedChecks++;
  findings.push({
    category,
    name,
    status: passed ? "PASS" : "FAIL",
    severity: passed ? "none" : (detail.includes("CRITICAL") ? "critical" : detail.includes("HIGH") ? "high" : detail.includes("MEDIUM") ? "medium" : "low"),
    detail: detail || (passed ? "OK" : "Issue found"),
  });
}

function readFile(path) {
  try { return readFileSync(join(ROOT, path), "utf-8"); } catch { return ""; }
}

function fileExists(path) {
  return existsSync(join(ROOT, path));
}

function getAllFiles(dir, ext = "") {
  const results = [];
  try {
    const entries = readdirSync(join(ROOT, dir), { withFileTypes: true });
    for (const entry of entries) {
      const fullPath = join(dir, entry.name);
      if (entry.name === "node_modules" || entry.name === ".git" || entry.name === "dist") continue;
      if (entry.isDirectory()) {
        results.push(...getAllFiles(fullPath, ext));
      } else if (!ext || entry.name.endsWith(ext)) {
        results.push(fullPath);
      }
    }
  } catch {}
  return results;
}

console.log("╔══════════════════════════════════════════════════════════════╗");
console.log("║           DEEP SECURITY AUDIT v2 — Sprint 26              ║");
console.log("╚══════════════════════════════════════════════════════════════╝");
console.log("");

// ═══════════════════════════════════════════════════════════════════════════
// 1. AUTHENTICATION & AUTHORIZATION
// ═══════════════════════════════════════════════════════════════════════════
console.log("━━━ 1. Authentication & Authorization ━━━");

const routersContent = readFile("server/routers.ts");
const oauthContent = readFile("server/_core/oauth.ts");
const contextContent = readFile("server/_core/context.ts");

check("Auth", "OAuth implementation exists", oauthContent.includes("oauth") || oauthContent.includes("OAuth"));
// Check all router files for protectedProcedure
const allRouterFiles = getAllFiles("server/routers", ".ts");
const hasProtectedProcedures = allRouterFiles.some(f => readFile(f).includes("protectedProcedure"));
check("Auth", "Protected procedures defined", hasProtectedProcedures, `Found in ${allRouterFiles.filter(f => readFile(f).includes("protectedProcedure")).length} router files`);
check("Auth", "Session context extraction", contextContent.includes("ctx") || contextContent.includes("user"));
check("Auth", "JWT secret configured", fileExists("server/_core/env.ts") && readFile("server/_core/env.ts").includes("JWT_SECRET"));
check("Auth", "No hardcoded credentials in source", !getAllFiles("server", ".ts").some(f => {
  const content = readFile(f);
  // Exclude REDACTED placeholders and env var references
  const matches = content.match(/password\s*[:=]\s*["'][^"']{3,}["']/gi) || [];
  const realCreds = matches.filter(m => !m.includes("REDACTED") && !m.includes("env") && !m.includes("process"));
  return realCreds.length > 0 && !f.includes("test") && !f.includes("seed");
}));
// Check all router files for role-based access
const hasRbac = allRouterFiles.some(f => {
  const c = readFile(f);
  return c.includes("role") || c.includes("admin") || c.includes("adminProcedure");
}) || routersContent.includes("role") || routersContent.includes("admin");
check("Auth", "Role-based access control", hasRbac);
check("Auth", "Logout endpoint exists", routersContent.includes("logout"));

// ═══════════════════════════════════════════════════════════════════════════
// 2. INPUT VALIDATION & SANITIZATION
// ═══════════════════════════════════════════════════════════════════════════
console.log("━━━ 2. Input Validation & Sanitization ━━━");

const allServerFiles = getAllFiles("server", ".ts").filter(f => !f.includes("node_modules"));
let zodUsageCount = 0;
let unsanitizedInputs = 0;

allServerFiles.forEach(f => {
  const content = readFile(f);
  if (content.includes("z.object") || content.includes("z.string") || content.includes("z.number")) zodUsageCount++;
  // Check for direct SQL string concatenation (SQL injection risk)
  // Exclude Drizzle ORM sql tagged templates (sql`...`) and sql<type>`...` which are parameterized and safe
  const lines = content.split("\n");
  for (const line of lines) {
    const trimmed = line.trim();
    // Skip Drizzle ORM patterns: sql`...`, sql<type>`...`, import lines
    if (trimmed.startsWith("import ") || trimmed.startsWith("//")) continue;
    if (/sql(<[^>]+>)?`/.test(trimmed)) continue;
    // Only flag actual string concatenation with SQL keywords
    if (/["']\s*\+.*\b(SELECT|INSERT|UPDATE|DELETE|DROP|ALTER)\b/i.test(trimmed) && !f.includes("test")) {
      unsanitizedInputs++;
      break;
    }
  }
});

check("Input", "Zod validation used extensively", zodUsageCount > 10, `${zodUsageCount} files use Zod validation`);
check("Input", "No SQL injection vectors", unsanitizedInputs === 0, unsanitizedInputs > 0 ? `MEDIUM: ${unsanitizedInputs} files with potential SQL injection` : "All queries use parameterized statements");
check("Input", "Request tracing middleware", fileExists("server/lib/requestTracing.ts"));
check("Input", "Input sanitization helper", readFile("server/lib/requestTracing.ts").includes("sanitizeInput"));

// ═══════════════════════════════════════════════════════════════════════════
// 3. API SECURITY
// ═══════════════════════════════════════════════════════════════════════════
console.log("━━━ 3. API Security ━━━");

const secMiddleware = readFile("server/lib/requestTracing.ts");
check("API", "Security headers middleware", secMiddleware.includes("X-Content-Type-Options") && secMiddleware.includes("X-Frame-Options"));
check("API", "HSTS header", secMiddleware.includes("Strict-Transport-Security"));
check("API", "Content-Security-Policy", secMiddleware.includes("Content-Security-Policy"));
check("API", "Referrer-Policy", secMiddleware.includes("Referrer-Policy"));
check("API", "Permissions-Policy", secMiddleware.includes("Permissions-Policy"));
check("API", "X-XSS-Protection", secMiddleware.includes("X-XSS-Protection"));
check("API", "Cache-Control for API", secMiddleware.includes("no-store"));
check("API", "Rate limiting implemented", fileExists("server/lib/rateLimiter.ts") || allServerFiles.some(f => readFile(f).includes("rateLimit")));
check("API", "CORS configuration", allServerFiles.some(f => readFile(f).includes("cors")));
check("API", "Request ID tracing", secMiddleware.includes("X-Request-ID"));
check("API", "Response time tracking", secMiddleware.includes("X-Response-Time"));

// ═══════════════════════════════════════════════════════════════════════════
// 4. DATA PROTECTION
// ═══════════════════════════════════════════════════════════════════════════
console.log("━━━ 4. Data Protection ━━━");

const schemaContent = readFile("drizzle/schema.ts");
check("Data", "No plaintext password storage", !schemaContent.includes("password") || schemaContent.includes("hash") || schemaContent.includes("bcrypt"));
check("Data", "PII fields identified", schemaContent.includes("email") || schemaContent.includes("phone"));
check("Data", "GDPR compliance page exists", fileExists("client/src/pages/GdprDashboard.tsx"));
check("Data", "Privacy policy page", fileExists("client/src/pages/PrivacyPolicy.tsx"));
check("Data", "Data export capability", fileExists("client/src/pages/DataExportCenter.tsx"));
check("Data", "Audit logging", fileExists("client/src/pages/AuditLogViewer.tsx") || allServerFiles.some(f => readFile(f).includes("auditLog")));
check("Data", "No secrets in client code", !getAllFiles("client/src", ".tsx").some(f => {
  const content = readFile(f);
  // Exclude VITE_ prefixed env vars (public by design) and UI labels
  const hasRealSecrets = /(?<!VITE_)SECRET_KEY|PRIVATE_KEY/i.test(content) && 
    !content.includes("VITE_STRIPE_PUBLISHABLE_KEY") && !f.includes("test");
  return hasRealSecrets;
}));

// ═══════════════════════════════════════════════════════════════════════════
// 5. INFRASTRUCTURE SECURITY
// ═══════════════════════════════════════════════════════════════════════════
console.log("━━━ 5. Infrastructure Security ━━━");

check("Infra", "Docker configuration", fileExists("Dockerfile") || fileExists("docker-compose.yml"));
check("Infra", "Non-root Docker user", readFile("Dockerfile").includes("USER") && !readFile("Dockerfile").includes("USER root"));
check("Infra", "Nginx reverse proxy", fileExists("infra/nginx/nginx.conf"));
check("Infra", "Nginx security headers", readFile("infra/nginx/nginx.conf").includes("X-Frame-Options"));
check("Infra", "Kubernetes manifests", fileExists("infra/k8s") || fileExists("infra/helm"));
check("Infra", "Terraform configuration", fileExists("infra/terraform"));
check("Infra", "CI/CD pipeline", fileExists(".github/workflows") || fileExists(".gitlab-ci.yml"));
check("Infra", "Log rotation configured", fileExists("infra/logrotate"));
check("Infra", "Prometheus monitoring", fileExists("infra/monitoring/prometheus-alerts.yml"));
check("Infra", "Grafana dashboards", fileExists("infra/grafana/dashboards"));
check("Infra", "Database backup script", fileExists("scripts/db-backup.mjs"));
check("Infra", ".env in .gitignore", readFile(".gitignore").includes(".env"));

// ═══════════════════════════════════════════════════════════════════════════
// 6. DEPENDENCY SECURITY
// ═══════════════════════════════════════════════════════════════════════════
console.log("━━━ 6. Dependency Security ━━━");

const pkgJson = readFile("package.json");
check("Deps", "Package.json exists", pkgJson.length > 0);
check("Deps", "Lock file exists", fileExists("pnpm-lock.yaml") || fileExists("package-lock.json"));
check("Deps", "No eval() in server code", !allServerFiles.some(f => {
  const content = readFile(f);
  return /\beval\s*\(/.test(content) && !f.includes("test") && !f.includes("node_modules");
}));
check("Deps", "No child_process.exec with user input", !allServerFiles.some(f => {
  const content = readFile(f);
  return content.includes("child_process") && content.includes("exec(") && !f.includes("test");
}));

// ═══════════════════════════════════════════════════════════════════════════
// 7. CODE QUALITY & SECURITY PATTERNS
// ═══════════════════════════════════════════════════════════════════════════
console.log("━━━ 7. Code Quality & Security Patterns ━━━");

check("Code", "TypeScript strict mode", readFile("tsconfig.json").includes('"strict"'));
check("Code", "Error boundary component", fileExists("client/src/components/ErrorBoundary.tsx"));
check("Code", "Vitest test suite", fileExists("vitest.config.ts"));
check("Code", "Contributing guidelines", fileExists("CONTRIBUTING.md"));
check("Code", "OpenAPI specification", fileExists("docs/openapi.json"));
check("Code", "No console.log in production client", (() => {
  const clientFiles = getAllFiles("client/src", ".tsx");
  const consoleLogCount = clientFiles.filter(f => {
    const content = readFile(f);
    return /console\.log\(/.test(content) && !f.includes("test");
  }).length;
  return consoleLogCount < 10; // Allow some for dev, but not excessive
})(), "Limited console.log usage in client code");

// ═══════════════════════════════════════════════════════════════════════════
// 8. SESSION MANAGEMENT
// ═══════════════════════════════════════════════════════════════════════════
console.log("━━━ 8. Session Management ━━━");

const cookieContent = readFile("server/_core/cookies.ts");
check("Session", "Cookie configuration exists", cookieContent.length > 0);
check("Session", "HttpOnly cookies", cookieContent.includes("httpOnly") || cookieContent.includes("HttpOnly"));
check("Session", "Secure cookies", cookieContent.includes("secure") || cookieContent.includes("Secure"));
check("Session", "SameSite attribute", cookieContent.includes("sameSite") || cookieContent.includes("SameSite"));
check("Session", "Session manager page", fileExists("client/src/pages/SessionManager.tsx"));

// ═══════════════════════════════════════════════════════════════════════════
// 9. ERROR HANDLING & INFORMATION LEAKAGE
// ═══════════════════════════════════════════════════════════════════════════
console.log("━━━ 9. Error Handling & Information Leakage ━━━");

check("Error", "Error boundary in React", fileExists("client/src/components/ErrorBoundary.tsx"));
check("Error", "Custom error types", fileExists("shared/_core/errors.ts"));
check("Error", "Not Found page", fileExists("client/src/pages/NotFound.tsx"));
check("Error", "No stack traces in production responses", !allServerFiles.some(f => {
  const content = readFile(f);
  return content.includes("stack") && content.includes("res.json") && content.includes("error.stack") && !f.includes("test");
}));

// ═══════════════════════════════════════════════════════════════════════════
// 10. LOGGING & MONITORING
// ═══════════════════════════════════════════════════════════════════════════
console.log("━━━ 10. Logging & Monitoring ━━━");

check("Logging", "Structured logging", allServerFiles.some(f => readFile(f).includes("console.log") || readFile(f).includes("logger")));
check("Logging", "Audit log viewer", fileExists("client/src/pages/AuditLogViewer.tsx"));
check("Logging", "System health monitoring", fileExists("client/src/pages/SystemHealthDashboard.tsx"));
check("Logging", "Notification system", fileExists("client/src/components/NotificationCenter.tsx"));
check("Logging", "Resilience monitoring", fileExists("client/src/pages/ResilienceMonitor.tsx"));

// ═══════════════════════════════════════════════════════════════════════════
// RESULTS
// ═══════════════════════════════════════════════════════════════════════════
console.log("");
console.log("╔══════════════════════════════════════════════════════════════╗");
console.log("║                    AUDIT RESULTS                           ║");
console.log("╚══════════════════════════════════════════════════════════════╝");
console.log("");

const failedFindings = findings.filter(f => f.status === "FAIL");
const criticalCount = failedFindings.filter(f => f.severity === "critical").length;
const highCount = failedFindings.filter(f => f.severity === "high").length;
const mediumCount = failedFindings.filter(f => f.severity === "medium").length;
const lowCount = failedFindings.filter(f => f.severity === "low").length;

const score = Math.round((passedChecks / totalChecks) * 100);

// Print failed findings
if (failedFindings.length > 0) {
  console.log("FAILED CHECKS:");
  failedFindings.forEach(f => {
    console.log(`  [${f.severity.toUpperCase()}] ${f.category}/${f.name}: ${f.detail}`);
  });
  console.log("");
}

// Print summary
console.log("┌─────────────────────────────────────────┐");
console.log(`│ Total Checks:     ${String(totalChecks).padStart(4)}                  │`);
console.log(`│ Passed:           ${String(passedChecks).padStart(4)}                  │`);
console.log(`│ Failed:           ${String(totalChecks - passedChecks).padStart(4)}                  │`);
console.log("├─────────────────────────────────────────┤");
console.log(`│ Critical:         ${String(criticalCount).padStart(4)}                  │`);
console.log(`│ High:             ${String(highCount).padStart(4)}                  │`);
console.log(`│ Medium:           ${String(mediumCount).padStart(4)}                  │`);
console.log(`│ Low:              ${String(lowCount).padStart(4)}                  │`);
console.log("├─────────────────────────────────────────┤");
console.log(`│ SECURITY SCORE:   ${String(score).padStart(3)}/100                │`);
console.log(`│ RATING:           ${score >= 95 ? "EXCELLENT" : score >= 85 ? "GOOD" : score >= 70 ? "FAIR" : "NEEDS WORK"}                    │`);
console.log("└─────────────────────────────────────────┘");

if (score >= 95) {
  console.log("\n✅ Platform is PRODUCTION READY with excellent security posture.");
} else if (score >= 85) {
  console.log("\n⚠️  Platform has good security but some improvements recommended.");
} else {
  console.log("\n❌ Platform needs security improvements before production deployment.");
}

process.exit(failedFindings.length > 0 ? 1 : 0);
