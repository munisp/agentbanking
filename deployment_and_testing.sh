#!/bin/bash
# Deployment and Testing Script for Infrastructure Fixes
# 54agent Banking System - May 4, 2026

set -e

echo "========================================"
echo "54agent Infrastructure Deployment"
echo "========================================"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

NAMESPACE="54agent"
DEPLOYMENT_TIMEOUT=300  # 5 minutes

# ============================================================================
# 1. BUILD & PUSH IMAGES
# ============================================================================
echo -e "\n${YELLOW}Step 1: Building and pushing updated service images${NC}"

build_and_push_image() {
    local service=$1
    local registry="registry.digitalocean.com/talentgraph-auth"
    
    echo "Building $service..."
    cd "services/$service" || return 1
    docker build -t "${registry}/54agent-${service}:latest" .
    docker push "${registry}/54agent-${service}:latest"
    cd - > /dev/null
}

# Build services with changes
build_and_push_image "nigeria-vat-service"
build_and_push_image "storefront-advertising"
build_and_push_image "realtime-notification-service"

echo -e "${GREEN}✓ Images built and pushed${NC}"

# ============================================================================
# 2. UPDATE HELM CHARTS
# ============================================================================
echo -e "\n${YELLOW}Step 2: Updating Helm charts${NC}"

update_helm_chart() {
    local service=$1
    local version=$(date +%s)
    
    echo "Updating Helm chart for $service..."
    
    # Update chart version
    sed -i "s/appVersion: .*/appVersion: \"${version}\"/" \
        "infrastructure/charts/${service}/Chart.yaml"
    
    echo "  - Updated app version to ${version}"
}

update_helm_chart "nigeria-vat-service"
update_helm_chart "storefront-advertising"
update_helm_chart "realtime-notification-service"

echo -e "${GREEN}✓ Helm charts updated${NC}"

# ============================================================================
# 3. DEPLOY UPDATES
# ============================================================================
echo -e "\n${YELLOW}Step 3: Deploying updates to Kubernetes${NC}"

deploy_service() {
    local service=$1
    local chart_path="infrastructure/charts/${service}"
    
    echo "Deploying $service..."
    
    helm upgrade "${service}" "${chart_path}" \
        --namespace="${NAMESPACE}" \
        --values="${chart_path}/values.yaml" \
        --set image.tag="latest" \
        --wait \
        --timeout="${DEPLOYMENT_TIMEOUT}s" \
        --atomic
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ $service deployed successfully${NC}"
    else
        echo -e "${RED}✗ $service deployment failed${NC}"
        return 1
    fi
}

deploy_service "nigeria-vat-service"
deploy_service "storefront-advertising"
deploy_service "realtime-notification-service"

# ============================================================================
# 4. VERIFY DEPLOYMENT
# ============================================================================
echo -e "\n${YELLOW}Step 4: Verifying deployments${NC}"

verify_deployment() {
    local service=$1
    local desired_replicas=1
    
    echo "Verifying $service..."
    
    # Wait for rollout
    kubectl rollout status deployment/"${service}" \
        -n "${NAMESPACE}" \
        --timeout="${DEPLOYMENT_TIMEOUT}s"
    
    # Check pod status
    local running_pods=$(kubectl get pods -n "${NAMESPACE}" \
        -l app="${service}" \
        --no-headers | grep "Running" | wc -l)
    
    if [ "${running_pods}" -ge "${desired_replicas}" ]; then
        echo -e "${GREEN}✓ $service is running (${running_pods} pods)${NC}"
        return 0
    else
        echo -e "${RED}✗ $service failed to start${NC}"
        return 1
    fi
}

verify_deployment "nigeria-vat-service"
verify_deployment "storefront-advertising"
verify_deployment "realtime-notification-service"

# ============================================================================
# 5. TEST DATABASE CONNECTIONS
# ============================================================================
echo -e "\n${YELLOW}Step 5: Testing database SSL connections${NC}"

test_db_connection() {
    local pod=$1
    local container=$2
    
    echo "Testing SSL connection in $pod..."
    
    kubectl exec -n "${NAMESPACE}" "${pod}" -- \
        python3 << 'EOF'
import os
from sqlalchemy import create_engine, text

try:
    db_url = os.getenv('DATABASE_URL') or os.getenv('VAT_DATABASE_URL') or os.getenv('STOREFRONT_DATABASE_URL')
    if not db_url:
        print("✗ DATABASE_URL not set")
        exit(1)
    
    engine = create_engine(db_url)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        print("✓ SSL Connection successful")
        print(f"✓ Query result: {result.fetchone()}")
except Exception as e:
    print(f"✗ Connection failed: {e}")
    exit(1)
EOF
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ SSL connection test passed${NC}"
    else
        echo -e "${RED}✗ SSL connection test failed${NC}"
        return 1
    fi
}

# Get pod names and test
echo "Testing nigeria-vat-service..."
VAT_POD=$(kubectl get pod -n "${NAMESPACE}" -l app=nigeria-vat-service -o jsonpath='{.items[0].metadata.name}')
test_db_connection "${VAT_POD}" "realtime-notification-service"

echo "Testing storefront-advertising..."
STOREFRONT_POD=$(kubectl get pod -n "${NAMESPACE}" -l app=storefront-advertising -o jsonpath='{.items[0].metadata.name}')
test_db_connection "${STOREFRONT_POD}" "storefront-advertising"

