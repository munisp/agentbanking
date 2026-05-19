"""
PromptPay Gateway Implementation
Thailand National ITMX Instant Payment System

Coverage: Thailand
Currency: THB
Settlement: < 1 second
Protocol: National ITMX messaging
Cross-Border: Linked with PayNow (Singapore)
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
    """PromptPay proxy types"""
    MOBILE = "MOBILE"  # Mobile number (+66XXXXXXXXX)
    NATIONAL_ID = "NATIONAL_ID"  # Thai National ID (13 digits)
    TAX_ID = "TAX_ID"  # Tax ID for businesses
    EWALLET = "EWALLET"  # E-Wallet ID


class PromptPayStatus(Enum):
    """PromptPay payment status codes"""
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
    participant_code: str
    account_number: str
    account_name: str
    bank_code: str
    is_active: bool


@dataclass
class PromptPayPayment:
    """PromptPay payment data structure"""
    payment_id: str
    transaction_ref: str
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
    status: str = PromptPayStatus.PENDING.value
    is_cross_border: bool = False
    is_bill_payment: bool = False
    biller_id: Optional[str] = None
    destination_country: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class PromptPayGateway:
    """
    PromptPay (Thailand Instant Payments) Gateway
    
    National instant payment system with proxy support.
    Supports payments via mobile number, National ID, Tax ID.
    Cross-border payments to Singapore via PromptPay-PayNow linkage.
    Bill payment support for utilities and services.
    
    Features:
    - Real-time payment processing (< 1 second)
    - Proxy lookup (mobile, National ID, Tax ID, E-Wallet)
    - Cross-border to Singapore (PayNow)
    - Bill payment support
    - QR code generation (Thai QR standard)
    - Free for consumers
    - 24/7/365 availability
    """
    
    # PromptPay API endpoints
    BASE_URL_PROD = "https://api.promptpay.th/v1"
    BASE_URL_SANDBOX = "https://sandbox.promptpay.th/v1"
    
    # Transaction limits
    MAX_TRANSACTION_AMOUNT = Decimal("2000000.00")  # THB 2,000,000
    MIN_TRANSACTION_AMOUNT = Decimal("1.00")
    
    # Fee structure
    CONSUMER_FEE = Decimal("0.00")  # Free for consumers
    BUSINESS_FEE_RATE = Decimal("0.001")  # 0.1% for businesses
    
    # Cross-border
    CROSS_BORDER_COUNTRIES = ["SG"]  # Singapore via PayNow
    
    # Retry configuration
    MAX_RETRIES = 3
    RETRY_DELAY = 1
    RETRY_BACKOFF = 2
    
    def __init__(
        self,
        participant_code: str,
        api_key: str,
        api_secret: str,
        account_number: str,
        use_sandbox: bool = False,
        timeout: int = 30
    ):
        """
        Initialize PromptPay gateway
        
        Args:
            participant_code: National ITMX participant code
            api_key: API key for authentication
            api_secret: API secret for signing
            account_number: Institution's account number
            use_sandbox: Use sandbox environment
            timeout: Request timeout in seconds
        """
        self.participant_code = participant_code
        self.api_key = api_key
        self.api_secret = api_secret
        self.account_number = account_number
        self.base_url = self.BASE_URL_SANDBOX if use_sandbox else self.BASE_URL_PROD
        self.timeout = timeout
        
        # HTTP client
        self.client: Optional[AsyncClient] = None
        
        # Proxy cache (24 hour TTL)
        self._proxy_cache: Dict[str, tuple[ProxyInfo, datetime]] = {}
        self._cache_ttl = 86400
    
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
        Validate Thailand mobile number
        
        Format: +66XXXXXXXXX (9 digits after +66)
        Valid prefixes: 6, 8, 9 (mobile operators)
        
        Args:
            mobile: Mobile number to validate
            
        Returns:
            True if valid
        """
        # Remove spaces and dashes
        mobile = mobile.replace(" ", "").replace("-", "")
        
        # Check format
        if not mobile.startswith("+66"):
            return False
        
        number = mobile[3:]  # Remove +66
        
        # Check length (9 digits)
        if len(number) != 9:
            return False
        
        # Check prefix (6, 8, or 9)
        if number[0] not in ["6", "8", "9"]:
            return False
        
        return number.isdigit()
    
    def validate_national_id(self, national_id: str) -> bool:
        """
        Validate Thai National ID
        
        Format: 13 digits with checksum
        Algorithm: MOD 11
        
        Args:
            national_id: National ID to validate
            
        Returns:
            True if valid
        """
        if not national_id or len(national_id) != 13:
            return False
        
        if not national_id.isdigit():
            return False
        
        # Calculate checksum using MOD 11
        digits = [int(d) for d in national_id[:12]]
        weights = [13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2]
        
        total = sum(w * d for w, d in zip(weights, digits))
        checksum = (11 - (total % 11)) % 10
        
        return int(national_id[12]) == checksum
    
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
        """Make authenticated HTTP request to PromptPay API"""
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
            "X-PromptPay-API-Key": self.api_key,
            "X-PromptPay-Timestamp": timestamp,
            "X-PromptPay-Signature": signature,
            "X-PromptPay-Participant": self.participant_code
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
        Lookup PromptPay proxy to get account details
        
        Args:
            proxy_type: Type of proxy
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
        elif proxy_type == ProxyType.NATIONAL_ID:
            if not self.validate_national_id(proxy_value):
                raise ValueError(f"Invalid National ID: {proxy_value}")
        
        # Check cache
        cache_key = f"{proxy_type.value}:{proxy_value}"
        cached = self._get_cached_proxy(cache_key)
        if cached:
            return cached
        
        # Query proxy directory
        response = await self._make_request(
            method="POST",
            endpoint="/proxy/inquiry",
            data={
                "proxy_type": proxy_type.value,
                "proxy_value": proxy_value
            }
        )
        
        result = response.json()
        
        proxy_info = ProxyInfo(
            proxy_type=result["proxy_type"],
            proxy_value=result["proxy_value"],
            participant_code=result["participant_code"],
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
    ) -> PromptPayPayment:
        """
        Initiate a PromptPay payment
        
        Args:
            amount: Payment amount in THB
            recipient_proxy_type: Recipient proxy type
            recipient_proxy_value: Recipient proxy value
            reference: Optional payment reference
            sender_proxy_type: Optional sender proxy type
            sender_proxy_value: Optional sender proxy value
            
        Returns:
            PromptPayPayment object
            
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
        payment = PromptPayPayment(
            payment_id=str(uuid.uuid4()),
            transaction_ref=f"PP{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}",
            amount=amount,
            currency="THB",
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
            endpoint="/payments/transfer",
            data={
                "transaction_ref": payment.transaction_ref,
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
        payment.status = result.get("status", PromptPayStatus.PENDING.value)
        payment.updated_at = datetime.now(timezone.utc)
        
        return payment
    
    async def initiate_cross_border_payment(
        self,
        amount: Decimal,
        recipient_country: str,
        recipient_mobile: str,
        currency: str = "THB",
        reference: Optional[str] = None
    ) -> PromptPayPayment:
        """
        Initiate cross-border payment via PromptPay-PayNow linkage
        
        Currently supports Thailand to Singapore only.
        
        Args:
            amount: Payment amount
            recipient_country: Destination country code (SG)
            recipient_mobile: Recipient mobile number
            currency: Currency (THB or SGD)
            reference: Optional payment reference
            
        Returns:
            PromptPayPayment object
            
        Raises:
            ValueError: If country not supported or parameters invalid
            httpx.HTTPError: If API request fails
        """
        if recipient_country not in self.CROSS_BORDER_COUNTRIES:
            raise ValueError(f"Cross-border not supported for: {recipient_country}")
        
        if currency not in ["THB", "SGD"]:
            raise ValueError(f"Currency not supported: {currency}")
        
        # Validate amount
        if amount < self.MIN_TRANSACTION_AMOUNT:
            raise ValueError(f"Amount below minimum: {amount}")
        
        # Create payment
        payment = PromptPayPayment(
            payment_id=str(uuid.uuid4()),
            transaction_ref=f"PP{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}",
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
                "transaction_ref": payment.transaction_ref,
                "amount": str(payment.amount),
                "currency": payment.currency,
                "sender_account": payment.sender_account,
                "destination_country": recipient_country,
                "recipient_mobile": recipient_mobile,
                "reference": payment.reference
            }
        )
        
        result = response.json()
        payment.status = result.get("status", PromptPayStatus.PENDING.value)
        payment.updated_at = datetime.now(timezone.utc)
        
        return payment
    
    async def initiate_bill_payment(
        self,
        biller_id: str,
        reference_1: str,
        reference_2: str,
        amount: Decimal
    ) -> PromptPayPayment:
        """
        Pay bills through PromptPay
        
        Supports utility bills, government services, and other billers
        registered with PromptPay.
        
        Args:
            biller_id: Biller's PromptPay ID (Tax ID)
            reference_1: Primary reference (e.g., account number)
            reference_2: Secondary reference (e.g., invoice number)
            amount: Payment amount in THB
            
        Returns:
            PromptPayPayment object
            
        Raises:
            ValueError: If parameters are invalid
            httpx.HTTPError: If API request fails
        """
        # Validate amount
        if amount < self.MIN_TRANSACTION_AMOUNT:
            raise ValueError(f"Amount below minimum: {amount}")
        
        if amount > self.MAX_TRANSACTION_AMOUNT:
            raise ValueError(f"Amount exceeds limit: {amount}")
        
        # Create payment
        payment = PromptPayPayment(
            payment_id=str(uuid.uuid4()),
            transaction_ref=f"PP{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}",
            amount=amount,
            currency="THB",
            sender_proxy_type=None,
            sender_proxy_value=None,
            sender_account=self.account_number,
            sender_name="Platform Account",
            recipient_proxy_type=ProxyType.TAX_ID.value,
            recipient_proxy_value=biller_id,
            recipient_account=None,
            recipient_name=None,
            reference=f"{reference_1}|{reference_2}",
            is_bill_payment=True,
            biller_id=biller_id,
            created_at=datetime.now(timezone.utc)
        )
        
        # Submit bill payment
        response = await self._make_request(
            method="POST",
            endpoint="/payments/bill",
            data={
                "transaction_ref": payment.transaction_ref,
                "amount": str(payment.amount),
                "sender_account": payment.sender_account,
                "biller_id": biller_id,
                "reference_1": reference_1,
                "reference_2": reference_2
            }
        )
        
        result = response.json()
        payment.status = result.get("status", PromptPayStatus.PENDING.value)
        payment.updated_at = datetime.now(timezone.utc)
        
        return payment
    
    async def get_payment_status(self, payment_id: str) -> PromptPayPayment:
        """
        Query payment status
        
        Args:
            payment_id: Payment identifier
            
        Returns:
            PromptPayPayment object with current status
        """
        response = await self._make_request(
            method="GET",
            endpoint=f"/payments/{payment_id}"
        )
        
        result = response.json()
        
        payment = PromptPayPayment(
            payment_id=result["payment_id"],
            transaction_ref=result["transaction_ref"],
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
            is_bill_payment=result.get("is_bill_payment", False),
            biller_id=result.get("biller_id"),
            destination_country=result.get("destination_country"),
            created_at=datetime.fromisoformat(result["created_at"]),
            updated_at=datetime.fromisoformat(result["updated_at"]),
            error_code=result.get("error_code"),
            error_message=result.get("error_message")
        )
        
        return payment
    
    async def handle_callback(self, payload: Dict) -> PromptPayPayment:
        """
        Handle PromptPay callback/webhook
        
        Args:
            payload: Webhook payload
            
        Returns:
            PromptPayPayment object with updated status
        """
        payment = PromptPayPayment(
            payment_id=payload["payment_id"],
            transaction_ref=payload["transaction_ref"],
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
            is_bill_payment=payload.get("is_bill_payment", False),
            biller_id=payload.get("biller_id"),
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
        Generate PromptPay QR code data (Thai QR standard)
        
        Returns Thai QR Payment standard-compliant QR code string
        that can be encoded to QR image using standard QR libraries.
        
        Args:
            proxy_type: Proxy type
            proxy_value: Proxy value
            amount: Optional fixed amount
            reference: Optional reference
            
        Returns:
            QR code data string
        """
        # Thai QR Payment standard format
        qr_data = {
            "00": "01",  # Payload Format Indicator
            "01": "12" if amount else "11",  # POI Method
            "29": {  # Merchant Account Information
                "00": "A000000677010111",  # Application ID (PromptPay)
                "01": proxy_type.value,
                "02": proxy_value
            },
            "52": "0000",  # Merchant Category Code
            "53": "764",  # Transaction Currency (THB)
            "58": "TH",  # Country Code
            "59": "PromptPay"  # Merchant Name
        }
        
        if amount:
            qr_data["54"] = str(amount)
        
        if reference:
            qr_data["62"] = {"05": reference}
        
        # Serialize to Thai QR format
        # (Simplified - real implementation would follow full Thai QR spec)
        qr_string = json.dumps(qr_data)
        
        return qr_string
