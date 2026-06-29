#!/usr/bin/env python3
"""
OpenCTI Integration Client
Integrates threat intelligence with the remittance platform
"""

from pycti import OpenCTIApiClient
import json
from datetime import datetime
from typing import Dict, List, Optional

class OpenCTIIntegration:
    """OpenCTI threat intelligence integration"""
    
    def __init__(self, url: str, token: str):
        self.client = OpenCTIApiClient(url, token)
        
    def check_ip_reputation(self, ip_address: str) -> Dict:
        """Check IP address reputation against threat intelligence"""
        try:
            # Query OpenCTI for IP indicators
            indicators = self.client.indicator.list(
                filters=[{
                    "key": "pattern",
                    "values": [ip_address]
                }]
            )
            
            if indicators:
                return {
                    "ip": ip_address,
                    "threat_level": self._calculate_threat_level(indicators),
                    "indicators": indicators,
                    "is_malicious": True
                }
            
            return {
                "ip": ip_address,
                "threat_level": "low",
                "indicators": [],
                "is_malicious": False
            }
        except Exception as e:
            return {
                "ip": ip_address,
                "error": str(e),
                "threat_level": "unknown"
            }
    
    def report_suspicious_transaction(self, transaction_data: Dict) -> Dict:
        """Report suspicious transaction to OpenCTI"""
        try:
            # Create incident report
            incident = self.client.incident.create(
                name=f"Suspicious Transaction: {transaction_data.get('transaction_id')}",
                description=f"Flagged transaction from {transaction_data.get('source_country')} to {transaction_data.get('destination_country')}",
                severity="medium",
                first_seen=datetime.utcnow().isoformat(),
                last_seen=datetime.utcnow().isoformat()
            )
            
            return {
                "success": True,
                "incident_id": incident["id"],
                "transaction_id": transaction_data.get("transaction_id")
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_threat_actors(self, country: Optional[str] = None) -> List[Dict]:
        """Get threat actors targeting specific country"""
        try:
            filters = []
            if country:
                filters.append({
                    "key": "country",
                    "values": [country]
                })
            
            threat_actors = self.client.threat_actor.list(filters=filters)
            return threat_actors
        except Exception as e:
            return []
    
    def _calculate_threat_level(self, indicators: List[Dict]) -> str:
        """Calculate overall threat level from indicators"""
        if not indicators:
            return "low"
        
        high_severity_count = sum(1 for i in indicators if i.get("x_opencti_score", 0) >= 70)
        
        if high_severity_count > 0:
            return "high"
        elif len(indicators) > 3:
            return "medium"
        else:
            return "low"

# Example usage
if __name__ == "__main__":
    # Initialize client
    opencti = OpenCTIIntegration(
        url="http://localhost:8080",
        token="changeme"
    )
    
    # Check IP reputation
    result = opencti.check_ip_reputation("192.168.1.1")
    print(json.dumps(result, indent=2))
