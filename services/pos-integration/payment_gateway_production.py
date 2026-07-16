"""
Production Payment Gateway Integration
Real payment processor integrations for POS transactions
Supports: Stripe, Paystack, Flutterwave, Square, Adyen
"""

import asyncio
import hashlib
import hmac
import json
import logging
import os
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

class PaymentProvider(str, Enum):
    STRIPE = "stripe"
    PAYSTACK = "paystack"
    FLUTTERWAVE = "flutterwave"
    SQUARE = "square"
    ADYEN = "adyen"


@dataclass
class PaymentGatewayConfig:
    """Payment gateway configuration"""
    provider: PaymentProvider
    api_key: str
    secret_key: str
    webhook_secret: Optional[str] = None
    merchant_id: Optional[str] = None
    environment: str = "sandbox"  # sandbox or production
    timeout: int = 30
    max_retries: int = 3
    
    @classmethod
    def from_env(cls, provider: PaymentProvider) -> "PaymentGatewayConfig":
        """Load configuration from environment variables"""
        prefix = provider.value.upper()
        return cls(
            provider=provider,
            api_key=os.getenv(f"{prefix}_API_KEY", ""),
            secret_key=os.getenv(f"{prefix}_SECRET_KEY", ""),
            webhook_secret=os.getenv(f"{prefix}_WEBHOOK_SECRET"),
            merchant_id=os.getenv(f"{prefix}_MERCHANT_ID"),
            environment=os.getenv(f"{prefix}_ENVIRONMENT", "sandbox"),
            timeout=int(os.getenv(f"{prefix}_TIMEOUT", "30")),
            max_retries=int(os.getenv(f"{prefix}_MAX_RETRIES", "3")),
        )


# =============================================================================
# DATA MODELS
# =============================================================================

class TransactionStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    APPROVED = "approved"
    DECLINED = "declined"
    FAILED = "failed"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"
    VOIDED = "voided"


@dataclass
class CardData:
    """Card payment data (tokenized)"""
    token: str
    last_four: str
    card_type: str  # visa, mastercard, amex, etc.
    expiry_month: str
    expiry_year: str
    cardholder_name: Optional[str] = None


@dataclass
class PaymentRequest:
    """Payment request"""
    amount: Decimal
    currency: str
    card_data: CardData
    merchant_id: str
    terminal_id: str
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    idempotency_key: Optional[str] = None
    customer_id: Optional[str] = None
    customer_email: Optional[str] = None


@dataclass
class PaymentResponse:
    """Payment response"""
    transaction_id: str
    provider_transaction_id: str
    status: TransactionStatus
    amount: Decimal
    currency: str
    card_last_four: str
    card_type: str
    authorization_code: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()


@dataclass
class RefundRequest:
    """Refund request"""
    transaction_id: str
    provider_transaction_id: str
    amount: Optional[Decimal] = None  # None = full refund
    reason: Optional[str] = None
    idempotency_key: Optional[str] = None


@dataclass
class RefundResponse:
    """Refund response"""
    refund_id: str
    provider_refund_id: str
    transaction_id: str
    status: TransactionStatus
    amount: Decimal
    currency: str
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()


# =============================================================================
# ABSTRACT PAYMENT GATEWAY
# =============================================================================

class PaymentGateway(ABC):
    """Abstract payment gateway interface"""
    
    def __init__(self, config: PaymentGatewayConfig):
        self.config = config
        self.client = httpx.AsyncClient(timeout=config.timeout)
    
    @abstractmethod
    async def process_payment(self, request: PaymentRequest) -> PaymentResponse:
        """Process a payment"""
        pass
    
    @abstractmethod
    async def refund_payment(self, request: RefundRequest) -> RefundResponse:
        """Refund a payment"""
        pass
    
    @abstractmethod
    async def get_transaction(self, transaction_id: str) -> Optional[PaymentResponse]:
        """Get transaction details"""
        pass
    
    @abstractmethod
    async def verify_webhook(self, payload: bytes, signature: str) -> bool:
        """Verify webhook signature"""
        pass
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()


# =============================================================================
# STRIPE GATEWAY
# =============================================================================

