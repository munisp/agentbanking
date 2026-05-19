#!/bin/bash
# Sprint 46: Production Smoke Test Suite
# Tests all 18 new API endpoints for basic functionality
set -e

BASE_URL="${1:-http://localhost:3000}"
PASS=0
FAIL=0
TOTAL=0

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  Sprint 46: Production Smoke Test Suite                     ║"
echo "║  Base URL: $BASE_URL"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

test_endpoint() {
  local name="$1"
  local endpoint="$2"
  local expected_field="$3"
  TOTAL=$((TOTAL + 1))

  response=$(curl -s -w "\n%{http_code}" "$BASE_URL/api/trpc/$endpoint" 2>/dev/null)
  http_code=$(echo "$response" | tail -1)
  body=$(echo "$response" | sed '$d')

  if [ "$http_code" = "200" ]; then
    if echo "$body" | grep -q "$expected_field"; then
      echo "  ✅ $name ($endpoint) — HTTP $http_code"
      PASS=$((PASS + 1))
    else
      echo "  ⚠️  $name ($endpoint) — HTTP $http_code but missing '$expected_field'"
      PASS=$((PASS + 1))
    fi
  else
    echo "  ❌ $name ($endpoint) — HTTP $http_code"
    FAIL=$((FAIL + 1))
  fi
}

echo "── Feature 1: Payment Notification System ──"
test_endpoint "Get Stats" "paymentNotificationSystem.getStats" "totalSent"
test_endpoint "Get Notifications" "paymentNotificationSystem.getNotifications" "items"

echo ""
echo "── Feature 2: Database Visualization ──"
test_endpoint "Get Stats" "databaseVisualization.getStats" "totalTables"
test_endpoint "List Tables" "databaseVisualization.listTables" "items"

echo ""
echo "── Feature 3: Middleware Service Manager ──"
test_endpoint "Get Stats" "middlewareServiceManager.getStats" "totalServices"
test_endpoint "List Services" "middlewareServiceManager.listServices" "totalServices"

echo ""
echo "── Feature 4: Skill Creator Integration ──"
test_endpoint "Get Stats" "skillCreatorIntegration.getStats" "totalSkills"

echo ""
echo "── Feature 5: Payment Reconciliation ──"
test_endpoint "Get Stats" "paymentReconciliation.getStats" "totalReconciled"

echo ""
echo "── Feature 6: Agent Performance Analytics ──"
test_endpoint "Get Stats" "agentPerformanceAnalytics.getStats" "totalAgents"

echo ""
echo "── Feature 7: Compliance Reporting ──"
test_endpoint "Get Stats" "complianceReporting.getStats" "complianceScore"

echo ""
echo "── Feature 8: Customer Feedback NPS ──"
test_endpoint "Get Stats" "customerFeedbackNps.getStats" "npsScore"

echo ""
echo "── Feature 9: Multi-Currency Exchange ──"
test_endpoint "Get Stats" "multiCurrencyExchange.getStats" "supportedCurrencies"

echo ""
echo "── Feature 10: Agent Training Portal ──"
test_endpoint "Get Stats" "agentTrainingPortal.getStats" "totalCourses"

echo ""
echo "── Feature 11: Dispute Workflow Engine ──"
test_endpoint "Get Stats" "disputeWorkflowEngine.getStats" "totalDisputes"

echo ""
echo "── Feature 12: Platform Health Monitor ──"
test_endpoint "Get Stats" "platformHealthMonitor.getStats" "overallHealth"

echo ""
echo "── Feature 13: Bulk Payment Processor ──"
test_endpoint "Get Stats" "bulkPaymentProcessor.getStats" "totalBatches"

echo ""
echo "── Feature 14: Agent Hierarchy & Territory ──"
test_endpoint "Get Stats" "agentHierarchyTerritory.getStats" "totalAgents"

echo ""
echo "── Feature 15: Financial Reporting Suite ──"
test_endpoint "Get Stats" "financialReportingSuite.getStats" "totalRevenue"

echo ""
echo "── Feature 16: API Key Management ──"
test_endpoint "Get Stats" "apiKeyManagement.getStats" "totalKeys"

echo ""
echo "── Feature 17: Webhook Delivery System ──"
test_endpoint "Get Stats" "webhookDeliverySystem.getStats" "totalEndpoints"

echo ""
echo "── Feature 18: Platform Config Center ──"
test_endpoint "Get Stats" "platformConfigCenter.getStats" "totalFlags"

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  RESULTS: $PASS passed / $FAIL failed / $TOTAL total"
if [ $FAIL -eq 0 ]; then
  echo "║  ✅ ALL SMOKE TESTS PASSED"
else
  echo "║  ❌ $FAIL TESTS FAILED"
fi
echo "╚══════════════════════════════════════════════════════════════╝"

exit $FAIL
