#!/bin/bash
#
# PostgreSQL Automated Backup Script
# Production-ready backup with compression, encryption, and rotation
#

set -e

# Configuration
POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_DB="${POSTGRES_DB:-remittance}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/postgresql}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
S3_BUCKET="${S3_BUCKET:-}"
ENCRYPTION_KEY="${BACKUP_ENCRYPTION_KEY:-}"

# Timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/${POSTGRES_DB}_${TIMESTAMP}.sql"
COMPRESSED_FILE="${BACKUP_FILE}.gz"
ENCRYPTED_FILE="${COMPRESSED_FILE}.enc"

# Create backup directory
mkdir -p "$BACKUP_DIR"

echo "================================================================================"
echo "PostgreSQL Backup Script"
echo "================================================================================"
echo "Database: $POSTGRES_DB"
echo "Host: $POSTGRES_HOST:$POSTGRES_PORT"
echo "Timestamp: $TIMESTAMP"
echo "================================================================================"
echo

# Step 1: Dump database
echo "📦 Step 1/5: Dumping database..."
pg_dump -h "$POSTGRES_HOST" \
        -p "$POSTGRES_PORT" \
        -U "$POSTGRES_USER" \
        -d "$POSTGRES_DB" \
        --format=plain \
        --no-owner \
        --no-acl \
        --verbose \
        > "$BACKUP_FILE" 2>&1

DUMP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo "✅ Database dumped: $DUMP_SIZE"
echo

# Step 2: Compress
echo "🗜️  Step 2/5: Compressing backup..."
gzip -9 "$BACKUP_FILE"
COMPRESSED_SIZE=$(du -h "$COMPRESSED_FILE" | cut -f1)
COMPRESSION_RATIO=$(echo "scale=1; $(stat -f%z "$COMPRESSED_FILE") * 100 / $(stat -f%z "$BACKUP_FILE")" | bc 2>/dev/null || echo "N/A")
echo "✅ Backup compressed: $COMPRESSED_SIZE (${COMPRESSION_RATIO}% of original)"
echo

# Step 3: Encrypt (if encryption key provided)
if [ -n "$ENCRYPTION_KEY" ]; then
    echo "🔒 Step 3/5: Encrypting backup..."
    openssl enc -aes-256-cbc \
                -salt \
                -in "$COMPRESSED_FILE" \
                -out "$ENCRYPTED_FILE" \
                -pass "pass:$ENCRYPTION_KEY"
    
    rm "$COMPRESSED_FILE"
    FINAL_FILE="$ENCRYPTED_FILE"
    echo "✅ Backup encrypted with AES-256"
else
    echo "⏭️  Step 3/5: Skipping encryption (no key provided)"
    FINAL_FILE="$COMPRESSED_FILE"
fi
echo

# Step 4: Upload to S3 (if configured)
if [ -n "$S3_BUCKET" ]; then
    echo "☁️  Step 4/5: Uploading to S3..."
    aws s3 cp "$FINAL_FILE" "s3://$S3_BUCKET/backups/postgresql/" \
        --storage-class STANDARD_IA \
        --server-side-encryption AES256
    echo "✅ Backup uploaded to S3: s3://$S3_BUCKET/backups/postgresql/$(basename $FINAL_FILE)"
else
    echo "⏭️  Step 4/5: Skipping S3 upload (not configured)"
fi
echo

# Step 5: Cleanup old backups
echo "🧹 Step 5/5: Cleaning up old backups (retention: $RETENTION_DAYS days)..."
find "$BACKUP_DIR" -name "${POSTGRES_DB}_*.sql.gz*" -type f -mtime +$RETENTION_DAYS -delete
REMAINING=$(find "$BACKUP_DIR" -name "${POSTGRES_DB}_*.sql.gz*" -type f | wc -l | tr -d ' ')
echo "✅ Cleanup complete. Remaining backups: $REMAINING"
echo

# Summary
echo "================================================================================"
echo "✅ BACKUP COMPLETE"
echo "================================================================================"
echo "File: $(basename $FINAL_FILE)"
echo "Size: $(du -h "$FINAL_FILE" | cut -f1)"
echo "Location: $FINAL_FILE"
if [ -n "$S3_BUCKET" ]; then
    echo "S3: s3://$S3_BUCKET/backups/postgresql/$(basename $FINAL_FILE)"
fi
echo "================================================================================"

# Create backup manifest
cat > "$BACKUP_DIR/latest_backup.json" << EOF
{
  "timestamp": "$TIMESTAMP",
  "database": "$POSTGRES_DB",
  "file": "$(basename $FINAL_FILE)",
  "size_bytes": $(stat -f%z "$FINAL_FILE" 2>/dev/null || stat -c%s "$FINAL_FILE"),
  "encrypted": $([ -n "$ENCRYPTION_KEY" ] && echo "true" || echo "false"),
  "s3_uploaded": $([ -n "$S3_BUCKET" ] && echo "true" || echo "false")
}
EOF

exit 0

