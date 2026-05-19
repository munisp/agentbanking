# Wazuh Security Monitoring

## Overview
Wazuh security monitoring integration for comprehensive security event detection and response.

## Features
- Real-time security event monitoring
- Vulnerability detection
- File integrity monitoring
- Log analysis and correlation
- Compliance monitoring (PCI-DSS, GDPR)
- Agent-based monitoring

## Deployment

### Docker Compose
```bash
cd services/security/wazuh
docker-compose up -d
```

### Kubernetes
```bash
kubectl create namespace security
kubectl apply -f wazuh-deployment.yaml
```

## Access
- Dashboard: https://localhost:443
- API: https://localhost:55000
- Default credentials: wazuh-wui / MyS3cr37P450r.*-

## Agent Installation

### Linux
```bash
curl -s https://packages.wazuh.com/key/GPG-KEY-WAZUH | apt-key add -
echo "deb https://packages.wazuh.com/4.x/apt/ stable main" | tee /etc/apt/sources.list.d/wazuh.list
apt-get update
apt-get install wazuh-agent
```

### Configure Agent
```bash
echo "WAZUH_MANAGER='wazuh-manager-ip'" > /var/ossec/etc/ossec.conf
systemctl restart wazuh-agent
```

## Integration
```python
from wazuh_client import WazuhIntegration

wazuh = WazuhIntegration(
    api_url="https://localhost:55000",
    username="wazuh-wui",
    password="your_password"
)

alerts = wazuh.get_security_alerts()
```

## Security Notes
- Change default passwords immediately
- Enable SSL/TLS for production
- Configure firewall rules for agent communication
- Regular security updates
