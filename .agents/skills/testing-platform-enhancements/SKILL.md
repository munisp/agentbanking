---
name: testing-platform-enhancements
description: Test platform enhancement features (KYC tiering, Temporal sagas, transactional outbox, i18n, settlement engine, polyglot services). Use when verifying middleware integration, persistence patterns, or UI/UX parity across PWA/Flutter/RN.
---

# Testing Platform Enhancements

## Overview
The platform has 32 enhancement features spanning KYC/KYB/Liveness, Flow of Funds, and UI/UX. Each feature must integrate with the full middleware stack and persist state to PostgreSQL.

## Environment Setup
- **Repo:** `munisp/agentbanking`
- **Branch:** `production-hardened` is the main development branch
- **No live server** in most sessions — no DATABASE_URL, Redis, Kafka env vars
- **TypeScript check:** `npx tsc --noEmit` (2 pre-existing errors in react-i18next are expected)
- **Test suite:** `npx vitest run` (8 pre-existing failures: db-performance×4, e2e×1, sprint46×1, sprint95×1, middleware-runtime×1)
- **Package manager:** pnpm

## Devin Secrets Needed
- `DATABASE_URL` — PostgreSQL connection string (not currently available; testing is shell-based)
- No other secrets required for structural validation

## Key Files
- **Middleware clients:** `server/lib/daprClient.ts`, `server/lib/lakehouseClient.ts`, `server/lib/cacheClient.ts`
- **KYC middleware:** `server/middleware/kycTieredLimits.ts`
- **Settlement engine:** `server/middleware/settlementEngine.ts`
- **Outbox pattern:** `server/middleware/transactionalOutbox.ts`
- **Saga orchestrator:** `server/routers/temporalSagaOrchestrator.ts`
- **i18n:** `client/src/lib/i18n.ts` (6 locales: en/ha/yo/pcm/fr/ig)
- **Migration:** `drizzle/0044_kyc_fof_platform_enhancements.sql` (18 tables)
- **Go services:** `services/go/kyc-nfc-attestation/main.go`, `services/go/reconciliation-engine/main.go`
- **Rust service:** `services/rust/kyc-verifiable-credentials/src/main.rs`
- **Python service:** `services/python/kyc-behavioral-biometrics/main.py`

## Testing Approach (Shell-Based Structural Validation)

### 1. TypeScript Compilation
```bash
npx tsc --noEmit 2>&1 | grep "error TS" | grep -v "react-i18next\|@dnd-kit"
```
**Expected:** Zero output (only 2 pre-existing errors filtered out)

### 2. Middleware Client Export Verification
```bash
for lib in daprClient lakehouseClient cacheClient; do
  FILE="server/lib/$lib.ts"
  EXPORTS=$(grep -c "^export" "$FILE")
  echo "$lib: $EXPORTS exports"
done
```
**Expected:** daprClient≥4, lakehouseClient≥3, cacheClient≥5

### 3. publishEvent Signature Check
All publishEvent calls must have 3+ arguments (topic, key, payload):
```bash
grep -n 'publishEvent(' server/middleware/kycTieredLimits.ts server/middleware/settlementEngine.ts server/middleware/transactionalOutbox.ts server/routers/temporalSagaOrchestrator.ts | grep -v "import\|//" | while read line; do
  COMMAS=$(echo "$line" | tr -cd ',' | wc -c)
  if [ "$COMMAS" -lt 2 ]; then echo "FAIL: $line"; fi
done
```

### 4. Fail-Open Pattern
Every middleware call (daprPublish, fluvioPublish, lakehouseIngest, tbCreateTransfer) must have `.catch()`:
```bash
for FILE in server/middleware/kycTieredLimits.ts server/middleware/settlementEngine.ts server/middleware/transactionalOutbox.ts server/routers/temporalSagaOrchestrator.ts; do
  MW=$(grep -c "daprPublish\|fluvioPublish\|lakehouseIngest\|tbCreateTransfer" "$FILE")
  CATCH=$(grep -c '\.catch(' "$FILE")
  echo "$(basename $FILE): $MW calls, $CATCH .catch() — $([ $CATCH -ge $MW ] && echo PASS || echo FAIL)"
done
```

