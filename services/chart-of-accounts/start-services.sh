#!/bin/bash

# Set to "false" to skip TigerBeetle if you don't have enough disk space
START_TIGERBEETLE="${START_TIGERBEETLE:-true}"

echo "Starting local services..."

# Start Redis
echo "Starting Redis..."
redis-server --daemonize yes
if [ $? -eq 0 ]; then
    echo "✓ Redis started successfully"
else
    echo "✗ Failed to start Redis"
fi

# Start PostgreSQL
echo "Starting PostgreSQL..."
sudo systemctl start postgresql
if [ $? -eq 0 ]; then
    echo "✓ PostgreSQL started successfully"
else
    echo "✗ Failed to start PostgreSQL"
fi

# Only start TigerBeetle if enabled
if [ "$START_TIGERBEETLE" = "true" ]; then
    # Check if TigerBeetle is available
    TIGERBEETLE_CMD=""
    if [ -f "./tigerbeetle" ]; then
        TIGERBEETLE_CMD="./tigerbeetle"
    elif command -v tigerbeetle &> /dev/null; then
        TIGERBEETLE_CMD="tigerbeetle"
    else
        echo "✗ TigerBeetle not found. Downloading..."
        curl -Lo tigerbeetle.zip https://github.com/tigerbeetle/tigerbeetle/releases/latest/download/tigerbeetle-x86_64-linux.zip
        unzip -o tigerbeetle.zip
        chmod +x tigerbeetle
        TIGERBEETLE_CMD="./tigerbeetle"
    fi

    # Check if TigerBeetle data file exists, create if not
    if [ ! -f "0_0.tigerbeetle" ]; then
        echo "Formatting TigerBeetle data file..."
        
        # Check available disk space (in KB)
        AVAILABLE=$(df . | tail -1 | awk '{print $4}')
        REQUIRED=1100000  # ~1.1GB in KB
        
        if [ $AVAILABLE -lt $REQUIRED ]; then
            echo "✗ Not enough disk space for TigerBeetle (need ~1.1GB, have $(($AVAILABLE/1024))MB)"
            echo "  Skipping TigerBeetle. To enable, free up space and set START_TIGERBEETLE=true"
            START_TIGERBEETLE="false"
        else
            $TIGERBEETLE_CMD format --cluster=0 --replica=0 --replica-count=1 0_0.tigerbeetle
            
            if [ $? -ne 0 ]; then
                echo "✗ Failed to format TigerBeetle data file"
                # Clean up partial file
                rm -f 0_0.tigerbeetle
                START_TIGERBEETLE="false"
            fi
        fi
    fi

    # Start TigerBeetle if format was successful
    if [ "$START_TIGERBEETLE" = "true" ]; then
        echo "Starting TigerBeetle..."
        $TIGERBEETLE_CMD start --addresses=0.0.0.0:3000 0_0.tigerbeetle &
        TIGERBEETLE_PID=$!
        echo "✓ TigerBeetle started with PID: $TIGERBEETLE_PID"
    fi
else
    echo "⊘ TigerBeetle skipped (disabled)"
fi

echo ""
echo "All services started!"
echo "PostgreSQL: localhost:5432"
echo "Redis: localhost:6379"
if [ "$START_TIGERBEETLE" = "true" ]; then
    echo "TigerBeetle: localhost:3000"
fi
