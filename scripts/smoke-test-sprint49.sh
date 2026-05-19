#!/bin/bash
echo "╔══════════════════════════════════════════╗"
echo "║  Sprint 49: Production Smoke Tests       ║"
echo "╚══════════════════════════════════════════╝"
BASE="http://localhost:3000/api/trpc"
PASS=0; FAIL=0; TOTAL=0
check() {
  TOTAL=$((TOTAL+1))
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/$1" 2>/dev/null)
  if [ "$STATUS" = "200" ]; then PASS=$((PASS+1)); echo "  ✅ $1: $STATUS"
  else FAIL=$((FAIL+1)); echo "  ❌ $1: $STATUS"; fi
}
echo ""
echo "=== Sprint 49 Endpoints ==="
for r in bankAccountManagement kycDocumentManagement floatReconciliation agentPerformanceScorecard customerDatabase reversalApproval commissionClawback pnlReport geoFencing transactionLimitsEngine regulatoryCompliance systemHealthDashboard agentSuspensionWorkflow auditExport middlewareServiceManager; do
  check "${r}.getStats"
done
echo ""
echo "=== Sidecar Health ==="
for port in 9100 9200 9300; do
  TOTAL=$((TOTAL+1))
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:${port}/health" 2>/dev/null)
  if [ "$STATUS" = "200" ]; then PASS=$((PASS+1)); echo "  ✅ Sidecar :${port}: $STATUS"
  else echo "  ⚠️  Sidecar :${port}: $STATUS (optional)"; fi
done
echo ""
echo "═══════════════════════════════════════════"
echo "  Results: ${PASS}/${TOTAL} passed, ${FAIL} failed"
echo "═══════════════════════════════════════════"
