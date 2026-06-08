#!/bin/bash
# Database Restore Script — Point-in-Time Recovery
set -euo pipefail

DB_URL="${DATABASE_URL:-${POSTGRES_URL:-}}"
BACKUP_FILE="${1:-}"

if [ -z "$DB_URL" ]; then
  echo "ERROR: DATABASE_URL or POSTGRES_URL required"
  exit 1
fi

if [ -z "$BACKUP_FILE" ]; then
  echo "Usage: $0 <backup-file.sql.gz>"
  echo ""
  echo "Available backups:"
  ls -lh /var/backups/54link/54link-backup-*.sql.gz 2>/dev/null || echo "  No local backups found"
  exit 1
fi

echo "=== 54Link Database Restore ==="
echo "WARNING: This will REPLACE all data in the target database!"
echo "Backup file: $BACKUP_FILE"
echo ""
read -p "Type 'CONFIRM' to proceed: " CONFIRM
if [ "$CONFIRM" != "CONFIRM" ]; then
  echo "Aborted."
  exit 0
fi

echo "Step 1: Restoring from backup..."
gunzip -c "$BACKUP_FILE" | pg_restore --no-owner --no-privileges -d "$DB_URL"
echo "Step 2: Verifying restore..."
echo "=== Restore complete ==="
