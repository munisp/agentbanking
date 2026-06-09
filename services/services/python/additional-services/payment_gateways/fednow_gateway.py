"""
FedNow Gateway Implementation
Federal Reserve Instant Payment Service

Coverage: United States
Currency: USD
Settlement: < 1 second (real-time gross settlement)
Protocol: ISO 20022 messaging
"""

import asyncio
import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Dict, Optional, List
from dataclasses import dataclass, asdict

import httpx
from httpx import AsyncClient, Response


class FedNowStatus(Enum):
    """FedNow payment status codes"""
    PENDING = "PDNG"
    ACCEPTED = "ACCP"
    COMPLETED = "ACSC"
    REJECTED = "RJCT"
    FAILED = "FAIL"
    CANCELLED = "CANC"


class FedNowErrorCode(Enum):
    """FedNow error codes"""
    INVALID_ROUTING = "AC01"  # Invalid routing number
    INVALID_ACCOUNT = "AC04"  # Closed account
    INSUFFICIENT_FUNDS = "AM04"  # Insufficient funds
    AMOUNT_EXCEEDS_LIMIT = "AM09"  # Amount exceeds limit
    INVALID_CREDITOR = "BE05"  # Invalid creditor
    TIMEOUT = "AB03"  # Timeout
    DUPLICATE = "DUPL"  # Duplicate transaction
    SYSTEM_ERROR = "ED05"  # System error


