# OpenSearch Integration

## Overview
OpenSearch as Elasticsearch replacement for search and analytics.

## Features
- Full-text search
- Real-time analytics
- Log aggregation
- Transaction indexing
- Dashboard visualization

## Deployment

### Docker Compose
```bash
cd services/infrastructure/opensearch
docker-compose up -d
```

### Kubernetes
```bash
kubectl create namespace infrastructure
kubectl apply -f opensearch-deployment.yaml
```

## Access
- API: https://localhost:9200
- Dashboards: http://localhost:5601
- Default credentials: admin / Admin@123

## Usage
```python
from opensearch_client import OpenSearchIntegration

client = OpenSearchIntegration(
    hosts=['https://localhost:9200'],
    auth=('admin', 'Admin@123')
)

# Index transaction
client.index_transaction({
    'transaction_id': 'TXN001',
    'amount': 100000,
    'corridor': 'PAPSS'
})

# Search
results = client.search_transactions({
    'match': {'corridor': 'PAPSS'}
})
```
