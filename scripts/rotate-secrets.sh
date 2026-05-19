#!/usr/bin/env bash
# =============================================================================
# 54Link Platform — Secret Rotation Script
# =============================================================================
# Generates fresh cryptographically secure values for all platform secrets
# and writes them to .env.production.
#
# Usage:
#   ./scripts/rotate-secrets.sh [--dry-run] [--env-file <path>]
#
# Options:
#   --dry-run       Print new values without writing to the env file
#   --env-file      Path to env file (default: .env.production)
#   --force         Skip confirmation prompt
#
# Secrets rotated:
#   JWT_SECRET              — 64-byte hex (session cookie signing)
#   INTERNAL_API_KEY        — 32-byte hex (service-to-service auth)
#   CRON_SECRET             — 32-byte hex (cron job authentication)
#   MINIO_ROOT_PASSWORD     — 32-char alphanumeric
#   MINIO_ACCESS_KEY        — 20-char alphanumeric
#   MINIO_SECRET_KEY        — 40-char alphanumeric
#   APISIX_ADMIN_KEY        — 32-byte hex
#   TIGERBEETLE_CLUSTER_ID  — random 32-bit unsigned int
#   VAPID_PUBLIC_KEY        — generated via web-push
#   VAPID_PRIVATE_KEY       — generated via web-push
#
# =============================================================================

set -euo pipefail

# ── Defaults ──────────────────────────────────────────────────────────────────
ENV_FILE=".env.production"
DRY_RUN=false
FORCE=false
BACKUP_SUFFIX=".bak.$(date +%Y%m%d_%H%M%S)"

# ── Parse arguments ───────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)   DRY_RUN=true; shift ;;
    --force)     FORCE=true; shift ;;
    --env-file)  ENV_FILE="$2"; shift 2 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

# ── Colors ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

