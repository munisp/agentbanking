---
name: testing-54link-future-features
description: Test the 20 future-proofing features (Open Banking, BNPL, NFC, AI Credit, AgriTech, etc.) end-to-end. Use when verifying tRPC routers, business validation, Flutter/RN components, or integration test suite changes.
---

# Testing 54Link Future-Proofing Features

## Prerequisites

- PostgreSQL running on localhost:5432 (user: `ngapp`, db: `ngapp`)
- Node.js + pnpm installed
- Run `npx drizzle-kit push --force` with `DATABASE_URL` set before starting dev server

## Devin Secrets Needed

- `POSTGRES_PASSWORD` — password for the `ngapp` PostgreSQL user (may need to be reset via `ALTER USER ngapp WITH PASSWORD '...'` if empty)

## Starting the Dev Server

```bash
cd /home/ubuntu/repos/NGApp
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/ngapp"
export REDIS_URL="" PORT=5000 NODE_ENV=development
npx drizzle-kit push --force
pnpm dev
```

**Important**: Use `pnpm dev` (not `npx tsx` directly) — the dev script resolves `@shared/*` path aliases correctly. Plain `npx tsx` will fail with `ERR_MODULE_NOT_FOUND: Cannot find package '@shared/const'`.

The server may auto-increment port if 5000 is busy (check output for "Port X is busy, using port Y instead"). Dev-login bypass: `GET /api/dev-login?returnTo=/`

## Key Architecture Notes

1. **Future feature pages are NOT routable** — lazy imports exist in App.tsx (line ~2192) but NO `<Route>` elements mount them. Sidebar nav links `/future/*` hit the fallback `/:screen` → POSShell route. Test via tRPC API (curl), NOT browser navigation.

2. **tRPC router paths**: `server/routers/{featureName}.ts` — 20 routers with 7 procedures each: `getStats`, `list`, `create`, `getById`, `updateStatus`, `analytics`, `serviceHealth`

3. **Sidebar nav group**: "Future Features" in DashboardLayout.tsx line ~1631, requires admin+ role

4. **Microservices**: 60 services (Go/Rust/Python) on ports 8230-8289. Won't be running locally — `serviceHealth` will report "unhealthy" which is expected.

5. **Middleware health endpoint**: `healthCheck.middlewareHealth` (public procedure) checks all 12 infrastructure services in parallel. Returns `{overall, services: {name: {status, latencyMs, details}}, summary, timestamp}`. All services report "unhealthy" locally since Redis/Kafka/etc. aren't running — this is expected and correct behavior.

6. **Middleware connectors** (`server/middleware/middlewareConnectors.ts`): 12 connector classes with real library imports (KafkaJS, ioredis, tigerbeetle-node). Imported by `serviceOrchestrator.ts` and `mockReplacements.ts`.

7. **New middleware modules** (standalone, not imported by routers):
   - `wafIntegration.ts` — OpenAppSec WAF health, IP reputation, incident reporting
   - `daprEventHandler.ts` — Dapr pub/sub event handler with DLQ
   - `mojaloopCallbacks.ts` — FSPIOP quote flow, settlement callbacks
   - `fluvioIntegration.ts` — Fluvio streaming producer/consumer/topic management

## Testing Strategy

### Infrastructure Component Health
```bash
# Authenticate first
curl -sf -c /tmp/cookies.txt -L "http://localhost:<port>/api/dev-login?returnTo=/" -o /dev/null

# Test middlewareHealth endpoint — should return all 12 services
curl -sf -b /tmp/cookies.txt "http://localhost:<port>/api/trpc/healthCheck.middlewareHealth" | python3 -m json.tool
# Expect: 12 service keys (redis, kafka, tigerbeetle, keycloak, permify, apisix, opensearch, mojaloop, fluvio, dapr, openappsec, temporal)
# Each has: status, latencyMs, details
# overall: "critical" (expected locally), summary: "0/12 services healthy"
```

