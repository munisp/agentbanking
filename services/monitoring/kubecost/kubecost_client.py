#!/usr/bin/env python3
"""
Kubecost Integration Client
Kubernetes cost monitoring and optimization
"""

import requests
from typing import Dict, List
from datetime import datetime, timedelta

class KubecostIntegration:
    """Kubecost integration for cost monitoring"""
    
    def __init__(self, api_url: str) -> None:
        self.api_url = api_url.rstrip('/')
    
    def get_cluster_costs(self, window: str = "7d") -> Dict:
        """Get cluster costs for specified time window"""
        try:
            response = requests.get(
                f"{self.api_url}/model/allocation",
                params={'window': window}
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {'error': str(e)}
    
    def get_namespace_costs(self, namespace: str, window: str = "7d") -> Dict:
        """Get costs for specific namespace"""
        try:
            response = requests.get(
                f"{self.api_url}/model/allocation",
                params={
                    'window': window,
                    'aggregate': 'namespace',
                    'filter': f'namespace:{namespace}'
                }
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {'error': str(e)}
    
    def get_service_costs(self, service: str, window: str = "7d") -> Dict:
        """Get costs for specific service"""
        try:
            response = requests.get(
                f"{self.api_url}/model/allocation",
                params={
                    'window': window,
                    'aggregate': 'service',
                    'filter': f'service:{service}'
                }
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {'error': str(e)}
    
    def get_cost_recommendations(self) -> List[Dict]:
        """Get cost optimization recommendations"""
        try:
            response = requests.get(
                f"{self.api_url}/savings"
            )
            response.raise_for_status()
            return response.json().get('recommendations', [])
        except Exception as e:
            return []
    
    def get_cost_summary(self) -> Dict:
        """Get cost summary for all services"""
        try:
            cluster_costs = self.get_cluster_costs(window="30d")
            
            summary = {
                'total_monthly_cost': 0,
                'by_namespace': {},
                'top_services': [],
                'recommendations': self.get_cost_recommendations()
            }
            
            # Process allocation data
            if 'data' in cluster_costs:
                for allocation in cluster_costs['data']:
                    namespace = allocation.get('namespace', 'unknown')
                    cost = allocation.get('totalCost', 0)
                    
                    if namespace not in summary['by_namespace']:
                        summary['by_namespace'][namespace] = 0
                    summary['by_namespace'][namespace] += cost
                    summary['total_monthly_cost'] += cost
            
            return summary
        except Exception as e:
            return {'error': str(e)}

# Example usage
if __name__ == "__main__":
    kubecost = KubecostIntegration(
        api_url="http://localhost:9090"
    )
    
    # Get cost summary
    summary = kubecost.get_cost_summary()
    print("Cost Summary:", summary)
    
    # Get recommendations
    recommendations = kubecost.get_cost_recommendations()
    print(f"Recommendations: {len(recommendations)}")
