#!/bin/bash

# Reset Permify - Restart container to clear all data
# This ensures a completely clean slate for testing

echo "========================================="
echo "Permify Reset Script"
echo "========================================="
echo ""

echo "Step 1: Finding Permify container..."
CONTAINER_ID=$(docker ps --filter "ancestor=ghcr.io/permify/permify" --format "{{.ID}}")

if [ -z "$CONTAINER_ID" ]; then
    echo "✗ No Permify container found"
    echo "Start Permify with: ./start_permify.sh"
    exit 1
fi

echo "✓ Found container: $CONTAINER_ID"
echo ""

echo "Step 2: Restarting Permify container..."
docker restart $CONTAINER_ID

echo ""
echo "Step 3: Waiting for Permify to be ready..."
sleep 3

# Check if Permify is responding
for i in {1..10}; do
    if curl -s http://localhost:3476/healthz > /dev/null 2>&1; then
        echo "✓ Permify is ready!"
        break
    fi
    echo "  Waiting... ($i/10)"
    sleep 1
done

echo ""
echo "Step 4: Reloading schema..."
cd /home/tani/Documents/54agent/54agent_core_banking/services/auth-service

if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

python3 << 'PYTHON'
from adapters.permify import load_schema
success = load_schema()
if success:
    print("✓ Schema reloaded successfully")
else:
    print("✗ Failed to reload schema")
PYTHON

echo ""
echo "========================================="
echo "Permify has been reset!"
echo "All permission data cleared."
echo "========================================="
echo ""
echo "You can now run: python3 test_permissions_direct.py"
