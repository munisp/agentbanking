"""
UPI Payment Gateway Client
"""

import httpx
from typing import Dict, Optional

class UpiClient:
    def __init__(self, api_key: str, base_url: str = "https://api.upi.com"):
        self.api_key = api_key
        self.base_url = base_url
        self.client = httpx.AsyncClient()
    
    async def initiate_transfer(self, data: Dict) -> Dict:
        """Initiate a transfer"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        response = await self.client.post(
            f"{self.base_url}/v1/transfers",
            json=data,
            headers=headers
        )
        return response.json()
    
    async def get_transfer_status(self, transfer_id: str) -> Dict:
        """Get transfer status"""
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }
        response = await self.client.get(
            f"{self.base_url}/v1/transfers/{transfer_id}",
            headers=headers
        )
        return response.json()
    
    async def get_exchange_rate(self, from_currency: str, to_currency: str) -> Dict:
        """Get exchange rate"""
        response = await self.client.get(
            f"{self.base_url}/v1/rates/{from_currency}/{to_currency}"
        )
        return response.json()
    
    async def close(self):
        await self.client.aclose()
