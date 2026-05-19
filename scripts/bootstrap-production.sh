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
echo "  ███████║     ██║███████╗██║██║ ╚████║██║  ██╗"
echo "  ╚══════╝     ╚═╝╚══════╝╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝"
echo ""
echo "  Agency Banking Platform — Production Bootstrap"
echo "  Version: 2.0.0 (Phase 161)"
echo ""

# ── Step 1: Prerequisites ─────────────────────────────────────────────────────
step "1/13 — Checking prerequisites"

check_cmd() {
  if ! command -v "$1" &>/dev/null; then
    error "Required command not found: $1. Please install it first."
  fi
  log "Found: $1 ($(command -v "$1"))"
}

check_cmd docker
check_cmd docker-compose || check_cmd "docker compose"
check_cmd curl
check_cmd jq

DOCKER_VERSION=$(docker --version | grep -oP '\d+\.\d+\.\d+' | head -1)
info "Docker version: ${DOCKER_VERSION}"

# Check Docker daemon is running
docker info &>/dev/null || error "Docker daemon is not running. Please start Docker."
log "Docker daemon is running"

# ── Step 2: Environment file ──────────────────────────────────────────────────
step "2/13 — Environment configuration"

if [[ ! -f ".env.production" ]]; then
  if [[ -f ".env.production.example" ]]; then
    warn ".env.production not found — copying from .env.production.example"
    cp .env.production.example .env.production
    warn "IMPORTANT: Edit .env.production and set all required secrets before proceeding!"
    warn "Press Enter to continue with example values, or Ctrl+C to abort."
    read -r
  else
    error ".env.production not found and no .env.production.example available."
  fi
else
  log ".env.production found"
fi

# Source env file for use in this script
set -a; source .env.production 2>/dev/null || true; set +a

DOMAIN="${DOMAIN:-54link.io}"
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@54link.io}"
info "Domain: ${DOMAIN}"
info "Admin email: ${ADMIN_EMAIL}"

