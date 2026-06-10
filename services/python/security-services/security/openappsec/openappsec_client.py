#!/usr/bin/env python3
"""
open-appsec Integration Client
Application security integration for the remittance platform
"""

import os
import requests
import json
import logging

logger = logging.getLogger(__name__)

_TLS_VERIFY = os.getenv("TLS_VERIFY", "true").lower() not in ("0", "false", "no")
_CA_BUNDLE = os.getenv("CA_BUNDLE_PATH", None) or _TLS_VERIFY
from typing import Dict, List
from datetime import datetime, timedelta

class OpenAppsecIntegration:
    """open-appsec application security integration"""
    
    def __init__(self, management_url: str, username: str, password: str):
        self.management_url = management_url.rstrip('/')
        self.username = username
        self.password = password
        self.session = requests.Session()
        self._authenticate()
    
    def _authenticate(self):
        """Authenticate with management console"""
        try:
            response = self.session.post(
                f"{self.management_url}/api/v1/auth/login",
                json={
                    'username': self.username,
                    'password': self.password
                },
                verify=_CA_BUNDLE
            )
            response.raise_for_status()
        except Exception as e:
            logger.error("Authentication failed: %s", e)
    
    def get_security_events(self, hours: int = 24) -> List[Dict]:
        """Get security events from the last N hours"""
        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=hours)
            
            response = self.session.get(
                f"{self.management_url}/api/v1/events",
                params={
                    'start_time': start_time.isoformat(),
                    'end_time': end_time.isoformat()
                },
                verify=_CA_BUNDLE
            )
            response.raise_for_status()
            return response.json().get('events', [])
        except Exception as e:
            logger.error("Failed to get events: %s", e)
            return []
    
    def get_threat_statistics(self) -> Dict:
        """Get threat statistics"""
        try:
            response = self.session.get(
                f"{self.management_url}/api/v1/statistics/threats",
                verify=_CA_BUNDLE
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error("Failed to get statistics: %s", e)
            return {}
    
    def update_security_policy(self, policy: Dict) -> Dict:
        """Update security policy"""
        try:
            response = self.session.put(
                f"{self.management_url}/api/v1/policy",
                json=policy,
                verify=_CA_BUNDLE
            )
            response.raise_for_status()
            return {
                'success': True,
                'message': 'Policy updated successfully'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def check_api_protection(self, endpoint: str) -> Dict:
        """Check protection status for specific API endpoint"""
        try:
            response = self.session.get(
                f"{self.management_url}/api/v1/protection/status",
                params={'endpoint': endpoint},
                verify=_CA_BUNDLE
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {
                'endpoint': endpoint,
                'protected': False,
                'error': str(e)
            }
    
    def get_blocked_requests(self, limit: int = 100) -> List[Dict]:
        """Get recently blocked requests"""
        try:
            response = self.session.get(
                f"{self.management_url}/api/v1/events/blocked",
                params={'limit': limit},
                verify=_CA_BUNDLE
            )
            response.raise_for_status()
            return response.json().get('blocked_requests', [])
        except Exception as e:
            logger.error("Failed to get blocked requests: %s", e)
            return []

# Example usage
if __name__ == "__main__":
    appsec = OpenAppsecIntegration(
        management_url="https://localhost:8443",
        username=os.getenv("OPENAPPSEC_USERNAME", "admin"),
        password=os.getenv("OPENAPPSEC_PASSWORD", "")
    )
    
    # Get threat statistics
    stats = appsec.get_threat_statistics()
    print("Threat Statistics:", json.dumps(stats, indent=2))
    
    # Get recent security events
    events = appsec.get_security_events(hours=1)
    print(f"Security Events (last hour): {len(events)}")
