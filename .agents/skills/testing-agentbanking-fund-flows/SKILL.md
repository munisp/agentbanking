---
name: testing-agentbanking-fund-flows
description: Test fund flow routers (cashIn, cashOut, NFC, QR, loans, BNPL, FX, etc.) for middleware completeness. Use when verifying tRPC router changes that affect financial transactions.
---

# Testing Agent Banking Fund Flow Routers

## Overview
The platform has 485+ tRPC routers. Financial routers that move money must have up to 10 middleware layers:

**Core (required for all financial mutations):**
1. **FOR UPDATE** — PostgreSQL row-level locking inside `withTransaction()` to prevent race conditions
2. **GL Journal Entries** — Double-entry accounting via `db.insert(gl_journal_entries).values({...})`
3. **Kafka Events** — Domain event publishing via `publishEvent(topic, ref, payload, metadata)`
4. **Idempotency** — Duplicate prevention via `withIdempotency(key, fn)` wrapper
5. **CBN Limits** — Nigerian regulatory daily limits via `checkDailyLimit(db, agentId, tier, amount)`
6. **Audit Log** — Mutation trail via `writeAuditLog({agentId, agentCode, action, resource, ...})`

**Extended (fire-and-forget, fail-open):**
7. **TigerBeetle** — Immutable dual-ledger via `tbCreateTransfer({debitAccountId, creditAccountId, amount, ref, txType, agentCode})`
8. **Fluvio** — Real-time fraud streaming via `publishTxToFluvio({txRef, agentCode, amount, type, timestamp})`
9. **Dapr** — Cross-service pub/sub via `dapr.publishEvent("pubsub", topic, payload)`
10. **Lakehouse** — Analytics pipeline via `ingestToLakehouse(table, data)`

**Optional (context-dependent):**
- **Redis** — Balance cache invalidation via `cacheSet(\`agent:balance:\${id}\`, "", 1)` on balance-affecting mutations

## Environment Setup
- **Primary repo:** `munisp/agentbanking` (default for all work)
- **Branch:** `production-hardened` is the main development branch
- **No live server available** in most sessions — no DATABASE_URL, Redis, or Kafka env vars
- **TypeScript check:** `npx tsc --noEmit` (6 pre-existing client errors in react-i18next and @dnd-kit are expected)
- **Test suite:** `npx vitest run` (5 pre-existing failures in db-performance and sprint46 are expected)
- **Package manager:** pnpm

## Devin Secrets Needed
- `DATABASE_URL` — PostgreSQL connection string (not currently available; testing is shell-based without it)
- No other secrets required for structural validation testing

## Testing Approach (Shell-Based)

### 1. TypeScript Compilation
```bash
npx tsc --noEmit 2>&1 | grep "error TS" | grep -v "react-i18next\|@dnd-kit\|i18next"
```
**Expected:** Zero output (only 6 pre-existing client errors filtered out)

### 2. Vitest Regression
```bash
npx vitest run 2>&1 | grep -E "Test Files|Tests  " | tail -3
```
**Expected:** 4,241+ pass, 5 pre-existing failures, no new failures

### 3. Import Completeness Check
Verify all financial routers have required middleware imports:
```bash
for f in cashIn cashOut agentLoanFacility nfcTapToPay dynamicQrPayment stablecoinRails loyalty commissionPayouts crossBorderRemittance multiCurrencyExchange bnplEngine chargebackManagement reversalApproval ecommerceOrders airtimeVending billPayments splitPayments recurringPayments; do
  FILE="server/routers/$f.ts"
  TB=$(grep -c 'from "../tbClient"' "$FILE")
  FL=$(grep -c 'from "../fluvio"' "$FILE")
  LH=$(grep -c 'from "../lakehouse"' "$FILE")
  DA=$(grep -c 'from "../middleware/middlewareConnectors"' "$FILE")
  MISSING=""
  [ "$TB" -eq 0 ] && MISSING="$MISSING tbClient"
  [ "$FL" -eq 0 ] && MISSING="$MISSING fluvio"
  [ "$LH" -eq 0 ] && MISSING="$MISSING lakehouse"
  [ "$DA" -eq 0 ] && MISSING="$MISSING middlewareConnectors"
  if [ -n "$MISSING" ]; then echo "FAIL $f: missing$MISSING"; else echo "PASS $f"; fi
done
```

### 4. Active Middleware Call Verification
Verify imports aren't dead — each router has actual function calls:
```bash
for f in <router_list>; do
  FILE="server/routers/$f.ts"
  TB=$(grep -c 'tbCreateTransfer(' "$FILE")
  FL=$(grep -c 'publishTxToFluvio(' "$FILE")
  DA=$(grep -c 'dapr.publishEvent(' "$FILE")
  LH=$(grep -c 'ingestToLakehouse(' "$FILE")
  echo "$f: TB=$TB FL=$FL DA=$DA LH=$LH"
done
```
**Pass criteria:** All counts >= 1 for every router.

