#!/usr/bin/env python3
"""
Wazuh Integration Client
Security monitoring integration for the remittance platform
"""

import os
import requests
import json
import logging

logger = logging.getLogger(__name__)

_TLS_VERIFY = os.getenv("TLS_VERIFY", "true").lower() not in ("0", "false", "no")
_CA_BUNDLE = os.getenv("CA_BUNDLE_PATH", None) or _TLS_VERIFY
from typing import Dict, List
from datetime import datetime

class WazuhIntegration:
    """Wazuh security monitoring integration"""
    
    def __init__(self, api_url: str, username: str, password: str):
        self.api_url = api_url.rstrip('/')
        self.username = username
        self.password = password
        self.token = None
        self._authenticate()
    
    def _authenticate(self):
        """Authenticate with Wazuh API"""
        try:
            response = requests.post(
                f"{self.api_url}/security/user/authenticate",
                auth=(self.username, self.password),
                verify=_CA_BUNDLE
            )
            response.raise_for_status()
            self.token = response.json()['data']['token']
        except Exception as e:
            logger.error("Authentication failed: %s", e)
    
    def get_headers(self) -> Dict:
        """Get API request headers"""
        return {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json'
        }
    
    def get_security_alerts(self, limit: int = 100) -> List[Dict]:
        """Get recent security alerts"""
        try:
            response = requests.get(
                f"{self.api_url}/security/alerts",
                headers=self.get_headers(),
                params={'limit': limit},
                verify=_CA_BUNDLE
            )
            response.raise_for_status()
            return response.json()['data']['affected_items']
        except Exception as e:
            logger.error("Failed to get alerts: %s", e)
            return []
    
    def get_agent_status(self) -> Dict:
        """Get status of all Wazuh agents"""
        try:
            response = requests.get(
                f"{self.api_url}/agents",
                headers=self.get_headers(),
                verify=_CA_BUNDLE
            )
            response.raise_for_status()
            agents = response.json()['data']['affected_items']
            
            status_summary = {
                'active': 0,
                'disconnected': 0,
                'never_connected': 0,
                'total': len(agents)
            }
            
            for agent in agents:
                status = agent.get('status', 'unknown')
                if status in status_summary:
                    status_summary[status] += 1
            
            return status_summary
        except Exception as e:
            logger.error("Failed to get agent status: %s", e)
            return {}
    
    def check_vulnerabilities(self, agent_id: str = None) -> List[Dict]:
        """Check for vulnerabilities on agents"""
        try:
            endpoint = f"{self.api_url}/vulnerability/{agent_id}" if agent_id else f"{self.api_url}/vulnerability"
            response = requests.get(
                endpoint,
                headers=self.get_headers(),
                verify=_CA_BUNDLE
            )
            response.raise_for_status()
            return response.json()['data']['affected_items']
        except Exception as e:
            logger.error("Failed to check vulnerabilities: %s", e)
            return []
    
    def monitor_payment_service(self, service_name: str) -> Dict:
        """Monitor specific payment service for security events"""
        try:
            response = requests.get(
                f"{self.api_url}/security/alerts",
                headers=self.get_headers(),
                params={
                    'q': f'rule.groups:service AND data.service:{service_name}',
                    'limit': 50
                },
                verify=_CA_BUNDLE
            )
            response.raise_for_status()
            alerts = response.json()['data']['affected_items']
            
            return {
                'service': service_name,
                'alert_count': len(alerts),
                'critical_alerts': sum(1 for a in alerts if a.get('rule', {}).get('level', 0) >= 12),
                'recent_alerts': alerts[:10]
            }
        except Exception as e:
            logger.error("Failed to monitor service: %s", e)
            return {}

# Example usage
if __name__ == "__main__":
    wazuh = WazuhIntegration(
        api_url="https://localhost:55000",
        username=os.getenv("WAZUH_USERNAME", "wazuh-wui"),
        password=os.getenv("WAZUH_PASSWORD", "")
    )
    
    # Get agent status
    status = wazuh.get_agent_status()
    print("Agent Status:", json.dumps(status, indent=2))
    
    # Get security alerts
    alerts = wazuh.get_security_alerts(limit=10)
    print(f"Recent Alerts: {len(alerts)}")
