#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Orphan Scanner — detects unregistered screens, routers, and pages
# Run: bash scripts/orphan-scanner.sh [--ci]
# In CI mode, exits with code 1 if orphans found (fails the build)
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

CI_MODE=false
[[ "${1:-}" == "--ci" ]] && CI_MODE=true

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

ORPHAN_COUNT=0
WARNINGS=""

echo "╔══════════════════════════════════════════════════════════╗"
echo "║          54Link Platform — Orphan Scanner               ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# ── 1. PWA Pages not in App.tsx routes ──────────────────────────────────────
echo "▸ Scanning PWA pages..."
PWA_ORPHANS=0
for f in client/src/pages/*.tsx; do
  [ -f "$f" ] || continue
  name=$(basename "$f" .tsx)
  # Skip index, layout, and test files
  [[ "$name" == "index" || "$name" == "_"* || "$name" == *".test" ]] && continue
  if ! grep -q "$name" client/src/App.tsx 2>/dev/null; then
    echo -e "  ${YELLOW}ORPHAN PAGE:${NC} $f"
    PWA_ORPHANS=$((PWA_ORPHANS + 1))
  fi
done
echo -e "  ${GREEN}Found: $PWA_ORPHANS orphan pages${NC}"
ORPHAN_COUNT=$((ORPHAN_COUNT + PWA_ORPHANS))

# ── 2. tRPC Routers not registered in routers.ts ───────────────────────────
echo ""
echo "▸ Scanning tRPC routers..."
ROUTER_ORPHANS=0
for f in server/routers/*.ts; do
  [ -f "$f" ] || continue
  name=$(basename "$f" .ts)
  # Skip test files and index
  [[ "$name" == *".test" || "$name" == *".spec" || "$name" == "index" ]] && continue
  if ! grep -q "$name" server/routers.ts 2>/dev/null; then
    echo -e "  ${YELLOW}ORPHAN ROUTER:${NC} $f"
    ROUTER_ORPHANS=$((ROUTER_ORPHANS + 1))
  fi
done
echo -e "  ${GREEN}Found: $ROUTER_ORPHANS orphan routers${NC}"
ORPHAN_COUNT=$((ORPHAN_COUNT + ROUTER_ORPHANS))

# ── 3. Flutter screens not routed in main.dart ──────────────────────────────
echo ""
echo "▸ Scanning Flutter screens..."
FLUTTER_ORPHANS=0
if [ -d "mobile-flutter/lib/screens" ]; then
  for f in mobile-flutter/lib/screens/*_screen.dart mobile-flutter/lib/screens/*Screen.dart; do
    [ -f "$f" ] || continue
    name=$(basename "$f" .dart)
    if ! grep -q "$name" mobile-flutter/lib/main.dart 2>/dev/null; then
      echo -e "  ${YELLOW}ORPHAN FLUTTER:${NC} $f"
      FLUTTER_ORPHANS=$((FLUTTER_ORPHANS + 1))
    fi
  done
fi
echo -e "  ${GREEN}Found: $FLUTTER_ORPHANS orphan Flutter screens${NC}"
ORPHAN_COUNT=$((ORPHAN_COUNT + FLUTTER_ORPHANS))

# ── 4. React Native screens not in App.tsx ──────────────────────────────────
echo ""
echo "▸ Scanning React Native screens..."
RN_ORPHANS=0
if [ -d "mobile-rn/src/screens" ]; then
  find mobile-rn/src/screens -name '*Screen.tsx' -o -name '*Screen_CDP.tsx' | while read -r f; do
    name=$(basename "$f" .tsx)
    if ! grep -q "$name" mobile-rn/src/App.tsx 2>/dev/null; then
      echo -e "  ${YELLOW}ORPHAN RN:${NC} $f"
      RN_ORPHANS=$((RN_ORPHANS + 1))
    fi
  done
fi
echo -e "  ${GREEN}Found: $RN_ORPHANS orphan React Native screens${NC}"
ORPHAN_COUNT=$((ORPHAN_COUNT + RN_ORPHANS))

# ── 5. Middleware connectors not used ───────────────────────────────────────
echo ""
echo "▸ Scanning for unused middleware exports..."
UNUSED_MW=0
for export_name in $(grep -oP 'export class \K\w+' server/middleware/middlewareConnectors.ts 2>/dev/null); do
  usage=$(grep -rl "$export_name" server/ --include="*.ts" 2>/dev/null | grep -v middlewareConnectors.ts | wc -l)
  if [ "$usage" -eq 0 ]; then
    echo -e "  ${YELLOW}UNUSED MIDDLEWARE:${NC} $export_name (0 imports)"
    UNUSED_MW=$((UNUSED_MW + 1))
  fi
done
echo -e "  ${GREEN}Found: $UNUSED_MW unused middleware classes${NC}"
ORPHAN_COUNT=$((ORPHAN_COUNT + UNUSED_MW))

# ── 6. Schema tables not referenced in any router ──────────────────────────
echo ""
echo "▸ Scanning for unused schema tables..."
UNUSED_TABLES=0
for table_name in $(grep -oP 'export const \K\w+(?= = pgTable)' drizzle/schema.ts 2>/dev/null | head -50); do
  usage=$(grep -rl "$table_name" server/routers/ --include="*.ts" 2>/dev/null | wc -l)
  if [ "$usage" -eq 0 ]; then
    echo -e "  ${YELLOW}UNUSED TABLE:${NC} $table_name (0 router references)"
    UNUSED_TABLES=$((UNUSED_TABLES + 1))
  fi
done
echo -e "  ${GREEN}Found: $UNUSED_TABLES unused schema tables${NC}"

# ── Summary ─────────────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════════════"
echo -e "  Total orphans: ${ORPHAN_COUNT}"
echo -e "  Unused tables: ${UNUSED_TABLES}"
echo "══════════════════════════════════════════════════════════"

if $CI_MODE && [ "$ORPHAN_COUNT" -gt 0 ]; then
  echo -e "${RED}CI FAIL: $ORPHAN_COUNT orphan features detected${NC}"
  exit 1
fi

exit 0