### Microservice Client Coverage
```bash
# Python: 20 services × 5 clients = 100
for svc in agritech-payments bnpl-engine ...; do
  grep -c 'class \(KeycloakClient\|PermifyClient\|TigerBeetleClient\|APISIXClient\|OpenAppSecClient\)' services/python/$svc/main.py
  # Expect: 5 per service
done

# Rust: 20 services × 5 structs = 100
for svc in agritech-payments bnpl-engine ...; do
  grep -c 'struct \(KeycloakClient\|PermifyClient\|MojaloopClient\|APISIXClient\|OpenAppSecClient\)' services/rust/$svc/src/main.rs
  # Expect: 5 per service, each with matching impl block
done

# Go: 20 services × 2 structs = 40
for svc in agritech-payments bnpl-engine ...; do
  grep -c 'type \(APISIXClient\|OpenAppSecClient\) struct' services/go/$svc/main.go
  # Expect: 2 per service, each with New* constructor
done
```

### Middleware Connector Stub Verification
```bash
# Verify NO stubs remain in middlewareConnectors.ts
grep -c '// In production:' server/middleware/middlewareConnectors.ts  # Expect: 0
grep -c 'import("kafkajs")' server/middleware/middlewareConnectors.ts  # Expect: >= 1
grep -c 'import("ioredis")' server/middleware/middlewareConnectors.ts  # Expect: >= 1
grep -c 'tigerbeetle-node' server/middleware/middlewareConnectors.ts  # Expect: >= 1
```

### Gap 1: Real SQL Aggregations
```bash
# Verify domain-specific stats fields in API response
curl -s http://localhost:<port>/api/trpc/openBankingApi.getStats -b /tmp/cookies.txt | python3 -m json.tool
# Expect: totalPartners, activeKeys, requestsToday, revenueThisMonth

# Verify no formula stats remain
grep -rl "total \* 0.85" server/routers/*.ts  # Should return 0 matches
grep -l "Promise.all" server/routers/openBankingApi.ts  # Should match
```

### Gap 2: Business Validation
```bash
# Test BNPL amount validation (min ₦1,000)
curl -s -X POST http://localhost:<port>/api/trpc/bnplEngine.create \
  -H "Content-Type: application/json" -b /tmp/cookies.txt \
  -d '{"json":{"data":{"amount":500}}}' | python3 -m json.tool
# Expect: BAD_REQUEST with "₦1,000 and ₦5,000,000"

# Test status enum validation
curl -s -X POST http://localhost:<port>/api/trpc/bnplEngine.updateStatus \
  -H "Content-Type: application/json" -b /tmp/cookies.txt \
  -d '{"json":{"id":1,"status":"cancelled"}}' | python3 -m json.tool
# Expect: BAD_REQUEST listing valid statuses
```

### Gap 3 & 4: Flutter/RN Domain Components
```bash
# Flutter: check for domain-specific _build methods
grep -c "_buildInstallmentProgress" mobile-flutter/lib/screens/bnpl_screen.dart
grep -c "_buildCreditScoreGauge" mobile-flutter/lib/screens/ai_credit_screen.dart
# Should return >= 1 each

# React Native: check for domain-specific components
grep -c "InstallmentBar" mobile-rn/src/screens/BnplScreen.tsx
grep -c "CreditGauge" mobile-rn/src/screens/AiCreditScreen.tsx
# Should return >= 1 each

# Verify no generic Object.entries rendering
grep -rl "Object.entries" mobile-flutter/lib/screens/*_screen.dart  # Should return 0
grep -rl "Object.entries" mobile-rn/src/screens/*Screen.tsx  # Should return 0
```

### Gap 5: Integration Test Suite
```bash
npx vitest run tests/integration/future-features.test.ts --reporter=verbose
# Expect: 16/16 tests pass
```

### Docker Compose Validation
```bash
grep -c "^  [a-z].*:" docker-compose.integration-test.yml  # Expect >= 63
grep -c "healthcheck:" docker-compose.integration-test.yml  # Expect >= 60
```

### OpenSearch & Dapr Config Validation
```bash
# OpenSearch index templates and ILM policies
python3 -c "import json; d=json.load(open('infra/opensearch/index-templates.json')); print(len(d['index_templates']), 'templates,', len(d['ilm_policies']), 'ILM policies')"
# Expect: 4 templates, 3 ILM policies

# Dapr subscriptions
grep -c 'topic: pos\.' infra/dapr/subscriptions.yaml
# Expect: 6 topics
```

