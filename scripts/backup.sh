#!/usr/bin/env bash
# ============================================================
# 54Link POS Shell — Production Backup Script
# Backs up PostgreSQL databases and MinIO buckets to S3.
# Usage: ./scripts/backup.sh [--full] [--db-only] [--minio-only]
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_DIR="/tmp/54link-backup-$TIMESTAMP"
LOG_FILE="/var/log/54link/backup-$TIMESTAMP.log"

# ── Load env ──────────────────────────────────────────────────────────────────
if [[ -f "$PROJECT_ROOT/.env.production" ]]; then
  # shellcheck disable=SC1091
  set -a; source "$PROJECT_ROOT/.env.production"; set +a
fi

# Required env vars
POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:-pos54link}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:?POSTGRES_PASSWORD required}"
BACKUP_S3_BUCKET="${BACKUP_S3_BUCKET:?BACKUP_S3_BUCKET required}"
BACKUP_S3_PREFIX="${BACKUP_S3_PREFIX:-backups/54link}"
AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:?AWS_ACCESS_KEY_ID required}"
AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:?AWS_SECRET_ACCESS_KEY required}"
AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}"

MINIO_ENDPOINT="${MINIO_ENDPOINT:-http://localhost:9000}"
MINIO_ACCESS_KEY="${MINIO_ACCESS_KEY:-minioadmin}"
MINIO_SECRET_KEY="${MINIO_SECRET_KEY:-minioadmin}"

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC}  $*" | tee -a "$LOG_FILE"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*" | tee -a "$LOG_FILE"; }
error() { echo -e "${RED}[ERROR]${NC} $*" | tee -a "$LOG_FILE"; exit 1; }

mkdir -p "$BACKUP_DIR" "$(dirname "$LOG_FILE")"

# ── Parse args ────────────────────────────────────────────────────────────────
DO_DB=true; DO_MINIO=true
while [[ $# -gt 0 ]]; do
  case "$1" in
    --db-only)    DO_MINIO=false; shift ;;
    --minio-only) DO_DB=false;    shift ;;
    --full)       DO_DB=true; DO_MINIO=true; shift ;;
    *) error "Unknown argument: $1" ;;
  esac
done

# ── PostgreSQL backup ─────────────────────────────────────────────────────────
if $DO_DB; then
  info "=== PostgreSQL Backup ==="
  DBS=(
    "pos54link"
    "keycloak"
    "temporal"
    "permify"
  )
  for db in "${DBS[@]}"; do
    info "  Dumping $db..."
    DUMP_FILE="$BACKUP_DIR/postgres-$db-$TIMESTAMP.sql.gz"
    PGPASSWORD="$POSTGRES_PASSWORD" pg_dump \
      -h "$POSTGRES_HOST" \
      -p "$POSTGRES_PORT" \
      -U "$POSTGRES_USER" \
      -d "$db" \
      --no-password \
      --format=custom \
      --compress=9 \
      2>>"$LOG_FILE" | gzip > "$DUMP_FILE" || warn "  Failed to dump $db"
    
    SIZE=$(du -sh "$DUMP_FILE" 2>/dev/null | cut -f1 || echo "unknown")
    info "  $db backup: $SIZE → $DUMP_FILE"
  done
fi

# ── MinIO backup ──────────────────────────────────────────────────────────────
if $DO_MINIO; then
  info "=== MinIO Backup ==="
  MINIO_BACKUP_DIR="$BACKUP_DIR/minio"
  mkdir -p "$MINIO_BACKUP_DIR"
  
  BUCKETS=(
    "pos54link-receipts"
    "pos54link-kyc-docs"
    "pos54link-reports"
    "pos54link-audit-logs"
  )
  
  # Use mc (MinIO Client) if available, otherwise use rclone
  if command -v mc &>/dev/null; then
    mc alias set backup-source "$MINIO_ENDPOINT" "$MINIO_ACCESS_KEY" "$MINIO_SECRET_KEY" 2>>"$LOG_FILE"
    for bucket in "${BUCKETS[@]}"; do
      info "  Syncing bucket: $bucket"
      mc mirror "backup-source/$bucket" "$MINIO_BACKUP_DIR/$bucket" 2>>"$LOG_FILE" || \
        warn "  Failed to mirror $bucket"
    done
  else
    warn "mc (MinIO Client) not found — skipping MinIO backup. Install with: wget https://dl.min.io/client/mc/release/linux-amd64/mc"
  fi
fi

# ── Upload to S3 ──────────────────────────────────────────────────────────────
info "=== Uploading to S3: s3://$BACKUP_S3_BUCKET/$BACKUP_S3_PREFIX/$TIMESTAMP/ ==="
if command -v aws &>/dev/null; then
  aws s3 sync "$BACKUP_DIR" \
    "s3://$BACKUP_S3_BUCKET/$BACKUP_S3_PREFIX/$TIMESTAMP/" \
    --storage-class STANDARD_IA \
    --sse AES256 \
    2>>"$LOG_FILE" || error "S3 upload failed"
  info "Upload complete."
else
  warn "AWS CLI not found — backup files saved locally at $BACKUP_DIR"
  warn "Install AWS CLI: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
fi

# ── Retention: delete backups older than 30 days ─────────────────────────────
if command -v aws &>/dev/null; then
  info "=== Applying 30-day retention policy ==="
  CUTOFF=$(date -d "30 days ago" +%Y%m%d 2>/dev/null || date -v-30d +%Y%m%d 2>/dev/null || echo "")
  if [[ -n "$CUTOFF" ]]; then
    aws s3 ls "s3://$BACKUP_S3_BUCKET/$BACKUP_S3_PREFIX/" | \
      awk '{print $2}' | \
      grep -E '^[0-9]{8}-' | \
      while read -r prefix; do
        prefix_date="${prefix:0:8}"
        if [[ "$prefix_date" < "$CUTOFF" ]]; then
          info "  Deleting old backup: $prefix"
          aws s3 rm "s3://$BACKUP_S3_BUCKET/$BACKUP_S3_PREFIX/$prefix" --recursive 2>>"$LOG_FILE" || true
        fi
      done
  fi
fi

# ── Summary ───────────────────────────────────────────────────────────────────
TOTAL_SIZE=$(du -sh "$BACKUP_DIR" 2>/dev/null | cut -f1 || echo "unknown")
info "=== Backup Complete ==="
info "  Timestamp:  $TIMESTAMP"
info "  Total size: $TOTAL_SIZE"
info "  Local path: $BACKUP_DIR"
info "  S3 path:    s3://$BACKUP_S3_BUCKET/$BACKUP_S3_PREFIX/$TIMESTAMP/"
info "  Log:        $LOG_FILE"
