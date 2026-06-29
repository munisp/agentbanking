#!/bin/bash

# Build script for verification-ui with environment variables

# Load environment variables from .env file
if [ -f .env ]; then
  export $(cat .env | grep -v '^#' | xargs)
fi

# Set default values if not in .env
VITE_VERIFICATION_API_URL=${VITE_VERIFICATION_API_URL:-https://54agent.upi.dev/verification}
VITE_KYC_FLOW_API_KEY=${VITE_KYC_FLOW_API_KEY:-Zr6lIvOEuGDlzlDyV+/dEDcUX7cChZKs}

# Get version from argument or use default
VERSION=${1:-0.0.10}

echo "Building verification-ui Docker image..."
echo "VITE_VERIFICATION_API_URL: $VITE_VERIFICATION_API_URL"
echo "VITE_KYC_FLOW_API_KEY: ${VITE_KYC_FLOW_API_KEY:0:10}..." # Only show first 10 chars
echo "Version: $VERSION"

# Build the Docker image
docker build \
  --build-arg VITE_VERIFICATION_API_URL="$VITE_VERIFICATION_API_URL" \
  --build-arg VITE_KYC_FLOW_API_KEY="$VITE_KYC_FLOW_API_KEY" \
  -t registry.digitalocean.com/talentgraph-auth/54agent-verification-ui:$VERSION \
  -f Dockerfile \
  .

echo "Build completed successfully!"
echo "To push the image, run:"
echo "  docker push registry.digitalocean.com/talentgraph-auth/54agent-verification-ui:$VERSION"
