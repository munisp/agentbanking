#!/bin/bash

# Script to build and push Docker images for all POS services
REGISTRY="registry.digitalocean.com/talentgraph-auth"
SERVICES_DIR="/home/tani/Documents/54agent/54agent_agent_banking/services"

# Array of POS services and their versions
declare -A SERVICES
SERVICES["pos-management"]="0.0.1"
SERVICES["pos-integration"]="0.0.1"
SERVICES["pos-hardware-management"]="0.0.1"
SERVICES["pos-terminal-management"]="0.0.1"

echo "Starting Docker build and push for POS services..."
echo "========================================"

for SERVICE in "${!SERVICES[@]}"; do
  VERSION="${SERVICES[$SERVICE]}"
  IMAGE_NAME="$REGISTRY/54agent-$SERVICE:$VERSION"
  
  echo ""
  echo "Building $SERVICE version $VERSION..."
  echo "--------------------------------------"
  
  cd "$SERVICES_DIR/$SERVICE" || exit 1
  
  # Build the Docker image
  docker build -t "$IMAGE_NAME" .
  
  if [ $? -eq 0 ]; then
    echo "✓ Successfully built $IMAGE_NAME"
    
    # Push the Docker image
    echo "Pushing $IMAGE_NAME..."
    docker push "$IMAGE_NAME"
    
    if [ $? -eq 0 ]; then
      echo "✓ Successfully pushed $IMAGE_NAME"
    else
      echo "✗ Failed to push $IMAGE_NAME"
      exit 1
    fi
  else
    echo "✗ Failed to build $IMAGE_NAME"
    exit 1
  fi
done

echo ""
echo "========================================"
echo "All POS service images built and pushed successfully!"
echo ""
echo "Images created:"
for SERVICE in "${!SERVICES[@]}"; do
  echo "  - $REGISTRY/54agent-$SERVICE:${SERVICES[$SERVICE]}"
done
