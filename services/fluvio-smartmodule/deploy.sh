#!/usr/bin/env bash
# deploy.sh — Build and deploy the 54agent Fluvio SmartModule to a Fluvio cluster
#
# Usage:
#   ./deploy.sh [--cluster <address>] [--topic <topic>] [--dry-run]
#
# Requirements:
#   - Rust toolchain with wasm32-wasip1 target: rustup target add wasm32-wasip1
#   - Fluvio CLI: curl -fsS https://hub.infinyon.cloud/install/install.sh | bash
#   - Authenticated Fluvio session: fluvio cloud login
#
# Environment variables (override defaults):
#   FLUVIO_CLUSTER    — Fluvio cluster address (default: localhost:9003)
#   FLUVIO_TOPIC      — Topic to attach the SmartModule to (default: pos-transactions)
#   FLUVIO_SM_NAME    — SmartModule name (default: pos-fraud-filter)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
WASM_TARGET="wasm32-wasip1"
WASM_PROFILE="release"
WASM_NAME="pos_fraud_smartmodule"
SM_NAME="${FLUVIO_SM_NAME:-pos-fraud-filter}"
TOPIC="${FLUVIO_TOPIC:-pos-transactions}"
DRY_RUN=false

# ── Parse arguments ────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --cluster) FLUVIO_CLUSTER="$2"; shift 2 ;;
    --topic)   TOPIC="$2"; shift 2 ;;
    --dry-run) DRY_RUN=true; shift ;;
    *) echo "Unknown argument: $1"; exit 1 ;;
  esac
done

echo "=== 54agent Fluvio SmartModule Deploy ==="
echo "  SmartModule : ${SM_NAME}"
echo "  Topic       : ${TOPIC}"
echo "  Dry-run     : ${DRY_RUN}"
echo ""

# ── Step 1: Ensure wasm32-wasip1 target is installed ──────────────────────────
echo "[1/4] Checking Rust WASM target..."
if ! rustup target list --installed | grep -q "${WASM_TARGET}"; then
  echo "  Installing ${WASM_TARGET}..."
  rustup target add "${WASM_TARGET}"
fi
echo "  OK: ${WASM_TARGET} is installed"

# ── Step 2: Build WASM ────────────────────────────────────────────────────────
echo "[2/4] Building SmartModule WASM..."
cd "${WORKSPACE_ROOT}"
cargo build --target "${WASM_TARGET}" --release -p pos-fraud-smartmodule 2>&1

WASM_PATH="${WORKSPACE_ROOT}/target/${WASM_TARGET}/${WASM_PROFILE}/${WASM_NAME}.wasm"
if [[ ! -f "${WASM_PATH}" ]]; then
  echo "ERROR: WASM file not found at ${WASM_PATH}"
  exit 1
fi

WASM_SIZE=$(du -sh "${WASM_PATH}" | cut -f1)
echo "  OK: ${WASM_PATH} (${WASM_SIZE})"

# Copy to dist/ for reference
mkdir -p "${SCRIPT_DIR}/dist"
cp "${WASM_PATH}" "${SCRIPT_DIR}/dist/${WASM_NAME}.wasm"

# ── Step 3: Check Fluvio CLI ──────────────────────────────────────────────────
echo "[3/4] Checking Fluvio CLI..."
if ! command -v fluvio &>/dev/null; then
  echo "  WARNING: fluvio CLI not found."
  echo "  Install with: curl -fsS https://hub.infinyon.cloud/install/install.sh | bash"
  if [[ "${DRY_RUN}" == "false" ]]; then
    echo "  Skipping deployment (run with --dry-run to suppress this error)"
    exit 1
  fi
else
  echo "  OK: $(fluvio version 2>/dev/null | head -1)"
fi

# ── Step 4: Deploy SmartModule ────────────────────────────────────────────────
echo "[4/4] Deploying SmartModule..."

if [[ "${DRY_RUN}" == "true" ]]; then
  echo "  DRY-RUN: Would run:"
  echo "    fluvio smartmodule create ${SM_NAME} --wasm-file ${WASM_PATH}"
  echo "    fluvio topic create ${TOPIC} --smartmodule ${SM_NAME}"
  echo ""
  echo "=== Dry-run complete. WASM artifact at: dist/${WASM_NAME}.wasm ==="
  exit 0
fi

# Delete existing SmartModule if it exists
if fluvio smartmodule list 2>/dev/null | grep -q "${SM_NAME}"; then
  echo "  Deleting existing SmartModule: ${SM_NAME}"
  fluvio smartmodule delete "${SM_NAME}" || true
fi

# Create SmartModule
echo "  Creating SmartModule: ${SM_NAME}"
fluvio smartmodule create "${SM_NAME}" --wasm-file "${WASM_PATH}"

# Ensure topic exists
if ! fluvio topic list 2>/dev/null | grep -q "${TOPIC}"; then
  echo "  Creating topic: ${TOPIC}"
  fluvio topic create "${TOPIC}"
fi

echo ""
echo "=== SmartModule deployed successfully ==="
echo "  Name  : ${SM_NAME}"
echo "  Topic : ${TOPIC}"
echo "  WASM  : ${WASM_SIZE}"
echo ""
echo "To consume filtered events:"
echo "  fluvio consume ${TOPIC} --smartmodule ${SM_NAME}"
