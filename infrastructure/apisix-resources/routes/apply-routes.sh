#!/bin/bash

ROUTES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Applying all APISIX routes from: $ROUTES_DIR"
echo "================================================"

SUCCESS=0
FAILED=0
SKIPPED=0

for file in "$ROUTES_DIR"/*.yaml; do
  filename=$(basename "$file")

  # Skip files with spaces in the name (e.g. backup/duplicate files)
  if [[ "$filename" == *" "* ]]; then
    echo "SKIP  $filename (filename contains spaces)"
    ((SKIPPED++))
    continue
  fi

  echo -n "Applying $filename ... "
  if output=$(kubectl apply -f "$file" 2>&1); then
    echo "$output"
    ((SUCCESS++))
  else
    echo "FAILED"
    echo "  Error: $output"
    ((FAILED++))
  fi
done

echo "================================================"
echo "Done. Success: $SUCCESS | Failed: $FAILED | Skipped: $SKIPPED"

if [[ $FAILED -gt 0 ]]; then
  exit 1
fi
