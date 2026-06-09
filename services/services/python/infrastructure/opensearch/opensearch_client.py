#!/usr/bin/env python3
"""
OpenSearch Integration Client
Search and analytics engine for the remittance platform
"""

from opensearchpy import OpenSearch
from typing import Dict, List
import json

class OpenSearchIntegration:
    """OpenSearch integration for logging and analytics"""
    
    def __init__(self, hosts: List[str], auth: tuple) -> None:
        self.client = OpenSearch(
            hosts=hosts,
            http_auth=auth,
            use_ssl=True,
            verify_certs=False,
            ssl_show_warn=False
        )
    
    def create_index(self, index_name: str, mappings: Dict = None) -> Dict[str, Any]:
        """Create an index with optional mappings"""
        body = {}
        if mappings:
            body['mappings'] = mappings
        
        try:
            self.client.indices.create(index=index_name, body=body)
            return {'success': True, 'index': index_name}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def index_transaction(self, transaction: Dict) -> Dict[str, Any]:
        """Index a transaction for search and analytics"""
        try:
            response = self.client.index(
                index='transactions',
                body=transaction
            )
            return response
        except Exception as e:
            return {'error': str(e)}
    
    def search_transactions(self, query: Dict, size: int = 10) -> List[Dict]:
        """Search transactions"""
        try:
            response = self.client.search(
                index='transactions',
                body={'query': query, 'size': size}
            )
            return response['hits']['hits']
        except Exception as e:
            return []
    
    def aggregate_by_corridor(self) -> Dict:
        """Aggregate transactions by payment corridor"""
        try:
            response = self.client.search(
                index='transactions',
                body={
                    'size': 0,
                    'aggs': {
                        'by_corridor': {
                            'terms': {
                                'field': 'corridor.keyword',
                                'size': 10
                            },
                            'aggs': {
                                'total_amount': {
                                    'sum': {
                                        'field': 'amount'
                                    }
                                }
                            }
                        }
                    }
                }
            )
            return response['aggregations']['by_corridor']
        except Exception as e:
            return {}

# Example usage
if __name__ == "__main__":
    client = OpenSearchIntegration(
        hosts=['https://localhost:9200'],
        auth=('admin', 'Admin@123')
    )
    
    # Create transactions index
    client.create_index('transactions', {
        'properties': {
            'transaction_id': {'type': 'keyword'},
            'amount': {'type': 'float'},
            'corridor': {'type': 'keyword'},
            'timestamp': {'type': 'date'}
        }
    })
    
    # Index a transaction
    client.index_transaction({
        'transaction_id': 'TXN001',
        'amount': 100000,
        'corridor': 'PAPSS',
        'timestamp': '2025-10-23T00:00:00Z'
    })
