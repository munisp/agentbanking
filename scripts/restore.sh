#!/usr/bin/env bash
# ============================================================
# 54Link POS Shell — Production Restore Script
# Restores PostgreSQL databases and MinIO buckets from S3 backup.
# Usage: ./scripts/restore.sh --timestamp <YYYYMMDD-HHMMSS> [--db-only] [--minio-only]
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_FILE="/var/log/54link/restore-$(date +%Y%m%d-%H%M%S).log"

# ── Load env ──────────────────────────────────────────────────────────────────
if [[ -f "$PROJECT_ROOT/.env.production" ]]; then
  set -a; source "$PROJECT_ROOT/.env.production"; set +a
fi

POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:-pos54link}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:?POSTGRES_PASSWORD required}"
BACKUP_S3_BUCKET="${BACKUP_S3_BUCKET:?BACKUP_S3_BUCKET required}"
BACKUP_S3_PREFIX="${BACKUP_S3_PREFIX:-backups/54link}"
MINIO_ENDPOINT="${MINIO_ENDPOINT:-http://localhost:9000}"
MINIO_ACCESS_KEY="${MINIO_ACCESS_KEY:-minioadmin}"
MINIO_SECRET_KEY="${MINIO_SECRET_KEY:-minioadmin}"

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC}  $*" | tee -a "$LOG_FILE"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*" | tee -a "$LOG_FILE"; }
error() { echo -e "${RED}[ERROR]${NC} $*" | tee -a "$LOG_FILE"; exit 1; }

mkdir -p "$(dirname "$LOG_FILE")"

# ── Parse args ────────────────────────────────────────────────────────────────
RESTORE_TIMESTAMP=""
DO_DB=true; DO_MINIO=true; DRY_RUN=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --timestamp)  RESTORE_TIMESTAMP="$2"; shift 2 ;;
    --db-only)    DO_MINIO=false; shift ;;
    --minio-only) DO_DB=false;    shift ;;
    --dry-run)    DRY_RUN=true;   shift ;;
    --list)
      info "Available backups:"
      aws s3 ls "s3://$BACKUP_S3_BUCKET/$BACKUP_S3_PREFIX/" | awk '{print "  " $2}'
      exit 0 ;;
    --help)
      echo "Usage: $0 --timestamp <YYYYMMDD-HHMMSS> [--db-only] [--minio-only] [--dry-run]"
      echo "       $0 --list   (list available backups)"
      exit 0 ;;
    *) error "Unknown argument: $1" ;;
  esac
done

[[ -z "$RESTORE_TIMESTAMP" ]] && error "Missing --timestamp. Run: $0 --list to see available backups."

S3_PATH="s3://$BACKUP_S3_BUCKET/$BACKUP_S3_PREFIX/$RESTORE_TIMESTAMP"
LOCAL_RESTORE_DIR="/tmp/54link-restore-$RESTORE_TIMESTAMP"

info "=== 54Link POS Shell — Restore from $RESTORE_TIMESTAMP ==="
$DRY_RUN && warn "DRY RUN MODE — no changes will be made"

# ── Download from S3 ──────────────────────────────────────────────────────────
info "Downloading backup from $S3_PATH..."
mkdir -p "$LOCAL_RESTORE_DIR"
if ! $DRY_RUN; then
  aws s3 sync "$S3_PATH/" "$LOCAL_RESTORE_DIR/" 2>>"$LOG_FILE" || \
    error "Failed to download backup from S3"
fi
info "Download complete."

# ── SAFETY: Stop application services ────────────────────────────────────────
info "Stopping application services (keeping DB + MinIO running)..."
if ! $DRY_RUN; then
  docker compose -f "$PROJECT_ROOT/docker-compose.production.yml" stop \
    pos-shell-app workflow-orchestrator fraud-engine tx-validator 2>>"$LOG_FILE" || \
    warn "Some services could not be stopped"
fi

# ── PostgreSQL restore ────────────────────────────────────────────────────────
if $DO_DB; then
  info "=== PostgreSQL Restore ==="
  DBS=("pos54link" "keycloak" "temporal" "permify")
  for db in "${DBS[@]}"; do
    DUMP_FILE=$(find "$LOCAL_RESTORE_DIR" -name "postgres-$db-*.sql.gz" | head -1)
    if [[ -z "$DUMP_FILE" ]]; then
      warn "  No dump file found for $db — skipping"
      continue
    fi
    info "  Restoring $db from $DUMP_FILE..."
    if ! $DRY_RUN; then
      # Drop and recreate database
      PGPASSWORD="$POSTGRES_PASSWORD" psql \
        -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" \
        -c "DROP DATABASE IF EXISTS \"$db\";" \
        -c "CREATE DATABASE \"$db\";" \
        2>>"$LOG_FILE" || warn "  Could not drop/create $db"
      
      # Restore from dump
      gunzip -c "$DUMP_FILE" | PGPASSWORD="$POSTGRES_PASSWORD" pg_restore \
        -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" \
        -d "$db" --no-password --format=custom \
        2>>"$LOG_FILE" || warn "  Restore of $db completed with warnings"
    fi
    info "  $db restored."
  done
fi

# ── MinIO restore ─────────────────────────────────────────────────────────────
if $DO_MINIO; then
  info "=== MinIO Restore ==="
  MINIO_BACKUP_DIR="$LOCAL_RESTORE_DIR/minio"
  if [[ -d "$MINIO_BACKUP_DIR" ]]; then
    if command -v mc &>/dev/null; then
      if ! $DRY_RUN; then
        mc alias set restore-target "$MINIO_ENDPOINT" "$MINIO_ACCESS_KEY" "$MINIO_SECRET_KEY" 2>>"$LOG_FILE"
        for bucket_dir in "$MINIO_BACKUP_DIR"/*/; do
          bucket=$(basename "$bucket_dir")
          info "  Restoring bucket: $bucket"
          mc mb --ignore-existing "restore-target/$bucket" 2>>"$LOG_FILE" || true
          mc mirror "$bucket_dir" "restore-target/$bucket" 2>>"$LOG_FILE" || \
            warn "  Failed to restore $bucket"
        done
      fi
    else
      warn "mc not found — skipping MinIO restore"
    fi
  else
    warn "No MinIO backup found in $MINIO_BACKUP_DIR"
  fi
fi

# ── Restart application services ─────────────────────────────────────────────
info "Restarting application services..."
if ! $DRY_RUN; then
  docker compose -f "$PROJECT_ROOT/docker-compose.production.yml" start \
    pos-shell-app workflow-orchestrator fraud-engine tx-validator 2>>"$LOG_FILE" || \
    warn "Some services could not be restarted"
  sleep 15
  "$SCRIPT_DIR/health-check.sh" || warn "Health check reported issues after restore"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
info "=== Restore Complete ==="
info "  Restored from: $RESTORE_TIMESTAMP"
info "  Log: $LOG_FILE"
$DRY_RUN && warn "DRY RUN — no actual changes were made"
