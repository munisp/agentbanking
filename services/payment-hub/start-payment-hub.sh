#!/bin/bash

echo "🚀 Starting Payment Hub stack..."

# Start scheduler in background
echo "▶ Starting Dapr Scheduler..."
~/.dapr/bin/scheduler --port 50006 > /tmp/dapr-scheduler.log 2>&1 &
echo "  Scheduler PID: $!"

# Start placement in background
echo "▶ Starting Dapr Placement..."
~/.dapr/bin/placement --port 50005 > /tmp/dapr-placement.log 2>&1 &
echo "  Placement PID: $!"

# Wait for both to be ready
sleep 2

# Start the app
echo "▶ Starting Payment Hub with Dapr..."
cd ~/Documents/54agent/54agent_core_banking/services/payment-hub

if [ -f .env ]; then
  set -a && source .env && set +a
fi

APP_PORT=${APP_PORT:-3001}
DAPR_HTTP_PORT=${DAPR_HTTP_PORT:-3501}
echo "ℹ️  Using APP_PORT=$APP_PORT, DAPR_HTTP_PORT=$DAPR_HTTP_PORT"

dapr run \
  --app-port $APP_PORT \
  --dapr-http-port $DAPR_HTTP_PORT \
  --config ./dapr/config.yaml \
  --app-id 54agent-paymenthub-core \
  --resources-path ./dapr/components \
  -- npm run dev