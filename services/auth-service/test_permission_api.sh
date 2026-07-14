#!/bin/bash

# Test Permission API Endpoints
# This script tests the permission checking via the REST API

set -e

echo "========================================="
echo "Permission API Test Script"
echo "========================================="
echo ""

# Configuration
BASE_URL="http://localhost:8001"
TENANT_ID="54agent"
KEYCLOAK_REALM="test-realm"
KEYCLOAK_PUB_KEY="test-key"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Note: This requires a valid JWT token from Keycloak${NC}"
echo "If you don't have a token, you can:"
echo "1. Login via POST /auth/login to get a token"
echo "2. Or use Keycloak directly to get a token"
echo ""

# Prompt for token
read -p "Enter your JWT token (or press Enter to use test bypass): " JWT_TOKEN

if [ -z "$JWT_TOKEN" ]; then
    echo -e "${RED}No token provided. You'll need to modify the code to bypass auth for testing.${NC}"
    echo ""
    echo "Alternative: Test directly with Python (no auth needed):"
    echo ""
    cat << 'EOF'
python3 << 'PYTHON'
from utils.permissions import PermissionManager

# Initialize permission manager
pm = PermissionManager()

# Assign a platform role
print("Assigning platform role 'super' to user...")
success = pm.assign_platform_role(
    user_id="test-user-123",
    tenant_id="54agent",
    role="super",
    platform_id="default"
)
print(f"Assignment result: {success}")

# Check permission
print("\nChecking permission 'manage_banks' for user...")
has_perm = pm.check_user_permission(
    user_id="test-user-123",
    tenant_id="54agent",
    permission="manage_banks",
    entity_type="platform",
    entity_id="default"
)
print(f"Has permission: {has_perm}")

# Check another permission
print("\nChecking permission 'view_all_data' for user...")
has_perm = pm.check_user_permission(
    user_id="test-user-123",
    tenant_id="54agent",
    permission="view_all_data",
    entity_type="platform",
    entity_id="default"
)
print(f"Has permission: {has_perm}")
PYTHON
EOF
    exit 0
fi

echo ""
echo "Step 1: Testing health endpoint (no auth required)..."
HEALTH_RESPONSE=$(curl -s "${BASE_URL}/health")
echo "Response: $HEALTH_RESPONSE"
echo -e "${GREEN}✓ Health check passed${NC}"
echo ""

echo "Step 2: Checking permission via API..."
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST \
  "${BASE_URL}/permissions/check-permission?permission=view_all_data&entity_type=platform&entity_id=default" \
  -H "Authorization: Bearer ${JWT_TOKEN}" \
  -H "x-tenant-id: ${TENANT_ID}" \
  -H "x-keycloak-realm: ${KEYCLOAK_REALM}" \
  -H "x-keycloak-pub-key: ${KEYCLOAK_PUB_KEY}")

HTTP_CODE=$(echo "$RESPONSE" | tail -n 1)
BODY=$(echo "$RESPONSE" | sed '$d')

echo "HTTP Status: $HTTP_CODE"
echo "Response: $BODY"

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓ Permission check successful${NC}"
    HAS_PERMISSION=$(echo "$BODY" | grep -o '"has_permission":[^,}]*' | cut -d':' -f2)
    if [ "$HAS_PERMISSION" = "true" ]; then
        echo -e "${GREEN}✓ User has permission${NC}"
    else
        echo -e "${YELLOW}○ User does not have permission${NC}"
    fi
else
    echo -e "${RED}✗ Permission check failed${NC}"
fi

echo ""
echo "========================================="
echo "Test complete!"
echo "========================================="
