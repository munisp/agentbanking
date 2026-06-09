# Kubecost Integration

## Overview
Kubecost provides real-time cost visibility and insights for Kubernetes clusters.

## Features
- Real-time cost allocation
- Cost breakdown by namespace, service, label
- Cost optimization recommendations
- Budget alerts
- Multi-cluster support

## Deployment

### Kubernetes
```bash
kubectl apply -f kubecost-deployment.yaml
```

### Helm (Alternative)
```bash
helm repo add kubecost https://kubecost.github.io/cost-analyzer/
helm install kubecost kubecost/cost-analyzer --namespace kubecost --create-namespace
```

## Access
- Dashboard: http://localhost:9090
- API: http://localhost:9090/model

## Usage
```python
from kubecost_client import KubecostIntegration

kubecost = KubecostIntegration(api_url="http://localhost:9090")

# Get cluster costs
costs = kubecost.get_cluster_costs(window="7d")

# Get namespace costs
ns_costs = kubecost.get_namespace_costs("payment-services")

# Get recommendations
recommendations = kubecost.get_cost_recommendations()
```

## Cost Optimization
- Right-size workloads based on actual usage
- Identify idle resources
- Optimize storage costs
- Set budget alerts
- Track cost trends
