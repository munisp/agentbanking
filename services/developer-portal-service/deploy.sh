#!/bin/bash
set -e

REGISTRY="registry.digitalocean.com/talentgraph-auth"
IMAGE="${REGISTRY}/54agent-developer-portal-service"
TAG="0.0.1"
NAMESPACE="54agent"
CHART="../../infrastructure/charts/developer-portal-service"
ROUTE="../../infrastructure/apisix-resources/routes/developer-portal-service.yaml"

cd "$(dirname "$0")"

echo "==> Building image ${IMAGE}:${TAG}"
docker build -t "${IMAGE}:${TAG}" .

echo "==> Pushing ${IMAGE}:${TAG}"
docker push "${IMAGE}:${TAG}"

echo "==> Deploying Helm chart"
helm upgrade --install developer-portal-service "${CHART}" \
  --namespace "${NAMESPACE}" \
  --values "${CHART}/values.yaml" \
  --set image.tag="${TAG}" \
  --wait \
  --timeout=5m \
  --atomic

echo "==> Applying APISIX route"
kubectl apply -f "${ROUTE}"

echo "==> Waiting for rollout"
kubectl rollout status deployment/developer-portal-service -n "${NAMESPACE}" --timeout=5m

echo "==> Done. Pods:"
kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=developer-portal-service
