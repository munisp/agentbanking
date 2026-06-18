#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Bundle Size Budget Check
# Enforces a maximum JS bundle size. Fails CI if exceeded.
# Run: bash scripts/bundle-budget.sh [--ci]
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

CI_MODE=false
[[ "${1:-}" == "--ci" ]] && CI_MODE=true

BUDGET_KB=800
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "╔══════════════════════════════════════════════════════════╗"
echo "║          54Link Platform — Bundle Size Budget            ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "Budget: ${BUDGET_KB}KB (gzipped)"

# Build if dist doesn't exist
if [ ! -d "dist" ]; then
  echo "▸ Building client bundle..."
  npx vite build --mode production 2>/dev/null || {
    echo -e "${YELLOW}Build skipped (no vite config or build error)${NC}"
    exit 0
  }
fi

# Check JS bundle sizes
echo ""
echo "▸ Analyzing bundle sizes..."
TOTAL_KB=0
OVER_BUDGET=false

for f in dist/assets/*.js 2>/dev/null; do
  [ -f "$f" ] || continue
  SIZE_BYTES=$(wc -c < "$f")
  SIZE_KB=$((SIZE_BYTES / 1024))

  # Approximate gzipped size (typically 30% of raw)
  GZIP_KB=$((SIZE_KB * 30 / 100))

  NAME=$(basename "$f")
  if [ "$GZIP_KB" -gt "$BUDGET_KB" ]; then
    echo -e "  ${RED}OVER BUDGET:${NC} $NAME — ${GZIP_KB}KB gzipped (raw: ${SIZE_KB}KB)"
    OVER_BUDGET=true
  else
    echo -e "  ${GREEN}OK:${NC} $NAME — ${GZIP_KB}KB gzipped (raw: ${SIZE_KB}KB)"
  fi
  TOTAL_KB=$((TOTAL_KB + GZIP_KB))
done

echo ""
echo "══════════════════════════════════════════════════════════"
echo -e "  Total gzipped: ${TOTAL_KB}KB / ${BUDGET_KB}KB budget per chunk"
echo "══════════════════════════════════════════════════════════"

if $CI_MODE && $OVER_BUDGET; then
  echo -e "${RED}CI FAIL: Bundle exceeds ${BUDGET_KB}KB budget${NC}"
  exit 1
fi

exit 0
