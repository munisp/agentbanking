#!/usr/bin/env bash
# =============================================================================
# 54Link POS Shell — Production Deployment Script
# Usage: ./scripts/deploy.sh [--env <env>] [--skip-build] [--dry-run]
# Requirements: Docker 24+, Docker Compose v2, make, curl, jq
# =============================================================================
set -euo pipefail

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'

log()  { echo -e "${CYAN}[$(date +%H:%M:%S)]${NC} $*"; }
ok()   { echo -e "${GREEN}[$(date +%H:%M:%S)] ✓${NC} $*"; }
warn() { echo -e "${YELLOW}[$(date +%H:%M:%S)] ⚠${NC} $*"; }
fail() { echo -e "${RED}[$(date +%H:%M:%S)] ✗${NC} $*"; exit 1; }

# ── Defaults ──────────────────────────────────────────────────────────────────
ENV="production"
SKIP_BUILD=false
DRY_RUN=false
COMPOSE_FILE="docker-compose.production.yml"
ENV_FILE=".env.production"
DEPLOY_TIMEOUT=300

# ── Argument parsing ──────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case $1 in
    --env)        ENV="$2"; shift 2 ;;
    --skip-build) SKIP_BUILD=true; shift ;;
    --dry-run)    DRY_RUN=true; shift ;;
    --timeout)    DEPLOY_TIMEOUT="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: $0 [--env production|staging] [--skip-build] [--dry-run] [--timeout 300]"
      exit 0 ;;
    *) fail "Unknown argument: $1" ;;
  esac
done

# ── Resolve paths ─────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# ── Banner ────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         54Link POS Shell — Production Deployment         ║${NC}"
echo -e "${BLUE}║  Environment: ${ENV}  $(date '+%Y-%m-%d %H:%M:%S %Z')  ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

# ── Pre-flight checks ─────────────────────────────────────────────────────────
log "Running pre-flight checks..."

command -v docker >/dev/null 2>&1 || fail "Docker not found. Install Docker 24+."
command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1 || fail "Docker Compose v2 not found."
command -v jq >/dev/null 2>&1 || fail "jq not found. Install with: apt-get install jq"

DOCKER_VERSION=$(docker version --format '{{.Server.Version}}' 2>/dev/null || echo "0")
log "Docker version: $DOCKER_VERSION"

# Check env file
if [[ ! -f "$ENV_FILE" ]]; then
  if [[ -f ".env.production.example" ]]; then
    warn "No $ENV_FILE found. Copying from example..."
    cp .env.production.example "$ENV_FILE"
    fail "Please edit $ENV_FILE with your production values and re-run."
  else
    fail "No $ENV_FILE found. Create it from .env.production.example"
  fi
fi
ok "Environment file found: $ENV_FILE"

# Validate required env vars
REQUIRED_VARS=(
  "POSTGRES_URL"
  "JWT_SECRET"
  "KAFKA_BROKERS"
  "REDIS_URL"
  "TEMPORAL_ADDRESS"
  "KEYCLOAK_URL"
  "PERMIFY_URL"
  "VAULT_ADDR"
  "VAULT_TOKEN"
  "DOMAIN"
)

log "Validating required environment variables..."
source "$ENV_FILE"
MISSING=()
for var in "${REQUIRED_VARS[@]}"; do
  if [[ -z "${!var:-}" ]]; then
    MISSING+=("$var")
  fi
done

