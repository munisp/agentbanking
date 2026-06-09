"""
PayNow Payment Gateway Implementation
Singapore Fast Payment System
"""

from typing import Dict, Any, Optional
from datetime import datetime
import httpx
from ..base_gateway import BasePaymentGateway

class PayNowGateway(BasePaymentGateway):
    """
    PayNow payment gateway implementation
    Handles payments through Singapore Fast Payment System
    """
    
    def __init__(self, api_key: str, api_secret: str, environment: str = "sandbox"):
        super().__init__()
        self.api_key = api_key
        self.api_secret = api_secret
        self.environment = environment
        self.base_url = self._get_base_url()
        
    def _get_base_url(self) -> str:
        """Get API base URL based on environment"""
        if self.environment == "production":
            return f"https://api.paynow.com/v1"
        return f"https://sandbox-api.paynow.com/v1"
    
    async def initialize_payment(
        self,
        amount: float,
        currency: str,
        sender_account: str,
        recipient_account: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Initialize a payment transaction"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/payments",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "amount": amount,
                        "currency": currency,
                        "sender": sender_account,
                        "recipient": recipient_account,
                        "metadata": metadata or {}
                    }
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            return {"error": str(e), "status": "failed"}
    
    async def check_status(self, transaction_id: str) -> Dict[str, Any]:
        """Check payment status"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/payments/{transaction_id}",
                    headers={"Authorization": f"Bearer {self.api_key}"}
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            return {"error": str(e), "status": "unknown"}
    
    async def process_refund(
        self,
        transaction_id: str,
        amount: Optional[float] = None,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process a refund"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/refunds",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "transaction_id": transaction_id,
                        "amount": amount,
                        "reason": reason
                    }
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            return {"error": str(e), "status": "failed"}
    
    async def validate_account(self, account_number: str) -> Dict[str, Any]:
        """Validate account number"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/accounts/validate/{account_number}",
                    headers={"Authorization": f"Bearer {self.api_key}"}
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            return {"error": str(e), "valid": False}
    
    async def get_exchange_rate(self, from_currency: str, to_currency: str) -> Dict[str, Any]:
        """Get current exchange rate"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/rates",
                    params={"from": from_currency, "to": to_currency},
                    headers={"Authorization": f"Bearer {self.api_key}"}
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            return {"error": str(e), "rate": None}
