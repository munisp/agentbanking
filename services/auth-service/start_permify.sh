#!/bin/bash

# Quick start script for testing Permify locally

echo "🚀 Starting Permify Testing..."
echo ""

# Check if Permify container exists
if docker ps -a | grep -q permify; then
    echo "📦 Permify container exists"
    
    # Check if it's running
    if docker ps | grep -q permify; then
        echo "✅ Permify is already running"
    else
        echo "▶️  Starting existing Permify container..."
        docker start permify
        sleep 3
    fi
else
    echo "📥 Permify container not found, creating new one..."
    docker run -d --name permify -p 3476:3476 ghcr.io/permify/permify serve
    echo "⏳ Waiting for Permify to start (15 seconds)..."
    sleep 15
fi

# Verify Permify is healthy
echo ""
echo "🔍 Checking Permify health..."
for i in {1..10}; do
    if curl -s http://localhost:3476/healthz > /dev/null 2>&1; then
        echo "✅ Permify is healthy!"
        break
    else
        if [ $i -eq 10 ]; then
            echo "❌ Permify failed to start"
            echo "Check logs with: docker logs permify"
            exit 1
        fi
        echo "⏳ Waiting... ($i/10)"
        sleep 2
    fi
done

echo ""
echo "========================================="
echo "✅ Ready to test!"
echo "========================================="
echo ""
echo "Run the test suite with:"
echo "  ./test_permify.sh"
echo ""
echo "Or start the auth service with:"
echo "  uvicorn main:app --reload --port 8001"
echo ""
