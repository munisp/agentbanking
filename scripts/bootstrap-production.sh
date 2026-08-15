#!/usr/bin/env bash
# ═════════════════════════════════════════════════════════════════════════════
# 54Link Agency Banking Platform — One-Command Production Bootstrap
#
# This script bootstraps the entire 54Link production environment:
#   1. Validates prerequisites (Docker, Docker Compose, jq, curl)
#   2. Creates required .env.production from template if missing
#   3. Pulls all Docker images
#   4. Starts infrastructure tier (PostgreSQL, Redis, Kafka, TigerBeetle, etc.)
#   5. Runs database migrations
#   6. Initialises MinIO buckets and lifecycle policies
#   7. Bootstraps HashiCorp Vault (init + AppRole)
#   8. Provisions TigerBeetle accounts
#   9. Seeds APISix routes and upstreams
#  10. Deploys Fluvio SmartModules and creates topics
#  11. Starts application tier (all microservices)
#  12. Starts monitoring tier (Prometheus, Grafana, Alertmanager)
#  13. Runs health checks on all services
#  14. Prints access URLs and credentials summary
#
# Usage:
#   ./scripts/bootstrap-production.sh [--skip-pull] [--skip-vault] [--dry-run]
#
# Options:
#   --skip-pull    Skip docker image pull (use cached images)
#   --skip-vault   Skip Vault initialisation (use existing Vault)
#   --skip-fluvio  Skip Fluvio SmartModule deployment
#   --dry-run      Print commands without executing
#   --profile APP  Only start services in this Docker Compose profile
#
# Environment variables (override defaults in .env.production):
#   DOMAIN         — Production domain (default: 54link.io)
#   ADMIN_EMAIL    — Admin email for Let's Encrypt (default: admin@54link.io)
# ═════════════════════════════════════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_DIR}"

# ── Parse arguments ───────────────────────────────────────────────────────────
SKIP_PULL=false
SKIP_VAULT=false
SKIP_FLUVIO=false
DRY_RUN=false
COMPOSE_PROFILE="all"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-pull)   SKIP_PULL=true; shift;;
    --skip-vault)  SKIP_VAULT=true; shift;;
    --skip-fluvio) SKIP_FLUVIO=true; shift;;
    --dry-run)     DRY_RUN=true; shift;;
    --profile)     COMPOSE_PROFILE="$2"; shift 2;;
    *) echo "Unknown argument: $1"; exit 1;;
  esac
done

# ── Logging ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log()     { echo -e "${GREEN}[$(date -u '+%H:%M:%S')] ✓ $*${NC}"; }
info()    { echo -e "${BLUE}[$(date -u '+%H:%M:%S')] ℹ $*${NC}"; }
warn()    { echo -e "${YELLOW}[$(date -u '+%H:%M:%S')] ⚠ $*${NC}"; }
error()   { echo -e "${RED}[$(date -u '+%H:%M:%S')] ✗ $*${NC}" >&2; exit 1; }
step()    { echo -e "\n${BLUE}══════════════════════════════════════════════════${NC}"; echo -e "${BLUE}  STEP $*${NC}"; echo -e "${BLUE}══════════════════════════════════════════════════${NC}"; }
run()     { if [[ "${DRY_RUN}" == "true" ]]; then echo "[DRY-RUN] $*"; else eval "$*"; fi; }

# ── Banner ────────────────────────────────────────────────────────────────────
echo ""
echo "  ███████╗██╗  ██╗██╗     ██╗███╗   ██╗██╗  ██╗"
echo "  ██╔════╝██║  ██║██║     ██║████╗  ██║██║ ██╔╝"
echo "  ███████╗███████║██║     ██║██╔██╗ ██║█████╔╝ "
echo "  ╚════██║╚════██║██║     ██║██║╚██╗██║██╔═██╗ "
echo "  ███████║     ██║███████╗██║██║ ╚████║██║  ██║"
echo "  ╚══════╝     ╚═╝╚══════╝╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝"
echo ""
echo "  Agency Banking Platform — Production Bootstrap"
echo "  Version: 2.0.0 (Phase 161)"
echo ""

