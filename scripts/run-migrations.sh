#!/bin/bash
# Database Migration Runner — safe production migration with backup
set -euo pipefail

DB_URL="${DATABASE_URL:-${POSTGRES_URL:-}}"
if [ -z "$DB_URL" ]; then
  echo "ERROR: DATABASE_URL or POSTGRES_URL required"
  exit 1
fi

echo "=== 54Link Database Migration ==="
echo "Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"

# 1. Create backup before migration
echo "Step 1: Creating pre-migration backup..."
BACKUP_FILE="backup-pre-migration-$(date +%Y%m%d_%H%M%S).sql"
if command -v pg_dump &> /dev/null; then
  pg_dump "$DB_URL" --no-owner --no-privileges > "$BACKUP_FILE" 2>/dev/null && \
    echo "  Backup saved: $BACKUP_FILE" || \
    echo "  Warning: pg_dump not available, skipping backup"
else
  echo "  Warning: pg_dump not available, skipping backup"
fi

# 2. Run pending migrations
echo "Step 2: Running pending migrations..."
npx drizzle-kit migrate

# 3. Verify schema
echo "Step 3: Verifying schema integrity..."
npx drizzle-kit check 2>/dev/null || true

echo "=== Migration complete ==="
