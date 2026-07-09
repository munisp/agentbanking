---
name: testing-persistence-elimination
description: Test that in-memory state has been eliminated from polyglot services (Go/Rust/Python/TypeScript) and replaced with PostgreSQL. Use when verifying persistence migrations or statelessness claims.
---

# Testing Persistence Elimination

## Overview

When services migrate from in-memory state to PostgreSQL, both sides must be verified:

1. **Negative proof**: No mutable module-level state patterns remain
2. **Positive proof**: All state operations route through DB queries

## Devin Secrets Needed

- `DATABASE_URL` — For runtime validation (optional; structural testing works without it)

## Testing Approach (Shell-Based Structural Validation)

### Go — Detect In-Memory State

```bash
# Mutable module-level maps/slices (exclude static config like allPermissions)
grep -n "^var.*map\[" service.go | grep -v "allPermissions\|allRoles\|incompatiblePairs"
# Should return 0 matches
```

### Go — Verify PostgreSQL

```bash
# Must have all of: database/sql import, lib/pq driver, initDB(), and query calls
grep -c '"database/sql"' service.go       # >= 1
grep -c 'db.QueryContext\|db.ExecContext' service.go  # >= 1
grep -c 'db.BeginTx' service.go           # >= 1 (for transactional writes)
```

### Rust — Detect In-Memory State

```bash
# Mutex<Vec<...>> or static mut or lazy_static are red flags
grep -n "Mutex\|static mut\|lazy_static" src/main.rs
# Should return 0 matches if fully migrated
```

### Rust — Verify PostgreSQL

```bash
grep -c 'use sqlx' src/main.rs            # >= 1
grep -c 'PgPool' src/main.rs              # >= 1 (in AppState)
grep -c 'sqlx::query' src/main.rs         # >= 3 (one per handler minimum)
```

### Python — Detect In-Memory State

```bash
# Module-level mutable assignments (dicts, lists, sets used as stores)
grep -n "^[a-z_]*: dict\|^[a-z_]*: list\|^[a-z_]*: set\|^[a-z_]* = {}\|^[a-z_]* = \[\]\|^[a-z_]* = set()" main.py
# Should return 0 matches (exclude type annotations without assignment)
```

### Python — Verify PostgreSQL

```bash
grep -c 'import asyncpg\|import psycopg' main.py  # >= 1
grep -c 'create_pool\|connect(' main.py            # >= 1
grep -c 'conn.execute\|conn.fetch\|conn.fetchrow\|conn.fetchval' main.py  # >= 1 per endpoint
```

### TypeScript — Detect In-Memory State

```bash
# Module-level Maps, arrays, or Sets used as data stores
grep -n "new Map<\|const.*Map<\|const.*\[\] =" middleware.ts | grep -v "//\|import"
# Should return 0 matches
```

### TypeScript — Verify PostgreSQL

```bash
# Each persistence function must have db.execute calls
for fn in functionName1 functionName2; do
  COUNT=$(sed -n "/export async function $fn/,/^export /p" file.ts | grep -c "db.execute")
  echo "$fn: $COUNT db.execute calls"  # Each should be >= 1
done
```

### Async Correctness

When functions change from sync to async, ALL callers must be updated:

```bash
# Find all call sites and verify they use await
grep -n "functionName(" router.ts | grep -v "import\|from" | grep -v "await"
# Should return 0 matches (all calls must be awaited)
```

## Key Patterns to Watch For

- **False positives on Go**: `var allPermissions = []Permission{...}` is STATIC config (never mutated at runtime), not in-memory state. Exclude these.
- **Python `pool` variable**: A connection pool variable (`pool: Optional[asyncpg.Pool] = None`) is infrastructure, not business state. This is acceptable.
- **TypeScript `getDb()`**: The singleton DB connection is fine — it's the connection, not stored data.
- **Rust `web::Data<AppState>`**: If `AppState` contains only `PgPool` + config, it's fine. Red flag: any `Mutex<Vec<...>>` or `RwLock<HashMap<...>>` inside it.

## CI Checks

- `Validate DB Migrations` CI job verifies the SQL migration files are syntactically valid
- TypeScript compilation: `npx tsc --noEmit` (6 pre-existing errors in react-i18next/@dnd-kit are expected)
- Test suite: `npx vitest run` (5-7 pre-existing failures in db-performance/sprint46/middleware-runtime are expected)