# ── Step 1: Prerequisites ─────────────────────────────────────────────────────
step "1/13 — Validating prerequisites"

for cmd in docker jq curl openssl; do
  if ! command -v $cmd &>/dev/null; then
    error "$cmd is required but not installed"
  fi
done

if ! docker compose version &>/dev/null; then
  error "Docker Compose v2 is required"
fi

log "All prerequisites satisfied"

# ── Step 2: Environment file ──────────────────────────────────────────────────
step "2/13 — Preparing environment"

if [[ ! -f .env.production ]]; then
  if [[ -f .env.production.template ]]; then
    cp .env.production.template .env.production
    warn "Created .env.production from template — EDIT IT before continuing in a real deployment"
  else
    error ".env.production not found and no template available"
  fi
fi

# shellcheck disable=SC2046
export $(grep -v '^#' .env.production | grep -v '^$' | xargs) || true

DOMAIN="${DOMAIN:-54link.io}"
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@54link.io}"

log "Environment loaded (domain: ${DOMAIN})"

# ── Step 3: Pull images ───────────────────────────────────────────────────────
step "3/13 — Pulling Docker images"

if [[ "${SKIP_PULL}" == "true" ]]; then
  warn "Skipping image pull (--skip-pull)"
else
  run "docker compose -f docker-compose.production.yml pull"
  log "All images pulled"
fi

# ── Step 4: Infrastructure tier ───────────────────────────────────────────────
step "4/13 — Starting infrastructure tier"

INFRA_SERVICES="postgres redis kafka tigerbeetle minio vault apisix etcd fluvio"

if [[ "${COMPOSE_PROFILE}" == "all" ]]; then
  run "docker compose -f docker-compose.production.yml up -d ${INFRA_SERVICES}"
else
  run "docker compose -f docker-compose.production.yml --profile ${COMPOSE_PROFILE} up -d"
fi

info "Waiting for infrastructure to be healthy..."
sleep 15

# Wait for PostgreSQL
for i in $(seq 1 30); do
  if docker compose -f docker-compose.production.yml exec -T postgres pg_isready -U postgres &>/dev/null; then
    log "PostgreSQL is ready"
    break
  fi
  sleep 2
done

# Wait for Redis
for i in $(seq 1 15); do
  if docker compose -f docker-compose.production.yml exec -T redis redis-cli ping 2>/dev/null | grep -q PONG; then
    log "Redis is ready"
    break
  fi
  sleep 2
done

# ── Step 5: Database migrations ───────────────────────────────────────────────
step "5/13 — Running database migrations"

if [[ -d db/migrations ]]; then
  run "bash db/migrations/run-all.sh --env production"
  log "Database migrations applied"
else
  warn "No db/migrations directory — skipping"
fi

# ── Step 6: MinIO buckets ─────────────────────────────────────────────────────
step "6/13 — Initialising MinIO buckets"

MINIO_ENDPOINT="${MINIO_ENDPOINT:-http://localhost:9000}"
if curl -sf "${MINIO_ENDPOINT}/minio/health/live" &>/dev/null; then
  run "bash infra/minio/init-buckets.sh"
  log "MinIO buckets created with lifecycle policies"
else
  warn "MinIO not reachable at ${MINIO_ENDPOINT} — skipping bucket init"
fi

# ── Step 7: Vault ─────────────────────────────────────────────────────────────
step "7/13 — Initialising HashiCorp Vault"

if [[ "${SKIP_VAULT}" == "true" ]]; then
  warn "Skipping Vault initialisation (--skip-vault)"
else
  VAULT_ADDR="${VAULT_ADDR:-http://localhost:8200}"
  if curl -sf "${VAULT_ADDR}/v1/sys/health" &>/dev/null; then
    run "bash infra/vault/init-vault-complete.sh"
    log "Vault initialised and AppRole configured"
  fi
fi

# ── Step 8: TigerBeetle provisioning ─────────────────────────────────────────
step "8/13 — Provisioning TigerBeetle accounts"

