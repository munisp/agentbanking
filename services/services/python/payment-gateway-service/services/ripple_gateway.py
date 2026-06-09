"""
Ripple Payment Gateway Implementation
RippleNet Cross-Border Payment Network
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import httpx
import hashlib
import hmac
from ..base_gateway import BasePaymentGateway

class RippleGateway(BasePaymentGateway):
    """
    Ripple payment gateway - RippleNet Cross-Border Payment Network
    Supports international money transfers with competitive rates
    """
    
    def __init__(self, api_key: str, api_secret: str, environment: str = "sandbox"):
        super().__init__()
        self.api_key = api_key
        self.api_secret = api_secret
        self.environment = environment
        self.base_url = self._get_base_url()
        self.session = None
        
    def _get_base_url(self) -> str:
        """Get API base URL based on environment"""
        urls = {
            "production": f"https://api.ripple.com/v2",
            "sandbox": f"https://sandbox-api.ripple.com/v2"
        }
        return urls.get(self.environment, urls["sandbox"])
    
    def _generate_signature(self, payload: str) -> str:
        """Generate HMAC signature for request authentication"""
        return hmac.new(
            self.api_secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
    
    async def initialize_payment(
        self,
        amount: float,
        currency: str,
        sender_account: str,
        recipient_account: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Initialize a payment transaction
        
        Args:
            amount: Transaction amount
            currency: Currency code (USD, EUR, NGN, etc.)
            sender_account: Sender account identifier
            recipient_account: Recipient account identifier
            metadata: Additional transaction metadata
            
        Returns:
            Dict containing transaction_id, status, and payment details
        """
        try:
            payload = {
                "amount": amount,
                "currency": currency,
                "sender": sender_account,
                "recipient": recipient_account,
                "purpose": metadata.get("purpose", "remittance") if metadata else "remittance",
                "timestamp": datetime.utcnow().isoformat()
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/transfers",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "X-Signature": self._generate_signature(json.dumps(payload)),
                        "Content-Type": "application/json"
                    },
                    json=payload
                )
                response.raise_for_status()
                result = response.json()
                
                return {
                    "transaction_id": result.get("id"),
                    "status": result.get("status", "pending"),
                    "amount": amount,
                    "currency": currency,
                    "fees": result.get("fees", 0),
                    "exchange_rate": result.get("rate"),
                    "estimated_delivery": result.get("delivery_time")
                }
                
        except httpx.HTTPError as e:
            return {
                "error": str(e),
                "status": "failed",
                "error_code": getattr(e.response, 'status_code', None)
            }
        except Exception as e:
            return {"error": str(e), "status": "failed"}
    
    async def check_status(self, transaction_id: str) -> Dict[str, Any]:
        """
        Check payment transaction status
        
        Args:
            transaction_id: Unique transaction identifier
            
        Returns:
            Dict containing current status and transaction details
        """
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    f"{self.base_url}/transfers/{transaction_id}",
                    headers={"Authorization": f"Bearer {self.api_key}"}
                )
                response.raise_for_status()
                result = response.json()
                
                return {
                    "transaction_id": transaction_id,
                    "status": result.get("status"),
                    "current_state": result.get("state"),
                    "last_updated": result.get("updated_at"),
                    "tracking_number": result.get("tracking_id")
                }
                
        except Exception as e:
            return {"error": str(e), "status": "unknown"}
    
    async def process_refund(
        self,
        transaction_id: str,
        amount: Optional[float] = None,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process a refund for a completed transaction
        
        Args:
            transaction_id: Original transaction identifier
            amount: Refund amount (None for full refund)
            reason: Reason for refund
            
        Returns:
            Dict containing refund status and details
        """
        try:
            payload = {
                "transaction_id": transaction_id,
                "amount": amount,
                "reason": reason or "Customer request",
                "timestamp": datetime.utcnow().isoformat()
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/refunds",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "X-Signature": self._generate_signature(json.dumps(payload)),
                        "Content-Type": "application/json"
                    },
                    json=payload
                )
                response.raise_for_status()
                result = response.json()
                
                return {
                    "refund_id": result.get("id"),
                    "status": result.get("status"),
                    "amount": result.get("amount"),
                    "processing_time": result.get("processing_time")
                }
                
        except Exception as e:
            return {"error": str(e), "status": "failed"}
    
    async def validate_account(self, account_number: str, country_code: str = "NG") -> Dict[str, Any]:
        """
        Validate recipient account number
        
        Args:
            account_number: Account number to validate
            country_code: ISO country code
            
        Returns:
            Dict containing validation result and account details
        """
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    f"{self.base_url}/accounts/validate",
                    params={
                        "account": account_number,
                        "country": country_code
                    },
                    headers={"Authorization": f"Bearer {self.api_key}"}
                )
                response.raise_for_status()
                result = response.json()
                
                return {
                    "valid": result.get("valid", False),
                    "account_name": result.get("name"),
                    "bank_name": result.get("bank"),
                    "account_type": result.get("type")
                }
                
        except Exception as e:
            return {"error": str(e), "valid": False}
    
    async def get_exchange_rate(
        self,
        from_currency: str,
        to_currency: str,
        amount: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Get current exchange rate
        
        Args:
            from_currency: Source currency code
            to_currency: Target currency code
            amount: Amount to convert (optional)
            
        Returns:
            Dict containing exchange rate and converted amount
        """
        try:
            params = {
                "from": from_currency,
                "to": to_currency
            }
            if amount:
                params["amount"] = amount
                
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/rates",
                    params=params,
                    headers={"Authorization": f"Bearer {self.api_key}"}
                )
                response.raise_for_status()
                result = response.json()
                
                return {
                    "rate": result.get("rate"),
                    "from_currency": from_currency,
                    "to_currency": to_currency,
                    "converted_amount": result.get("converted_amount"),
                    "valid_until": result.get("expires_at")
                }
                
        except Exception as e:
            return {"error": str(e), "rate": None}
    
    async def get_transaction_fees(
        self,
        amount: float,
        currency: str,
        payment_method: str = "bank_transfer"
    ) -> Dict[str, Any]:
        """
        Calculate transaction fees
        
        Args:
            amount: Transaction amount
            currency: Currency code
            payment_method: Payment method type
            
        Returns:
            Dict containing fee breakdown
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/fees",
                    params={
                        "amount": amount,
                        "currency": currency,
                        "method": payment_method
                    },
                    headers={"Authorization": f"Bearer {self.api_key}"}
                )
                response.raise_for_status()
                result = response.json()
                
                return {
                    "total_fees": result.get("total_fee"),
                    "service_fee": result.get("service_fee"),
                    "processing_fee": result.get("processing_fee"),
                    "currency": currency
                }
                
        except Exception as e:
            return {"error": str(e), "total_fees": 0}
