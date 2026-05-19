#!/usr/bin/env node
// SECURITY-AUDIT-TOOL: This file is a security scanner. References to eval/XSS/CORS are detection patterns, not vulnerabilities.
/**
 * Security Audit — 54Link POS Shell (Sprint 41)
 * Comprehensive vulnerability scan across all code.
 * Usage: node scripts/security-audit-sprint41.mjs
 */
import fs from "fs";
import path from "path";

const PROJECT_ROOT = process.cwd();
let totalVulns = 0;
let fixedVulns = 0;
const findings = [];

function scan(dir, extensions = [".ts", ".tsx", ".mjs", ".js"]) {
  const files = [];
  function walk(d) {
    for (const entry of fs.readdirSync(d, { withFileTypes: true })) {
      const full = path.join(d, entry.name);
      if (entry.isDirectory() && !entry.name.startsWith(".") && entry.name !== "node_modules" && entry.name !== "dist") {
        walk(full);
      } else if (entry.isFile() && extensions.some(ext => entry.name.endsWith(ext))) {
        files.push(full);
      }
    }
  }
  walk(dir);
  return files;
}

function check(file, content) {
  const rel = path.relative(PROJECT_ROOT, file);
  
  // 1. Hardcoded secrets
  const secretPatterns = [
    { regex: /sk_live_[a-zA-Z0-9]{20,}/, name: "Stripe Live Key" },
    { regex: /AKIA[A-Z0-9]{16}/, name: "AWS Access Key" },
    { regex: /password\s*[:=]\s*["'][^"']{8,}["'](?!.*example|placeholder|test|mock)/i, name: "Hardcoded Password" },
    { regex: /api[_-]?key\s*[:=]\s*["'][a-zA-Z0-9]{20,}["']/i, name: "Hardcoded API Key" },
    { regex: /-----BEGIN (RSA |EC )?PRIVATE KEY-----/, name: "Private Key" },
  ];
  for (const { regex, name } of secretPatterns) {
    if (regex.test(content)) {
      findings.push({ file: rel, severity: "CRITICAL", type: name, desc: `Found ${name} in source code` });
      totalVulns++;
    }
  }

  // 2. SQL Injection
  if (/\$\{.*\}.*(?:SELECT|INSERT|UPDATE|DELETE|DROP|ALTER)/i.test(content) && !content.includes("drizzle")) {
    findings.push({ file: rel, severity: "HIGH", type: "SQL Injection", desc: "Potential SQL injection via template literal" });
    totalVulns++;
  }

  // 3. XSS via dangerouslySetInnerHTML
  if (/dangerouslySetInnerHTML/.test(content)) {
    findings.push({ file: rel, severity: "MEDIUM", type: "XSS Risk", desc: "dangerouslySetInnerHTML usage detected" });
    totalVulns++;
  }

  // 4. eval() usage
  if (/\beval\s*\(/.test(content) && !file.includes("node_modules")) {
    findings.push({ file: rel, severity: "HIGH", type: "Code Injection", desc: "eval() usage detected" });
    totalVulns++;
  }

  // 5. Unvalidated redirects
  if (/res\.redirect\(.*req\.(?:query|body|params)/.test(content)) {
    findings.push({ file: rel, severity: "MEDIUM", type: "Open Redirect", desc: "Unvalidated redirect using user input" });
    totalVulns++;
  }

  // 6. Missing input validation on tRPC procedures
  if (/publicProcedure\s*\.mutation\(/.test(content) && !/\.input\(/.test(content)) {
    // Only flag if no input validation at all
    const mutations = content.match(/publicProcedure\s*\.mutation\(/g);
    if (mutations && mutations.length > 0) {
      findings.push({ file: rel, severity: "LOW", type: "Missing Validation", desc: "Public mutation without input schema validation" });
      totalVulns++;
    }
  }

  // 7. CORS wildcard
  if (/origin:\s*["']\*["']/.test(content) || /Access-Control-Allow-Origin.*\*/.test(content)) {
    findings.push({ file: rel, severity: "MEDIUM", type: "CORS Misconfiguration", desc: "Wildcard CORS origin detected" });
    totalVulns++;
  }

  // 8. Insecure cookie settings
  if (/secure\s*:\s*false/.test(content) && !file.includes("test")) {
    findings.push({ file: rel, severity: "MEDIUM", type: "Insecure Cookie", desc: "Cookie with secure: false" });
    totalVulns++;
  }

  // 9. Console.log with sensitive data
  if (/console\.log\(.*(?:password|secret|token|key|credential)/i.test(content) && !file.includes("test")) {
    findings.push({ file: rel, severity: "LOW", type: "Info Leak", desc: "Logging potentially sensitive data" });
    totalVulns++;
  }

  // 10. Missing rate limiting on auth endpoints
  if (/auth|login|register/i.test(rel) && !/rateLimit|throttle/i.test(content)) {
    // Only flag actual auth route handlers
    if (/router|app\.(post|get)|mutation/.test(content)) {
      findings.push({ file: rel, severity: "LOW", type: "Missing Rate Limit", desc: "Auth endpoint without rate limiting" });
      totalVulns++;
    }
  }
}

console.log("🔒 54Link POS Shell — Security Audit (Sprint 41)");
console.log("═".repeat(60));

const files = scan(PROJECT_ROOT);
console.log(`\nScanning ${files.length} source files...\n`);

for (const file of files) {
  const content = fs.readFileSync(file, "utf-8");
  check(file, content);
}

// Categorize findings
const critical = findings.filter(f => f.severity === "CRITICAL");
const high = findings.filter(f => f.severity === "HIGH");
const medium = findings.filter(f => f.severity === "MEDIUM");
const low = findings.filter(f => f.severity === "LOW");

console.log("📊 Vulnerability Summary:");
console.log(`   CRITICAL: ${critical.length}`);
console.log(`   HIGH:     ${high.length}`);
console.log(`   MEDIUM:   ${medium.length}`);
console.log(`   LOW:      ${low.length}`);
console.log(`   TOTAL:    ${totalVulns}`);

if (findings.length > 0) {
  console.log("\n📋 Detailed Findings:");
  for (const f of findings) {
    console.log(`   [${f.severity}] ${f.type} — ${f.file}`);
    console.log(`           ${f.desc}`);
  }
}

// Calculate security score
const maxScore = 100;
const deductions = critical.length * 25 + high.length * 15 + medium.length * 5 + low.length * 2;
const score = Math.max(0, maxScore - deductions);

console.log(`\n${"═".repeat(60)}`);
console.log(`🏆 Security Score: ${score}/100`);
if (score >= 90) console.log("   Grade: A — Excellent security posture");
else if (score >= 80) console.log("   Grade: B — Good security, minor improvements needed");
else if (score >= 70) console.log("   Grade: C — Acceptable, address medium/high issues");
else if (score >= 60) console.log("   Grade: D — Below standard, immediate action required");
else console.log("   Grade: F — Critical vulnerabilities must be fixed immediately");
console.log(`${"═".repeat(60)}`);

// Write report
const report = {
  timestamp: new Date().toISOString(),
  filesScanned: files.length,
  totalVulnerabilities: totalVulns,
  score,
  findings,
  summary: { critical: critical.length, high: high.length, medium: medium.length, low: low.length },
};
fs.writeFileSync(path.join(PROJECT_ROOT, "security-audit-report.json"), JSON.stringify(report, null, 2));
console.log("\n📄 Full report saved to security-audit-report.json");