TB_SIDECAR_URL="${TB_SIDECAR_URL:-http://localhost:8080}"
if curl -sf "${TB_SIDECAR_URL}/health" &>/dev/null; then
  run "bash infra/tigerbeetle/provision.sh --sidecar ${TB_SIDECAR_URL}"
  log "TigerBeetle accounts provisioned"
else
  warn "TigerBeetle sidecar not reachable at ${TB_SIDECAR_URL} — skipping account provisioning"
fi

# ── Step 9: APISix bootstrap ──────────────────────────────────────────────────
step "9/13 — Bootstrapping APISix routes"

APISIX_ADMIN_URL="${APISIX_ADMIN_URL:-http://localhost:9180}"
if [ -z "${APISIX_ADMIN_KEY:-}" ]; then
  error "APISIX_ADMIN_KEY is required (no default admin key is permitted); set it in the environment or .env.production"
fi
if curl -sf -H "X-API-KEY: ${APISIX_ADMIN_KEY}" "${APISIX_ADMIN_URL}/apisix/admin/routes" &>/dev/null; then
  run "bash infra/apisix/bootstrap.sh --host ${APISIX_ADMIN_URL}"
  log "APISix routes and upstreams configured"
else
  warn "APISix admin API not reachable — skipping route bootstrap"
fi

# ── Step 10: Fluvio SmartModules ──────────────────────────────────────────────
step "10/13 — Deploying Fluvio SmartModules"

if [[ "${SKIP_FLUVIO}" == "true" ]]; then
  warn "Skipping Fluvio deployment (--skip-fluvio)"
else
  FLUVIO_ENDPOINT="${FLUVIO_ENDPOINT:-localhost:9003}"
  run "bash infra/fluvio/deploy-smartmodule.sh --local"
  log "Fluvio topics and SmartModules deployed"
fi

# ── Step 11: Start application tier ──────────────────────────────────────────
step "11/13 — Starting application services"

if [[ "${COMPOSE_PROFILE}" == "all" ]]; then
  run "docker compose -f docker-compose.production.yml up -d"
  log "All application services started"
else
  run "docker compose -f docker-compose.production.yml --profile ${COMPOSE_PROFILE} up -d"
fi

info "Waiting for services to be healthy..."
sleep 20

# ── Step 12: Monitoring tier ──────────────────────────────────────────────────
step "12/13 — Starting monitoring tier"

run "docker compose -f docker-compose.production.yml up -d prometheus grafana alertmanager"
log "Monitoring stack started"

# ── Step 13: Health checks ────────────────────────────────────────────────────
step "13/13 — Running health checks"

HEALTH_ENDPOINTS=(
  "http://localhost:8080/health|API Gateway"
  "http://localhost:9090/-/healthy|Prometheus"
  "http://localhost:3000/api/health|Grafana"
)

FAILED=0
for entry in "${HEALTH_ENDPOINTS[@]}"; do
  url="${entry%%|*}"
  name="${entry##*|}"
  if curl -sf "$url" &>/dev/null; then
    log "${name} healthy"
  else
    warn "${name} not responding at $url"
    FAILED=$((FAILED+1))
  fi
done

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  54Link Production Environment — Bootstrap Complete"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "  API Gateway:    https://api.${DOMAIN}"
echo "  Admin Console:  https://admin.${DOMAIN}"
echo "  Grafana:        https://grafana.${DOMAIN}"
echo "  Vault:          https://vault.${DOMAIN}"
echo ""
echo "  Health check failures: ${FAILED}"
echo ""
echo "  Next steps:"
echo "    1. Verify DNS records point to this host"
echo "    2. Configure TLS certificates (certbot or cert-manager)"
echo "    3. Review .env.production and rotate default credentials"
echo "    4. Run integration tests: make test-integration"
eecho ""

if [[ ${FAILED} -gt 0 ]]; then
  warn "Some health checks failed — review logs: docker compose -f docker-compose.production.yml logs"
fi
