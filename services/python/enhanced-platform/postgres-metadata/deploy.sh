#!/bin/bash
set -e

echo "🚀 Deploying PostgreSQL Metadata Service..."

# Local deployment
docker-compose down
docker-compose build
docker-compose up -d

echo "⏳ Waiting for service to be ready..."
sleep 10

# Test health
curl -f http://localhost:5433/health || {
    echo "❌ Health check failed"
    exit 1
}

echo "✅ PostgreSQL Metadata Service deployed successfully!"
echo "📊 Service URL: http://localhost:5433"
echo "🔍 Health Check: http://localhost:5433/health"
