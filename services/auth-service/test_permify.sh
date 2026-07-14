#!/bin/bash

# Test script for Permify integration
# This script helps you test the Permify implementation locally

echo "========================================="
echo "Permify Integration Test Script"
echo "========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
    echo -e "${GREEN}✓ Virtual environment activated${NC}"
    echo ""
elif [ -d ".venv" ]; then
    source .venv/bin/activate
    echo -e "${GREEN}✓ Virtual environment activated${NC}"
    echo ""
fi

# Load .env file if it exists
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
    echo -e "${GREEN}✓ Environment variables loaded from .env${NC}"
    echo ""
fi

# Step 1: Check if Permify is running
echo -e "${YELLOW}Step 1: Checking if Permify is running...${NC}"
if curl -s http://localhost:3476/healthz > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Permify is running${NC}"
else
    echo -e "${RED}✗ Permify is not running${NC}"
    echo ""
    echo "To start Permify, run:"
    echo "  docker run -p 3476:3476 ghcr.io/permify/permify serve"
    echo ""
    echo "Or with PostgreSQL:"
    echo "  docker run -p 3476:3476 -e PERMIFY_DATABASE_ENGINE=postgres \\"
    echo "    -e PERMIFY_DATABASE_DSN='postgresql://user:password@host:5432/permify' \\"
    echo "    ghcr.io/permify/permify serve"
    echo ""
    exit 1
fi

echo ""

# Step 2: Check environment variables
echo -e "${YELLOW}Step 2: Checking environment variables...${NC}"
if [ -z "$PERMIFY_URL" ]; then
    echo -e "${RED}✗ PERMIFY_URL not set${NC}"
    echo "Please add PERMIFY_URL=http://localhost:3476 to your .env file"
    exit 1
else
    echo -e "${GREEN}✓ PERMIFY_URL is set to: $PERMIFY_URL${NC}"
fi

echo ""

# Step 3: Test schema loading
echo -e "${YELLOW}Step 3: Testing schema load...${NC}"
python3 << 'EOF'
import sys
sys.path.insert(0, '.')
from adapters.permify import load_schema

try:
    load_schema()
    print("\033[0;32m✓ Schema loaded successfully\033[0m")
except Exception as e:
    print(f"\033[0;31m✗ Schema load failed: {e}\033[0m")
    sys.exit(1)
EOF

if [ $? -ne 0 ]; then
    exit 1
fi

echo ""

# Step 4: Test permission check
echo -e "${YELLOW}Step 4: Testing permission check...${NC}"
python3 << 'EOF'
import sys
sys.path.insert(0, '.')
from adapters.permify import check_permission

try:
    # This will return False since we haven't assigned any roles yet
    result = check_permission(
        user_id="test-user-123",
        tenant_id="54agent",
        permission="view_all_data",
        entity_type="platform",
        entity_id="default"
    )
    print(f"\033[0;32m✓ Permission check executed (result: {result})\033[0m")
except Exception as e:
    print(f"\033[0;31m✗ Permission check failed: {e}\033[0m")
    sys.exit(1)
EOF

if [ $? -ne 0 ]; then
    exit 1
fi

echo ""

# Step 5: Test role assignment
echo -e "${YELLOW}Step 5: Testing role assignment...${NC}"
python3 << 'EOF'
import sys
sys.path.insert(0, '.')
from adapters.permify import assign_role

try:
    result = assign_role(
        user_id="test-user-123",
        tenant_id="54agent",
        role="super",
        entity_type="platform",
        entity_id="default"
    )
    if result:
        print("\033[0;32m✓ Role assignment successful\033[0m")
    else:
        print("\033[0;31m✗ Role assignment returned False\033[0m")
        sys.exit(1)
except Exception as e:
    print(f"\033[0;31m✗ Role assignment failed: {e}\033[0m")
    sys.exit(1)
EOF

if [ $? -ne 0 ]; then
    exit 1
fi

echo ""

# Step 6: Verify permission after role assignment
echo -e "${YELLOW}Step 6: Verifying permission after role assignment...${NC}"
python3 << 'EOF'
import sys
sys.path.insert(0, '.')
from adapters.permify import check_permission

try:
    result = check_permission(
        user_id="test-user-123",
        tenant_id="54agent",
        permission="view_all_data",
        entity_type="platform",
        entity_id="default"
    )
    if result:
        print("\033[0;32m✓ Permission check now returns True (user has permission)\033[0m")
    else:
        print("\033[0;31m✗ Permission check still returns False\033[0m")
        sys.exit(1)
except Exception as e:
    print(f"\033[0;31m✗ Permission verification failed: {e}\033[0m")
    sys.exit(1)
EOF

if [ $? -ne 0 ]; then
    exit 1
fi

echo ""

# Step 7: Test Permission Manager
echo -e "${YELLOW}Step 7: Testing PermissionManager class...${NC}"
python3 << 'EOF'
import sys
sys.path.insert(0, '.')
from utils.permissions import PermissionManager

try:
    pm = PermissionManager()
    
    # Test platform role assignment
    result = pm.assign_platform_role(
        user_id="test-user-456",
        tenant_id="54agent",
        role="analyst",
        platform_id="default"
    )
    
    if result:
        print("\033[0;32m✓ PermissionManager.assign_platform_role successful\033[0m")
    else:
        print("\033[0;31m✗ PermissionManager.assign_platform_role failed\033[0m")
        sys.exit(1)
    
    # Test permission check
    has_perm = pm.check_user_permission(
        user_id="test-user-456",
        tenant_id="54agent",
        permission="view_analytics",
        entity_type="platform",
        entity_id="default"
    )
    
    if has_perm:
        print("\033[0;32m✓ PermissionManager.check_user_permission successful\033[0m")
    else:
        print("\033[0;31m✗ User doesn't have expected permission\033[0m")
        sys.exit(1)
        
except Exception as e:
    print(f"\033[0;31m✗ PermissionManager test failed: {e}\033[0m")
    import traceback
    traceback.print_exc()
    sys.exit(1)
EOF

if [ $? -ne 0 ]; then
    exit 1
fi

echo ""
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}All tests passed! ✓${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""
echo "Next steps:"
echo "1. Start the auth service:"
echo "   ./run.sh"
echo ""
echo "2. Test the API endpoints:"
echo "   curl http://localhost:8001/health"
echo ""
echo "3. Test permission endpoints:"
echo "   curl -X POST http://localhost:8001/permissions/check-permission \\"
echo "     -H 'x-tenant-id: 54agent' \\"
echo "     -H 'x-keycloak-realm: test' \\"
echo "     -H 'x-keycloak-pub-key: test' \\"
echo "     -H 'Authorization: Bearer YOUR_TOKEN' \\"
echo "     -d 'permission=view_all_data&entity_type=platform&entity_id=default'"
echo ""
