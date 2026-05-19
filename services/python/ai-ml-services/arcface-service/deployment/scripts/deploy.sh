#!/bin/bash
# ArcFace Face Matching Service - Deployment Automation Script
# Supports Docker, Docker Compose, and Kubernetes deployments

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
DEPLOYMENT_TYPE="${DEPLOYMENT_TYPE:-docker-compose}"
ENVIRONMENT="${ENVIRONMENT:-staging}"
SERVICE_NAME="arcface-service"
VERSION="1.0.0"

# Paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DEPLOYMENT_DIR="$PROJECT_ROOT/deployment"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}ArcFace Service Deployment Script${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "Environment: ${GREEN}$ENVIRONMENT${NC}"
echo -e "Deployment Type: ${GREEN}$DEPLOYMENT_TYPE${NC}"
echo -e "Version: ${GREEN}$VERSION${NC}"
echo ""

# Function to check prerequisites
check_prerequisites() {
    echo -e "${YELLOW}Checking prerequisites...${NC}"
    
    case $DEPLOYMENT_TYPE in
        docker)
            if ! command -v docker &> /dev/null; then
                echo -e "${RED}✗ Docker not found${NC}"
                exit 1
            fi
            echo -e "${GREEN}✓ Docker installed${NC}"
            ;;
        docker-compose)
            if ! command -v docker &> /dev/null; then
                echo -e "${RED}✗ Docker not found${NC}"
                exit 1
            fi
            if ! command -v docker-compose &> /dev/null; then
                echo -e "${RED}✗ Docker Compose not found${NC}"
                exit 1
            fi
            echo -e "${GREEN}✓ Docker and Docker Compose installed${NC}"
            ;;
        kubernetes)
            if ! command -v kubectl &> /dev/null; then
                echo -e "${RED}✗ kubectl not found${NC}"
                exit 1
            fi
            echo -e "${GREEN}✓ kubectl installed${NC}"
            ;;
        *)
            echo -e "${RED}✗ Unknown deployment type: $DEPLOYMENT_TYPE${NC}"
            exit 1
            ;;
    esac
    
    echo ""
}

# Function to check models
check_models() {
    echo -e "${YELLOW}Checking models...${NC}"
    
    if [ ! -f "$PROJECT_ROOT/models/det_10g.onnx" ] || [ ! -f "$PROJECT_ROOT/models/w600k_r50.onnx" ]; then
        echo -e "${YELLOW}Models not found. Downloading...${NC}"
        bash "$SCRIPT_DIR/download_models.sh"
    else
        echo -e "${GREEN}✓ Models found${NC}"
    fi
    
    echo ""
}

# Function to build Docker image
build_docker_image() {
    echo -e "${YELLOW}Building Docker image...${NC}"
    
    cd "$PROJECT_ROOT"
    
    if [ "$DEVICE" = "cpu" ]; then
        docker build -t "$SERVICE_NAME:$VERSION-cpu" -f deployment/docker/Dockerfile.cpu .
        echo -e "${GREEN}✓ CPU image built: $SERVICE_NAME:$VERSION-cpu${NC}"
    else
        docker build -t "$SERVICE_NAME:$VERSION" -f deployment/docker/Dockerfile .
        echo -e "${GREEN}✓ GPU image built: $SERVICE_NAME:$VERSION${NC}"
    fi
    
    echo ""
}

# Function to deploy with Docker
deploy_docker() {
    echo -e "${YELLOW}Deploying with Docker...${NC}"
    
    # Stop existing container
    if docker ps -a | grep -q "$SERVICE_NAME"; then
        echo -e "${YELLOW}Stopping existing container...${NC}"
        docker stop "$SERVICE_NAME" || true
        docker rm "$SERVICE_NAME" || true
    fi
    
    # Run container
    if [ "$DEVICE" = "cuda" ]; then
        docker run -d \
            --name "$SERVICE_NAME" \
            --gpus all \
            -p 8004:8004 \
            -v "$PROJECT_ROOT/models:/app/models:ro" \
            -v "$PROJECT_ROOT/logs:/var/log/arcface-service" \
            --env-file "$DEPLOYMENT_DIR/.env.$ENVIRONMENT" \
            --restart unless-stopped \
            "$SERVICE_NAME:$VERSION"
    else
        docker run -d \
            --name "$SERVICE_NAME" \
            -p 8004:8004 \
            -v "$PROJECT_ROOT/models:/app/models:ro" \
            -v "$PROJECT_ROOT/logs:/var/log/arcface-service" \
            --env-file "$DEPLOYMENT_DIR/.env.$ENVIRONMENT" \
            --restart unless-stopped \
            "$SERVICE_NAME:$VERSION-cpu"
    fi
    
    echo -e "${GREEN}✓ Container started${NC}"
    echo ""
}

# Function to deploy with Docker Compose
deploy_docker_compose() {
    echo -e "${YELLOW}Deploying with Docker Compose...${NC}"
    
    cd "$DEPLOYMENT_DIR/docker"
    
    # Stop existing services
    docker-compose -f "docker-compose.$ENVIRONMENT.yml" down || true
    
    # Start services
    docker-compose -f "docker-compose.$ENVIRONMENT.yml" up -d
    
    echo -e "${GREEN}✓ Services started${NC}"
    echo ""
}

