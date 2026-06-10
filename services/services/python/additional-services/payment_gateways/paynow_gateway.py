"""
PayNow Gateway Implementation
Singapore Fast And Secure Transfers (FAST)

Coverage: Singapore
Currency: SGD
Settlement: < 1 second
Protocol: FAST messaging
Cross-Border: Linked with PromptPay (Thailand)
"""

import asyncio
import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Dict, Optional, List
from dataclasses import dataclass

import httpx
from httpx import AsyncClient, Response


class ProxyType(Enum):
    """PayNow proxy types"""
    MOBILE = "MOBILE"  # Mobile number (+65XXXXXXXX)
    NRIC = "NRIC"  # National Registration Identity Card
    FIN = "FIN"  # Foreign Identification Number
    UEN = "UEN"  # Unique Entity Number (business)
    VPA = "VPA"  # Virtual Payment Address


class PayNowStatus(Enum):
    """PayNow payment status codes"""
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


@dataclass
class ProxyInfo:
    """Proxy lookup result"""
    proxy_type: str
    proxy_value: str
    participant_id: str
    account_number: str
    account_name: str
    bank_code: str
    is_active: bool


@dataclass
class PayNowPayment:
    """PayNow payment data structure"""
    payment_id: str
    transaction_id: str
    amount: Decimal
    currency: str
    sender_proxy_type: Optional[str]
    sender_proxy_value: Optional[str]
    sender_account: str
    sender_name: str
    recipient_proxy_type: str
    recipient_proxy_value: str
    recipient_account: Optional[str]
    recipient_name: Optional[str]
    reference: Optional[str]
    status: str = PayNowStatus.PENDING.value
    is_cross_border: bool = False
    destination_country: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class PayNowGateway:
    """
    PayNow (Singapore Instant Payments) Gateway
    
    Mobile-first instant payment system with proxy support.
    Supports payments via mobile number, NRIC/FIN, UEN, and VPA.
    Cross-border payments to Thailand via PayNow-PromptPay linkage.
    
    Features:
    - Real-time payment processing (< 1 second)
    - Proxy lookup (mobile, NRIC, FIN, UEN, VPA)
    - Cross-border to Thailand (PromptPay)
    - QR code generation
    - Free for consumers
    - 24/7/365 availability
    """
    
    # PayNow API endpoints
    BASE_URL_PROD = "https://api.paynow.sg/v1"
    BASE_URL_SANDBOX = "https://sandbox.paynow.sg/v1"
    
    # Transaction limits
    MAX_TRANSACTION_AMOUNT = Decimal("200000.00")  # SGD 200,000
    MIN_TRANSACTION_AMOUNT = Decimal("0.01")
    
    # Fee structure
    CONSUMER_FEE = Decimal("0.00")  # Free for consumers
    BUSINESS_FEE_RATE = Decimal("0.001")  # 0.1% for businesses
    
    # Cross-border
    CROSS_BORDER_COUNTRIES = ["TH"]  # Thailand via PromptPay
    
    # Retry configuration
    MAX_RETRIES = 3
    RETRY_DELAY = 1
    RETRY_BACKOFF = 2
    
    def __init__(
        self,
        participant_id: str,
        participant_bic: str,
        api_key: str,
        api_secret: str,
        account_number: str,
        use_sandbox: bool = False,
        timeout: int = 30
    ):
        """
        Initialize PayNow gateway
        
        Args:
            participant_id: FAST participant identifier
            participant_bic: Bank Identifier Code
            api_key: API key for authentication
            api_secret: API secret for signing
            account_number: Institution's account number
            use_sandbox: Use sandbox environment
            timeout: Request timeout in seconds
        """
        self.participant_id = participant_id
        self.participant_bic = participant_bic
        self.api_key = api_key
        self.api_secret = api_secret
        self.account_number = account_number
        self.base_url = self.BASE_URL_SANDBOX if use_sandbox else self.BASE_URL_PROD
        self.timeout = timeout
        
        # HTTP client
        self.client: Optional[AsyncClient] = None
        
        # Proxy cache (24 hour TTL)
        self._proxy_cache: Dict[str, tuple[ProxyInfo, datetime]] = {}
        self._cache_ttl = 86400  # 24 hours in seconds
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.client = AsyncClient(timeout=self.timeout)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.client:
            await self.client.aclose()
    
    def validate_mobile_number(self, mobile: str) -> bool:
        """
        Validate Singapore mobile number
        
        Format: +65XXXXXXXX (8 or 9 digits after +65)
        Valid prefixes: 8, 9 (8 digits) or 3 (9 digits for newer numbers)
        
        Args:
            mobile: Mobile number to validate
            
        Returns:
            True if valid
        """
        # Remove spaces and dashes
        mobile = mobile.replace(" ", "").replace("-", "")
        
        # Check format
        if not mobile.startswith("+65"):
            return False
        
        number = mobile[3:]  # Remove +65
        
        # Check length and prefix
        if len(number) == 8 and number[0] in ["8", "9"]:
            return number.isdigit()
        elif len(number) == 9 and number[0] == "3":
            return number.isdigit()
        
        return False
    
    def validate_nric(self, nric: str) -> bool:
        """
        Validate Singapore NRIC/FIN
        
        Format: S/T/F/G + 7 digits + checksum letter
        S/T: Singapore Citizens and PRs (born before/after 2000)
        F/G: Foreigners (issued before/after 2000)
        
        Args:
            nric: NRIC/FIN to validate
            
        Returns:
            True if valid
        """
        if not nric or len(nric) != 9:
            return False
        
        nric = nric.upper()
        
        # Check format
        if nric[0] not in ["S", "T", "F", "G"]:
            return False
        
        if not nric[1:8].isdigit():
            return False
        
        # Validate checksum
        weights = [2, 7, 6, 5, 4, 3, 2]
        digits = [int(d) for d in nric[1:8]]
        
        total = sum(w * d for w, d in zip(weights, digits))
        
        # Add offset for T/G
        if nric[0] in ["T", "G"]:
            total += 4
        
        checksum_letters_st = "JZIHGFEDCBA"
        checksum_letters_fg = "XWUTRQPNMLK"
        
        checksum_index = total % 11
        
        if nric[0] in ["S", "T"]:
            expected = checksum_letters_st[checksum_index]
        else:
            expected = checksum_letters_fg[checksum_index]
        
        return nric[8] == expected
    
    def _get_cached_proxy(self, proxy_key: str) -> Optional[ProxyInfo]:
        """Get proxy info from cache if not expired"""
        if proxy_key in self._proxy_cache:
            info, cached_at = self._proxy_cache[proxy_key]
            age = (datetime.now(timezone.utc) - cached_at).total_seconds()
            if age < self._cache_ttl:
                return info
            else:
                del self._proxy_cache[proxy_key]
        return None
    
    def _cache_proxy(self, proxy_key: str, info: ProxyInfo):
        """Cache proxy info"""
        self._proxy_cache[proxy_key] = (info, datetime.now(timezone.utc))
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        retry_count: int = 0
    ) -> Response:
        """Make authenticated HTTP request to PayNow API"""
        if not self.client:
            raise RuntimeError("Gateway not initialized. Use async context manager.")
        
        url = f"{self.base_url}{endpoint}"
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Generate signature
        payload = json.dumps(data) if data else ""
        signature = hashlib.sha256(
            f"{timestamp}:{payload}:{self.api_secret}".encode()
        ).hexdigest()
        
        headers = {
            "Content-Type": "application/json",
            "X-PayNow-API-Key": self.api_key,
            "X-PayNow-Timestamp": timestamp,
            "X-PayNow-Signature": signature,
            "X-PayNow-Participant-ID": self.participant_id
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
            if retry_count < self.MAX_RETRIES:
                if isinstance(e, (httpx.TimeoutException, httpx.NetworkError)):
                    delay = self.RETRY_DELAY * (self.RETRY_BACKOFF ** retry_count)
                    await asyncio.sleep(delay)
                    return await self._make_request(method, endpoint, data, retry_count + 1)
            raise
    
    async def lookup_proxy(
        self,
        proxy_type: ProxyType,
        proxy_value: str
    ) -> ProxyInfo:
        """
        Lookup PayNow proxy to get account details
        
        Args:
            proxy_type: Type of proxy (MOBILE, NRIC, etc.)
            proxy_value: Proxy value
            
        Returns:
            ProxyInfo with account details
            
        Raises:
            ValueError: If proxy is invalid
            httpx.HTTPError: If API request fails
        """
        # Validate proxy format
        if proxy_type == ProxyType.MOBILE:
            if not self.validate_mobile_number(proxy_value):
                raise ValueError(f"Invalid mobile number: {proxy_value}")
        elif proxy_type in [ProxyType.NRIC, ProxyType.FIN]:
            if not self.validate_nric(proxy_value):
                raise ValueError(f"Invalid NRIC/FIN: {proxy_value}")
        
        # Check cache
        cache_key = f"{proxy_type.value}:{proxy_value}"
        cached = self._get_cached_proxy(cache_key)
        if cached:
            return cached
        
        # Query proxy directory
        response = await self._make_request(
            method="POST",
            endpoint="/proxy/lookup",
            data={
                "proxy_type": proxy_type.value,
                "proxy_value": proxy_value
            }
        )
        
        result = response.json()
        
        proxy_info = ProxyInfo(
            proxy_type=result["proxy_type"],
            proxy_value=result["proxy_value"],
            participant_id=result["participant_id"],
            account_number=result["account_number"],
            account_name=result["account_name"],
            bank_code=result["bank_code"],
            is_active=result["is_active"]
        )
        
        # Cache result
        self._cache_proxy(cache_key, proxy_info)
        
        return proxy_info
    
    async def initiate_payment(
        self,
        amount: Decimal,
        recipient_proxy_type: ProxyType,
        recipient_proxy_value: str,
        reference: Optional[str] = None,
        sender_proxy_type: Optional[ProxyType] = None,
        sender_proxy_value: Optional[str] = None
    ) -> PayNowPayment:
        """
        Initiate a PayNow payment
        
        Args:
            amount: Payment amount in SGD
            recipient_proxy_type: Recipient proxy type
            recipient_proxy_value: Recipient proxy value
            reference: Optional payment reference
            sender_proxy_type: Optional sender proxy type
            sender_proxy_value: Optional sender proxy value
            
        Returns:
            PayNowPayment object
            
        Raises:
            ValueError: If parameters are invalid
            httpx.HTTPError: If API request fails
        """
        # Validate amount
        if amount < self.MIN_TRANSACTION_AMOUNT:
            raise ValueError(f"Amount below minimum: {amount}")
        
        if amount > self.MAX_TRANSACTION_AMOUNT:
            raise ValueError(f"Amount exceeds limit: {amount}")
        
        # Lookup recipient proxy
        recipient_info = await self.lookup_proxy(recipient_proxy_type, recipient_proxy_value)
        
        if not recipient_info.is_active:
            raise ValueError("Recipient proxy is not active")
        
        # Create payment
        payment = PayNowPayment(
            payment_id=str(uuid.uuid4()),
            transaction_id=f"PN{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}",
            amount=amount,
            currency="SGD",
            sender_proxy_type=sender_proxy_type.value if sender_proxy_type else None,
            sender_proxy_value=sender_proxy_value,
            sender_account=self.account_number,
            sender_name="Platform Account",
            recipient_proxy_type=recipient_proxy_type.value,
            recipient_proxy_value=recipient_proxy_value,
            recipient_account=recipient_info.account_number,
            recipient_name=recipient_info.account_name,
            reference=reference,
            created_at=datetime.now(timezone.utc)
        )
        
        # Submit payment
        response = await self._make_request(
            method="POST",
            endpoint="/payments",
            data={
                "transaction_id": payment.transaction_id,
                "amount": str(payment.amount),
                "currency": payment.currency,
                "sender_account": payment.sender_account,
                "recipient_proxy_type": payment.recipient_proxy_type,
                "recipient_proxy_value": payment.recipient_proxy_value,
                "recipient_account": payment.recipient_account,
                "reference": payment.reference
            }
        )
        
        result = response.json()
        payment.status = result.get("status", PayNowStatus.PENDING.value)
        payment.updated_at = datetime.now(timezone.utc)
        
        return payment
    
    async def initiate_cross_border_payment(
        self,
        amount: Decimal,
        recipient_country: str,
        recipient_mobile: str,
        currency: str = "SGD",
        reference: Optional[str] = None
    ) -> PayNowPayment:
        """
        Initiate cross-border payment via PayNow-PromptPay linkage
        
        Currently supports Singapore to Thailand only.
        
        Args:
            amount: Payment amount
            recipient_country: Destination country code (TH)
            recipient_mobile: Recipient mobile number
            currency: Currency (SGD or THB)
            reference: Optional payment reference
            
        Returns:
            PayNowPayment object
            
        Raises:
            ValueError: If country not supported or parameters invalid
            httpx.HTTPError: If API request fails
        """
        if recipient_country not in self.CROSS_BORDER_COUNTRIES:
            raise ValueError(f"Cross-border not supported for: {recipient_country}")
        
        if currency not in ["SGD", "THB"]:
            raise ValueError(f"Currency not supported: {currency}")
        
        # Validate amount
        if amount < self.MIN_TRANSACTION_AMOUNT:
            raise ValueError(f"Amount below minimum: {amount}")
        
        # Create payment
        payment = PayNowPayment(
            payment_id=str(uuid.uuid4()),
            transaction_id=f"PN{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}",
            amount=amount,
            currency=currency,
            sender_proxy_type=None,
            sender_proxy_value=None,
            sender_account=self.account_number,
            sender_name="Platform Account",
            recipient_proxy_type=ProxyType.MOBILE.value,
            recipient_proxy_value=recipient_mobile,
            recipient_account=None,
            recipient_name=None,
            reference=reference,
            is_cross_border=True,
            destination_country=recipient_country,
            created_at=datetime.now(timezone.utc)
        )
        
        # Submit cross-border payment
        response = await self._make_request(
            method="POST",
            endpoint="/payments/cross-border",
            data={
                "transaction_id": payment.transaction_id,
                "amount": str(payment.amount),
                "currency": payment.currency,
                "sender_account": payment.sender_account,
                "destination_country": recipient_country,
                "recipient_mobile": recipient_mobile,
                "reference": payment.reference
            }
        )
        
        result = response.json()
        payment.status = result.get("status", PayNowStatus.PENDING.value)
        payment.updated_at = datetime.now(timezone.utc)
        
        return payment
    
    async def get_payment_status(self, payment_id: str) -> PayNowPayment:
        """
        Query payment status
        
        Args:
            payment_id: Payment identifier
            
        Returns:
            PayNowPayment object with current status
        """
        response = await self._make_request(
            method="GET",
            endpoint=f"/payments/{payment_id}"
        )
        
        result = response.json()
        
        payment = PayNowPayment(
            payment_id=result["payment_id"],
            transaction_id=result["transaction_id"],
            amount=Decimal(result["amount"]),
            currency=result["currency"],
            sender_proxy_type=result.get("sender_proxy_type"),
            sender_proxy_value=result.get("sender_proxy_value"),
            sender_account=result["sender_account"],
            sender_name=result["sender_name"],
            recipient_proxy_type=result["recipient_proxy_type"],
            recipient_proxy_value=result["recipient_proxy_value"],
            recipient_account=result.get("recipient_account"),
            recipient_name=result.get("recipient_name"),
            reference=result.get("reference"),
            status=result["status"],
            is_cross_border=result.get("is_cross_border", False),
            destination_country=result.get("destination_country"),
            created_at=datetime.fromisoformat(result["created_at"]),
            updated_at=datetime.fromisoformat(result["updated_at"]),
            error_code=result.get("error_code"),
            error_message=result.get("error_message")
        )
        
        return payment
    
    async def handle_callback(self, payload: Dict) -> PayNowPayment:
        """
        Handle PayNow callback/webhook
        
        Args:
            payload: Webhook payload
            
        Returns:
            PayNowPayment object with updated status
        """
        payment = PayNowPayment(
            payment_id=payload["payment_id"],
            transaction_id=payload["transaction_id"],
            amount=Decimal(payload["amount"]),
            currency=payload["currency"],
            sender_proxy_type=payload.get("sender_proxy_type"),
            sender_proxy_value=payload.get("sender_proxy_value"),
            sender_account=payload["sender_account"],
            sender_name=payload["sender_name"],
            recipient_proxy_type=payload["recipient_proxy_type"],
            recipient_proxy_value=payload["recipient_proxy_value"],
            recipient_account=payload.get("recipient_account"),
            recipient_name=payload.get("recipient_name"),
            reference=payload.get("reference"),
            status=payload["status"],
            is_cross_border=payload.get("is_cross_border", False),
            destination_country=payload.get("destination_country"),
            updated_at=datetime.now(timezone.utc),
            error_code=payload.get("error_code"),
            error_message=payload.get("error_message")
        )
        
        return payment
    
    def generate_qr_code(
        self,
        proxy_type: ProxyType,
        proxy_value: str,
        amount: Optional[Decimal] = None,
        reference: Optional[str] = None
    ) -> str:
        """
        Generate PayNow QR code data
        
        Returns EMVCo-compliant QR code string that can be encoded
        to QR image using standard QR libraries.
        
        Args:
            proxy_type: Proxy type
            proxy_value: Proxy value
            amount: Optional fixed amount
            reference: Optional reference
            
        Returns:
            QR code data string
        """
        # EMVCo QR code format for PayNow
        qr_data = {
            "00": "01",  # Payload Format Indicator
            "01": "12",  # Point of Initiation Method (12 = static, 11 = dynamic)
            "26": {  # Merchant Account Information
                "00": "SG.PAYNOW",
                "01": "2",  # Proxy type code
                "02": proxy_value,  # Proxy value
                "03": "1" if amount else "0"  # Editable amount
            },
            "52": "0000",  # Merchant Category Code
            "53": "702",  # Transaction Currency (SGD)
            "58": "SG",  # Country Code
            "59": "PayNow",  # Merchant Name
            "60": "Singapore"  # Merchant City
        }
        
        if amount:
            qr_data["54"] = str(amount)  # Transaction Amount
        
        if reference:
            qr_data["62"] = {"01": reference}  # Additional Data
        
        # Serialize to EMVCo format
        # (Simplified - real implementation would follow full EMVCo spec)
        qr_string = json.dumps(qr_data)
        
        return qr_string
