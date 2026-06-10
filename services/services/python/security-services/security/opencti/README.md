# OpenCTI Integration

## Overview
OpenCTI (Open Cyber Threat Intelligence) integration for the Nigerian Remittance Platform.

## Features
- IP reputation checking
- Suspicious transaction reporting
- Threat actor intelligence
- Incident management

## Deployment

### Docker Compose
```bash
cd services/security/opencti
docker-compose up -d
```

### Kubernetes
```bash
kubectl create namespace security
kubectl apply -f opencti-deployment.yaml
```

## Configuration
- Default URL: http://localhost:8080
- Default credentials: admin@opencti.io / admin_password
- API Token: changeme (CHANGE IN PRODUCTION!)

## Integration
```python
from opencti_client import OpenCTIIntegration

opencti = OpenCTIIntegration(url="http://opencti:8080", token="your_token")
result = opencti.check_ip_reputation("suspicious_ip")
```

## Security Notes
- Change default passwords before production deployment
- Use secrets management for API tokens
- Enable SSL/TLS for production
- Configure proper network policies
