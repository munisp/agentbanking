# 54Link Database Migration Strategy

## Overview

The platform uses **Drizzle ORM** with a PostgreSQL database. This document defines the strategy for safe, versioned database migrations in production.

## Current State

- Schema defined in `drizzle/schema.ts` (5,141 lines, 198+ tables)
- Development uses `npx drizzle-kit push` for rapid iteration
- Production MUST use versioned migrations for audit trail and rollback capability

## Migration Workflow

### 1. Generate Migration

After modifying `drizzle/schema.ts`:

```bash
# Generate a new migration file
npx drizzle-kit generate --name="describe-your-change"

# This creates: drizzle/migrations/YYYYMMDDHHMMSS_describe-your-change.sql
```

### 2. Review Migration

```bash
# Review the generated SQL
cat drizzle/migrations/$(ls -t drizzle/migrations/ | head -1)

# Verify it does what you expect — check for:
# - Destructive operations (DROP TABLE, DROP COLUMN)
# - Data loss risk (ALTER COLUMN with type change)
# - Lock-heavy operations (ALTER TABLE on large tables)
```

### 3. Test on Staging

```bash
# Apply to staging database
DATABASE_URL=$STAGING_DB_URL npx drizzle-kit migrate

# Run integration tests against staging
npm run test:integration -- --env=staging
```

### 4. Apply to Production

```bash
# Production migration (within maintenance window for destructive changes)
DATABASE_URL=$PROD_DB_URL npx drizzle-kit migrate

# Verify migration applied
psql $PROD_DB_URL -c "SELECT * FROM drizzle.__drizzle_migrations ORDER BY created_at DESC LIMIT 5;"
```

### 5. Rollback (if needed)

Drizzle doesn't auto-generate rollback SQL. For each migration, manually create a rollback script:

```bash
# Create rollback file alongside migration
# drizzle/migrations/YYYYMMDDHHMMSS_describe-your-change.rollback.sql
```

Example:

```sql
-- Migration: add email_verified column
ALTER TABLE users ADD COLUMN email_verified boolean DEFAULT false;

-- Rollback: remove email_verified column
ALTER TABLE users DROP COLUMN IF EXISTS email_verified;
```

## Production Migration Rules

### MUST follow

1. **Never use `drizzle-kit push` in production** — always use versioned migrations
2. **All migrations must be reviewed** by at least one other engineer
3. **Destructive migrations require a maintenance window** (DROP TABLE, DROP COLUMN, type changes)
4. **Always backup before migrating**: `pg_dump -Fc $DATABASE_URL > pre-migration-$(date +%s).dump`
5. **Test on staging first** — no exceptions
6. **One migration per PR** — don't bundle unrelated schema changes

### Non-destructive (safe to apply anytime)

- `CREATE TABLE`
- `ADD COLUMN` (with DEFAULT)
- `CREATE INDEX CONCURRENTLY` (non-blocking)
- `ADD CONSTRAINT` (CHECK, NOT NULL with DEFAULT)

### Destructive (requires maintenance window)

- `DROP TABLE` / `DROP COLUMN`
- `ALTER COLUMN` (type change)
- `CREATE INDEX` (without CONCURRENTLY — locks table)
- `RENAME TABLE` / `RENAME COLUMN`

## CI Integration

The `db-migration-check.yml` workflow validates:

1. Schema and migrations are in sync (`drizzle-kit check`)
2. No pending migrations exist without a corresponding rollback script
3. Generated SQL doesn't contain `DROP` without explicit approval label

## Environment Configuration

```bash
# Development — direct push allowed
NODE_ENV=development
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ngapp
DRIZZLE_MIGRATION_MODE=push

# Staging — migrations only
NODE_ENV=staging
DATABASE_URL=$STAGING_DB_URL
DRIZZLE_MIGRATION_MODE=migrate

# Production — migrations only, with additional safety checks
NODE_ENV=production
DATABASE_URL=$PROD_DB_URL
DRIZZLE_MIGRATION_MODE=migrate
DRIZZLE_REQUIRE_ROLLBACK=true
```
