#!/bin/bash
# Test permission check via kubectl

set -e

# Configuration
NAMESPACE="${PERMIFY_NAMESPACE:-permify}"
TENANT_ID="${TENANT_ID:-bpmgd}"
PERMIFY_PORT="3476"

# Parameters
USER_ID="${1:-}"
PERMISSION="${2:-manage_compliance}"
RESOURCE_TYPE="${3:-bank}"
RESOURCE_ID="${4:-$TENANT_ID}"

if [ -z "$USER_ID" ]; then
    echo "Usage: $0 <user_id> [permission] [resource_type] [resource_id]"
    echo ""
    echo "Example:"
    echo "  $0 03004859-44d0-4447-9d78-c20da127418c manage_compliance bank bpmgd"
    exit 1
fi

echo "🧪 Testing Permission Check"
echo "=================================================="
echo "👤 User ID: $USER_ID"
echo "🔐 Permission: $PERMISSION"
echo "📦 Resource: $RESOURCE_TYPE:$RESOURCE_ID"
echo "🏢 Tenant: $TENANT_ID"
echo ""

# Get first Permify pod
POD_NAME=$(kubectl get pods -n "$NAMESPACE" -l app.kubernetes.io/name=permify -o jsonpath='{.items[0].metadata.name}')

if [ -z "$POD_NAME" ]; then
    echo "❌ No Permify pods found"
    exit 1
fi

# Start port-forward in background
echo "🔄 Setting up port-forward..."
kubectl port-forward -n "$NAMESPACE" "$POD_NAME" "$PERMIFY_PORT:$PERMIFY_PORT" > /dev/null 2>&1 &
PORT_FORWARD_PID=$!

# Wait for port-forward to be ready
sleep 2

# Cleanup function
cleanup() {
    kill $PORT_FORWARD_PID 2>/dev/null || true
}
trap cleanup EXIT

# Prepare payload
PAYLOAD=$(jq -n \
  --arg tenant "$TENANT_ID" \
  --arg type "$RESOURCE_TYPE" \
  --arg id "$RESOURCE_ID" \
  --arg perm "$PERMISSION" \
  --arg user "$USER_ID" \
  '{tenant_id: $tenant, entity: {type: $type, id: $id}, permission: $perm, subject: {type: "user", id: $user}, metadata: {schema_version: "1.0"}}')

echo "🚀 Checking permission via Permify..."
echo ""

RESPONSE=$(curl -s -X POST "http://localhost:$PERMIFY_PORT/v1/tenants/$TENANT_ID/permissions/check" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD")

echo "Response:"
echo "$RESPONSE" | jq -C '.'

# Parse result
CAN=$(echo "$RESPONSE" | jq -r '.can // empty')

if [ "$CAN" = "RESULT_ALLOWED" ]; then
    echo ""
    echo "✅ Permission GRANTED"
    exit 0
elif [ "$CAN" = "RESULT_DENIED" ]; then
    echo ""
    echo "❌ Permission DENIED"
    exit 1
else
    echo ""
    echo "⚠️  Unknown response"
    exit 2
fi
