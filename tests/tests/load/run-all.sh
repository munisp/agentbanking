#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# run-all.sh — 54agent POS Shell k6 Load Test Runner
# ─────────────────────────────────────────────────────────────────────────────
# Runs all k6 load test scenarios in sequence:
#   1. Smoke test (pre-flight health check)
#   2. Transaction throughput (200 VUs, p95 < 500 ms)
#   3. Float top-up flow (50 VUs)
#   4. Dispute creation (spike to 100 RPS)
#
# Grafana annotations are posted at the start and end of each test run so
# load test windows appear as vertical markers on the dashboard, making it
# easy to correlate throughput spikes with latency regressions.
#
# Prerequisites:
#   - k6 installed: https://k6.io/docs/getting-started/installation/
#   - POS Shell server running and accessible at BASE_URL
#   - (Optional) GRAFANA_URL + GRAFANA_API_KEY for dashboard annotations
#
# Usage:
#   ./tests/load/run-all.sh [BASE_URL] [AGENT_CODE] [AGENT_PIN]
#
# Examples:
#   ./tests/load/run-all.sh http://localhost:3000 AGT001 1234
#   BASE_URL=https://staging.54agent.com ./tests/load/run-all.sh
#
# Grafana annotation env vars (optional — silently skipped if not set):
#   GRAFANA_URL=http://localhost:3001
#   GRAFANA_API_KEY=glsa_xxxxxxxxxxxxxxxxxxxx
#   GRAFANA_DASHBOARD_UID=pos-shell-prod-v1
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

BASE_URL="${1:-${BASE_URL:-http://localhost:3000}}"
AGENT_CODE="${2:-${AGENT_CODE:-AGT001}}"
AGENT_PIN="${3:-${AGENT_PIN:-1234}}"
RESULTS_DIR="tests/load/results/$(date +%Y%m%d-%H%M%S)"

# Grafana annotation settings (optional)
GRAFANA_URL="${GRAFANA_URL:-}"
GRAFANA_API_KEY="${GRAFANA_API_KEY:-}"
GRAFANA_DASHBOARD_UID="${GRAFANA_DASHBOARD_UID:-pos-shell-prod-v1}"

echo "═══════════════════════════════════════════════════════════════"
echo "  54agent POS Shell — k6 Load Test Suite"
echo "  Target:  ${BASE_URL}"
echo "  Results: ${RESULTS_DIR}"
echo "  Grafana: ${GRAFANA_URL:-not configured (set GRAFANA_URL to enable annotations)}"
echo "═══════════════════════════════════════════════════════════════"

# ── Grafana annotation helper ─────────────────────────────────────────────────
# Posts a vertical marker to the Grafana dashboard.
# Silently skips if GRAFANA_URL or GRAFANA_API_KEY are not set.
# Never fails the test run — annotation errors are non-fatal.
grafana_annotate() {
  local text="$1"
  local tags_csv="${2:-k6,load-test}"

  if [[ -z "${GRAFANA_URL}" || -z "${GRAFANA_API_KEY}" ]]; then
    return 0
  fi

  # Build JSON array from comma-separated tags
  local tags_json
  tags_json=$(echo "${tags_csv}" | awk -F',' '{
    printf "["
    for (i=1; i<=NF; i++) {
      printf "\"%s\"", $i
      if (i < NF) printf ","
    }
    printf "]"
  }')

  local epoch_ms
  epoch_ms=$(date +%s%3N)

  curl -sf \
    -X POST \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer ${GRAFANA_API_KEY}" \
    "${GRAFANA_URL}/api/annotations" \
    -d "{
      \"dashboardUID\": \"${GRAFANA_DASHBOARD_UID}\",
      \"time\": ${epoch_ms},
      \"tags\": ${tags_json},
      \"text\": \"${text}\"
    }" \
    --max-time 5 \
    > /dev/null 2>&1 || true

  echo "  [Grafana] ✓ Annotation: ${text}"
}

# ── Check k6 is installed ─────────────────────────────────────────────────────
if ! command -v k6 &>/dev/null; then
  echo ""
  echo "ERROR: k6 is not installed."
  echo "Install it from: https://k6.io/docs/getting-started/installation/"
  echo ""
  echo "  macOS:   brew install k6"
  echo "  Linux:   sudo apt-get install k6  (or see k6.io)"
  echo "  Docker:  docker run --rm -i grafana/k6 run - <script.js"
  exit 1
