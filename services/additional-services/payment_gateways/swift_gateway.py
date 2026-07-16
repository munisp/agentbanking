"""
SWIFT Payment Gateway
International wire transfers via SWIFT network

Coverage: 200+ countries, 11,000+ banks
Settlement: 1-3 business days
Fee: 0.5-1.0%
Use Case: Large transactions, business payments
"""

import asyncio
import hashlib
import hmac
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional
import xml.etree.ElementTree as ET

import httpx


class SWIFTMessageType(Enum):
    """SWIFT message types"""
    MT103 = "MT103"  # Single customer credit transfer
    MT202 = "MT202"  # Financial institution transfer
    MT900 = "MT900"  # Confirmation of debit
    MT910 = "MT910"  # Confirmation of credit


class PaymentStatus(Enum):
    """Payment status"""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class SWIFTGateway:
    """
    SWIFT Payment Gateway
    
    Provides international wire transfers via SWIFT network
    
    Features:
    - MT103 message format
    - BIC/SWIFT code validation
    - IBAN validation
    - Multi-currency support
    - Compliance checks (OFAC, sanctions)
    - Real-time tracking
    """
    
    def __init__(
        self,
        api_url: str,
        bic_code: str,  # Our bank's BIC
        api_key: str,
        api_secret: str
    ):
        """
        Initialize SWIFT gateway
        
        Args:
            api_url: SWIFT API endpoint
            bic_code: Bank Identifier Code
            api_key: API key
            api_secret: API secret for HMAC
        """
        self.api_url = api_url
        self.bic_code = bic_code
        self.api_key = api_key
        self.api_secret = api_secret
        
        # HTTP client
        self.client: Optional[httpx.AsyncClient] = None
        
        # Transaction tracking
        self._transactions: Dict[str, Dict] = {}
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.client = httpx.AsyncClient(timeout=60)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.client:
            await self.client.aclose()
    
    async def initiate_payment(
        self,
        transaction_id: str,
        sender_name: str,
        sender_account: str,
        sender_bank_bic: str,
        recipient_name: str,
        recipient_account: str,  # IBAN or account number
        recipient_bank_bic: str,
        amount: Decimal,
        currency: str,
        purpose: str = "International transfer",
        reference: Optional[str] = None
    ) -> Dict:
        """
        Initiate SWIFT payment
        
        Args:
            transaction_id: Unique transaction ID
            sender_name: Sender full name
            sender_account: Sender account number
            sender_bank_bic: Sender bank BIC code
            recipient_name: Recipient full name
            recipient_account: Recipient IBAN or account number
            recipient_bank_bic: Recipient bank BIC code
            amount: Transfer amount
            currency: Currency code (ISO 4217)
            purpose: Payment purpose/description
            reference: Optional reference number
            
        Returns:
            Payment initiation response
        """
        if not self.client:
            raise RuntimeError("Gateway not initialized. Use async context manager.")
        
        # Validate inputs
        self._validate_bic(sender_bank_bic)
        self._validate_bic(recipient_bank_bic)
        if recipient_account.startswith(("GB", "DE", "FR", "IT", "ES")):
            self._validate_iban(recipient_account)
        
        # Check sanctions/OFAC
        compliance_check = await self._check_compliance(
            recipient_name,
            recipient_bank_bic
        )
        
        if not compliance_check["approved"]:
            return {
                "status": "REJECTED",
                "reason": "Compliance check failed",
                "details": compliance_check
            }
        
        # Build MT103 message
        mt103_message = self._build_mt103_message(
            transaction_id=transaction_id,
            sender_name=sender_name,
            sender_account=sender_account,
            sender_bank_bic=sender_bank_bic,
            recipient_name=recipient_name,
            recipient_account=recipient_account,
            recipient_bank_bic=recipient_bank_bic,
            amount=amount,
            currency=currency,
            purpose=purpose,
            reference=reference or transaction_id
        )
        
        # Generate signature
        signature = self._generate_signature(mt103_message)
        
        # Send to SWIFT network
        try:
            response = await self.client.post(
                f"{self.api_url}/payments",
                json={
                    "message_type": "MT103",
                    "message": mt103_message,
                    "signature": signature
                },
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "X-BIC-Code": self.bic_code
                }
            )
            
            response.raise_for_status()
            data = response.json()
            
            # Store transaction
            self._transactions[transaction_id] = {
                "transaction_id": transaction_id,
                "swift_reference": data.get("swift_reference"),
                "status": PaymentStatus.PROCESSING.value,
                "amount": float(amount),
                "currency": currency,
                "recipient_bic": recipient_bank_bic,
                "initiated_at": datetime.now(timezone.utc).isoformat(),
                "estimated_completion": self._estimate_completion_time()
            }
            
            return {
                "status": "SUCCESS",
                "transaction_id": transaction_id,
                "swift_reference": data.get("swift_reference"),
                "uetr": data.get("uetr"),  # Unique End-to-End Transaction Reference
                "estimated_completion": self._transactions[transaction_id]["estimated_completion"],
                "fee": self._calculate_fee(amount, currency)
            }
            
        except httpx.HTTPStatusError as e:
            error_detail = e.response.json() if e.response else {}
            return {
                "status": "FAILED",
                "error": error_detail.get("error", "Payment initiation failed"),
                "error_code": error_detail.get("code", "SWIFT_ERROR")
            }
        except Exception as e:
            return {
                "status": "FAILED",
                "error": str(e),
                "error_code": "NETWORK_ERROR"
            }
    
    async def get_payment_status(
        self,
        transaction_id: str,
        swift_reference: Optional[str] = None
    ) -> Dict:
        """
        Get payment status
        
        Args:
            transaction_id: Transaction ID
            swift_reference: SWIFT reference number
            
        Returns:
            Payment status information
        """
        if not self.client:
            raise RuntimeError("Gateway not initialized")
        
        # Check local cache first
        if transaction_id in self._transactions:
            local_status = self._transactions[transaction_id]
            
            # If completed or failed, return cached status
            if local_status["status"] in ["COMPLETED", "FAILED", "CANCELLED"]:
                return local_status
        
        # Query SWIFT network
        try:
            reference = swift_reference or self._transactions.get(transaction_id, {}).get("swift_reference")
            
            if not reference:
                return {
                    "status": "NOT_FOUND",
                    "error": "Transaction not found"
                }
            
            response = await self.client.get(
                f"{self.api_url}/payments/{reference}/status",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "X-BIC-Code": self.bic_code
                }
            )
            
            response.raise_for_status()
            data = response.json()
            
            # Update local cache
            status = self._map_swift_status(data.get("status"))
            if transaction_id in self._transactions:
                self._transactions[transaction_id]["status"] = status
                if status == PaymentStatus.COMPLETED.value:
                    self._transactions[transaction_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
            
            return {
                "transaction_id": transaction_id,
                "swift_reference": reference,
                "status": status,
                "current_location": data.get("current_location"),
                "intermediary_banks": data.get("intermediary_banks", []),
                "estimated_completion": data.get("estimated_completion"),
                "last_updated": data.get("last_updated")
            }
            
        except httpx.HTTPStatusError as e:
            return {
                "status": "ERROR",
                "error": "Failed to retrieve status",
                "error_code": e.response.status_code
            }
        except Exception as e:
            return {
                "status": "ERROR",
                "error": str(e)
            }
    
    async def cancel_payment(
        self,
        transaction_id: str,
        reason: str
    ) -> Dict:
        """
        Cancel pending payment
        
        Args:
            transaction_id: Transaction ID
            reason: Cancellation reason
            
        Returns:
            Cancellation result
        """
        if not self.client:
            raise RuntimeError("Gateway not initialized")
        
        if transaction_id not in self._transactions:
            return {
                "status": "NOT_FOUND",
                "error": "Transaction not found"
            }
        
        local_status = self._transactions[transaction_id]
        
        # Can only cancel pending/processing payments
        if local_status["status"] not in ["PENDING", "PROCESSING"]:
            return {
                "status": "CANNOT_CANCEL",
                "error": f"Cannot cancel payment in {local_status['status']} status"
            }
        
        try:
            swift_reference = local_status.get("swift_reference")
            
            response = await self.client.post(
                f"{self.api_url}/payments/{swift_reference}/cancel",
                json={"reason": reason},
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "X-BIC-Code": self.bic_code
                }
            )
            
            response.raise_for_status()
            
            # Update local status
            self._transactions[transaction_id]["status"] = PaymentStatus.CANCELLED.value
            self._transactions[transaction_id]["cancelled_at"] = datetime.now(timezone.utc).isoformat()
            self._transactions[transaction_id]["cancellation_reason"] = reason
            
            return {
                "status": "SUCCESS",
                "transaction_id": transaction_id,
                "message": "Payment cancelled successfully"
            }
            
        except httpx.HTTPStatusError as e:
            return {
                "status": "FAILED",
                "error": "Cancellation failed",
                "error_code": e.response.status_code
            }
        except Exception as e:
            return {
                "status": "FAILED",
                "error": str(e)
            }
    
    def _build_mt103_message(
        self,
        transaction_id: str,
        sender_name: str,
        sender_account: str,
        sender_bank_bic: str,
        recipient_name: str,
        recipient_account: str,
        recipient_bank_bic: str,
        amount: Decimal,
        currency: str,
        purpose: str,
        reference: str
    ) -> str:
        """Build MT103 SWIFT message"""
        # Simplified MT103 format
        # In production, use proper SWIFT message library
        
        value_date = datetime.now(timezone.utc).strftime("%y%m%d")
        
        mt103 = f"""{{1:F01{self.bic_code}0000000000}}
{{2:I103{recipient_bank_bic}N}}
{{3:{{108:{reference}}}}}
{{4:
:20:{reference}
:23B:CRED
:32A:{value_date}{currency}{amount}
:50K:/{sender_account}
{sender_name}
:52A:{sender_bank_bic}
:57A:{recipient_bank_bic}
:59:/{recipient_account}
{recipient_name}
:70:{purpose}
:71A:OUR
-}}"""
        
        return mt103
    
    def _validate_bic(self, bic: str) -> bool:
        """Validate BIC/SWIFT code format"""
        # BIC format: 4 letters (bank) + 2 letters (country) + 2 alphanumeric (location) + optional 3 alphanumeric (branch)
        if not bic or len(bic) not in [8, 11]:
            raise ValueError(f"Invalid BIC code length: {bic}")
        
        if not bic[:4].isalpha():
            raise ValueError(f"Invalid BIC code format: {bic}")
        
        if not bic[4:6].isalpha():
            raise ValueError(f"Invalid BIC country code: {bic}")
        
        return True
    
    def _validate_iban(self, iban: str) -> bool:
        """Validate IBAN format"""
        # Remove spaces
        iban = iban.replace(" ", "").upper()
        
        # Check length (15-34 characters)
        if len(iban) < 15 or len(iban) > 34:
            raise ValueError(f"Invalid IBAN length: {iban}")
        
        # Check format: 2 letters + 2 digits + alphanumeric
        if not iban[:2].isalpha() or not iban[2:4].isdigit():
            raise ValueError(f"Invalid IBAN format: {iban}")
        
        # Checksum validation (MOD 97)
        # Move first 4 characters to end
        rearranged = iban[4:] + iban[:4]
        
        # Convert letters to numbers (A=10, B=11, ..., Z=35)
        numeric = ""
        for char in rearranged:
            if char.isalpha():
                numeric += str(ord(char) - ord('A') + 10)
            else:
                numeric += char
        
        # Check MOD 97 = 1
        if int(numeric) % 97 != 1:
            raise ValueError(f"Invalid IBAN checksum: {iban}")
        
        return True
    
    async def _check_compliance(
        self,
        recipient_name: str,
        recipient_bank_bic: str
    ) -> Dict:
        """Check OFAC and sanctions lists"""
        # Simplified compliance check
        # In production, integrate with actual OFAC/sanctions APIs
        
        # Extract country from BIC
        country_code = recipient_bank_bic[4:6]
        
        # Sanctioned countries (simplified list)
        sanctioned_countries = ["IR", "KP", "SY", "CU"]
        
        if country_code in sanctioned_countries:
            return {
                "approved": False,
                "reason": f"Country {country_code} is sanctioned",
                "risk_level": "HIGH"
            }
        
        # Check recipient name against watchlist (simplified)
        watchlist_keywords = ["terrorist", "cartel", "sanctioned"]
        recipient_lower = recipient_name.lower()
        
        for keyword in watchlist_keywords:
            if keyword in recipient_lower:
                return {
                    "approved": False,
                    "reason": "Name matches watchlist",
                    "risk_level": "HIGH"
                }
        
        return {
            "approved": True,
            "risk_level": "LOW"
        }
    
    def _generate_signature(self, message: str) -> str:
        """Generate HMAC signature for message"""
        signature = hmac.new(
            self.api_secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def _calculate_fee(self, amount: Decimal, currency: str) -> Decimal:
        """Calculate SWIFT transfer fee"""
        # Base fee: 0.5% - 1.0% depending on amount
        if amount < Decimal("1000"):
            rate = Decimal("0.01")  # 1.0%
        elif amount < Decimal("10000"):
            rate = Decimal("0.0075")  # 0.75%
        else:
            rate = Decimal("0.005")  # 0.5%
        
        fee = amount * rate
        
        # Minimum fee: $15
        min_fee = Decimal("15")
        
        return max(fee, min_fee)
    
    def _estimate_completion_time(self) -> str:
        """Estimate payment completion time"""
        # SWIFT typically takes 1-3 business days
        completion = datetime.now(timezone.utc)
        
        # Add 2 business days (simplified)
        days_to_add = 2
        while days_to_add > 0:
            completion = completion.replace(hour=0, minute=0, second=0, microsecond=0)
            completion = completion + timedelta(days=1)
            # Skip weekends
            if completion.weekday() < 5:  # Monday = 0, Friday = 4
                days_to_add -= 1
        
        return completion.isoformat()
    
    def _map_swift_status(self, swift_status: str) -> str:
        """Map SWIFT status to internal status"""
        status_map = {
            "ACCP": PaymentStatus.PROCESSING.value,  # Accepted
            "ACSC": PaymentStatus.COMPLETED.value,  # Accepted Settlement Completed
            "RJCT": PaymentStatus.FAILED.value,  # Rejected
            "CANC": PaymentStatus.CANCELLED.value,  # Cancelled
            "PDNG": PaymentStatus.PENDING.value  # Pending
        }
        
        return status_map.get(swift_status, PaymentStatus.PROCESSING.value)


# Import for timedelta
from datetime import timedelta
