#!/bin/bash
# Run script for inventory service

cd "$(dirname "$0")"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Set environment variables
export DATABASE_URL=${DATABASE_URL:-"postgresql://postgres:password@localhost:5432/remittance_network"}
export PORT=${PORT:-8096}

# Run the application
exec uvicorn main:app --host 0.0.0.0 --port $PORT --reload
