#!/bin/bash
#
# PostgreSQL Restore Script
# Restore from encrypted/compressed backups
#

set -e

# Configuration
POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_DB="${POSTGRES_DB:-remittance}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/postgresql}"
ENCRYPTION_KEY="${BACKUP_ENCRYPTION_KEY:-}"

# Check arguments
if [ $# -lt 1 ]; then
    echo "Usage: $0 <backup_file> [--force]"
    echo
    echo "Available backups:"
    ls -lh "$BACKUP_DIR"/${POSTGRES_DB}_*.sql.gz* 2>/dev/null || echo "No backups found"
    exit 1
fi

BACKUP_FILE="$1"
FORCE_RESTORE="$2"

# Verify backup file exists
if [ ! -f "$BACKUP_FILE" ]; then
    echo "❌ Error: Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "================================================================================"
echo "PostgreSQL Restore Script"
echo "================================================================================"
echo "Database: $POSTGRES_DB"
echo "Host: $POSTGRES_HOST:$POSTGRES_PORT"
echo "Backup: $(basename $BACKUP_FILE)"
echo "Size: $(du -h "$BACKUP_FILE" | cut -f1)"
echo "================================================================================"
echo

# Warning
if [ "$FORCE_RESTORE" != "--force" ]; then
    echo "⚠️  WARNING: This will DROP and recreate the database!"
    echo "⚠️  All existing data will be PERMANENTLY DELETED!"
    echo
    read -p "Are you sure you want to continue? (type 'yes' to confirm): " CONFIRM
    
    if [ "$CONFIRM" != "yes" ]; then
        echo "❌ Restore cancelled"
        exit 0
    fi
fi

# Step 1: Decrypt (if encrypted)
TEMP_DIR=$(mktemp -d)
WORKING_FILE="$BACKUP_FILE"

if [[ "$BACKUP_FILE" == *.enc ]]; then
    echo "🔓 Step 1/5: Decrypting backup..."
    
    if [ -z "$ENCRYPTION_KEY" ]; then
        echo "❌ Error: Backup is encrypted but no BACKUP_ENCRYPTION_KEY provided"
        exit 1
    fi
    
    DECRYPTED_FILE="$TEMP_DIR/backup.sql.gz"
    openssl enc -aes-256-cbc \
                -d \
                -in "$BACKUP_FILE" \
                -out "$DECRYPTED_FILE" \
                -pass "pass:$ENCRYPTION_KEY"
    
    WORKING_FILE="$DECRYPTED_FILE"
    echo "✅ Backup decrypted"
else
    echo "⏭️  Step 1/5: Skipping decryption (backup not encrypted)"
fi
echo

# Step 2: Decompress
echo "🗜️  Step 2/5: Decompressing backup..."
SQL_FILE="$TEMP_DIR/backup.sql"
gunzip -c "$WORKING_FILE" > "$SQL_FILE"
SQL_SIZE=$(du -h "$SQL_FILE" | cut -f1)
echo "✅ Backup decompressed: $SQL_SIZE"
echo

# Step 3: Drop existing database
echo "🗑️  Step 3/5: Dropping existing database..."
psql -h "$POSTGRES_HOST" \
     -p "$POSTGRES_PORT" \
     -U "$POSTGRES_USER" \
     -d postgres \
     -c "DROP DATABASE IF EXISTS $POSTGRES_DB;"
echo "✅ Database dropped"
echo

# Step 4: Create new database
echo "🆕 Step 4/5: Creating new database..."
psql -h "$POSTGRES_HOST" \
     -p "$POSTGRES_PORT" \
     -U "$POSTGRES_USER" \
     -d postgres \
     -c "CREATE DATABASE $POSTGRES_DB;"
echo "✅ Database created"
echo

# Step 5: Restore data
echo "📥 Step 5/5: Restoring data..."
psql -h "$POSTGRES_HOST" \
     -p "$POSTGRES_PORT" \
     -U "$POSTGRES_USER" \
     -d "$POSTGRES_DB" \
     < "$SQL_FILE"
echo "✅ Data restored"
echo

# Cleanup
rm -rf "$TEMP_DIR"

# Verify restoration
echo "🔍 Verifying restoration..."
TABLE_COUNT=$(psql -h "$POSTGRES_HOST" \
                   -p "$POSTGRES_PORT" \
                   -U "$POSTGRES_USER" \
                   -d "$POSTGRES_DB" \
                   -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" | tr -d ' ')

echo "✅ Tables restored: $TABLE_COUNT"
echo

echo "================================================================================"
echo "✅ RESTORE COMPLETE"
echo "================================================================================"
echo "Database: $POSTGRES_DB"
echo "Tables: $TABLE_COUNT"
echo "================================================================================"

exit 0

