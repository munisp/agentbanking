#!/bin/bash
# Quick start script for realtime notification service

set -e

echo "╔════════════════════════════════════════════════════════════╗"
echo "║  Starting Realtime Notification Service                   ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Check if running in the correct directory
if [ ! -f "main.py" ]; then
    echo "❌ Error: main.py not found"
    echo "   Please run this script from the realtime-notification-service directory"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -q -r requirements.txt

# Check if database is accessible
echo "🗄️  Checking database connection..."
DB_URL=${DATABASE_URL:-"postgresql://postgres:password@localhost:5432/link_core_banking"}
export DATABASE_URL=$DB_URL

# Set environment variables
export DAPR_PUBSUB_NAME=${DAPR_PUBSUB_NAME:-"pubsub"}
export DEFAULT_GEOFENCE_RADIUS_KM=${DEFAULT_GEOFENCE_RADIUS_KM:-"5.0"}

echo ""
echo "Configuration:"
echo "  Database: ${DB_URL#*@}"
echo "  Pubsub: $DAPR_PUBSUB_NAME"
echo "  Port: 8094"
echo ""

# Check if Dapr is available
if command -v dapr &> /dev/null; then
    echo "✅ Dapr is available"
    
    # Ask user if they want to run with Dapr
    read -p "Run with Dapr? (y/n) [y]: " use_dapr
    use_dapr=${use_dapr:-y}
    
    if [[ $use_dapr == "y" || $use_dapr == "Y" ]]; then
        echo ""
        echo "🚀 Starting service with Dapr..."
        echo "   App ID: realtime-notification-service"
        echo "   HTTP Port: 8094"
        echo "   Dapr HTTP Port: 3594"
        echo ""
        
        # Check if components path exists
        COMPONENTS_PATH="../../infrastructure/components"
        if [ ! -d "$COMPONENTS_PATH" ]; then
            COMPONENTS_PATH="../../../infrastructure/components"
        fi
        
        if [ -d "$COMPONENTS_PATH" ]; then
            echo "   Components: $COMPONENTS_PATH"
            
            dapr run \
                --app-id realtime-notification-service \
                --app-port 8094 \
                --dapr-http-port 3594 \
                --components-path "$COMPONENTS_PATH" \
                -- python main.py
        else
            echo "⚠️  Components directory not found, running without components"
            
            dapr run \
                --app-id realtime-notification-service \
                --app-port 8094 \
                --dapr-http-port 3594 \
                -- python main.py
        fi
    else
        echo ""
        echo "🚀 Starting service without Dapr..."
        echo "   ⚠️  Note: Pubsub events will not be received without Dapr"
        echo ""
        python main.py
    fi
else
    echo "⚠️  Dapr not found. Running without Dapr..."
    echo "   Note: Install Dapr to receive pubsub events"
    echo "   Visit: https://docs.dapr.io/getting-started/install-dapr-cli/"
    echo ""
    python main.py
fi
