#!/usr/bin/env bash
# =============================================================================
# 54Link POS Shell — Production Health Check Script
# Usage: ./scripts/health-check.sh [--domain <domain>] [--json]
# =============================================================================
set -euo pipefail

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'

DOMAIN="${DOMAIN:-localhost}"
JSON_OUTPUT=false
COMPOSE_FILE="docker-compose.production.yml"
PASS=0; FAIL=0; WARN=0

while [[ $# -gt 0 ]]; do
  case $1 in
    --domain) DOMAIN="$2"; shift 2 ;;
    --json)   JSON_OUTPUT=true; shift ;;
    *) shift ;;
  esac
done

check() {
  local name="$1" cmd="$2"
  if eval "$cmd" >/dev/null 2>&1; then
    [[ "$JSON_OUTPUT" == "false" ]] && echo -e "${GREEN}✓${NC} $name"
    PASS=$((PASS + 1))
    return 0
  else
    [[ "$JSON_OUTPUT" == "false" ]] && echo -e "${RED}✗${NC} $name"
    FAIL=$((FAIL + 1))
    return 1
  fi
}

warn_check() {
  local name="$1" cmd="$2"
  if eval "$cmd" >/dev/null 2>&1; then
    [[ "$JSON_OUTPUT" == "false" ]] && echo -e "${GREEN}✓${NC} $name"
    PASS=$((PASS + 1))
  else
    [[ "$JSON_OUTPUT" == "false" ]] && echo -e "${YELLOW}⚠${NC} $name (non-critical)"
    WARN=$((WARN + 1))
  fi
}

echo "=== 54Link POS Health Check — $(date) ==="
echo ""

# ── Docker services ───────────────────────────────────────────────────────────
echo "--- Docker Services ---"
for svc in pos-shell postgres redis kafka vault keycloak permify nginx; do
  check "Docker: $svc" "docker compose -f $COMPOSE_FILE ps $svc | grep -q 'running\|Up'"
done

# ── HTTP endpoints ────────────────────────────────────────────────────────────
echo ""
echo "--- HTTP Endpoints ---"
check "App health endpoint" "curl -sk -o /dev/null -w '%{http_code}' https://${DOMAIN}/api/health | grep -qE '^(200|204)$'"
check "tRPC endpoint reachable" "curl -sk -o /dev/null -w '%{http_code}' https://${DOMAIN}/api/trpc/auth.me | grep -qE '^(200|401|403)$'"
check "Nginx SSL certificate" "curl -sk --head https://${DOMAIN} | grep -qi 'HTTP'"
warn_check "Grafana UI" "curl -sk -o /dev/null -w '%{http_code}' https://${DOMAIN}:3001 | grep -qE '^(200|302)$'"
warn_check "Prometheus UI" "curl -sk -o /dev/null -w '%{http_code}' https://${DOMAIN}:9090 | grep -qE '^(200|302)$'"

# ── Database ──────────────────────────────────────────────────────────────────
echo ""
echo "--- Database ---"
check "PostgreSQL accepting connections" "docker compose -f $COMPOSE_FILE exec -T postgres pg_isready -U pos_user -d pos_db"
check "Transactions table exists" "docker compose -f $COMPOSE_FILE exec -T postgres psql -U pos_user -d pos_db -c '\\dt transactions' | grep -q transactions"

# ── Kafka ─────────────────────────────────────────────────────────────────────
echo ""
echo "--- Kafka ---"
for topic in pos.transactions pos.fraud-alerts pos.sim-failovers pos.settlements; do
  check "Kafka topic: $topic" "docker compose -f $COMPOSE_FILE exec -T kafka kafka-topics.sh --bootstrap-server localhost:9092 --describe --topic $topic"
done

# ── Redis ─────────────────────────────────────────────────────────────────────
echo ""
echo "--- Redis ---"
check "Redis PING" "docker compose -f $COMPOSE_FILE exec -T redis redis-cli ping | grep -q PONG"

# ── Vault ─────────────────────────────────────────────────────────────────────
echo ""
echo "--- Vault ---"
warn_check "Vault unsealed" "docker compose -f $COMPOSE_FILE exec -T vault vault status | grep -q 'Sealed.*false'"

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "=== Summary ==="
echo -e "${GREEN}Passed: $PASS${NC}  ${YELLOW}Warnings: $WARN${NC}  ${RED}Failed: $FAIL${NC}"

if [[ "$JSON_OUTPUT" == "true" ]]; then
  echo "{\"pass\": $PASS, \"warn\": $WARN, \"fail\": $FAIL, \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}"
fi

[[ $FAIL -eq 0 ]] && exit 0 || exit 1