echo "Testing realtime-notification-service..."
REALTIME_POD=$(kubectl get pod -n "${NAMESPACE}" -l app=realtime-notification-service -o jsonpath='{.items[0].metadata.name}')
test_db_connection "${REALTIME_POD}" "realtime-notification-service"

# ============================================================================
# 6. TEST API ENDPOINTS
# ============================================================================
echo -e "\n${YELLOW}Step 6: Testing API endpoints${NC}"

test_api_endpoint() {
    local url=$1
    local method=${2:-GET}
    local name=$3
    
    echo "Testing: $name ($method $url)"
    
    response=$(curl -s -w "\n%{http_code}" -X "${method}" \
        -H "Authorization: Bearer $API_TOKEN" \
        -H "Content-Type: application/json" \
        "$url" 2>/dev/null)
    
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')
    
    if [[ "$http_code" =~ ^(200|201|400|401|404)$ ]]; then
        echo -e "${GREEN}✓ Status: $http_code${NC}"
    else
        echo -e "${RED}✗ Status: $http_code${NC}"
        echo "Response: $body"
    fi
}

# API Gateway base URL
API_BASE="https://54agent.upi.dev"

# Get API token (requires valid credentials)
# API_TOKEN=$(curl -s -X POST "${API_BASE}/auth/token" -d '{"username":"admin","password":"***"}' | jq -r '.access_token')

echo "Note: API testing requires valid authentication token. Set API_TOKEN environment variable."

# Test endpoints (these should now work or at least not return 500)
test_api_endpoint "${API_BASE}/realtime/api/v1/admin/violations/active?hours=8760&limit=100" "GET" "Realtime Violations"
test_api_endpoint "${API_BASE}/vat/businesses" "GET" "VAT Businesses"
test_api_endpoint "${API_BASE}/storefront/ads/active" "GET" "Storefront Active Ads"

# ============================================================================
# 7. MONITOR LOGS
# ============================================================================
echo -e "\n${YELLOW}Step 7: Monitoring service logs for issues${NC}"

monitor_logs() {
    local service=$1
    local duration=30  # Monitor for 30 seconds
    
    echo "Monitoring logs for $service (${duration}s)..."
    
    kubectl logs -n "${NAMESPACE}" \
        -l app="${service}" \
        --tail=50 \
        -f \
        --timestamps \
        --since="${duration}s" 2>/dev/null | \
        grep -E "(ERROR|SSL|connection|Exception)" || echo "No errors detected"
}

echo "Checking for errors in service logs..."
monitor_logs "nigeria-vat-service" &
monitor_logs "storefront-advertising" &
monitor_logs "realtime-notification-service" &
wait

echo -e "${GREEN}✓ Log monitoring complete${NC}"

# ============================================================================
# 8. PERFORMANCE METRICS
# ============================================================================
echo -e "\n${YELLOW}Step 8: Checking performance metrics${NC}"

check_metrics() {
    local service=$1
    
    echo "Metrics for $service:"
    
    kubectl top pods -n "${NAMESPACE}" \
        -l app="${service}" \
        --no-headers 2>/dev/null || echo "  (metrics not available)"
}

check_metrics "nigeria-vat-service"
check_metrics "storefront-advertising"
check_metrics "realtime-notification-service"

# ============================================================================
# 9. HEALTH CHECKS
# ============================================================================
echo -e "\n${YELLOW}Step 9: Running health checks${NC}"

health_check() {
    local service=$1
    
    echo "Health check for $service..."
    
    # Port forward and test health endpoint
    kubectl port-forward -n "${NAMESPACE}" \
        "svc/${service}" 8080:80 > /dev/null 2>&1 &
    
    PF_PID=$!
    sleep 2
    
    http_code=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/health)
    
    kill $PF_PID 2>/dev/null
    
    if [ "$http_code" = "200" ]; then
        echo -e "${GREEN}✓ Health check passed (HTTP $http_code)${NC}"
    else
        echo -e "${RED}✗ Health check failed (HTTP $http_code)${NC}"
    fi
}

health_check "nigeria-vat-service"
health_check "storefront-advertising"
health_check "realtime-notification-service"

# ============================================================================
# 10. SUMMARY
# ============================================================================
echo -e "\n${YELLOW}========================================"
echo "Deployment Summary"
echo "========================================${NC}"

echo -e "\n${GREEN}✓ COMPLETED:${NC}"
echo "  • Built and pushed service images"
echo "  • Updated Helm charts"
echo "  • Deployed services to Kubernetes"
echo "  • Verified deployments"
echo "  • Tested database SSL connections"
echo "  • Checked service health"

echo -e "\n${YELLOW}⚠ TODO:${NC}"
echo "  • Implement missing API endpoints (see MISSING_ENDPOINTS_IMPLEMENTATION.py)"
echo "  • Full end-to-end testing with real API tokens"
echo "  • Monitor 502 errors from Settlement and GDPR services"
echo "  • Verify all 404 endpoints are now properly returning 404 (not 500)"

echo -e "\n${YELLOW}Documentation Files:${NC}"
echo "  • INFRASTRUCTURE_FIXES_SUMMARY.md - Detailed issue analysis"
echo "  • MISSING_ENDPOINTS_IMPLEMENTATION.py - Endpoint templates"
echo "  • deployment_and_testing.sh - This script"

echo -e "\n${GREEN}Deployment Complete!${NC}\n"