log_info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
log_success() { echo -e "${GREEN}[OK]${NC}   $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ── Check prerequisites ───────────────────────────────────────────────────────
check_prereqs() {
  local missing=()
  command -v openssl &>/dev/null || missing+=("openssl")
  command -v node    &>/dev/null || missing+=("node")
  command -v npx     &>/dev/null || missing+=("npx")
  if [[ ${#missing[@]} -gt 0 ]]; then
    log_error "Missing required tools: ${missing[*]}"
    exit 1
  fi
}

# ── Secret generation functions ───────────────────────────────────────────────
gen_hex()         { openssl rand -hex "$1"; }
gen_base64()      { openssl rand -base64 "$1" | tr -d '=\n/+' | head -c "$1"; }
gen_alphanum()    { openssl rand -base64 64 | tr -dc 'A-Za-z0-9' | head -c "$1"; }
gen_uint32()      { python3 -c "import secrets; print(secrets.randbelow(2**32))"; }

# ── Generate VAPID keys ───────────────────────────────────────────────────────
gen_vapid_keys() {
  local output
  output=$(npx web-push generate-vapid-keys --json 2>/dev/null || echo '{}')
  VAPID_PUBLIC_KEY=$(echo "$output" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('publicKey',''))" 2>/dev/null || echo "")
  VAPID_PRIVATE_KEY=$(echo "$output" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('privateKey',''))" 2>/dev/null || echo "")
  if [[ -z "$VAPID_PUBLIC_KEY" || -z "$VAPID_PRIVATE_KEY" ]]; then
    log_warn "web-push VAPID generation failed — using openssl fallback"
    VAPID_PRIVATE_KEY=$(openssl ecparam -name prime256v1 -genkey -noout 2>/dev/null | openssl ec -outform DER 2>/dev/null | tail -c +8 | head -c 32 | base64 | tr -d '=' | tr '/+' '_-' || gen_base64 32)
    VAPID_PUBLIC_KEY="(regenerate-manually-with-npx-web-push-generate-vapid-keys)"
  fi
}

# ── Update a single key in the env file ──────────────────────────────────────
update_env_key() {
  local key="$1"
  local value="$2"
  local file="$3"

  if grep -q "^${key}=" "$file" 2>/dev/null; then
    # Key exists — replace it
    sed -i "s|^${key}=.*|${key}=${value}|" "$file"
  else
    # Key doesn't exist — append it
    echo "${key}=${value}" >> "$file"
  fi
}

# ── Main ──────────────────────────────────────────────────────────────────────
main() {
  echo ""
  echo -e "${BOLD}╔══════════════════════════════════════════════════════════════╗${NC}"
  echo -e "${BOLD}║         54Link Platform — Secret Rotation                    ║${NC}"
  echo -e "${BOLD}╚══════════════════════════════════════════════════════════════╝${NC}"
  echo ""

  check_prereqs

  if [[ "$DRY_RUN" == "true" ]]; then
    log_warn "DRY RUN MODE — no changes will be written to disk"
    echo ""
  fi

  # Confirm before rotating
  if [[ "$FORCE" == "false" && "$DRY_RUN" == "false" ]]; then
    echo -e "${YELLOW}WARNING: This will rotate ALL platform secrets in ${ENV_FILE}${NC}"
    echo -e "${YELLOW}         All running services must be restarted after rotation.${NC}"
    echo ""
    read -rp "Are you sure you want to rotate all secrets? [y/N] " confirm
    if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
      log_info "Rotation cancelled."
      exit 0
    fi
    echo ""
  fi

  # Backup existing env file
  if [[ "$DRY_RUN" == "false" && -f "$ENV_FILE" ]]; then
    cp "$ENV_FILE" "${ENV_FILE}${BACKUP_SUFFIX}"
    log_success "Backed up ${ENV_FILE} → ${ENV_FILE}${BACKUP_SUFFIX}"
  fi

  # Generate all new secrets
  log_info "Generating new secrets..."
  echo ""

  NEW_JWT_SECRET=$(gen_hex 64)
  NEW_INTERNAL_API_KEY=$(gen_hex 32)
  NEW_CRON_SECRET=$(gen_hex 32)
  NEW_MINIO_ROOT_PASSWORD=$(gen_alphanum 32)
  NEW_MINIO_ACCESS_KEY=$(gen_alphanum 20)
  NEW_MINIO_SECRET_KEY=$(gen_alphanum 40)
  NEW_APISIX_ADMIN_KEY=$(gen_hex 32)
  NEW_TIGERBEETLE_CLUSTER_ID=$(gen_uint32)
  gen_vapid_keys

  # Display new values
  printf "  %-30s %s\n" "JWT_SECRET"             "${NEW_JWT_SECRET:0:16}...${NEW_JWT_SECRET: -8}"
  printf "  %-30s %s\n" "INTERNAL_API_KEY"        "${NEW_INTERNAL_API_KEY:0:8}...${NEW_INTERNAL_API_KEY: -4}"
  printf "  %-30s %s\n" "CRON_SECRET"             "${NEW_CRON_SECRET:0:8}...${NEW_CRON_SECRET: -4}"
  printf "  %-30s %s\n" "MINIO_ROOT_PASSWORD"     "${NEW_MINIO_ROOT_PASSWORD:0:8}...${NEW_MINIO_ROOT_PASSWORD: -4}"
  printf "  %-30s %s\n" "MINIO_ACCESS_KEY"        "${NEW_MINIO_ACCESS_KEY:0:8}...${NEW_MINIO_ACCESS_KEY: -4}"
  printf "  %-30s %s\n" "MINIO_SECRET_KEY"        "${NEW_MINIO_SECRET_KEY:0:8}...${NEW_MINIO_SECRET_KEY: -4}"
  printf "  %-30s %s\n" "APISIX_ADMIN_KEY"        "${NEW_APISIX_ADMIN_KEY:0:8}...${NEW_APISIX_ADMIN_KEY: -4}"
  printf "  %-30s %s\n" "TIGERBEETLE_CLUSTER_ID"  "${NEW_TIGERBEETLE_CLUSTER_ID}"
  printf "  %-30s %s\n" "VAPID_PUBLIC_KEY"        "${VAPID_PUBLIC_KEY:0:20}..."
  printf "  %-30s %s\n" "VAPID_PRIVATE_KEY"       "${VAPID_PRIVATE_KEY:0:8}..."
  echo ""

  if [[ "$DRY_RUN" == "true" ]]; then
    log_warn "DRY RUN: Values shown above. No files were modified."
    echo ""
    return 0
  fi

  # Write to env file
  log_info "Writing new secrets to ${ENV_FILE}..."

  # Create env file if it doesn't exist
  touch "$ENV_FILE"

  update_env_key "JWT_SECRET"             "$NEW_JWT_SECRET"            "$ENV_FILE"
  update_env_key "INTERNAL_API_KEY"       "$NEW_INTERNAL_API_KEY"      "$ENV_FILE"
  update_env_key "CRON_SECRET"            "$NEW_CRON_SECRET"           "$ENV_FILE"
  update_env_key "MINIO_ROOT_PASSWORD"    "$NEW_MINIO_ROOT_PASSWORD"   "$ENV_FILE"
  update_env_key "MINIO_ACCESS_KEY"       "$NEW_MINIO_ACCESS_KEY"      "$ENV_FILE"
  update_env_key "MINIO_SECRET_KEY"       "$NEW_MINIO_SECRET_KEY"      "$ENV_FILE"
  update_env_key "APISIX_ADMIN_KEY"       "$NEW_APISIX_ADMIN_KEY"      "$ENV_FILE"
  update_env_key "TIGERBEETLE_CLUSTER_ID" "$NEW_TIGERBEETLE_CLUSTER_ID" "$ENV_FILE"
  update_env_key "VAPID_PUBLIC_KEY"       "$VAPID_PUBLIC_KEY"          "$ENV_FILE"
  update_env_key "VAPID_PRIVATE_KEY"      "$VAPID_PRIVATE_KEY"         "$ENV_FILE"

  log_success "All secrets written to ${ENV_FILE}"
  echo ""

  # Post-rotation instructions
  echo -e "${BOLD}╔══════════════════════════════════════════════════════════════╗${NC}"
  echo -e "${BOLD}║  IMPORTANT: Post-Rotation Steps Required                     ║${NC}"
  echo -e "${BOLD}╚══════════════════════════════════════════════════════════════╝${NC}"
  echo ""
  echo -e "  ${YELLOW}1.${NC} Restart all services to pick up new secrets:"
  echo -e "     ${BLUE}make down && make up-all${NC}"
  echo ""
  echo -e "  ${YELLOW}2.${NC} Update MinIO credentials (if MinIO is running):"
  echo -e "     ${BLUE}make minio-rotate-creds MINIO_NEW_PASSWORD=${NEW_MINIO_ROOT_PASSWORD:0:8}...${NC}"
  echo ""
  echo -e "  ${YELLOW}3.${NC} Update APISix admin key:"
  echo -e "     ${BLUE}make apisix-bootstrap${NC}"
  echo ""
  echo -e "  ${YELLOW}4.${NC} Invalidate all active user sessions (JWT rotation):"
  echo -e "     ${BLUE}make invalidate-sessions${NC}"
  echo ""
  echo -e "  ${YELLOW}5.${NC} Update CI/CD secrets in GitHub/GitLab:"
  echo -e "     Update JWT_SECRET, INTERNAL_API_KEY, CRON_SECRET in repository secrets"
  echo ""
  echo -e "  ${YELLOW}6.${NC} Verify all services are healthy:"
  echo -e "     ${BLUE}make health-all${NC}"
  echo ""
  log_success "Secret rotation complete. Backup saved at: ${ENV_FILE}${BACKUP_SUFFIX}"
  echo ""
}

main "$@"