fi

mkdir -p "${RESULTS_DIR}"

# Track pass/fail
FAILED_TESTS=()
PASSED_TESTS=()

# ── Helper: run a single k6 test ─────────────────────────────────────────────
run_test() {
  local name="$1"
  local script="$2"

  echo ""
  echo "───────────────────────────────────────────────────────────────"
  echo "  Running: ${name}"
  echo "───────────────────────────────────────────────────────────────"

  local summary_file="${RESULTS_DIR}/${name// /-}-summary.json"

  grafana_annotate "k6 ${name} started" "k6,load-test,${name},start"

  if k6 run \
      -e "BASE_URL=${BASE_URL}" \
      -e "AGENT_CODE=${AGENT_CODE}" \
      -e "AGENT_PIN=${AGENT_PIN}" \
      --summary-export="${summary_file}" \
      "${script}"; then
    PASSED_TESTS+=("${name}")
    grafana_annotate "k6 ${name} PASSED" "k6,load-test,${name},pass"
    echo "  ✓ ${name} PASSED"
    return 0
  else
    FAILED_TESTS+=("${name}")
    grafana_annotate "k6 ${name} FAILED" "k6,load-test,${name},fail"
    echo "  ✗ ${name} FAILED — see ${summary_file}"
    return 1
  fi
}

# ── Mark suite start ──────────────────────────────────────────────────────────
grafana_annotate "k6 load test suite started — target: ${BASE_URL}" "k6,load-test,suite-start"

# ── 1. Smoke test (must pass before running load tests) ──────────────────────
echo ""
echo "Step 1/4: Smoke test (pre-flight health check)"
if ! run_test "smoke-test" "tests/load/smoke-test.js"; then
  echo ""
  echo "ABORT: Smoke test failed. Fix server issues before running load tests."
  grafana_annotate "k6 suite ABORTED — smoke test failed" "k6,load-test,suite-abort"
  exit 1
fi

# ── 2. Transaction throughput ─────────────────────────────────────────────────
echo ""
echo "Step 2/4: Transaction throughput (200 VUs, ~3 min)"
run_test "transaction-throughput" "tests/load/transaction-throughput.js" || true

# ── 3. Float top-up flow ──────────────────────────────────────────────────────
echo ""
echo "Step 3/4: Float top-up flow (50 VUs, ~3 min)"
run_test "float-topup" "tests/load/float-topup.js" || true

# ── 4. Dispute creation spike ─────────────────────────────────────────────────
echo ""
echo "Step 4/4: Dispute creation spike (100 RPS, ~3 min)"
run_test "dispute-creation" "tests/load/dispute-creation.js" || true

# ── Mark suite end ────────────────────────────────────────────────────────────
if [[ ${#FAILED_TESTS[@]} -eq 0 ]]; then
  grafana_annotate "k6 suite PASSED — all ${#PASSED_TESTS[@]} tests green" "k6,load-test,suite-end,pass"
else
  grafana_annotate "k6 suite COMPLETED — ${#FAILED_TESTS[@]} test(s) failed" "k6,load-test,suite-end,fail"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  Load test suite complete."
echo "  JSON summaries saved to: ${RESULTS_DIR}/"

if [[ ${#PASSED_TESTS[@]} -gt 0 ]]; then
  echo ""
  echo "  PASSED (${#PASSED_TESTS[@]}):"
  for t in "${PASSED_TESTS[@]}"; do
    echo "    ✓ ${t}"
  done
fi

if [[ ${#FAILED_TESTS[@]} -gt 0 ]]; then
  echo ""
  echo "  FAILED (${#FAILED_TESTS[@]}):"
  for t in "${FAILED_TESTS[@]}"; do
    echo "    ✗ ${t}"
  done
  echo ""
  echo "  Review JSON summaries in ${RESULTS_DIR}/ for details."
  echo "  Analyse results:"
  echo "    cat ${RESULTS_DIR}/*.json | jq '.metrics.http_req_duration'"
  echo "═══════════════════════════════════════════════════════════════"
  exit 1
fi

echo ""
echo "  All tests passed. ✓"
echo ""
echo "  Analyse results:"
echo "    cat ${RESULTS_DIR}/*.json | jq '.metrics.http_req_duration'"
echo ""
echo "  Import into Grafana k6 Cloud:"
echo "    k6 run --out cloud tests/load/transaction-throughput.js"
echo "═══════════════════════════════════════════════════════════════"
