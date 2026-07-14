#!/bin/bash
# Deploy all 32 consolidated Helm charts.
# Usage:
#   ./03_install_charts.sh                  # deploy all
#   ./03_install_charts.sh agent-core       # resume from (and including) this chart
#   IMAGE_TAG=0.0.2 ./03_install_charts.sh  # override image tag
set -e

NS=54agent
CHARTS_DIR="$(dirname "$0")/charts"
START_FROM="$1"

STARTED=false

for chart in $(ls -d "$CHARTS_DIR"/* | sort); do
  if [ -d "$chart" ]; then
    RELEASE_NAME=$(basename "$chart")

    if [ -n "$START_FROM" ] && [ "$STARTED" = false ]; then
      if [ "$RELEASE_NAME" = "$START_FROM" ]; then
        STARTED=true
      else
        echo "Skipping chart: $RELEASE_NAME"
        continue
      fi
    fi

    TAG=$(grep 'tag:' "$chart/values.yaml" 2>/dev/null | head -1 | awk '{print $2}' | tr -d '"')
    echo "Deploying chart: $RELEASE_NAME  (tag=${TAG:-from values.yaml})"

    helm upgrade --install "$RELEASE_NAME" \
      "$chart" \
      -n "$NS" \
      --create-namespace \
      --atomic=false
  fi
done

echo "All charts deployed."
