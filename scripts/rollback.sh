#!/usr/bin/env bash
# ============================================================
# 54Link POS Shell — Production Rollback Script
# Usage: ./scripts/rollback.sh [--tag <git-sha>] [--service <name>]
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$PROJECT_ROOT/docker-compose.production.yml"
REGISTRY="${REGISTRY:-ghcr.io/54link}"
LOG_FILE="/var/log/54link/rollback-$(date +%Y%m%d-%H%M%S).log"

# ── Colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC}  $*" | tee -a "$LOG_FILE"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*" | tee -a "$LOG_FILE"; }
error() { echo -e "${RED}[ERROR]${NC} $*" | tee -a "$LOG_FILE"; exit 1; }

mkdir -p "$(dirname "$LOG_FILE")"

# ── Parse arguments ───────────────────────────────────────────────────────────
TARGET_TAG=""
TARGET_SERVICE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --tag)     TARGET_TAG="$2";     shift 2 ;;
    --service) TARGET_SERVICE="$2"; shift 2 ;;
    --help)
      echo "Usage: $0 [--tag <git-sha-or-semver>] [--service <service-name>]"
      echo "  --tag       Docker image tag to roll back to (default: previous tag from .rollback-state)"
      echo "  --service   Roll back only one service (default: all services)"
      exit 0 ;;
    *) error "Unknown argument: $1" ;;
  esac
done

# ── Determine rollback tag ────────────────────────────────────────────────────
ROLLBACK_STATE="$PROJECT_ROOT/.rollback-state"
if [[ -z "$TARGET_TAG" ]]; then
  if [[ -f "$ROLLBACK_STATE" ]]; then
    TARGET_TAG=$(cat "$ROLLBACK_STATE")
    info "Using saved rollback tag: $TARGET_TAG"
  else
    error "No rollback tag specified and no .rollback-state file found. Run: $0 --tag <sha>"
  fi
fi

info "Rolling back to tag: $TARGET_TAG"
[[ -n "$TARGET_SERVICE" ]] && info "Targeting service: $TARGET_SERVICE"

# ── Save current tag as new rollback state ────────────────────────────────────
CURRENT_TAG=$(git -C "$PROJECT_ROOT" rev-parse --short HEAD 2>/dev/null || echo "unknown")
echo "$CURRENT_TAG" > "$ROLLBACK_STATE"
info "Saved current tag $CURRENT_TAG as next rollback target"

# ── Pull rollback images ──────────────────────────────────────────────────────
SERVICES=(
  "pos-shell-app"
  "workflow-orchestrator"
  "fraud-engine"
  "tx-validator"
  "ledger-bridge"
  "pos-printer"
  "i18n-currency"
)

if [[ -n "$TARGET_SERVICE" ]]; then
  SERVICES=("$TARGET_SERVICE")
fi

info "Pulling rollback images..."
for svc in "${SERVICES[@]}"; do
  IMAGE="$REGISTRY/$svc:$TARGET_TAG"
  info "  Pulling $IMAGE"
  docker pull "$IMAGE" || warn "  Could not pull $IMAGE — skipping"
done

# ── Update docker-compose override ───────────────────────────────────────────
OVERRIDE_FILE="$PROJECT_ROOT/docker-compose.rollback.yml"
cat > "$OVERRIDE_FILE" << YAML
version: '3.9'
services:
YAML

for svc in "${SERVICES[@]}"; do
  cat >> "$OVERRIDE_FILE" << YAML
  $svc:
    image: $REGISTRY/$svc:$TARGET_TAG
YAML
done

info "Generated rollback override: $OVERRIDE_FILE"

# ── Rolling restart ───────────────────────────────────────────────────────────
info "Performing rolling restart..."
if [[ -n "$TARGET_SERVICE" ]]; then
  docker compose -f "$COMPOSE_FILE" -f "$OVERRIDE_FILE" up -d --no-deps "$TARGET_SERVICE"
else
  # Roll back app services first, then infrastructure stays unchanged
  for svc in "${SERVICES[@]}"; do
    info "  Restarting $svc..."
    docker compose -f "$COMPOSE_FILE" -f "$OVERRIDE_FILE" up -d --no-deps "$svc" || \
      warn "  Failed to restart $svc"
    sleep 2
  done
fi

# ── Health check ─────────────────────────────────────────────────────────────
info "Running health checks..."
sleep 10
"$SCRIPT_DIR/health-check.sh" || warn "Health check reported issues — review logs at $LOG_FILE"

# ── Notify ───────────────────────────────────────────────────────────────────
info "Rollback to $TARGET_TAG complete."
info "Log: $LOG_FILE"
echo ""
echo "  To undo this rollback, run: $0 --tag $CURRENT_TAG"
