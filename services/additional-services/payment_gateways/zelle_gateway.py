"""
Zelle Payment Gateway
USA P2P instant transfers

Coverage: United States
Settlement: Minutes
Fee: Free for consumers
Use Case: USA P2P transfers
"""

import asyncio
import hashlib
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Dict, Optional

import httpx


class PaymentStatus(Enum):
    """Payment status"""
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ZelleGateway:
    """
    Zelle Payment Gateway
    
    USA instant P2P payment system
    
    Features:
    - Email/mobile recipient lookup
    - Instant settlement
    - Bank account integration
    - Split payments
    """
    
    def __init__(
        self,
        api_url: str,
        bank_id: str,
        api_key: str,
        api_secret: str
    ):
        """Initialize Zelle gateway"""
        self.api_url = api_url
        self.bank_id = bank_id
        self.api_key = api_key
        self.api_secret = api_secret
        
        self.client: Optional[httpx.AsyncClient] = None
        self._transactions: Dict[str, Dict] = {}
    
    async def __aenter__(self):
        self.client = httpx.AsyncClient(timeout=30)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()
    
    async def send_payment(
        self,
        transaction_id: str,
        sender_token: str,  # Zelle enrollment token
        recipient_identifier: str,  # Email or mobile
        recipient_name: str,
        amount: Decimal,
        memo: str = "Zelle payment"
    ) -> Dict:
        """Send Zelle payment"""
        if not self.client:
            raise RuntimeError("Gateway not initialized")
        
        # Validate amount ($0.01 - $2,500 per transaction)
        if amount < Decimal("0.01") or amount > Decimal("2500"):
            return {
                "status": "REJECTED",
                "reason": "Amount must be between $0.01 and $2,500"
            }
        
        # Lookup recipient
        recipient_info = await self._lookup_recipient(recipient_identifier)
        
        if not recipient_info or not recipient_info.get("enrolled"):
            return {
                "status": "REJECTED",
                "reason": "Recipient not enrolled in Zelle"
            }
        
        try:
            response = await self.client.post(
                f"{self.api_url}/payments",
                json={
                    "sender_token": sender_token,
                    "recipient_token": recipient_info["token"],
                    "amount": float(amount),
                    "currency": "USD",
                    "memo": memo
                },
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "X-Bank-ID": self.bank_id
                }
            )
            
            response.raise_for_status()
            data = response.json()
            
            self._transactions[transaction_id] = {
                "transaction_id": transaction_id,
                "zelle_id": data.get("payment_id"),
                "status": PaymentStatus.COMPLETED.value,  # Zelle is instant
                "amount": float(amount),
                "recipient": recipient_identifier,
                "completed_at": datetime.now(timezone.utc).isoformat()
            }
            
            return {
                "status": "SUCCESS",
                "transaction_id": transaction_id,
                "zelle_id": data["payment_id"],
                "estimated_completion": "Instant",
                "fee": Decimal("0.00")
            }
            
        except httpx.HTTPStatusError as e:
            error_detail = e.response.json() if e.response else {}
            return {
                "status": "FAILED",
                "error": error_detail.get("error", "Payment failed"),
                "error_code": error_detail.get("code")
            }
        except Exception as e:
            return {"status": "FAILED", "error": str(e)}
    
    async def get_payment_status(
        self,
        transaction_id: str
    ) -> Dict:
        """Get payment status"""
        if transaction_id in self._transactions:
            return self._transactions[transaction_id]
        return {"status": "NOT_FOUND"}
    
    async def _lookup_recipient(self, identifier: str) -> Optional[Dict]:
        """Lookup recipient enrollment"""
        if not self.client:
            return None
        
        try:
            response = await self.client.get(
                f"{self.api_url}/enrollment/lookup",
                params={"identifier": identifier},
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "X-Bank-ID": self.bank_id
                }
            )
            
            if response.status_code == 200:
                return response.json()
            
            return None
            
        except:
            return None
