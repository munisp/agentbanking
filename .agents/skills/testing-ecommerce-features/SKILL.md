---
name: testing-ecommerce-features
description: Test ecommerce features (cart, catalog, orders, social commerce, promotions, agent store) end-to-end. Use when verifying middleware integration, persistence patterns, mobile parity, or payment flow changes in ecommerce routers.
---

# Testing Ecommerce Features

## Overview

The ecommerce layer spans 6 TypeScript routers, 1 Go service, 1 Rust service, 1 Python service, 5 Flutter screens, and 5 React Native screens. Each mutation must integrate with the middleware stack and persist to PostgreSQL.

## Environment Setup

- **Repo:** `munisp/agentbanking`
- **Branch:** `production-hardened` is the main development branch
- **No live server** in most sessions — no DATABASE_URL, Redis, Kafka env vars
- **TypeScript check:** `npx tsc --noEmit` (pre-existing errors in react-i18next/@dnd-kit are expected)
- **Test suite:** `npx vitest run` (8 pre-existing failures: db-performance x4, e2e x1, sprint46 x1, sprint95 x1, middleware-runtime x2)
- **Package manager:** pnpm

## Devin Secrets Needed

- `DATABASE_URL` — PostgreSQL connection string (not currently available; testing is shell-based)
- No other secrets required for structural validation

## Key Files

- **TS Routers:** `server/routers/ecommerceOrders.ts`, `ecommerceCatalog.ts`, `ecommerceCart.ts`, `agentStore.ts`, `promotions.ts`, `socialCommerceGateway.ts`
- **Kafka topics:** `server/kafkaClient.ts` (KafkaTopic union type)
- **Rust cart:** `server/ecommerce-cart-rust/src/{main,cart,checkout,offline}.rs`
- **Go catalog:** `server/ecommerce-catalog-go/handlers/handlers.go`
- **Python intelligence:** `server/ecommerce-intelligence-py/main.py`
- **Migration:** `drizzle/drizzle/0044_ecommerce_enhancements.sql`
- **Flutter screens:** `mobile-flutter/mobile-flutter/lib/screens/ecommerce_*.dart`
- **RN screens:** `mobile-rn/mobile-rn/src/screens/Ecommerce*.tsx`
- **Middleware clients:** `server/tbClient.ts`, `server/fluvio.ts`, `server/lakehouse.ts`, `server/redisClient.ts`, `server/middleware/middlewareConnectors.ts`

## Testing Approach (Shell-Based Structural Validation)

### 1. TypeScript Compilation

```bash
npx tsc --noEmit 2>&1 | grep "error TS" | grep -E "ecommerceOrders|ecommerceCatalog|ecommerceCart|agentStore|promotions|socialCommerce|kafkaClient"
```

**Expected:** Zero output (0 errors in modified ecommerce files)

### 2. Middleware Active Calls (NOT Dead Code)

This is the MOST IMPORTANT test. PR #46/#48 had middleware helpers defined but never called. Check that each router has active calls (total - 1 definition >= 3):

```bash
for f in ecommerceCatalog ecommerceCart agentStore promotions socialCommerceGateway ecommerceOrders; do
  FILE="server/routers/$f.ts"
  TOTAL=$(grep -c "publish.*Middleware(" "$FILE")
  ACTIVE=$((TOTAL - 1))
  echo "$f: $ACTIVE active calls $([ $ACTIVE -ge 3 ] && echo PASS || echo FAIL)"
done
```

### 3. Fail-Open Pattern

Extract each router's middleware helper body and verify .catch() count >= middleware call count:

```bash
for f in ecommerceCatalog ecommerceCart agentStore promotions socialCommerceGateway ecommerceOrders; do
  FILE="server/routers/$f.ts"
  HELPER_BODY=$(sed -n '/async function publish.*Middleware/,/^}/p' "$FILE")
  MW=$(echo "$HELPER_BODY" | grep -c "publishEvent\|tbCreateTransfer\|publishTxToFluvio\|dapr.publishEvent\|ingestToLakehouse\|cacheSet")
  CATCH=$(echo "$HELPER_BODY" | grep -c '\.catch(')
  echo "$f: $MW calls, $CATCH catches — $([ $CATCH -ge $MW ] && echo PASS || echo FAIL)"
done
```

### 4. Rust Cart Persistence

```bash
# DashMap must be fully eliminated
grep -rn "DashMap\|dashmap" server/ecommerce-cart-rust/src/
# Should return 0 matches

# PostgreSQL must be present
grep -c "PgPool" server/ecommerce-cart-rust/src/main.rs   # >= 3
grep -c "sqlx::query" server/ecommerce-cart-rust/src/cart.rs  # >= 10
grep -c "sqlx::query" server/ecommerce-cart-rust/src/checkout.rs  # >= 5
grep -c "sqlx::query" server/ecommerce-cart-rust/src/offline.rs  # >= 5
```

### 5. KafkaTopic Union

All topics used in publishEvent calls must exist in the KafkaTopic union in `server/kafkaClient.ts`:

```bash
USED=$(grep -ohP 'publishEvent\("([^"]+)"' server/routers/ecommerce*.ts server/routers/agentStore.ts server/routers/promotions.ts server/routers/socialCommerceGateway.ts | sed 's/publishEvent("//;s/"//' | sort -u)
for topic in $USED; do
  [ "$topic" = "pubsub" ] && continue
  grep -q "\"$topic\"" server/kafkaClient.ts && echo "PASS: $topic" || echo "FAIL: $topic"
done
```

### 6. TigerBeetle Type Safety

socialCommerceGateway previously used BigInt() which mismatched TBTransferRequest (expects string/number):

```bash
grep -c "BigInt" server/routers/socialCommerceGateway.ts
# Must be 0
```

### 7. ecommerceOrders Key Features

```bash
# New endpoints exist
for ep in recoverAbandonedCarts releaseExpiredReservations checkoutFlashSale getDeliveryTracking updateDeliveryTracking convertOrderCurrency; do
  grep -q "$ep:" server/routers/ecommerceOrders.ts && echo "PASS: $ep" || echo "FAIL: $ep"
done

# Payment verification wired to createFromCart
grep -A 200 "createFromCart:" server/routers/ecommerceOrders.ts | head -200 | grep -c "verifyPaymentGateway"  # >= 1

# Notifications wired to updateStatus
grep -A 200 "updateStatus:" server/routers/ecommerceOrders.ts | head -200 | grep -c "sendOrderNotification"  # >= 1

# Flash sale FOR UPDATE locking
grep -A 50 "checkoutFlashSale:" server/routers/ecommerceOrders.ts | head -50 | grep -c "FOR UPDATE"  # >= 1
```

### 8. Go Catalog Events

```bash
grep -c "publishCatalogEvent.*inventory" server/ecommerce-catalog-go/handlers/handlers.go
# >= 3 (reserved, released, deducted)
```

### 9. Python Innovation Endpoints

```bash
for ep in "checkout-adjust" "offline-bundle" "barcode-to-cart"; do
  grep -q "$ep" server/ecommerce-intelligence-py/main.py && echo "PASS: $ep" || echo "FAIL: $ep"
done
```

### 10. Migration DDL

```bash
TABLE_COUNT=$(grep -ci "CREATE TABLE" drizzle/drizzle/0044_ecommerce_enhancements.sql)
INDEX_COUNT=$(grep -ci "CREATE INDEX" drizzle/drizzle/0044_ecommerce_enhancements.sql)
echo "Tables: $TABLE_COUNT (expect 12), Indexes: $INDEX_COUNT (expect 11)"
```

### 11. Mobile Screens (Not Scaffolds)

Scaffold screens had 0 API calls and ~131/163 lines. Real screens should have >= 2 API calls:

```bash
for f in ecommerce_shopping_cart_screen ecommerce_product_catalog_screen ecommerce_checkout_screen; do
  FILE="mobile-flutter/mobile-flutter/lib/screens/$f.dart"
  API=$(grep -c "ApiService\|\.get(\|\.post(" "$FILE")
  echo "Flutter $f: $API API calls (>=2 = real)"
done
for f in EcommerceShoppingCartScreen EcommerceProductCatalogScreen EcommerceCheckoutScreen; do
  FILE="mobile-rn/mobile-rn/src/screens/$f.tsx"
  API=$(grep -c "apiService\.\|\.get(\|\.post(" "$FILE")
  echo "RN $f: $API API calls (>=2 = real)"
done
```

## Common Issues

### Dead middleware code (PR #46/#48 bug)

The `publishXxxMiddleware()` helper can be defined but never called from mutation handlers. Always verify active call count, not just that the function exists. Count total references minus 1 (the definition).

### BigInt vs String in TigerBeetle

`TBTransferRequest` expects `debitAccountId: string` and `creditAccountId: string`. Using `BigInt()` causes TS2322. Use `String()` instead.

### agentStore input field names

- `createDeliveryZone` uses `input.zoneName` (not `input.name`)
- `createPaymentSplit` uses `input.orderTotal` (not `input.orderAmount`)
  Check Zod schema before referencing input fields.

### Multi-line middleware calls

`tbCreateTransfer({...}).catch()` spans 4-5 lines. Single-line grep for `.catch()` will miss it. Use `sed` to extract the helper body first, then count within the block.

### Rust DashMap → PgPool migration

After migration, check both directions:

1. **Negative:** 0 DashMap/dashmap references in src/
2. **Positive:** PgPool in AppState + sqlx::query calls in every handler

### Pre-existing failures

These are known and unrelated to ecommerce:

1. `db-performance.test.ts` x4 (needs PgBouncer)
2. `e2e/critical-flows.spec.ts` x1 (needs live server)
3. `sprint46.test.ts` x1 (currency count)
4. `sprint95.test.ts` x1 (router count hardcoded)
5. `middleware-integration-runtime.test.ts` x2 (needs live Redis)

## Recording

No recording needed — all validation is shell-based. Only record if testing involves browser UI interactions (e.g., testing the PWA storefront or checkout flow with a live server).
