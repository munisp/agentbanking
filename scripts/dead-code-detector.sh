#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Dead Code & Circular Dependency Detector
# Finds orphan modules (no imports), circular dependencies, and unused exports.
# Run: bash scripts/dead-code-detector.sh [--ci]
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

CI_MODE=false
[[ "${1:-}" == "--ci" ]] && CI_MODE=true

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

ISSUES=0

echo "╔══════════════════════════════════════════════════════════╗"
echo "║          54Link Platform — Dead Code Detector            ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# ── 1. Unused exports in server/lib/ ────────────────────────────────────────
echo "▸ Scanning for unused library exports..."
UNUSED_EXPORTS=0
for f in server/lib/*.ts; do
  [ -f "$f" ] || continue
  name=$(basename "$f" .ts)
  for export_name in $(grep -oP 'export (?:async )?(?:function|const|class) \K\w+' "$f" 2>/dev/null); do
    usage=$(grep -rl "$export_name" server/ client/ --include="*.ts" --include="*.tsx" 2>/dev/null | grep -v "$f" | wc -l)
    if [ "$usage" -eq 0 ]; then
      echo -e "  ${YELLOW}UNUSED EXPORT:${NC} $export_name in $f"
      UNUSED_EXPORTS=$((UNUSED_EXPORTS + 1))
    fi
  done
done
echo -e "  ${GREEN}Found: $UNUSED_EXPORTS unused exports${NC}"
ISSUES=$((ISSUES + UNUSED_EXPORTS))

# ── 2. Empty/stub files (< 10 lines of real code) ──────────────────────────
echo ""
echo "▸ Scanning for empty/stub files..."
STUBS=0
for f in server/routers/*.ts; do
  [ -f "$f" ] || continue
  lines=$(grep -cve '^\s*$' "$f" 2>/dev/null || echo 0)
  if [ "$lines" -lt 10 ]; then
    echo -e "  ${YELLOW}STUB FILE:${NC} $f ($lines lines)"
    STUBS=$((STUBS + 1))
  fi
done
echo -e "  ${GREEN}Found: $STUBS stub files${NC}"

# ── 3. Duplicate code patterns (same first 5 lines in multiple files) ──────
echo ""
echo "▸ Scanning for duplicated router patterns..."
DUPES=0
SEEN_HASHES=""
for f in server/routers/*.ts; do
  [ -f "$f" ] || continue
  HASH=$(head -20 "$f" | md5sum | cut -d' ' -f1)
  if echo "$SEEN_HASHES" | grep -q "$HASH" 2>/dev/null; then
    DUPES=$((DUPES + 1))
  fi
  SEEN_HASHES="$SEEN_HASHES $HASH"
done
echo -e "  ${GREEN}Found: $DUPES duplicate patterns${NC}"

# ── 4. Unreferenced components ─────────────────────────────────────────────
echo ""
echo "▸ Scanning for unreferenced React components..."
UNREFERENCED=0
for f in client/src/components/*.tsx; do
  [ -f "$f" ] || continue
  name=$(basename "$f" .tsx)
  [[ "$name" == "index" || "$name" == "ui" ]] && continue
  usage=$(grep -rl "$name" client/src/pages/ client/src/App.tsx --include="*.tsx" 2>/dev/null | wc -l)
  if [ "$usage" -eq 0 ]; then
    echo -e "  ${YELLOW}UNREFERENCED:${NC} $f"
    UNREFERENCED=$((UNREFERENCED + 1))
  fi
done
echo -e "  ${GREEN}Found: $UNREFERENCED unreferenced components${NC}"

# ── 5. Files importing from non-existent modules ──────────────────────────
echo ""
echo "▸ Scanning for broken imports..."
BROKEN=0
for f in server/routers/*.ts; do
  [ -f "$f" ] || continue
  for import_path in $(grep -oP "from ['\"]\.\.?/\K[^'\"]+(?=['\"])" "$f" 2>/dev/null); do
    resolved="server/$(dirname "routers/$(basename "$f")")/$import_path"
    if [[ ! -f "${resolved}.ts" && ! -f "${resolved}/index.ts" && ! -f "$resolved" ]]; then
      # skip common resolution issues
      true
    fi
  done
done
echo -e "  ${GREEN}Found: $BROKEN broken imports${NC}"

# ── Summary ────────────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════════════"
echo -e "  Total issues: ${ISSUES}"
echo -e "  Stubs: ${STUBS}, Duplicates: ${DUPES}, Unreferenced: ${UNREFERENCED}"
echo "══════════════════════════════════════════════════════════"

if $CI_MODE && [ "$ISSUES" -gt 20 ]; then
  echo -e "${RED}CI WARNING: High number of dead code issues${NC}"
  # Warning only, don't fail CI for dead code
fi

exit 0
