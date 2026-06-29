#!/bin/bash

# Kill existing service
sudo lsof -ti:8080 | xargs sudo kill -9 2>/dev/null
sleep 1

# Load environment and start service
cd /home/tani/Documents/54link/54link_core_banking/services/chart-of-accounts-service
set -a
source .env
set +a
go run . &

echo "Service started. Check with: curl http://localhost:8080/health"