# ── VAPID key auto-generation ─────────────────────────────────────────────────
if [[ -z "${VAPID_PUBLIC_KEY:-}" ]] || [[ -z "${VAPID_PRIVATE_KEY:-}" ]]; then
  info "VAPID keys not set — auto-generating cryptographically secure VAPID key pair..."
  # Use web-push CLI (available as project devDependency)
  if node -e "require('./node_modules/web-push')" &>/dev/null 2>&1; then
    VAPID_JSON=$(node -e "
      const wp = require('./node_modules/web-push');
      const k = wp.generateVAPIDKeys();
      process.stdout.write(JSON.stringify(k));
    " 2>/dev/null || echo "")
    if [[ -n "${VAPID_JSON}" ]]; then
      GENERATED_PUBLIC=$(echo "${VAPID_JSON}"  | node -e "let d='';process.stdin.on('data',c=>d+=c);process.stdin.on('end',()=>process.stdout.write(JSON.parse(d).publicKey));")
      GENERATED_PRIVATE=$(echo "${VAPID_JSON}" | node -e "let d='';process.stdin.on('data',c=>d+=c);process.stdin.on('end',()=>process.stdout.write(JSON.parse(d).privateKey));")
      # Persist to .env.production
      if grep -q '^VAPID_PUBLIC_KEY=' .env.production 2>/dev/null; then
        sed -i "s|^VAPID_PUBLIC_KEY=.*|VAPID_PUBLIC_KEY=${GENERATED_PUBLIC}|" .env.production
        sed -i "s|^VAPID_PRIVATE_KEY=.*|VAPID_PRIVATE_KEY=${GENERATED_PRIVATE}|" .env.production
      else
        { echo ""; echo "# Auto-generated VAPID keys ($(date -u '+%Y-%m-%dT%H:%M:%SZ'))"; echo "VAPID_PUBLIC_KEY=${GENERATED_PUBLIC}"; echo "VAPID_PRIVATE_KEY=${GENERATED_PRIVATE}"; } >> .env.production
      fi
      export VAPID_PUBLIC_KEY="${GENERATED_PUBLIC}" VAPID_PRIVATE_KEY="${GENERATED_PRIVATE}"
      log "VAPID keys generated and persisted to .env.production"
      log "  Public key prefix: ${GENERATED_PUBLIC:0:24}..."
    else
      warn "web-push key generation returned empty output — push notifications disabled"
    fi
  else
    warn "web-push not available in node_modules — run 'pnpm install' first"
    warn "Then re-run this script, or manually run: npx web-push generate-vapid-keys"
  fi
else
  log "VAPID keys already configured (${VAPID_PUBLIC_KEY:0:16}...)"
fi

# ── Validate critical secrets ─────────────────────────────────────────────────
MISSING_SECRETS=()
[[ -z "${JWT_SECRET:-}" ]]              && MISSING_SECRETS+=("JWT_SECRET")
[[ -z "${POSTGRES_URL:-}" ]]           && MISSING_SECRETS+=("POSTGRES_URL")
[[ -z "${KEYCLOAK_CLIENT_SECRET:-}" ]] && MISSING_SECRETS+=("KEYCLOAK_CLIENT_SECRET")
[[ -z "${MINIO_SECRET_KEY:-}" ]]       && MISSING_SECRETS+=("MINIO_SECRET_KEY")
[[ -z "${APISIX_ADMIN_KEY:-}" ]]       && MISSING_SECRETS+=("APISIX_ADMIN_KEY")
[[ -z "${CRON_SECRET:-}" ]]            && MISSING_SECRETS+=("CRON_SECRET")
if [[ ${#MISSING_SECRETS[@]} -gt 0 ]]; then
  warn "The following required secrets are not set in .env.production:"
  for secret in "${MISSING_SECRETS[@]}"; do
    warn "  ✗ ${secret}"
  done
  warn "The platform will start but some features will be degraded."
  warn "Set these secrets in .env.production before going live."
else
  log "All critical secrets validated"
fi

# ── Step 3: Pull images ───────────────────────────────────────────────────────
step "3/13 — Pulling Docker images"

if [[ "${SKIP_PULL}" == "true" ]]; then
  warn "Skipping image pull (--skip-pull)"
else
  run "docker compose -f docker-compose.production.yml --profile ${COMPOSE_PROFILE} pull --quiet"
  log "All images pulled"
fi

# ── Step 4: Start infrastructure tier ────────────────────────────────────────
step "4/13 — Starting infrastructure services"

run "docker compose -f docker-compose.production.yml --profile infra up -d"

info "Waiting for infrastructure services to be healthy..."
INFRA_SERVICES=(postgres redis kafka tigerbeetle minio vault keycloak)
for svc in "${INFRA_SERVICES[@]}"; do
  info "Waiting for ${svc}..."
  for i in $(seq 1 60); do
    STATUS=$(docker compose -f docker-compose.production.yml ps --format json "${svc}" 2>/dev/null | jq -r '.[0].Health // "unknown"' 2>/dev/null || echo "unknown")
    if [[ "${STATUS}" == "healthy" ]]; then
      log "${svc} is healthy"
      break
    fi
    [[ $i -eq 60 ]] && warn "${svc} did not become healthy after 60 attempts (continuing anyway)"
    sleep 3
  done
done

# ── Step 5: Database migrations ───────────────────────────────────────────────
step "5/13 — Running database migrations"

run "docker compose -f docker-compose.production.yml run --rm app pnpm db:push"
log "Database migrations complete"

# ── Step 6: MinIO initialisation ──────────────────────────────────────────────
step "6/13 — Initialising MinIO buckets"

run "docker compose -f docker-compose.production.yml run --rm minio-init"
log "MinIO buckets and lifecycle policies configured"

# ── Step 7: Vault initialisation ─────────────────────────────────────────────
step "7/13 — Bootstrapping HashiCorp Vault"

if [[ "${SKIP_VAULT}" == "true" ]]; then
  warn "Skipping Vault initialisation (--skip-vault)"
else
  VAULT_ADDR="${VAULT_ADDR:-http://localhost:8200}"
  VAULT_INIT_STATUS=$(curl -sf "${VAULT_ADDR}/v1/sys/init" | jq -r '.initialized' 2>/dev/null || echo "false")

  if [[ "${VAULT_INIT_STATUS}" == "true" ]]; then
    warn "Vault already initialised — skipping init"
  else
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
if curl -sf -H "X-API-KEY: ${APISIX_ADMIN_KEY:-edd1c9f034335f136f87ad84b625c8f1}" "${APISIX_ADMIN_URL}/apisix/admin/routes" &>/dev/null; then
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

run "docker compose -f docker-compose.production.yml --profile app up -d"
log "Application services started"

# ── Step 12: Start monitoring tier ────────────────────────────────────────────
step "12/13 — Starting monitoring services"

run "docker compose -f docker-compose.production.yml --profile monitoring up -d"
log "Monitoring services started (Prometheus, Grafana, Alertmanager)"

# ── Step 13: Health checks ────────────────────────────────────────────────────
step "13/13 — Running health checks"

APP_URL="${APP_URL:-http://localhost:3000}"
SERVICES_TO_CHECK=(
  "${APP_URL}/health:Main App"
  "http://localhost:9090/-/healthy:Prometheus"
  "http://localhost:3001/api/health:Grafana"
  "http://localhost:9000/minio/health/live:MinIO"
  "http://localhost:9080:APISix"
)

HEALTHY=0
UNHEALTHY=0
for entry in "${SERVICES_TO_CHECK[@]}"; do
  url="${entry%%:*}"
  name="${entry##*:}"
  if curl -sf --max-time 5 "${url}" &>/dev/null; then
    log "${name}: healthy"
    ((HEALTHY++))
  else
    warn "${name}: not responding at ${url}"
    ((UNHEALTHY++))
  fi
done

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  54Link Production Bootstrap Complete"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "  Services healthy: ${HEALTHY}/${#SERVICES_TO_CHECK[@]}"
echo ""
echo "  Access URLs:"
echo "    Main App:      ${APP_URL}"
echo "    Grafana:       http://localhost:3001  (admin / admin)"
echo "    Prometheus:    http://localhost:9090"
echo "    Alertmanager:  http://localhost:9093"
echo "    MinIO Console: http://localhost:9001"
echo "    Keycloak:      http://localhost:8080"
echo "    Vault:         http://localhost:8200"
echo "    APISix:        http://localhost:9080"
echo ""
echo "  Logs:  docker compose -f docker-compose.production.yml logs -f"
echo "  Stop:  docker compose -f docker-compose.production.yml down"
echo ""
if [[ ${UNHEALTHY} -gt 0 ]]; then
  warn "${UNHEALTHY} service(s) did not respond to health checks."
  warn "Check logs: docker compose -f docker-compose.production.yml logs --tail=50"
fi
echo "═══════════════════════════════════════════════════════════════"