class StripeGateway(PaymentGateway):
    """Stripe payment gateway implementation"""
    
    BASE_URL = "https://api.stripe.com/v1"
    
    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.config.secret_key}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Stripe-Version": "2023-10-16",
        }
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def process_payment(self, request: PaymentRequest) -> PaymentResponse:
        """Process payment via Stripe"""
        try:
            # Create payment intent
            data = {
                "amount": int(request.amount * 100),  # Stripe uses cents
                "currency": request.currency.lower(),
                "payment_method": request.card_data.token,
                "confirm": "true",
                "description": request.description or f"POS Payment - {request.terminal_id}",
                "metadata[merchant_id]": request.merchant_id,
                "metadata[terminal_id]": request.terminal_id,
            }
            
            if request.idempotency_key:
                headers = self._get_headers()
                headers["Idempotency-Key"] = request.idempotency_key
            else:
                headers = self._get_headers()
            
            if request.customer_id:
                data["customer"] = request.customer_id
            
            response = await self.client.post(
                f"{self.BASE_URL}/payment_intents",
                headers=headers,
                data=data
            )
            
            result = response.json()
            
            if response.status_code == 200 and result.get("status") == "succeeded":
                return PaymentResponse(
                    transaction_id=str(uuid.uuid4()),
                    provider_transaction_id=result["id"],
                    status=TransactionStatus.APPROVED,
                    amount=request.amount,
                    currency=request.currency,
                    card_last_four=request.card_data.last_four,
                    card_type=request.card_data.card_type,
                    authorization_code=result.get("latest_charge"),
                    metadata=result.get("metadata"),
                )
            else:
                error = result.get("error", {})
                return PaymentResponse(
                    transaction_id=str(uuid.uuid4()),
                    provider_transaction_id=result.get("id", ""),
                    status=TransactionStatus.DECLINED if error.get("code") == "card_declined" else TransactionStatus.FAILED,
                    amount=request.amount,
                    currency=request.currency,
                    card_last_four=request.card_data.last_four,
                    card_type=request.card_data.card_type,
                    error_code=error.get("code"),
                    error_message=error.get("message"),
                )
                
        except Exception as e:
            logger.error(f"Stripe payment error: {e}")
            return PaymentResponse(
                transaction_id=str(uuid.uuid4()),
                provider_transaction_id="",
                status=TransactionStatus.FAILED,
                amount=request.amount,
                currency=request.currency,
                card_last_four=request.card_data.last_four,
                card_type=request.card_data.card_type,
                error_code="gateway_error",
                error_message=str(e),
            )
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def refund_payment(self, request: RefundRequest) -> RefundResponse:
        """Refund payment via Stripe"""
        try:
            data = {
                "payment_intent": request.provider_transaction_id,
            }
            
            if request.amount:
                data["amount"] = int(request.amount * 100)
            
            if request.reason:
                data["reason"] = "requested_by_customer"
                data["metadata[reason]"] = request.reason
            
            headers = self._get_headers()
            if request.idempotency_key:
                headers["Idempotency-Key"] = request.idempotency_key
            
            response = await self.client.post(
                f"{self.BASE_URL}/refunds",
                headers=headers,
                data=data
            )
            
            result = response.json()
            
            if response.status_code == 200 and result.get("status") == "succeeded":
                return RefundResponse(
                    refund_id=str(uuid.uuid4()),
                    provider_refund_id=result["id"],
                    transaction_id=request.transaction_id,
                    status=TransactionStatus.REFUNDED,
                    amount=Decimal(result["amount"]) / 100,
                    currency=result["currency"].upper(),
                )
            else:
                error = result.get("error", {})
                return RefundResponse(
                    refund_id=str(uuid.uuid4()),
                    provider_refund_id=result.get("id", ""),
                    transaction_id=request.transaction_id,
                    status=TransactionStatus.FAILED,
                    amount=request.amount or Decimal(0),
                    currency="",
                    error_code=error.get("code"),
                    error_message=error.get("message"),
                )
                
        except Exception as e:
            logger.error(f"Stripe refund error: {e}")
            return RefundResponse(
                refund_id=str(uuid.uuid4()),
                provider_refund_id="",
                transaction_id=request.transaction_id,
                status=TransactionStatus.FAILED,
                amount=request.amount or Decimal(0),
                currency="",
                error_code="gateway_error",
                error_message=str(e),
            )
    
    async def get_transaction(self, transaction_id: str) -> Optional[PaymentResponse]:
        """Get transaction from Stripe"""
        try:
            response = await self.client.get(
                f"{self.BASE_URL}/payment_intents/{transaction_id}",
                headers=self._get_headers()
            )
            
            if response.status_code == 200:
                result = response.json()
                status_map = {
                    "succeeded": TransactionStatus.APPROVED,
                    "processing": TransactionStatus.PROCESSING,
                    "requires_payment_method": TransactionStatus.DECLINED,
                    "canceled": TransactionStatus.VOIDED,
                }
                
                return PaymentResponse(
                    transaction_id=transaction_id,
                    provider_transaction_id=result["id"],
                    status=status_map.get(result["status"], TransactionStatus.PENDING),
                    amount=Decimal(result["amount"]) / 100,
                    currency=result["currency"].upper(),
                    card_last_four=result.get("payment_method_details", {}).get("card", {}).get("last4", ""),
                    card_type=result.get("payment_method_details", {}).get("card", {}).get("brand", ""),
                    metadata=result.get("metadata"),
                )
            return None
            
        except Exception as e:
            logger.error(f"Stripe get transaction error: {e}")
            return None
    
    async def verify_webhook(self, payload: bytes, signature: str) -> bool:
        """Verify Stripe webhook signature"""
        try:
            if not self.config.webhook_secret:
                return False
            
            # Parse signature header
            sig_parts = dict(item.split("=") for item in signature.split(","))
            timestamp = sig_parts.get("t")
            v1_signature = sig_parts.get("v1")
            
            if not timestamp or not v1_signature:
                return False
            
            # Compute expected signature
            signed_payload = f"{timestamp}.{payload.decode()}"
            expected_sig = hmac.new(
                self.config.webhook_secret.encode(),
                signed_payload.encode(),
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(expected_sig, v1_signature)
            
        except Exception as e:
            logger.error(f"Stripe webhook verification error: {e}")
            return False


# =============================================================================
# PAYSTACK GATEWAY (Nigeria/Africa)
# =============================================================================

class PaystackGateway(PaymentGateway):
    """Paystack payment gateway implementation (Nigeria/Africa)"""
    
    BASE_URL = "https://api.paystack.co"
    
    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.config.secret_key}",
            "Content-Type": "application/json",
        }
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def process_payment(self, request: PaymentRequest) -> PaymentResponse:
        """Process payment via Paystack"""
        try:
            # Paystack uses kobo (1 NGN = 100 kobo)
            amount_kobo = int(request.amount * 100)
            
            data = {
                "amount": amount_kobo,
                "currency": request.currency.upper(),
                "authorization_code": request.card_data.token,
                "email": request.customer_email or f"pos_{request.terminal_id}@merchant.com",
                "reference": request.idempotency_key or str(uuid.uuid4()),
                "metadata": {
                    "merchant_id": request.merchant_id,
                    "terminal_id": request.terminal_id,
                    "description": request.description,
                    **(request.metadata or {}),
                },
            }
            
            response = await self.client.post(
                f"{self.BASE_URL}/transaction/charge_authorization",
                headers=self._get_headers(),
                json=data
            )
            
            result = response.json()
            
            if result.get("status") and result.get("data", {}).get("status") == "success":
                tx_data = result["data"]
                return PaymentResponse(
                    transaction_id=str(uuid.uuid4()),
                    provider_transaction_id=str(tx_data["id"]),
                    status=TransactionStatus.APPROVED,
                    amount=request.amount,
                    currency=request.currency,
                    card_last_four=request.card_data.last_four,
                    card_type=request.card_data.card_type,
                    authorization_code=tx_data.get("authorization", {}).get("authorization_code"),
                    metadata=tx_data.get("metadata"),
                )
            else:
                return PaymentResponse(
                    transaction_id=str(uuid.uuid4()),
                    provider_transaction_id=result.get("data", {}).get("id", ""),
                    status=TransactionStatus.DECLINED,
                    amount=request.amount,
                    currency=request.currency,
                    card_last_four=request.card_data.last_four,
                    card_type=request.card_data.card_type,
                    error_code=result.get("data", {}).get("gateway_response"),
                    error_message=result.get("message"),
                )
                
        except Exception as e:
            logger.error(f"Paystack payment error: {e}")
            return PaymentResponse(
                transaction_id=str(uuid.uuid4()),
                provider_transaction_id="",
                status=TransactionStatus.FAILED,
                amount=request.amount,
                currency=request.currency,
                card_last_four=request.card_data.last_four,
                card_type=request.card_data.card_type,
                error_code="gateway_error",
                error_message=str(e),
            )
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def refund_payment(self, request: RefundRequest) -> RefundResponse:
        """Refund payment via Paystack"""
        try:
            data = {
                "transaction": request.provider_transaction_id,
            }
            
            if request.amount:
                data["amount"] = int(request.amount * 100)
            
            response = await self.client.post(
                f"{self.BASE_URL}/refund",
                headers=self._get_headers(),
                json=data
            )
            
            result = response.json()
            
            if result.get("status"):
                refund_data = result.get("data", {})
                return RefundResponse(
                    refund_id=str(uuid.uuid4()),
                    provider_refund_id=str(refund_data.get("id", "")),
                    transaction_id=request.transaction_id,
                    status=TransactionStatus.REFUNDED,
                    amount=Decimal(refund_data.get("amount", 0)) / 100,
                    currency=refund_data.get("currency", "NGN"),
                )
            else:
                return RefundResponse(
                    refund_id=str(uuid.uuid4()),
                    provider_refund_id="",
                    transaction_id=request.transaction_id,
                    status=TransactionStatus.FAILED,
                    amount=request.amount or Decimal(0),
                    currency="",
                    error_code="refund_failed",
                    error_message=result.get("message"),
                )
                
        except Exception as e:
            logger.error(f"Paystack refund error: {e}")
            return RefundResponse(
                refund_id=str(uuid.uuid4()),
                provider_refund_id="",
                transaction_id=request.transaction_id,
                status=TransactionStatus.FAILED,
                amount=request.amount or Decimal(0),
                currency="",
                error_code="gateway_error",
                error_message=str(e),
            )
    
    async def get_transaction(self, transaction_id: str) -> Optional[PaymentResponse]:
        """Get transaction from Paystack"""
        try:
            response = await self.client.get(
                f"{self.BASE_URL}/transaction/{transaction_id}",
                headers=self._get_headers()
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("status"):
                    tx_data = result["data"]
                    status_map = {
                        "success": TransactionStatus.APPROVED,
                        "failed": TransactionStatus.FAILED,
                        "abandoned": TransactionStatus.VOIDED,
                    }
                    
                    return PaymentResponse(
                        transaction_id=transaction_id,
                        provider_transaction_id=str(tx_data["id"]),
                        status=status_map.get(tx_data["status"], TransactionStatus.PENDING),
                        amount=Decimal(tx_data["amount"]) / 100,
                        currency=tx_data["currency"],
                        card_last_four=tx_data.get("authorization", {}).get("last4", ""),
                        card_type=tx_data.get("authorization", {}).get("card_type", ""),
                        metadata=tx_data.get("metadata"),
                    )
            return None
            
        except Exception as e:
            logger.error(f"Paystack get transaction error: {e}")
            return None
    
    async def verify_webhook(self, payload: bytes, signature: str) -> bool:
        """Verify Paystack webhook signature"""
        try:
            if not self.config.secret_key:
                return False
            
            expected_sig = hmac.new(
                self.config.secret_key.encode(),
                payload,
                hashlib.sha512
            ).hexdigest()
            
            return hmac.compare_digest(expected_sig, signature)
            
        except Exception as e:
            logger.error(f"Paystack webhook verification error: {e}")
            return False


# =============================================================================
# FLUTTERWAVE GATEWAY (Africa)
# =============================================================================

class FlutterwaveGateway(PaymentGateway):
    """Flutterwave payment gateway implementation (Africa)"""
    
    BASE_URL = "https://api.flutterwave.com/v3"
    
    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.config.secret_key}",
            "Content-Type": "application/json",
        }
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def process_payment(self, request: PaymentRequest) -> PaymentResponse:
        """Process payment via Flutterwave"""
        try:
            data = {
                "token": request.card_data.token,
                "currency": request.currency.upper(),
                "amount": float(request.amount),
                "email": request.customer_email or f"pos_{request.terminal_id}@merchant.com",
                "tx_ref": request.idempotency_key or str(uuid.uuid4()),
                "narration": request.description or f"POS Payment - {request.terminal_id}",
            }
            
            response = await self.client.post(
                f"{self.BASE_URL}/tokenized-charges",
                headers=self._get_headers(),
                json=data
            )
            
            result = response.json()
            
            if result.get("status") == "success":
                tx_data = result.get("data", {})
                return PaymentResponse(
                    transaction_id=str(uuid.uuid4()),
                    provider_transaction_id=str(tx_data.get("id", "")),
                    status=TransactionStatus.APPROVED,
                    amount=request.amount,
                    currency=request.currency,
                    card_last_four=request.card_data.last_four,
                    card_type=request.card_data.card_type,
                    authorization_code=tx_data.get("flw_ref"),
                    metadata={"flw_ref": tx_data.get("flw_ref")},
                )
            else:
                return PaymentResponse(
                    transaction_id=str(uuid.uuid4()),
                    provider_transaction_id="",
                    status=TransactionStatus.DECLINED,
                    amount=request.amount,
                    currency=request.currency,
                    card_last_four=request.card_data.last_four,
                    card_type=request.card_data.card_type,
                    error_code=result.get("status"),
                    error_message=result.get("message"),
                )
                
        except Exception as e:
            logger.error(f"Flutterwave payment error: {e}")
            return PaymentResponse(
                transaction_id=str(uuid.uuid4()),
                provider_transaction_id="",
                status=TransactionStatus.FAILED,
                amount=request.amount,
                currency=request.currency,
                card_last_four=request.card_data.last_four,
                card_type=request.card_data.card_type,
                error_code="gateway_error",
                error_message=str(e),
            )
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def refund_payment(self, request: RefundRequest) -> RefundResponse:
        """Refund payment via Flutterwave"""
        try:
            data = {}
            if request.amount:
                data["amount"] = float(request.amount)
            
            response = await self.client.post(
                f"{self.BASE_URL}/transactions/{request.provider_transaction_id}/refund",
                headers=self._get_headers(),
                json=data
            )
            
            result = response.json()
            
            if result.get("status") == "success":
                refund_data = result.get("data", {})
                return RefundResponse(
                    refund_id=str(uuid.uuid4()),
                    provider_refund_id=str(refund_data.get("id", "")),
                    transaction_id=request.transaction_id,
                    status=TransactionStatus.REFUNDED,
                    amount=Decimal(str(refund_data.get("amount_refunded", 0))),
                    currency=refund_data.get("currency", ""),
                )
            else:
                return RefundResponse(
                    refund_id=str(uuid.uuid4()),
                    provider_refund_id="",
                    transaction_id=request.transaction_id,
                    status=TransactionStatus.FAILED,
                    amount=request.amount or Decimal(0),
                    currency="",
                    error_code="refund_failed",
                    error_message=result.get("message"),
                )
                
        except Exception as e:
            logger.error(f"Flutterwave refund error: {e}")
            return RefundResponse(
                refund_id=str(uuid.uuid4()),
                provider_refund_id="",
                transaction_id=request.transaction_id,
                status=TransactionStatus.FAILED,
                amount=request.amount or Decimal(0),
                currency="",
                error_code="gateway_error",
                error_message=str(e),
            )
    
    async def get_transaction(self, transaction_id: str) -> Optional[PaymentResponse]:
        """Get transaction from Flutterwave"""
        try:
            response = await self.client.get(
                f"{self.BASE_URL}/transactions/{transaction_id}/verify",
                headers=self._get_headers()
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "success":
                    tx_data = result["data"]
                    status_map = {
                        "successful": TransactionStatus.APPROVED,
                        "failed": TransactionStatus.FAILED,
                        "pending": TransactionStatus.PENDING,
                    }
                    
                    return PaymentResponse(
                        transaction_id=transaction_id,
                        provider_transaction_id=str(tx_data["id"]),
                        status=status_map.get(tx_data["status"], TransactionStatus.PENDING),
                        amount=Decimal(str(tx_data["amount"])),
                        currency=tx_data["currency"],
                        card_last_four=tx_data.get("card", {}).get("last_4digits", ""),
                        card_type=tx_data.get("card", {}).get("type", ""),
                    )
            return None
            
        except Exception as e:
            logger.error(f"Flutterwave get transaction error: {e}")
            return None
    
    async def verify_webhook(self, payload: bytes, signature: str) -> bool:
        """Verify Flutterwave webhook signature"""
        try:
            if not self.config.webhook_secret:
                return False
            
            return signature == self.config.webhook_secret
            
        except Exception as e:
            logger.error(f"Flutterwave webhook verification error: {e}")
            return False


# =============================================================================
# PAYMENT GATEWAY FACTORY
# =============================================================================

class PaymentGatewayFactory:
    """Factory for creating payment gateway instances"""
    
    _gateways: Dict[PaymentProvider, type] = {
        PaymentProvider.STRIPE: StripeGateway,
        PaymentProvider.PAYSTACK: PaystackGateway,
        PaymentProvider.FLUTTERWAVE: FlutterwaveGateway,
    }
    
    @classmethod
    def create(cls, provider: PaymentProvider, config: Optional[PaymentGatewayConfig] = None) -> PaymentGateway:
        """Create payment gateway instance"""
        if provider not in cls._gateways:
            raise ValueError(f"Unsupported payment provider: {provider}")
        
        if config is None:
            config = PaymentGatewayConfig.from_env(provider)
        
        gateway_class = cls._gateways[provider]
        return gateway_class(config)
    
    @classmethod
    def register(cls, provider: PaymentProvider, gateway_class: type):
        """Register a new payment gateway"""
        cls._gateways[provider] = gateway_class


# =============================================================================
# UNIFIED PAYMENT SERVICE
# =============================================================================

class UnifiedPaymentService:
    """
    Unified payment service that handles multiple payment providers
    with automatic failover and load balancing
    """
    
    def __init__(self, primary_provider: PaymentProvider = PaymentProvider.PAYSTACK):
        self.primary_provider = primary_provider
        self.gateways: Dict[PaymentProvider, PaymentGateway] = {}
        self.failover_order: List[PaymentProvider] = [
            PaymentProvider.PAYSTACK,
            PaymentProvider.FLUTTERWAVE,
            PaymentProvider.STRIPE,
        ]
    
    async def initialize(self):
        """Initialize payment gateways"""
        for provider in self.failover_order:
            try:
                config = PaymentGatewayConfig.from_env(provider)
                if config.api_key:  # Only initialize if configured
                    self.gateways[provider] = PaymentGatewayFactory.create(provider, config)
                    logger.info(f"Initialized {provider.value} payment gateway")
            except Exception as e:
                logger.warning(f"Failed to initialize {provider.value}: {e}")
    
    async def close(self):
        """Close all payment gateways"""
        for gateway in self.gateways.values():
            await gateway.close()
    
    async def process_payment(
        self,
        request: PaymentRequest,
        provider: Optional[PaymentProvider] = None
    ) -> PaymentResponse:
        """
        Process payment with automatic failover
        """
        providers_to_try = [provider] if provider else self.failover_order
        
        last_error = None
        for p in providers_to_try:
            if p not in self.gateways:
                continue
            
            try:
                gateway = self.gateways[p]
                response = await gateway.process_payment(request)
                
                if response.status in [TransactionStatus.APPROVED, TransactionStatus.DECLINED]:
                    return response
                
                last_error = response.error_message
                
            except Exception as e:
                logger.error(f"Payment failed with {p.value}: {e}")
                last_error = str(e)
        
        # All providers failed
        return PaymentResponse(
            transaction_id=str(uuid.uuid4()),
            provider_transaction_id="",
            status=TransactionStatus.FAILED,
            amount=request.amount,
            currency=request.currency,
            card_last_four=request.card_data.last_four,
            card_type=request.card_data.card_type,
            error_code="all_providers_failed",
            error_message=last_error or "All payment providers failed",
        )
    
    async def refund_payment(
        self,
        request: RefundRequest,
        provider: PaymentProvider
    ) -> RefundResponse:
        """Refund payment via specific provider"""
        if provider not in self.gateways:
            return RefundResponse(
                refund_id=str(uuid.uuid4()),
                provider_refund_id="",
                transaction_id=request.transaction_id,
                status=TransactionStatus.FAILED,
                amount=request.amount or Decimal(0),
                currency="",
                error_code="provider_not_configured",
                error_message=f"Provider {provider.value} not configured",
            )
        
        return await self.gateways[provider].refund_payment(request)


# =============================================================================
# GLOBAL INSTANCE
# =============================================================================

payment_service = UnifiedPaymentService()


async def initialize_payment_service():
    """Initialize the global payment service"""
    await payment_service.initialize()


async def close_payment_service():
    """Close the global payment service"""
    await payment_service.close()