### 5. Fail-Open Pattern Verification
All extended middleware calls MUST have `.catch(() => {})`. Use Python for multi-line detection:
```python
import re
for fn in ['tbCreateTransfer', 'publishTxToFluvio', 'dapr.publishEvent', 'ingestToLakehouse']:
    for m in re.finditer(fn + r'\(', content):
        chunk = content[m.start():m.start()+500]
        if '.catch(' not in chunk:
            print(f'UNCAUGHT: {fn}')
```
**Important:** Do NOT use single-line grep for this — `tbCreateTransfer` spans multiple lines with `.catch` on the closing `})` line. Naive single-line grep will produce false positives.

### 6. GL Account ID Correctness
Use Python regex for reliable multi-line extraction of GL account pairs:
```python
import re
m = re.search(r'tbCreateTransfer\(\{([^}]+)\}', content)
block = m.group(1)
debit = re.search(r'debitAccountId:\s*"(\d+)"', block)
credit = re.search(r'creditAccountId:\s*"(\d+)"', block)
```
**Do NOT use `grep -A3 | grep -oP`** — it captures debit IDs for both fields due to how multi-line grep works.

### 7. Reversible Operation GL Consistency
Verify that payment/refund pairs use reversed GL account IDs:
- cashIn(1001→2001) ↔ cashOut(2001→1001)
- loanDisburse(2001→2004) ↔ loanRepay(2004→2001)
- nfcPayment(1001→2001) ↔ nfcRefund(2001→1001)

### 8. Dapr Topic + Lakehouse Table Uniqueness
```bash
# Dapr topics should be unique and semantic
grep -rn 'dapr.publishEvent("pubsub"' server/routers/ | grep -oP '"pubsub", "[^"]*"' | sort -u
# Lakehouse tables — each should appear in exactly 1 router
grep -rn 'ingestToLakehouse(' server/routers/ | grep -oP 'ingestToLakehouse\("[^"]*"' | sort | uniq -c | sort -rn
```

## Key GL Account IDs
| ID | Name | Usage |
|----|------|-------|
| 1001 | Cash-on-Hand | Cash deposits/withdrawals |
| 1003 | Stablecoin Holding | Crypto-fiat |
| 2001 | Agent Float | Agent balance operations |
| 2004 | Loan Payable | Loan disbursement/repayment |
| 2005 | Loyalty Payable | Points redemption |
| 3001 | Remittance Payable | Cross-border |
| 3002 | FX Conversion | Currency exchange |
| 4001 | Fee Revenue | Transaction fees/commission payouts |
| 4002 | Penalty Revenue | Late penalties |
| 5001-5004 | Expense accounts | Chargebacks, refunds, loyalty |
| 6001 | Interest Expense | Savings interest accrual |

## Middleware Client Files (Function Signatures)
- `server/tbClient.ts` — `tbCreateTransfer(req: TBTransferRequest)` where `debitAccountId` and `creditAccountId` are **strings** (not numbers)
- `server/fluvio.ts` — `publishTxToFluvio({txRef, agentCode, amount, type, timestamp})`
- `server/redisClient.ts` — `cacheSet(key: string, value: string, ttlSeconds?: number)`
- `server/lakehouse.ts` — `ingestToLakehouse(table: string, data: Record<string, unknown>, source?: string)`
- `server/middleware/middlewareConnectors.ts` — `dapr.publishEvent(pubsubName, topic, data)`

## Key Kafka Topics
All financial events publish to `pos.transactions.created` with a `type` field distinguishing event types (e.g., `nfc_payment`, `qr_payment`, `loan_disbursement`, `stablecoin_created`, `loyalty_redemption`).

## Common Issues
- **`ctx.user` has no `agentCode` property** — The tRPC user context type only has `id`, `keycloakSub`, `name`, `email`, `role`, etc. Use `String(ctx.user?.id ?? "system")` instead of `ctx.user?.agentCode`.
- **`CommissionSplit` has no `commission` property** — Use `agentShare`, `platformShare`, `superAgentShare`, or `aggregatorShare` instead.
- **Duplicate schema imports** — If adding `gl_journal_entries` to a file that already imports from `../../drizzle/schema`, consolidate into one import statement.
- **`input.billerCode` doesn't exist** — The billPayments schema uses `billerId`, not `billerCode`. Always check the Zod schema before referencing input fields.
- **`input.amount` doesn't exist on split payments** — splitPayments uses `input.totalAmount` and `input.splits[].amount`. Check the router's input schema.
- **Multi-line middleware calls** — `tbCreateTransfer({...})` spans 4-5 lines. Testing with single-line grep will miss `.catch()` on the closing line. Use Python or multi-line tools.
- **Script-generated code may have wrong variable names** — When using Python scripts to bulk-add middleware, the script may use generic `ref` or `input.amount` variables that don't exist in the target router's scope. Always verify with `npx tsc --noEmit` after scripted changes.
- **Pre-existing TS errors** — 6 errors in `client/src/components/LanguageSelector.tsx` and `client/src/pages/POSShell.tsx` for missing `react-i18next` and `@dnd-kit` type declarations. These are NOT from your changes.
- **Pre-existing test failures** — `db-performance.test.ts` (4 failures, fetch failed) and `sprint46.test.ts` (1 failure, activePairs 48 vs expected 42).

## Recording
No recording needed for fund flow testing — all validation is shell-based. Only record if testing involves browser UI interactions (e.g., testing the PWA QR scanner page or NFC settings dashboard).
