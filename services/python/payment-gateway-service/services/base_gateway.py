"""
Base Payment Gateway Interface

This module defines the abstract base class for all payment gateway integrations.
All payment gateways must implement this interface to ensure consistency.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from decimal import Decimal
from enum import Enum
from dataclasses import dataclass
from datetime import datetime


class PaymentStatus(str, Enum):
    """Payment transaction status"""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    EXPIRED = "expired"


class TransactionType(str, Enum):
    """Transaction type"""
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    TRANSFER = "transfer"
    REFUND = "refund"


@dataclass
class PaymentRequest:
    """Payment request data"""
    amount: Decimal
    currency: str
    source_currency: str
    destination_currency: str
    sender_id: str
    recipient_id: str
    sender_account: Optional[str] = None
    recipient_account: str = None
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    callback_url: Optional[str] = None
    transaction_type: TransactionType = TransactionType.TRANSFER


@dataclass
class PaymentResponse:
    """Payment response data"""
    success: bool
    transaction_id: str
    gateway_reference: Optional[str] = None
    status: PaymentStatus = PaymentStatus.PENDING
    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    fee: Optional[Decimal] = None
    exchange_rate: Optional[Decimal] = None
    message: Optional[str] = None
    payment_url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None


@dataclass
class RefundRequest:
    """Refund request data"""
    transaction_id: str
    amount: Optional[Decimal] = None  # None means full refund
    reason: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class RefundResponse:
    """Refund response data"""
    success: bool
    refund_id: str
    transaction_id: str
    amount: Decimal
    status: PaymentStatus
    message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class TransactionQuery:
    """Transaction query data"""
    transaction_id: Optional[str] = None
    gateway_reference: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class BasePaymentGateway(ABC):
    """
    Abstract base class for payment gateway integrations.
    
    All payment gateways must implement this interface to ensure
    consistent behavior across different providers.
    """
    
    def __init__(self, config: Dict[str, Any]) -> None:
        """
        Initialize the payment gateway.
        
        Args:
            config: Gateway configuration including API keys, endpoints, etc.
        """
        self.config = config
        self.gateway_name = self.__class__.__name__
        self.is_test_mode = config.get("test_mode", False)
        self.api_key = config.get("api_key")
        self.secret_key = config.get("secret_key")
        self.base_url = config.get("base_url")
        
    @abstractmethod
    async def initialize_payment(self, request: PaymentRequest) -> PaymentResponse:
        """
        Initialize a payment transaction.
        
        Args:
            request: Payment request data
            
        Returns:
            PaymentResponse with transaction details
            
        Raises:
            PaymentGatewayError: If payment initialization fails
        """
        pass
    
    @abstractmethod
    async def verify_payment(self, transaction_id: str) -> PaymentResponse:
        """
        Verify the status of a payment transaction.
        
        Args:
            transaction_id: Transaction ID to verify
            
        Returns:
            PaymentResponse with current transaction status
            
        Raises:
            PaymentGatewayError: If verification fails
        """
        pass
    
    @abstractmethod
    async def process_refund(self, request: RefundRequest) -> RefundResponse:
        """
        Process a refund for a completed transaction.
        
        Args:
            request: Refund request data
            
        Returns:
            RefundResponse with refund details
            
        Raises:
            PaymentGatewayError: If refund processing fails
        """
        pass
    
    @abstractmethod
    async def get_transaction_status(self, transaction_id: str) -> PaymentStatus:
        """
        Get the current status of a transaction.
        
        Args:
            transaction_id: Transaction ID to check
            
        Returns:
            Current PaymentStatus
            
        Raises:
            PaymentGatewayError: If status check fails
        """
        pass
    
    @abstractmethod
    async def get_balance(self) -> Dict[str, Decimal]:
        """
        Get the current balance in the gateway account.
        
        Returns:
            Dictionary mapping currency codes to balances
            
        Raises:
            PaymentGatewayError: If balance retrieval fails
        """
        pass
    
    @abstractmethod
    async def get_supported_currencies(self) -> List[str]:
        """
        Get list of supported currencies.
        
        Returns:
            List of currency codes (ISO 4217)
        """
        pass
    
    @abstractmethod
    async def calculate_fee(self, amount: Decimal, currency: str) -> Decimal:
        """
        Calculate the transaction fee for a given amount.
        
        Args:
            amount: Transaction amount
            currency: Currency code
            
        Returns:
            Fee amount in the same currency
        """
        pass
    
    @abstractmethod
    async def get_exchange_rate(
        self, 
        source_currency: str, 
        destination_currency: str
    ) -> Decimal:
        """
        Get the current exchange rate between two currencies.
        
        Args:
            source_currency: Source currency code
            destination_currency: Destination currency code
            
        Returns:
            Exchange rate (1 source = X destination)
            
        Raises:
            PaymentGatewayError: If rate retrieval fails
        """
        pass
    
    @abstractmethod
    async def validate_account(
        self, 
        account_number: str, 
        bank_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate a bank account or payment account.
        
        Args:
            account_number: Account number to validate
            bank_code: Bank code (if applicable)
            
        Returns:
            Account details including name, status, etc.
            
        Raises:
            PaymentGatewayError: If validation fails
        """
        pass
    
    @abstractmethod
    async def handle_webhook(self, payload: Dict[str, Any], headers: Dict[str, str]) -> bool:
        """
        Handle webhook notifications from the payment gateway.
        
        Args:
            payload: Webhook payload data
            headers: HTTP headers from the webhook request
            
        Returns:
            True if webhook was successfully processed
            
        Raises:
            PaymentGatewayError: If webhook processing fails
        """
        pass
    
    def validate_config(self) -> bool:
        """
        Validate that all required configuration is present.
        
        Returns:
            True if configuration is valid
            
        Raises:
            ValueError: If required configuration is missing
        """
        required_fields = ["api_key", "secret_key", "base_url"]
        missing_fields = [field for field in required_fields if not self.config.get(field)]
        
        if missing_fields:
            raise ValueError(
                f"Missing required configuration fields for {self.gateway_name}: "
                f"{', '.join(missing_fields)}"
            )
        
        return True
    
    def get_headers(self) -> Dict[str, str]:
        """
        Get common HTTP headers for API requests.
        
        Returns:
            Dictionary of HTTP headers
        """
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": f"NigerianRemittancePlatform/{self.gateway_name}",
        }
    
    async def health_check(self) -> bool:
        """
        Perform a health check on the gateway connection.
        
        Returns:
            True if gateway is accessible and healthy
        """
        try:
            await self.get_supported_currencies()
            return True
        except Exception:
            return False


class PaymentGatewayError(Exception):
    """Base exception for payment gateway errors"""
    
    def __init__(
        self, 
        message: str, 
        gateway_name: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        self.message = message
        self.gateway_name = gateway_name
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)


class PaymentGatewayConnectionError(PaymentGatewayError):
    """Exception raised when gateway connection fails"""
    pass


class PaymentGatewayAuthenticationError(PaymentGatewayError):
    """Exception raised when gateway authentication fails"""
    pass


class PaymentGatewayValidationError(PaymentGatewayError):
    """Exception raised when request validation fails"""
    pass


class PaymentGatewayInsufficientFundsError(PaymentGatewayError):
    """Exception raised when account has insufficient funds"""
    pass


class PaymentGatewayTransactionError(PaymentGatewayError):
    """Exception raised when transaction processing fails"""
    pass
