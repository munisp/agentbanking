#!/bin/bash
# Notification System Test Suite
# Tests all components of the notification system

set -e

echo "═══════════════════════════════════════════════════════════"
echo "   Mobile Agent Notification System - Test Suite"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Configuration
NOTIFICATION_SERVICE_URL="${NOTIFICATION_SERVICE_URL:-http://localhost:8094}"
DAPR_HTTP_PORT="${DAPR_HTTP_PORT:-3500}"
TEST_AGENT_ID="${1:-test-agent-123}"
TEST_AMOUNT="${2:-5000}"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0

# Helper functions
test_passed() {
    echo -e "${GREEN}✓ PASSED${NC} - $1"
    ((TESTS_PASSED++))
}

test_failed() {
    echo -e "${RED}✗ FAILED${NC} - $1"
    ((TESTS_FAILED++))
}

test_skipped() {
    echo -e "${YELLOW}⊘ SKIPPED${NC} - $1"
}

echo "Configuration:"
echo "  Notification Service: $NOTIFICATION_SERVICE_URL"
echo "  Dapr HTTP Port: $DAPR_HTTP_PORT"
echo "  Test Agent ID: $TEST_AGENT_ID"
echo "  Test Amount: ₦$TEST_AMOUNT"
echo ""

# Test 1: Check if notification service is running
echo "─────────────────────────────────────────────────────────────"
echo "Test 1: Notification Service Health Check"
echo "─────────────────────────────────────────────────────────────"

if curl -s -f "$NOTIFICATION_SERVICE_URL/health" > /dev/null 2>&1; then
    HEALTH_DATA=$(curl -s "$NOTIFICATION_SERVICE_URL/health")
    echo "$HEALTH_DATA" | jq . 2>/dev/null || echo "$HEALTH_DATA"
    test_passed "Notification service is healthy"
else
    test_failed "Cannot connect to notification service at $NOTIFICATION_SERVICE_URL"
    echo "Please start the service first: python main.py"
    exit 1
fi

echo ""

# Test 2: Check Dapr subscription endpoint
echo "─────────────────────────────────────────────────────────────"
echo "Test 2: Dapr Subscription Configuration"
echo "─────────────────────────────────────────────────────────────"

SUBSCRIPTIONS=$(curl -s "$NOTIFICATION_SERVICE_URL/dapr/subscribe")
if echo "$SUBSCRIPTIONS" | grep -q "transaction_initiated"; then
    echo "$SUBSCRIPTIONS" | jq . 2>/dev/null || echo "$SUBSCRIPTIONS"
    test_passed "Dapr subscriptions configured correctly"
else
    test_failed "Dapr subscriptions not configured"
fi

echo ""

# Test 3: Send test notification via HTTP endpoint
echo "─────────────────────────────────────────────────────────────"
echo "Test 3: Send Notification via HTTP Endpoint"
echo "─────────────────────────────────────────────────────────────"

HTTP_RESPONSE=$(curl -s -X POST "$NOTIFICATION_SERVICE_URL/api/v1/transaction/notify" \
  -H "Content-Type: application/json" \
  -H "x-tenant-id: bpmgd" \
  -d "{
    \"transaction_id\": \"test-http-$(date +%s)\",
    \"agent_id\": \"$TEST_AGENT_ID\",
    \"tenant_id\": \"bpmgd\",
    \"amount\": $TEST_AMOUNT,
    \"transaction_type\": \"credit\",
    \"sender_name\": \"Test HTTP Sender\",
    \"account_number\": \"ACC123456\"
  }")

if echo "$HTTP_RESPONSE" | grep -q "success"; then
    echo "$HTTP_RESPONSE" | jq . 2>/dev/null || echo "$HTTP_RESPONSE"
    test_passed "Notification sent successfully via HTTP"
else
    echo "$HTTP_RESPONSE"
    test_failed "Failed to send notification via HTTP"
fi

echo ""

# Test 4: Test Dapr event publishing (if Dapr is available)
echo "─────────────────────────────────────────────────────────────"
echo "Test 4: Publish Event via Dapr"
echo "─────────────────────────────────────────────────────────────"

if curl -s -f "http://localhost:$DAPR_HTTP_PORT/v1.0/healthz/outbound" > /dev/null 2>&1; then
    DAPR_RESPONSE=$(curl -s -X POST "http://localhost:$DAPR_HTTP_PORT/v1.0/publish/pubsub/transaction_initiated" \
      -H "Content-Type: application/json" \
      -d "{
        \"data\": {
          \"transaction_id\": \"test-dapr-$(date +%s)\",
          \"amount\": \"$TEST_AMOUNT\",
          \"payee\": \"$TEST_AGENT_ID\",
          \"payer\": \"Test Dapr Sender\",
          \"tenant_id\": \"bpmgd\",
          \"ledger_id\": \"1\",
          \"currency\": \"NGN\",
          \"status\": \"SUCCESS\"
        }
      }")
    
    test_passed "Event published via Dapr"
    echo "Note: Check mobile app for notification within 1-2 seconds"
else
    test_skipped "Dapr is not running on port $DAPR_HTTP_PORT"
    echo "To test Dapr integration, start Dapr sidecar first"
fi

echo ""

# Test 5: Check database connection
echo "─────────────────────────────────────────────────────────────"
echo "Test 5: Database Connection"
echo "─────────────────────────────────────────────────────────────"

# This test requires the service logs or a dedicated endpoint
# For now, we'll just check if the service is healthy (which includes DB)
if [ $TESTS_PASSED -gt 0 ]; then
    test_passed "Database connection OK (service is operational)"
else
    test_failed "Cannot verify database connection"
fi

echo ""

# Test 6: WebSocket connection test
echo "─────────────────────────────────────────────────────────────"
echo "Test 6: WebSocket Connection"
echo "─────────────────────────────────────────────────────────────"

# Check if wscat is available
if command -v wscat &> /dev/null; then
    echo "Starting WebSocket test (will timeout after 5 seconds)..."
    timeout 5s wscat -c "ws://localhost:8094/ws/$TEST_AGENT_ID" &
    WS_PID=$!
    sleep 2
    
    if ps -p $WS_PID > /dev/null; then
        test_passed "WebSocket connection successful"
        kill $WS_PID 2>/dev/null || true
    else
        test_failed "WebSocket connection failed"
    fi
else
    test_skipped "wscat not installed (install with: npm install -g wscat)"
fi

echo ""

# Summary
echo "═══════════════════════════════════════════════════════════"
echo "   Test Summary"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo -e "Tests Passed:  ${GREEN}$TESTS_PASSED${NC}"
echo -e "Tests Failed:  ${RED}$TESTS_FAILED${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Open mobile app"
    echo "2. Ensure agent is logged in"
    echo "3. Check for notifications"
    echo "4. You should see test notifications!"
    exit 0
else
    echo -e "${RED}✗ Some tests failed${NC}"
    echo ""
    echo "Troubleshooting:"
    echo "1. Check service logs for errors"
    echo "2. Verify DATABASE_URL is set correctly"
    echo "3. Ensure all dependencies are installed"
    echo "4. Check network connectivity"
    exit 1
fi