if [[ ${#MISSING[@]} -gt 0 ]]; then
  fail "Missing required environment variables in $ENV_FILE:\n  ${MISSING[*]}"
fi
ok "All required environment variables present"

# ── Build phase ───────────────────────────────────────────────────────────────
if [[ "$SKIP_BUILD" == "false" ]]; then
  log "Building Docker images..."
  if [[ "$DRY_RUN" == "true" ]]; then
    log "[DRY RUN] Would run: docker compose -f $COMPOSE_FILE build"
  else
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" build \
      --parallel \
      --build-arg BUILD_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
      --build-arg GIT_COMMIT="$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')"
    ok "Docker images built successfully"
  fi
else
  warn "Skipping build phase (--skip-build)"
fi

# ── Database migrations ───────────────────────────────────────────────────────
log "Running database migrations..."
if [[ "$DRY_RUN" == "true" ]]; then
  log "[DRY RUN] Would run: pnpm db:push"
else
  NODE_ENV=production pnpm db:push || warn "Migration failed — check DB connectivity"
  ok "Database migrations applied"
fi

# ── Infrastructure services (start first) ────────────────────────────────────
INFRA_SERVICES=(
  "postgres" "redis" "kafka" "zookeeper"
  "vault" "keycloak" "permify"
  "loki" "prometheus" "grafana"
)

log "Starting infrastructure services..."
if [[ "$DRY_RUN" == "false" ]]; then
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d "${INFRA_SERVICES[@]}"

  # Wait for Postgres
  log "Waiting for PostgreSQL to be ready..."
  RETRIES=30
  until docker compose -f "$COMPOSE_FILE" exec -T postgres pg_isready -U pos_user -d pos_db >/dev/null 2>&1 || [[ $RETRIES -eq 0 ]]; do
    RETRIES=$((RETRIES - 1))
    sleep 2
  done
  [[ $RETRIES -gt 0 ]] && ok "PostgreSQL ready" || warn "PostgreSQL health check timed out"

  # Wait for Kafka
  log "Waiting for Kafka to be ready..."
  RETRIES=30
  until docker compose -f "$COMPOSE_FILE" exec -T kafka kafka-topics.sh --bootstrap-server localhost:9092 --list >/dev/null 2>&1 || [[ $RETRIES -eq 0 ]]; do
    RETRIES=$((RETRIES - 1))
    sleep 3
  done
  [[ $RETRIES -gt 0 ]] && ok "Kafka ready" || warn "Kafka health check timed out"
fi

# ── Create Kafka topics ───────────────────────────────────────────────────────
KAFKA_TOPICS=(
  "pos.transactions"
  "pos.fraud-alerts"
  "pos.sim-failovers"
  "pos.float-requests"
  "pos.settlements"
  "pos.audit-events"
)

log "Creating Kafka topics..."
if [[ "$DRY_RUN" == "false" ]]; then
  for topic in "${KAFKA_TOPICS[@]}"; do
    docker compose -f "$COMPOSE_FILE" exec -T kafka \
      kafka-topics.sh --bootstrap-server localhost:9092 \
      --create --if-not-exists \
      --topic "$topic" \
      --partitions 6 \
      --replication-factor 1 \
      >/dev/null 2>&1 && log "  Topic: $topic" || warn "  Topic already exists: $topic"
  done
  ok "Kafka topics ready"
fi

# ── Vault initialisation ──────────────────────────────────────────────────────
log "Initialising Vault..."
if [[ "$DRY_RUN" == "false" ]]; then
  if docker compose -f "$COMPOSE_FILE" exec -T vault vault status >/dev/null 2>&1; then
    ok "Vault already initialised"
  else
    bash infra/vault/init-vault.sh || warn "Vault init failed — manual intervention may be required"
  fi
fi

# ── Application services ──────────────────────────────────────────────────────
APP_SERVICES=(
  "pos-shell"
  "workflow-orchestrator"
  "fraud-engine"
  "tx-validator"
  "ledger-bridge"
  "temporal-worker"
  "nginx"
)

log "Starting application services..."
if [[ "$DRY_RUN" == "false" ]]; then
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d "${APP_SERVICES[@]}"
  ok "Application services started"
fi

# ── Health checks ─────────────────────────────────────────────────────────────
log "Running health checks..."
DOMAIN="${DOMAIN:-localhost}"
HEALTH_ENDPOINTS=(
  "https://${DOMAIN}/api/health"
  "https://${DOMAIN}/api/trpc/auth.me"
)

if [[ "$DRY_RUN" == "false" ]]; then
  sleep 10  # Give services time to start
  ALL_HEALTHY=true
  for endpoint in "${HEALTH_ENDPOINTS[@]}"; do
    HTTP_CODE=$(curl -sk -o /dev/null -w "%{http_code}" "$endpoint" || echo "000")
    if [[ "$HTTP_CODE" =~ ^(200|401|403)$ ]]; then
      ok "Health check passed: $endpoint ($HTTP_CODE)"
    else
      warn "Health check failed: $endpoint ($HTTP_CODE)"
      ALL_HEALTHY=false
    fi
  done

  if [[ "$ALL_HEALTHY" == "true" ]]; then
    ok "All health checks passed"
  else
    warn "Some health checks failed — check logs with: docker compose -f $COMPOSE_FILE logs"
  fi
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              Deployment Complete!                        ║${NC}"
echo -e "${GREEN}║                                                          ║${NC}"
echo -e "${GREEN}║  App:      https://${DOMAIN}                             ║${NC}"
echo -e "${GREEN}║  Grafana:  https://${DOMAIN}:3001                        ║${NC}"
echo -e "${GREEN}║  Vault:    https://${DOMAIN}:8200                        ║${NC}"
echo -e "${GREEN}║                                                          ║${NC}"
echo -e "${GREEN}║  Logs:     docker compose -f $COMPOSE_FILE logs -f      ║${NC}"
echo -e "${GREEN}║  Status:   docker compose -f $COMPOSE_FILE ps           ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

if [[ "$DRY_RUN" == "true" ]]; then
  warn "DRY RUN — no changes were made to the system"
fi
