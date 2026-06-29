"""
BRICS-PAY Payment Gateway Service
"""

from .client import BricsPayClient
from typing import Dict
import os

class BricsPayService:
    def __init__(self):
        self.client = BricsPayClient(
            api_key=os.getenv("BRICS-PAY_API_KEY", "test_key")
        )
    
    async def process_transfer(self, transfer_data: Dict) -> Dict:
        """Process a transfer through brics-pay"""
        try:
            result = await self.client.initiate_transfer(transfer_data)
            return {
                "success": True,
                "gateway": "brics-pay",
                "transfer_id": result.get("id"),
                "status": result.get("status"),
                "data": result
            }
        except Exception as e:
            return {
                "success": False,
                "gateway": "brics-pay",
                "error": str(e)
            }
    
    async def check_status(self, transfer_id: str) -> Dict:
        """Check transfer status"""
        try:
            result = await self.client.get_transfer_status(transfer_id)
            return {
                "success": True,
                "gateway": "brics-pay",
                "status": result.get("status"),
                "data": result
            }
        except Exception as e:
            return {
                "success": False,
                "gateway": "brics-pay",
                "error": str(e)
            }