## Common Issues

- **`ERR_MODULE_NOT_FOUND: @shared/const`**: Use `pnpm dev` instead of `npx tsx server/_core/index.ts`. The pnpm workspace resolves path aliases.
- **POSTGRES_PASSWORD empty**: The env var might not be set. Use `DATABASE_URL="postgresql://postgres:postgres@localhost:5432/ngapp"` directly (postgres:postgres works if the default user wasn't changed).
- **Port busy**: Dev server auto-increments port. Check output for "Port X is busy, using port Y instead"
- **Stats return 0**: Normal — domain tables are empty without seed data. The SQL queries execute correctly.
- **Temporal connection refused**: Expected in local dev — Temporal server not running.
- **`require is not defined` warnings**: Non-fatal — some CJS modules in ESM context. Server still starts.
- **All middleware services "unhealthy"**: Expected locally — Redis, Kafka, TigerBeetle, Keycloak, etc. are not running. The health check correctly detects their absence.
- **redisClient module not found in healthCheck.status**: Pre-existing path resolution issue — the import path `../../redisClient` doesn't resolve correctly in the tsx runner. Does not affect middlewareHealth endpoint.

## Production Readiness Testing (7 Areas + Docker)

This section covers testing the production hardening changes: observability, resilient HTTP, graceful degradation, shutdown handlers, gRPC, security, and Docker optimization.

### Observability Module
```bash
# Must use npx tsx (not node) since these are TypeScript modules
npx tsx -e "
import * as obs from './server/lib/observability';
const fns = ['startSpan','endSpan','withSpan','resetMetrics','getAllEngineMetrics','exportPrometheusMetrics','getEngineMetrics','addSpanEvent','getActiveSpans','getMetricsSummary','structuredLog','logger','recordMetric','getMetrics','getMetricsPrometheus','sendAlert','getActiveAlerts','acknowledgeAlert','requestTimer','extractTraceContext','createTraceparent','settlementTracer','disputeTracer','commissionTracer','fraudTracer','kycTracer'];
const missing = fns.filter(f => typeof (obs as any)[f] !== 'function' && typeof (obs as any)[f] !== 'object');
console.log('Missing:', missing.length > 0 ? missing.join(', ') : 'NONE');
console.log('Total exports verified:', fns.length - missing.length);
"
# Expect: Missing: NONE, Total exports verified: 26
```

### Span Tracking E2E
```bash
npx tsx -e "
import {startSpan, endSpan, resetMetrics, getEngineMetrics, exportPrometheusMetrics} from './server/lib/observability';
resetMetrics();
const span = startSpan('settlement', 'processBatch', {batchSize: 100});
const ended = endSpan(span.spanId, 'ok')!;
const metrics = getEngineMetrics('settlement')!;
const prom = exportPrometheusMetrics();
console.log('spanId:', span.spanId.length === 16 ? 'OK' : 'FAIL');
console.log('traceId:', span.traceId.length === 32 ? 'OK' : 'FAIL');
console.log('status transition:', ended.status === 'ok' ? 'OK' : 'FAIL');
console.log('metrics:', metrics.totalOperations === 1 ? 'OK' : 'FAIL');
console.log('prometheus:', prom.includes('fiveforlink_settlement_operations_total 1') ? 'OK' : 'FAIL');
"
```

### Cross-Service Contract Tests
```bash
npx vitest run tests/integration/cross-service-contracts.test.ts --reporter=verbose
# Expect: 15/15 tests pass (proto, HTTP resilience, degradation, shutdown, security, Docker, DB)
```

### Docker Optimization
```bash
# Count service definitions excluding YAML config keys and volume definitions
node -e "
const fs = require('fs');
const excludeKeys = new Set(['interval','timeout','retries','start_period','condition','context','dockerfile','ports','environment','depends_on','restart','healthcheck','build','test','command','volumes','networks','version','services']);
const count = (c) => {
  const m = c.match(/^\s{2}[a-z][a-z0-9_-]+:/gm);
  if (!m) return 0;
  return m.filter(x => { const k = x.trim().replace(':',''); return !excludeKeys.has(k) && !k.endsWith('-data') && !k.startsWith('x-'); }).length;
};
const opt = fs.readFileSync('docker-compose.optimized.yml','utf-8');
const orig = fs.readFileSync('docker-compose.yml','utf-8');
console.log('Optimized:', count(opt), 'Original:', count(orig), 'Ratio:', (count(opt)/count(orig)).toFixed(3));
"
# Expect: Ratio < 0.7
```

### Shutdown Handler Coverage
```bash
# Python (target >= 90%)
TOTAL=$(find services/python -name "main.py" -not -path "*/test*" | wc -l)
WITH=$(find services/python -name "main.py" -not -path "*/test*" -exec grep -l "SIGTERM\|SIGINT\|signal\|shutdown" {} \; | wc -l)
echo "Python: $WITH/$TOTAL = $(echo "scale=3; $WITH / $TOTAL" | bc)"

# Go (target >= 90%)
TOTAL=$(find services/go -name "main.go" | wc -l)
WITH=$(find services/go -name "main.go" -exec grep -l "SIGTERM\|SIGINT\|signal\|shutdown\|os.Signal" {} \; | wc -l)
echo "Go: $WITH/$TOTAL"

# Rust (target >= 90%)
TOTAL=$(find services/rust -name "main.rs" | wc -l)
WITH=$(find services/rust -name "main.rs" -exec grep -l "SIGTERM\|signal\|shutdown\|ctrl_c" {} \; | wc -l)
echo "Rust: $WITH/$TOTAL"
```

### Security — No Hardcoded Passwords
```bash
grep -n 'password:' k8s/charts/keycloak/values.yaml k8s/charts/mojaloop/values.yaml | grep -v '""' | grep -v "REQUIRED" | grep -v "#"
# Expect: no output (exit code 1)
```

### Business Logic Library Verification (Production Hardening)

Test the domain calculation and transaction helper libraries directly with `npx tsx -e`:

```bash
# Verify domain calculations return exact expected values
npx tsx -e "
import { calculateFee, calculateCommission, calculateTax, calculateVAT } from './server/lib/domainCalculations';
const fee = calculateFee(10000, 'transfer');
console.log('fee:', JSON.stringify(fee));
// Expect: {fee:50, breakdown:{flat:25, percentage:25}}
const comm = calculateCommission(50, 'transfer');
console.log('comm:', JSON.stringify(comm));
// Expect: {agentShare:17.5, platformShare:17.5, superAgentShare:10, aggregatorShare:5}
const tax = calculateTax(50, 'VAT');
console.log('tax:', JSON.stringify(tax));
// Expect: {taxAmount:3.75, netAmount:46.25, taxRate:7.5, taxType:'VAT'}
// NOTE: TAX_RATES keys are UPPERCASE. calculateTax(50, 'vat') returns taxAmount:0
"

# Verify transaction helper functions
npx tsx -e "
import { withTransaction, auditFinancialAction, withIdempotency, validateAmount } from './server/lib/transactionHelper';
console.log('withTransaction:', typeof withTransaction);  // function
console.log('auditFinancialAction:', typeof auditFinancialAction);  // function
auditFinancialAction('UPDATE', 'test', 'id-1', 'test entry');  // should not throw
const v = validateAmount(1000);
console.log('validateAmount(1000):', JSON.stringify(v));  // {valid: true}
// NOTE: validateAmount returns {valid: boolean}, NOT a boolean directly
"

# Verify production hardening middleware metrics
npx tsx -e "
import { getHardeningMetrics } from './server/middleware/productionHardeningMiddleware';
const m = getHardeningMetrics();
console.log(JSON.stringify(m));
// Expect: 9 numeric keys (totalMutations, totalQueries, transactionWrapped, idempotencyHits, auditLogged, slowMutations, slowQueries, feeCalculations, authorizationChecks)
"

# Verify router imports work (catches broken imports/circular deps)
npx tsx -e "
const routers = ['settlement','billingLedger','agentCommissionCalc','amlScreening','fraud'];
for (const r of routers) {
  const mod = require('./server/routers/' + r);
  const key = Object.keys(mod).find(k => k.endsWith('Router'));
  console.log(r + ':', key ? 'OK' : 'MISSING');
}
"
```

### Audit Score Verification

```bash
# Run the deep audit script to verify overall score
python3 /tmp/deep-audit-v2.py
# Expect: OVERALL 9.8/10, 0 routers below 7.0
# Script location may vary — check /tmp/ or /home/ubuntu/ for deep-audit-v2.py
# If missing, the script counts patterns in server/routers/*.ts files:
# db_operations (.select/.insert/.update/.delete), validation (z.xxx()),
# business rules (if()), error handling (TRPCError/try{), calculations (calculateXxx()),
# audit trail (audit/createdAt), tx safety (withTransaction/.transaction()),
# data integrity (eq/and/gte/lte), response quality (return {}), completeness (.query()/.mutation())
```

### Known Issues

- **InviteCodes column name mismatch**: The `invite_codes` table may be created by Drizzle with camelCase columns (`maxUses`, `usedCount`, etc.) but the raw SQL in `inviteCodes.ts` uses snake_case (`max_uses`, `used_count`). The `CREATE TABLE IF NOT EXISTS` in the router is a no-op when the Drizzle-created table already exists, causing INSERT failures. The fallback to in-memory also might not trigger because there's no try/catch around the INSERT itself.
- **Dev server port**: May bind to 5002 or 5003 if lower ports are busy. Always check with `ss -tlnp | grep -E "500[0-9]"` after starting.
- **TypeScript module imports**: Always use `npx tsx -e` (not `node -e`) when testing TypeScript modules like observability.ts or resilientHttpClient.ts.
- **Top-level await not supported**: When using `npx tsx -e` with async functions (e.g., `withIdempotency`), wrap in an async IIFE: `(async () => { ... })()`. Top-level await fails with "not supported with cjs output format".
- **Dev server startup time**: With 477 router files, `pnpm dev` (tsx watch) may take 2+ minutes to start. `npx tsx server/_core/index.ts` (without watch) starts faster. Check port with `ss -tlnp | grep -E "500[0-9]"`.
- **Audit trail noise on startup**: The audit trail module logs ~100 seed entries on startup (`[AUDIT:HIGH] LOGIN...`, `[AUDIT:CRITICAL] APPROVE...`). This is non-blocking.
- **Non-fatal CJS/ESM warnings**: `require is not defined` for shutdown/cron/etag/dbpool-monitor. Server starts and responds correctly despite these.
- **healthCheck.status database "unhealthy"**: Reports `query.getSQL is not a function` — pre-existing Drizzle ORM compatibility issue. Doesn't affect actual DB operations in routers.
- **validateAmount returns object**: `validateAmount(1000)` returns `{valid: true}`, NOT `true`. Check `.valid` property.
- **Tax key casing**: `calculateTax(amount, "vat")` returns 0 because TAX_RATES keys are uppercase ("VAT"). Always use uppercase tax type strings.

## Validation Checklist

- [ ] 20/20 routers have `Promise.all` for SQL aggregations
- [ ] 0/20 routers have formula stats (`total * 0.85`)
- [ ] Business validation rejects invalid input with domain-specific error messages
- [ ] Status enums are DIFFERENT per feature (BNPL ≠ Open Banking ≠ Pension)
- [ ] 29+ unique Flutter `_build` widget methods
- [ ] 20+ unique React Native component names
- [ ] 0 Flutter/RN screens use `Object.entries`
- [ ] 16/16 vitest integration tests pass
- [ ] middlewareHealth returns 12 services with correct structure
- [ ] 0 stub comments ("// In production:") in middlewareConnectors.ts
- [ ] 100/100 Python client classes (20 services × 5 clients)
- [ ] 100/100 Rust client structs + impls (20 services × 5 clients)
- [ ] 40/40 Go client structs + constructors (20 services × 2 clients)
- [ ] OpenSearch: 4 index templates, 3 ILM policies
- [ ] Dapr: 6 subscription topics with content-based routing
- [ ] TypeScript compiles cleanly (`npx tsc --noEmit` exit 0)