@dataclass
class FedNowPayment:
    """FedNow payment data structure"""
    payment_id: str
    message_id: str
    amount: Decimal
    currency: str
    debtor_routing: str
    debtor_account: str
    debtor_name: str
    creditor_routing: str
    creditor_account: str
    creditor_name: str
    remittance_info: Optional[str] = None
    end_to_end_id: Optional[str] = None
    status: str = FedNowStatus.PENDING.value
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class FedNowGateway:
    """
    FedNow (Federal Reserve Instant Payments) Gateway
    
    Real-time gross settlement system for US domestic payments.
    Supports instant payments 24/7/365 with ISO 20022 messaging.
    
    Features:
    - Real-time payment processing (< 1 second)
    - ISO 20022 pacs.008 message format
    - Routing number validation
    - Transaction limits up to $500,000
    - Comprehensive error handling
    - Automatic retries with exponential backoff
    """
    
    # FedNow API endpoints
    BASE_URL_PROD = "https://api.fednow.gov/v1"
    BASE_URL_SANDBOX = "https://sandbox.fednow.gov/v1"
    
    # Transaction limits
    MAX_TRANSACTION_AMOUNT = Decimal("500000.00")
    MIN_TRANSACTION_AMOUNT = Decimal("0.01")
    
    # Fee structure
    TRANSACTION_FEE = Decimal("0.045")  # $0.045 per transaction
    
    # Retry configuration
    MAX_RETRIES = 3
    RETRY_DELAY = 1  # seconds
    RETRY_BACKOFF = 2  # exponential backoff multiplier
    
    def __init__(
        self,
        routing_number: str,
        account_number: str,
        participant_id: str,
        api_key: str,
        api_secret: str,
        use_sandbox: bool = False,
        timeout: int = 30
    ):
        """
        Initialize FedNow gateway
        
        Args:
            routing_number: Institution's ABA routing number (9 digits)
            account_number: Institution's account number
            participant_id: FedNow participant identifier
            api_key: API key for authentication
            api_secret: API secret for request signing
            use_sandbox: Use sandbox environment for testing
            timeout: Request timeout in seconds
        """
        self.routing_number = routing_number
        self.account_number = account_number
        self.participant_id = participant_id
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = self.BASE_URL_SANDBOX if use_sandbox else self.BASE_URL_PROD
        self.timeout = timeout
        
        # Validate routing number
        if not self._validate_routing_number(routing_number):
            raise ValueError(f"Invalid routing number: {routing_number}")
        
        # HTTP client
        self.client: Optional[AsyncClient] = None
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.client = AsyncClient(timeout=self.timeout)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.client:
            await self.client.aclose()
    
    def _validate_routing_number(self, routing_number: str) -> bool:
        """
        Validate ABA routing number using checksum algorithm
        
        The routing number checksum is calculated as:
        3(d1 + d4 + d7) + 7(d2 + d5 + d8) + (d3 + d6 + d9) mod 10 = 0
        
        Args:
            routing_number: 9-digit routing number
            
        Returns:
            True if valid, False otherwise
        """
        if not routing_number or len(routing_number) != 9:
            return False
        
        if not routing_number.isdigit():
            return False
        
        # Calculate checksum
        digits = [int(d) for d in routing_number]
        checksum = (
            3 * (digits[0] + digits[3] + digits[6]) +
            7 * (digits[1] + digits[4] + digits[7]) +
            (digits[2] + digits[5] + digits[8])
        ) % 10
        
        return checksum == 0
    
    def _generate_message_id(self) -> str:
        """Generate unique message ID for ISO 20022"""
        return f"FEDNOW{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:8].upper()}"
    
    def _generate_signature(self, payload: str, timestamp: str) -> str:
        """
        Generate HMAC-SHA256 signature for request authentication
        
        Args:
            payload: JSON payload as string
            timestamp: ISO 8601 timestamp
            
        Returns:
            Base64-encoded signature
        """
        message = f"{timestamp}:{payload}"
        signature = hmac.new(
            self.api_secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def _build_iso20022_message(self, payment: FedNowPayment) -> Dict:
        """
        Build ISO 20022 pacs.008 message (FIToFICstmrCdtTrf)
        
        This is the Financial Institution to Financial Institution
        Customer Credit Transfer message format.
        
        Args:
            payment: Payment data
            
        Returns:
            ISO 20022 message as dictionary
        """
        now = datetime.now(timezone.utc)
        
        message = {
            "FIToFICstmrCdtTrf": {
                "GrpHdr": {
                    "MsgId": payment.message_id,
                    "CreDtTm": now.isoformat(),
                    "NbOfTxs": "1",
                    "SttlmInf": {
                        "SttlmMtd": "CLRG",
                        "ClrSys": {
                            "Cd": "FDW"  # FedNow code
                        }
                    },
                    "InstgAgt": {
                        "FinInstnId": {
                            "ClrSysMmbId": {
                                "MmbId": self.participant_id
                            }
                        }
                    }
                },
                "CdtTrfTxInf": {
                    "PmtId": {
                        "InstrId": payment.payment_id,
                        "EndToEndId": payment.end_to_end_id or payment.payment_id
                    },
                    "IntrBkSttlmAmt": {
                        "Ccy": payment.currency,
                        "Value": str(payment.amount)
                    },
                    "IntrBkSttlmDt": now.date().isoformat(),
                    "ChrgBr": "SLEV",  # Service level
                    "Dbtr": {
                        "Nm": payment.debtor_name,
                        "Id": {
                            "OrgId": {
                                "Othr": {
                                    "Id": payment.debtor_account
                                }
                            }
                        }
                    },
                    "DbtrAcct": {
                        "Id": {
                            "Othr": {
                                "Id": payment.debtor_account
                            }
                        }
                    },
                    "DbtrAgt": {
                        "FinInstnId": {
                            "ClrSysMmbId": {
                                "MmbId": payment.debtor_routing
                            }
                        }
                    },
                    "CdtrAgt": {
                        "FinInstnId": {
                            "ClrSysMmbId": {
                                "MmbId": payment.creditor_routing
                            }
                        }
                    },
                    "Cdtr": {
                        "Nm": payment.creditor_name,
                        "Id": {
                            "OrgId": {
                                "Othr": {
                                    "Id": payment.creditor_account
                                }
                            }
                        }
                    },
                    "CdtrAcct": {
                        "Id": {
                            "Othr": {
                                "Id": payment.creditor_account
                            }
                        }
                    }
                }
            }
        }
        
        # Add remittance information if provided
        if payment.remittance_info:
            message["FIToFICstmrCdtTrf"]["CdtTrfTxInf"]["RmtInf"] = {
                "Ustrd": payment.remittance_info
            }
        
        return message
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        retry_count: int = 0
    ) -> Response:
        """
        Make authenticated HTTP request to FedNow API
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            data: Request payload
            retry_count: Current retry attempt
            
        Returns:
            HTTP response
            
        Raises:
            httpx.HTTPError: On request failure after retries
        """
        if not self.client:
            raise RuntimeError("Gateway not initialized. Use async context manager.")
        
        url = f"{self.base_url}{endpoint}"
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Prepare payload
        payload = json.dumps(data) if data else ""
        signature = self._generate_signature(payload, timestamp)
        
        # Headers
        headers = {
            "Content-Type": "application/json",
            "X-FedNow-API-Key": self.api_key,
            "X-FedNow-Timestamp": timestamp,
            "X-FedNow-Signature": signature,
            "X-FedNow-Participant-ID": self.participant_id
        }
        
        try:
            response = await self.client.request(
                method=method,
                url=url,
                json=data,
                headers=headers
            )
            response.raise_for_status()
            return response
            
        except httpx.HTTPError as e:
            # Retry logic for transient errors
            if retry_count < self.MAX_RETRIES:
                if isinstance(e, (httpx.TimeoutException, httpx.NetworkError)):
                    delay = self.RETRY_DELAY * (self.RETRY_BACKOFF ** retry_count)
                    await asyncio.sleep(delay)
                    return await self._make_request(method, endpoint, data, retry_count + 1)
            raise
    
    async def initiate_payment(
        self,
        amount: Decimal,
        creditor_routing: str,
        creditor_account: str,
        creditor_name: str,
        remittance_info: Optional[str] = None,
        end_to_end_id: Optional[str] = None
    ) -> FedNowPayment:
        """
        Initiate a FedNow payment
        
        Args:
            amount: Payment amount in USD
            creditor_routing: Recipient's routing number
            creditor_account: Recipient's account number
            creditor_name: Recipient's name
            remittance_info: Optional payment description
            end_to_end_id: Optional end-to-end reference
            
        Returns:
            FedNowPayment object with payment details
            
        Raises:
            ValueError: If payment parameters are invalid
            httpx.HTTPError: If API request fails
        """
        # Validate amount
        if amount < self.MIN_TRANSACTION_AMOUNT:
            raise ValueError(f"Amount below minimum: {amount} < {self.MIN_TRANSACTION_AMOUNT}")
        
        if amount > self.MAX_TRANSACTION_AMOUNT:
            raise ValueError(f"Amount exceeds limit: {amount} > {self.MAX_TRANSACTION_AMOUNT}")
        
        # Validate routing number
        if not self._validate_routing_number(creditor_routing):
            raise ValueError(f"Invalid creditor routing number: {creditor_routing}")
        
        # Create payment object
        payment = FedNowPayment(
            payment_id=str(uuid.uuid4()),
            message_id=self._generate_message_id(),
            amount=amount,
            currency="USD",
            debtor_routing=self.routing_number,
            debtor_account=self.account_number,
            debtor_name="Platform Account",  # Would come from config
            creditor_routing=creditor_routing,
            creditor_account=creditor_account,
            creditor_name=creditor_name,
            remittance_info=remittance_info,
            end_to_end_id=end_to_end_id,
            created_at=datetime.now(timezone.utc)
        )
        
        # Build ISO 20022 message
        iso_message = self._build_iso20022_message(payment)
        
        # Submit payment
        response = await self._make_request(
            method="POST",
            endpoint="/payments",
            data=iso_message
        )
        
        # Parse response
        result = response.json()
        payment.status = result.get("status", FedNowStatus.PENDING.value)
        payment.updated_at = datetime.now(timezone.utc)
        
        return payment
    
    async def get_payment_status(self, payment_id: str) -> FedNowPayment:
        """
        Query payment status
        
        Args:
            payment_id: Payment identifier
            
        Returns:
            FedNowPayment object with current status
            
        Raises:
            httpx.HTTPError: If API request fails
        """
        response = await self._make_request(
            method="GET",
            endpoint=f"/payments/{payment_id}"
        )
        
        result = response.json()
        
        # Parse response into FedNowPayment
        payment = FedNowPayment(
            payment_id=result["payment_id"],
            message_id=result["message_id"],
            amount=Decimal(result["amount"]),
            currency=result["currency"],
            debtor_routing=result["debtor_routing"],
            debtor_account=result["debtor_account"],
            debtor_name=result["debtor_name"],
            creditor_routing=result["creditor_routing"],
            creditor_account=result["creditor_account"],
            creditor_name=result["creditor_name"],
            remittance_info=result.get("remittance_info"),
            end_to_end_id=result.get("end_to_end_id"),
            status=result["status"],
            created_at=datetime.fromisoformat(result["created_at"]),
            updated_at=datetime.fromisoformat(result["updated_at"]),
            error_code=result.get("error_code"),
            error_message=result.get("error_message")
        )
        
        return payment
    
    async def handle_callback(self, payload: Dict) -> FedNowPayment:
        """
        Handle FedNow callback/webhook
        
        Args:
            payload: Webhook payload from FedNow
            
        Returns:
            FedNowPayment object with updated status
        """
        # Verify signature (in production)
        # signature = payload.get("signature")
        # if not self._verify_signature(payload, signature):
        #     raise ValueError("Invalid signature")
        
        # Parse callback data
        payment = FedNowPayment(
            payment_id=payload["payment_id"],
            message_id=payload["message_id"],
            amount=Decimal(payload["amount"]),
            currency=payload["currency"],
            debtor_routing=payload["debtor_routing"],
            debtor_account=payload["debtor_account"],
            debtor_name=payload["debtor_name"],
            creditor_routing=payload["creditor_routing"],
            creditor_account=payload["creditor_account"],
            creditor_name=payload["creditor_name"],
            status=payload["status"],
            updated_at=datetime.now(timezone.utc),
            error_code=payload.get("error_code"),
            error_message=payload.get("error_message")
        )
        
        return payment
    
    def get_error_message(self, error_code: str) -> str:
        """
        Get user-friendly error message for FedNow error code
        
        Args:
            error_code: FedNow error code
            
        Returns:
            User-friendly error message
        """
        error_messages = {
            FedNowErrorCode.INVALID_ROUTING.value: "Invalid routing number",
            FedNowErrorCode.INVALID_ACCOUNT.value: "Account is closed or invalid",
            FedNowErrorCode.INSUFFICIENT_FUNDS.value: "Insufficient funds",
            FedNowErrorCode.AMOUNT_EXCEEDS_LIMIT.value: "Amount exceeds transaction limit",
            FedNowErrorCode.INVALID_CREDITOR.value: "Invalid recipient information",
            FedNowErrorCode.TIMEOUT.value: "Request timeout - please try again",
            FedNowErrorCode.DUPLICATE.value: "Duplicate transaction",
            FedNowErrorCode.SYSTEM_ERROR.value: "System error - please contact support"
        }
        
        return error_messages.get(error_code, f"Unknown error: {error_code}")
    
    async def cancel_payment(self, payment_id: str, reason: str) -> bool:
        """
        Cancel a pending payment
        
        Args:
            payment_id: Payment identifier
            reason: Cancellation reason
            
        Returns:
            True if cancelled successfully
            
        Raises:
            httpx.HTTPError: If API request fails
        """
        response = await self._make_request(
            method="POST",
            endpoint=f"/payments/{payment_id}/cancel",
            data={"reason": reason}
        )
        
        result = response.json()
        return result.get("status") == FedNowStatus.CANCELLED.value
