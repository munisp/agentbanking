#!/bin/bash
# 54Link Staging Environment Health Check
# Validates all services are running and responsive

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

PASS=0
FAIL=0

check_service() {
  local name=$1
  local url=$2
  local expected_status=${3:-200}
  
  status=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "$url" 2>/dev/null || echo "000")
  
  if [ "$status" = "$expected_status" ]; then
    echo -e "${GREEN}[PASS]${NC} $name (HTTP $status)"
    PASS=$((PASS + 1))
  else
    echo -e "${RED}[FAIL]${NC} $name (expected $expected_status, got $status)"
    FAIL=$((FAIL + 1))
  fi
}

check_tcp() {
  local name=$1
  local host=$2
  local port=$3
  
  if nc -z -w5 "$host" "$port" 2>/dev/null; then
    echo -e "${GREEN}[PASS]${NC} $name ($host:$port reachable)"
    PASS=$((PASS + 1))
  else
    echo -e "${RED}[FAIL]${NC} $name ($host:$port unreachable)"
    FAIL=$((FAIL + 1))
  fi
}

echo "=== 54Link Staging Health Check ==="
echo ""

# Core services
check_service "App Server" "http://localhost:3000/api/health"
check_service "App tRPC" "http://localhost:3000/api/trpc"

# Infrastructure
check_tcp "PostgreSQL" "localhost" 5432
check_tcp "Redis" "localhost" 6379
check_tcp "Kafka" "localhost" 9092
check_tcp "Keycloak" "localhost" 8080
check_tcp "Temporal" "localhost" 7233
check_tcp "OTEL Collector (gRPC)" "localhost" 4317
check_tcp "OTEL Collector (HTTP)" "localhost" 4318

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="

if [ $FAIL -gt 0 ]; then
  exit 1
fi
