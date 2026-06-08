#!/bin/bash
# Automated Database Backup Script — PostgreSQL
# Schedule via cron: 0 2 * * * /path/to/backup-database.sh
set -euo pipefail

DB_URL="${DATABASE_URL:-${POSTGRES_URL:-}}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/54link}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
S3_BUCKET="${BACKUP_S3_BUCKET:-}"

if [ -z "$DB_URL" ]; then
  echo "ERROR: DATABASE_URL or POSTGRES_URL required"
  exit 1
fi

mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/54link-backup-$TIMESTAMP.sql.gz"

echo "=== 54Link Database Backup ==="
echo "Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "Target: $BACKUP_FILE"

# 1. Create compressed backup
echo "Step 1: Creating backup..."
pg_dump "$DB_URL" --no-owner --no-privileges --format=custom | gzip > "$BACKUP_FILE"
SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo "  Backup created: $SIZE"

# 2. Verify backup integrity
echo "Step 2: Verifying backup..."
gunzip -t "$BACKUP_FILE" && echo "  Integrity check: PASSED" || { echo "  Integrity check: FAILED"; exit 1; }

# 3. Upload to S3 (if configured)
if [ -n "$S3_BUCKET" ]; then
  echo "Step 3: Uploading to S3..."
  aws s3 cp "$BACKUP_FILE" "s3://$S3_BUCKET/backups/$TIMESTAMP/" --storage-class STANDARD_IA
  echo "  Uploaded to s3://$S3_BUCKET/backups/$TIMESTAMP/"
fi

# 4. Cleanup old backups
echo "Step 4: Cleaning up backups older than $RETENTION_DAYS days..."
find "$BACKUP_DIR" -name "54link-backup-*.sql.gz" -mtime +$RETENTION_DAYS -delete
REMAINING=$(ls -1 "$BACKUP_DIR"/54link-backup-*.sql.gz 2>/dev/null | wc -l)
echo "  $REMAINING backups retained"

echo "=== Backup complete ==="
