"""
NIBSS Payment Gateway Service
"""

from .client import NibssClient
from typing import Dict
import os

class NibssService:
    def __init__(self):
        self.client = NibssClient(
            api_key=os.getenv("NIBSS_API_KEY", "test_key")
        )
    
    async def process_transfer(self, transfer_data: Dict) -> Dict:
        """Process a transfer through nibss"""
        try:
            result = await self.client.initiate_transfer(transfer_data)
            return {
                "success": True,
                "gateway": "nibss",
                "transfer_id": result.get("id"),
                "status": result.get("status"),
                "data": result
            }
        except Exception as e:
            return {
                "success": False,
                "gateway": "nibss",
                "error": str(e)
            }
    
    async def check_status(self, transfer_id: str) -> Dict:
        """Check transfer status"""
        try:
            result = await self.client.get_transfer_status(transfer_id)
            return {
                "success": True,
                "gateway": "nibss",
                "status": result.get("status"),
                "data": result
            }
        except Exception as e:
            return {
                "success": False,
                "gateway": "nibss",
                "error": str(e)
            }
