"""
PIX Payment Gateway Service
"""

from .client import PixClient
from typing import Dict
import os

class PixService:
    def __init__(self):
        self.client = PixClient(
            api_key=os.getenv("PIX_API_KEY", "test_key")
        )
    
    async def process_transfer(self, transfer_data: Dict) -> Dict:
        """Process a transfer through pix"""
        try:
            result = await self.client.initiate_transfer(transfer_data)
            return {
                "success": True,
                "gateway": "pix",
                "transfer_id": result.get("id"),
                "status": result.get("status"),
                "data": result
            }
        except Exception as e:
            return {
                "success": False,
                "gateway": "pix",
                "error": str(e)
            }
    
    async def check_status(self, transfer_id: str) -> Dict:
        """Check transfer status"""
        try:
            result = await self.client.get_transfer_status(transfer_id)
            return {
                "success": True,
                "gateway": "pix",
                "status": result.get("status"),
                "data": result
            }
        except Exception as e:
            return {
                "success": False,
                "gateway": "pix",
                "error": str(e)
            }
