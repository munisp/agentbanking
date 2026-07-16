#!/bin/bash
# Apply all 450 consolidated APISIX routes.
# Usage:
#   ./04_apply_routes.sh                         # apply all
#   ./04_apply_routes.sh account-service.yaml    # resume from (and including) this file
set -e

ROUTES_DIR=./apisix-resources/routes
START_FROM="$1"
NS=54agent

STARTED=false
APPLIED=0
FAILED=0

for route in $(ls "$ROUTES_DIR" | sort); do
    if [[ -n "$START_FROM" && "$STARTED" == false ]]; then
        if [[ "$route" == "$START_FROM" ]]; then
            STARTED=true
        else
            continue
        fi
    fi

    if kubectl apply -f "$ROUTES_DIR/$route" -n "$NS"; then
        ((APPLIED++))
    else
        echo "WARN: failed to apply $route"
        ((FAILED++))
    fi
done

echo ""
echo "Done. Applied: $APPLIED  Failed: $FAILED"
[ "$FAILED" -gt 0 ] && exit 1 || exit 0