### 5. Polyglot Persistence (No In-Memory State)
```bash
# Go — no mutable maps, has database/sql + lib/pq + queries
for SVC in services/go/kyc-nfc-attestation/main.go services/go/reconciliation-engine/main.go; do
  MEM=$(grep -c "^var.*map\[" "$SVC")
  SQL=$(grep -c '"database/sql"' "$SVC")
  PQ=$(grep -c '_ "github.com/lib/pq"' "$SVC")
  Q=$(grep -c 'db.QueryRow\|db.Query\|db.Exec' "$SVC")
  echo "$SVC: mem=$MEM(expect 0), sql=$SQL(≥1), pq=$PQ(≥1), queries=$Q(≥3)"
done

# Rust — no Mutex/static mut, has sqlx + PgPool
SVC="services/rust/kyc-verifiable-credentials/src/main.rs"
echo "Rust: mutex=$(grep -c 'Mutex<Vec\|static mut\|lazy_static' $SVC)(expect 0), sqlx=$(grep -c 'use sqlx\|sqlx::' $SVC)(≥1), pgpool=$(grep -c PgPool $SVC)(≥1)"

# Python — no module-level dicts/sets, has asyncpg
SVC="services/python/kyc-behavioral-biometrics/main.py"
echo "Python: mem=$(grep -n '^[a-z_]* = {}\|^[a-z_]* = \[\]' $SVC | grep -v '#' | wc -l)(expect 0), asyncpg=$(grep -c asyncpg $SVC)(≥1)"
```

### 6. CBN Tiered Limits
Note: Values use underscore separators (e.g., `5_000_000` not `5000000`):
```bash
grep -n "dailyLimit:" server/middleware/kycTieredLimits.ts | head -5
# Expected: 5_000_000 (₦50K), 20_000_000 (₦200K), 500_000_000 (₦5M)
```

### 7. Fee Waterfall Verification
```bash
grep -n "0\.40\|0\.35\|0\.20\|platformShare\|agentShare\|superAgentShare\|taxShare" server/middleware/settlementEngine.ts | head -10
# Expected: 40%/35%/20%/remainder pattern with 4 TigerBeetle transfers
```

### 8. Migration DDL
```bash
MIGRATION="drizzle/0044_kyc_fof_platform_enhancements.sql"
echo "Tables: $(grep -ci 'CREATE TABLE' $MIGRATION)"
for TBL in liveness_cooldown kyc_tiers event_outbox event_dead_letter settlement_batches fee_waterfall float_threshold_alerts; do
  grep -qi "$TBL" "$MIGRATION" && echo "PASS: $TBL" || echo "FAIL: $TBL"
done
```

### 9. i18n Language Completeness
The sprint19 and sprint27 tests verify i18n exports. Run them directly:
```bash
npx vitest run server/sprint19.test.ts server/sprint27.test.ts 2>&1 | grep "✓\|×"
```
**Expected:** All tests pass (6 languages with changeLanguage export and default export)

### 10. PWA/Mobile Feature Parity
```bash
for COMP in OfflineStatusBanner SpeechToFormInput AdaptiveUI QuickActions KycVerificationFlow; do
  [ -f "client/src/components/$COMP.tsx" ] && echo "PASS: $COMP" || echo "FAIL: $COMP"
done
for SCR in biometric_login_screen kyc_full_flow_screen; do
  [ -f "mobile-flutter/mobile-flutter/lib/screens/$SCR.dart" ] && echo "PASS: $SCR" || echo "FAIL: $SCR"
done
for SCR in BiometricLoginScreen KycFullFlowScreen; do
  [ -f "mobile-rn/mobile-rn/src/screens/$SCR.tsx" ] && echo "PASS: $SCR" || echo "FAIL: $SCR"
done
```

## Common Issues

### i18n backward compatibility
The i18n module (`client/src/lib/i18n.ts`) must export:
- `changeLanguage(code)` — for LanguageSelector component
- `export default i18n` — for components using `i18n.t()`
- All 6 locales in the `translations` object (not just the type)

If sprint19/sprint27 tests fail after modifying i18n, check these exports are present.

### Numeric literals in grep
CBN tier limits use TypeScript numeric separators (`5_000_000` not `5000000`). Adjust grep patterns accordingly.

### Pre-existing test failures
These 8 failures are known and unrelated to platform enhancements:
1. `server/db-performance.test.ts` (4) — needs PgBouncer
2. `tests/e2e/critical-flows.spec.ts` (1) — needs live server
3. `server/sprint46.test.ts` (1) — multiCurrencyExchange currencies
4. `server/sprint95.test.ts` (1) — router count (hardcoded expectation of 481)
5. `tests/middleware-integration-runtime.test.ts` (1) — needs live Redis