# Function to deploy to Kubernetes
deploy_kubernetes() {
    echo -e "${YELLOW}Deploying to Kubernetes...${NC}"
    
    cd "$DEPLOYMENT_DIR/kubernetes"
    
    # Create namespace
    kubectl apply -f - <<EOF
apiVersion: v1
kind: Namespace
metadata:
  name: arcface-$ENVIRONMENT
  labels:
    name: arcface-$ENVIRONMENT
    environment: $ENVIRONMENT
EOF
    
    # Apply Redis
    kubectl apply -f redis.yaml
    
    # Apply main deployment
    kubectl apply -f deployment.yaml
    
    echo -e "${GREEN}✓ Kubernetes resources applied${NC}"
    echo ""
}

# Function to wait for service
wait_for_service() {
    echo -e "${YELLOW}Waiting for service to be ready...${NC}"
    
    MAX_RETRIES=30
    RETRY_COUNT=0
    
    while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
        if curl -s -f http://localhost:8004/api/v1/face-matching/health > /dev/null 2>&1; then
            echo -e "${GREEN}✓ Service is ready${NC}"
            return 0
        fi
        
        RETRY_COUNT=$((RETRY_COUNT + 1))
        echo -e "  Attempt $RETRY_COUNT/$MAX_RETRIES..."
        sleep 5
    done
    
    echo -e "${RED}✗ Service failed to start${NC}"
    return 1
}

# Function to run health check
run_health_check() {
    echo -e "${YELLOW}Running health check...${NC}"
    
    HEALTH_RESPONSE=$(curl -s http://localhost:8004/api/v1/face-matching/health)
    
    if echo "$HEALTH_RESPONSE" | grep -q '"status":"healthy"'; then
        echo -e "${GREEN}✓ Health check passed${NC}"
        echo "$HEALTH_RESPONSE" | python3 -m json.tool
    else
        echo -e "${RED}✗ Health check failed${NC}"
        echo "$HEALTH_RESPONSE"
        return 1
    fi
    
    echo ""
}

# Function to show deployment info
show_deployment_info() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}Deployment Complete!${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    echo -e "Service: ${GREEN}$SERVICE_NAME${NC}"
    echo -e "Version: ${GREEN}$VERSION${NC}"
    echo -e "Environment: ${GREEN}$ENVIRONMENT${NC}"
    echo ""
    echo -e "${YELLOW}Access Points:${NC}"
    echo -e "  API: http://localhost:8004"
    echo -e "  Docs: http://localhost:8004/docs"
    echo -e "  Health: http://localhost:8004/api/v1/face-matching/health"
    echo ""
    
    if [ "$DEPLOYMENT_TYPE" = "docker-compose" ]; then
        echo -e "${YELLOW}Additional Services:${NC}"
        echo -e "  Prometheus: http://localhost:9090"
        echo -e "  Grafana: http://localhost:3000 (admin/admin_change_in_production)"
        echo -e "  Redis: localhost:6379"
        echo ""
    fi
    
    echo -e "${YELLOW}Useful Commands:${NC}"
    
    case $DEPLOYMENT_TYPE in
        docker)
            echo -e "  View logs: docker logs -f $SERVICE_NAME"
            echo -e "  Stop service: docker stop $SERVICE_NAME"
            echo -e "  Restart service: docker restart $SERVICE_NAME"
            ;;
        docker-compose)
            echo -e "  View logs: docker-compose -f deployment/docker/docker-compose.$ENVIRONMENT.yml logs -f"
            echo -e "  Stop services: docker-compose -f deployment/docker/docker-compose.$ENVIRONMENT.yml down"
            echo -e "  Restart services: docker-compose -f deployment/docker/docker-compose.$ENVIRONMENT.yml restart"
            ;;
        kubernetes)
            echo -e "  View pods: kubectl get pods -n arcface-$ENVIRONMENT"
            echo -e "  View logs: kubectl logs -f deployment/arcface-service -n arcface-$ENVIRONMENT"
            echo -e "  Scale: kubectl scale deployment/arcface-service --replicas=3 -n arcface-$ENVIRONMENT"
            ;;
    esac
    
    echo ""
}

# Main deployment flow
main() {
    check_prerequisites
    check_models
    
    case $DEPLOYMENT_TYPE in
        docker)
            build_docker_image
            deploy_docker
            ;;
        docker-compose)
            build_docker_image
            deploy_docker_compose
            ;;
        kubernetes)
            build_docker_image
            deploy_kubernetes
            ;;
    esac
    
    wait_for_service
    run_health_check
    show_deployment_info
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -t|--type)
            DEPLOYMENT_TYPE="$2"
            shift 2
            ;;
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -d|--device)
            DEVICE="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  -t, --type TYPE          Deployment type (docker, docker-compose, kubernetes)"
            echo "  -e, --environment ENV    Environment (staging, production)"
            echo "  -d, --device DEVICE      Device (cpu, cuda)"
            echo "  -h, --help               Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0 -t docker -e staging -d cuda"
            echo "  $0 -t docker-compose -e staging"
            echo "  $0 -t kubernetes -e production"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Run main
main

exit 0
