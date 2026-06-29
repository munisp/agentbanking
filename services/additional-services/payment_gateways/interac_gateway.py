"""
Interac e-Transfer Payment Gateway
Canadian domestic instant transfers

Coverage: Canada
Settlement: Minutes to hours
Fee: Free for consumers
Use Case: Canadian P2P and business transfers
"""

import asyncio
import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional

import httpx


class PaymentStatus(Enum):
    """Payment status"""
    PENDING = "PENDING"
    DEPOSITED = "DEPOSITED"
    COMPLETED = "COMPLETED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    DECLINED = "DECLINED"


class InteracGateway:
    """
    Interac e-Transfer Gateway
    
    Canadian instant payment system
    
    Features:
    - Email/mobile recipient lookup
    - Security question/answer
    - Autodeposit support
    - Request money
    - Bulk transfers
    """
    
    def __init__(
        self,
        api_url: str,
        financial_institution_id: str,
        api_key: str,
        api_secret: str
    ):
        """
        Initialize Interac gateway
        
        Args:
            api_url: Interac API endpoint
            financial_institution_id: Financial institution ID
            api_key: API key
            api_secret: API secret
        """
        self.api_url = api_url
        self.fi_id = financial_institution_id
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
    
    async def send_money(
        self,
        transaction_id: str,
        sender_name: str,
        sender_email: str,
        recipient_email: str,
        recipient_name: str,
        amount: Decimal,
        security_question: Optional[str] = None,
        security_answer: Optional[str] = None,
        message: str = "Interac e-Transfer",
        expiry_days: int = 30
    ) -> Dict:
        """
        Send money via Interac e-Transfer
        
        Args:
            transaction_id: Unique transaction ID
            sender_name: Sender name
            sender_email: Sender email
            recipient_email: Recipient email
            recipient_name: Recipient name
            amount: Amount in CAD
            security_question: Security question (if no autodeposit)
            security_answer: Security answer
            message: Transfer message
            expiry_days: Days until expiry
            
        Returns:
            Transfer result
        """
        if not self.client:
            raise RuntimeError("Gateway not initialized")
        
        # Validate amount
        if amount < Decimal("0.01") or amount > Decimal("10000"):
            return {
                "status": "REJECTED",
                "reason": "Amount must be between $0.01 and $10,000 CAD"
            }
        
        # Check if recipient has autodeposit
        autodeposit = await self._check_autodeposit(recipient_email)
        
        # If no autodeposit, require security Q&A
        if not autodeposit and (not security_question or not security_answer):
            return {
                "status": "REJECTED",
                "reason": "Security question and answer required"
            }
        
        # Generate reference number
        reference_number = self._generate_reference_number()
        
        try:
            response = await self.client.post(
                f"{self.api_url}/transfers",
                json={
                    "reference_number": reference_number,
                    "sender": {
                        "name": sender_name,
                        "email": sender_email
                    },
                    "recipient": {
                        "name": recipient_name,
                        "email": recipient_email
                    },
                    "amount": float(amount),
                    "currency": "CAD",
                    "message": message,
                    "security_question": security_question if not autodeposit else None,
                    "security_answer_hash": self._hash_answer(security_answer) if security_answer else None,
                    "expiry_date": (datetime.now(timezone.utc) + timedelta(days=expiry_days)).isoformat(),
                    "autodeposit": autodeposit
                },
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "X-FI-ID": self.fi_id
                }
            )
            
            response.raise_for_status()
            data = response.json()
            
            self._transactions[transaction_id] = {
                "transaction_id": transaction_id,
                "reference_number": reference_number,
                "status": PaymentStatus.DEPOSITED.value if autodeposit else PaymentStatus.PENDING.value,
                "amount": float(amount),
                "recipient_email": recipient_email,
                "autodeposit": autodeposit,
                "initiated_at": datetime.now(timezone.utc).isoformat(),
                "expires_at": data.get("expiry_date")
            }
            
            return {
                "status": "SUCCESS",
                "transaction_id": transaction_id,
                "reference_number": reference_number,
                "autodeposit": autodeposit,
                "estimated_completion": "Instant" if autodeposit else "When recipient accepts",
                "expires_at": data.get("expiry_date"),
                "fee": Decimal("0.00")  # Free for consumers
            }
            
        except httpx.HTTPStatusError as e:
            error_detail = e.response.json() if e.response else {}
            return {
                "status": "FAILED",
                "error": error_detail.get("error", "Transfer failed"),
                "error_code": error_detail.get("code")
            }
        except Exception as e:
            return {
                "status": "FAILED",
                "error": str(e)
            }
    
    async def get_transfer_status(
        self,
        transaction_id: str,
        reference_number: Optional[str] = None
    ) -> Dict:
        """Get transfer status"""
        if not self.client:
            raise RuntimeError("Gateway not initialized")
        
        if transaction_id in self._transactions:
            local_status = self._transactions[transaction_id]
            if local_status["status"] in ["COMPLETED", "EXPIRED", "CANCELLED", "DECLINED"]:
                return local_status
        
        try:
            ref = reference_number or self._transactions.get(transaction_id, {}).get("reference_number")
            
            if not ref:
                return {"status": "NOT_FOUND"}
            
            response = await self.client.get(
                f"{self.api_url}/transfers/{ref}/status",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "X-FI-ID": self.fi_id
                }
            )
            
            response.raise_for_status()
            data = response.json()
            
            status = self._map_interac_status(data.get("status"))
            if transaction_id in self._transactions:
                self._transactions[transaction_id]["status"] = status
                if status == PaymentStatus.COMPLETED.value:
                    self._transactions[transaction_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
            
            return {
                "transaction_id": transaction_id,
                "reference_number": ref,
                "status": status,
                "deposited_at": data.get("deposited_at"),
                "last_updated": data.get("last_updated")
            }
            
        except Exception as e:
            return {"status": "ERROR", "error": str(e)}
    
    async def cancel_transfer(
        self,
        transaction_id: str,
        reason: str
    ) -> Dict:
        """Cancel pending transfer"""
        if not self.client:
            raise RuntimeError("Gateway not initialized")
        
        if transaction_id not in self._transactions:
            return {"status": "NOT_FOUND"}
        
        local_status = self._transactions[transaction_id]
        
        if local_status["status"] not in ["PENDING"]:
            return {
                "status": "CANNOT_CANCEL",
                "error": f"Cannot cancel transfer in {local_status['status']} status"
            }
        
        try:
            ref = local_status["reference_number"]
            
            response = await self.client.post(
                f"{self.api_url}/transfers/{ref}/cancel",
                json={"reason": reason},
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "X-FI-ID": self.fi_id
                }
            )
            
            response.raise_for_status()
            
            self._transactions[transaction_id]["status"] = PaymentStatus.CANCELLED.value
            self._transactions[transaction_id]["cancelled_at"] = datetime.now(timezone.utc).isoformat()
            
            return {
                "status": "SUCCESS",
                "transaction_id": transaction_id,
                "message": "Transfer cancelled"
            }
            
        except Exception as e:
            return {"status": "FAILED", "error": str(e)}
    
    async def request_money(
        self,
        request_id: str,
        requester_name: str,
        requester_email: str,
        payer_email: str,
        amount: Decimal,
        message: str = "Payment request",
        expiry_days: int = 30
    ) -> Dict:
        """Request money from someone"""
        if not self.client:
            raise RuntimeError("Gateway not initialized")
        
        try:
            response = await self.client.post(
                f"{self.api_url}/requests",
                json={
                    "requester": {
                        "name": requester_name,
                        "email": requester_email
                    },
                    "payer_email": payer_email,
                    "amount": float(amount),
                    "currency": "CAD",
                    "message": message,
                    "expiry_date": (datetime.now(timezone.utc) + timedelta(days=expiry_days)).isoformat()
                },
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "X-FI-ID": self.fi_id
                }
            )
            
            response.raise_for_status()
            data = response.json()
            
            return {
                "status": "SUCCESS",
                "request_id": request_id,
                "reference_number": data.get("reference_number"),
                "expires_at": data.get("expiry_date")
            }
            
        except Exception as e:
            return {"status": "FAILED", "error": str(e)}
    
    async def _check_autodeposit(self, email: str) -> bool:
        """Check if recipient has autodeposit enabled"""
        if not self.client:
            return False
        
        try:
            response = await self.client.get(
                f"{self.api_url}/autodeposit/check",
                params={"email": email},
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "X-FI-ID": self.fi_id
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("autodeposit_enabled", False)
            
            return False
            
        except:
            return False
    
    def _generate_reference_number(self) -> str:
        """Generate unique reference number"""
        return f"IT{secrets.token_hex(8).upper()}"
    
    def _hash_answer(self, answer: str) -> str:
        """Hash security answer"""
        return hashlib.sha256(answer.lower().strip().encode()).hexdigest()
    
    def _map_interac_status(self, interac_status: str) -> str:
        """Map Interac status"""
        status_map = {
            "PENDING": PaymentStatus.PENDING.value,
            "DEPOSITED": PaymentStatus.DEPOSITED.value,
            "COMPLETED": PaymentStatus.COMPLETED.value,
            "EXPIRED": PaymentStatus.EXPIRED.value,
            "CANCELLED": PaymentStatus.CANCELLED.value,
            "DECLINED": PaymentStatus.DECLINED.value
        }
        return status_map.get(interac_status, PaymentStatus.PENDING.value)
