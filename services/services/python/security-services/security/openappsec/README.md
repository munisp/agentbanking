# open-appsec Application Security

## Overview
open-appsec provides ML-powered application security for APIs and web applications.

## Features
- API protection
- OWASP Top 10 protection
- Zero-day threat prevention
- Rate limiting
- Bot protection
- DDoS mitigation
- Real-time threat intelligence

## Deployment

### Docker Compose
```bash
cd services/security/openappsec
export AGENT_TOKEN="your-agent-token"
docker-compose up -d
```

### Kubernetes
```bash
kubectl create namespace security
kubectl create secret generic openappsec-secrets   --from-literal=agent-token=your-agent-token   -n security
kubectl apply -f openappsec-deployment.yaml
```

## Access
- Management Console: https://localhost:8443
- Default credentials: admin / SecurePassword123!

## Configuration

### Policy Example
```yaml
version: "1.0"
name: "api-protection-policy"
practices:
  - name: "rate-limiting"
    enabled: true
    limit: 1000
    window: 60
  - name: "sql-injection"
    action: "prevent"
  - name: "xss-protection"
    action: "prevent"
```

## Integration
```python
from openappsec_client import OpenAppsecIntegration

appsec = OpenAppsecIntegration(
    management_url="https://localhost:8443",
    username="admin",
    password="your_password"
)

stats = appsec.get_threat_statistics()
events = appsec.get_security_events(hours=24)
```

## Security Notes
- Change default credentials immediately
- Use strong agent tokens
- Enable SSL/TLS for production
- Regular policy updates
- Monitor security events
