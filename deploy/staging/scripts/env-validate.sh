#!/bin/bash
# 54Link Environment Validation
# Ensures all required environment variables are set before deployment

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

MISSING=0
WARNINGS=0

require_var() {
  local var_name=$1
  local description=$2
  if [ -z "${!var_name}" ]; then
    echo -e "${RED}[MISSING]${NC} $var_name — $description"
    MISSING=$((MISSING + 1))
  else
    echo -e "${GREEN}[SET]${NC} $var_name"
  fi
}

warn_var() {
  local var_name=$1
  local description=$2
  if [ -z "${!var_name}" ]; then
    echo -e "${YELLOW}[WARN]${NC} $var_name — $description (optional)"
    WARNINGS=$((WARNINGS + 1))
  else
    echo -e "${GREEN}[SET]${NC} $var_name"
  fi
}

echo "=== 54Link Environment Validation ==="
echo ""

echo "--- Core ---"
require_var "DATABASE_URL" "PostgreSQL connection string"
require_var "JWT_SECRET" "JWT signing secret (min 32 chars)"
require_var "REDIS_URL" "Redis connection string"

echo ""
echo "--- Security ---"
require_var "CSRF_SECRET" "CSRF token secret"
warn_var "RATE_LIMIT_MAX" "Max requests per window (default: 100)"

echo ""
echo "--- Integrations ---"
warn_var "KAFKA_BROKERS" "Kafka broker addresses"
warn_var "KEYCLOAK_URL" "Keycloak IAM URL"
warn_var "TEMPORAL_ADDRESS" "Temporal workflow engine address"
warn_var "OTEL_EXPORTER_OTLP_ENDPOINT" "OpenTelemetry collector endpoint"

echo ""
echo "--- Payment Providers ---"
warn_var "PAYSTACK_SECRET_KEY" "Paystack payment gateway"
warn_var "FLUTTERWAVE_SECRET_KEY" "Flutterwave payment gateway"

echo ""
echo "--- CBN Compliance ---"
warn_var "CBN_REPORTING_URL" "CBN regulatory reporting endpoint"
warn_var "NIN_VERIFICATION_URL" "NIN verification service"
warn_var "BVN_VERIFICATION_URL" "BVN verification service"

echo ""
echo "=== Results: $MISSING required missing, $WARNINGS optional missing ==="

if [ $MISSING -gt 0 ]; then
  echo -e "${RED}Cannot proceed with deployment — $MISSING required variables missing${NC}"
  exit 1
fi
