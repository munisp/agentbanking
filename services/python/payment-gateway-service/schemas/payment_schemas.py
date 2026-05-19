"""
Payment API Pydantic Schemas

Request and response models for the payment gateway API endpoints.
"""

from pydantic import BaseModel, Field, validator, root_validator
from typing import Optional, Dict, Any, List
from decimal import Decimal
from datetime import datetime
from enum import Enum


# Enums
class PaymentStatusEnum(str, Enum):
    """Payment status enum"""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    EXPIRED = "expired"


class TransactionTypeEnum(str, Enum):
    """Transaction type enum"""
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    TRANSFER = "transfer"
    REFUND = "refund"


class GatewayTypeEnum(str, Enum):
    """Payment gateway enum"""
    PAYSTACK = "paystack"
    FLUTTERWAVE = "flutterwave"
    INTERSWITCH = "interswitch"
    STRIPE = "stripe"
    PAYPAL = "paypal"
    REMITA = "remita"
    PAGA = "paga"
    OPAY = "opay"
    KUDA = "kuda"
    CHIPPER_CASH = "chipper_cash"
    NIBSS = "nibss"
    GTPAY = "gtpay"
    ECOBANK = "ecobank"
    AUTO = "auto"  # Automatic gateway selection


# Request Schemas
class PaymentInitiateRequest(BaseModel):
    """Request schema for initiating a payment"""
    amount: Decimal = Field(..., gt=0, description="Transaction amount (must be positive)")
    currency: str = Field(..., min_length=3, max_length=3, description="Currency code (ISO 4217)")
    source_currency: str = Field(..., min_length=3, max_length=3, description="Source currency code")
    destination_currency: str = Field(..., min_length=3, max_length=3, description="Destination currency code")
    recipient_id: str = Field(..., description="Recipient user ID")
    recipient_account: Optional[str] = Field(None, description="Recipient account number/identifier")
    gateway: GatewayTypeEnum = Field(GatewayTypeEnum.AUTO, description="Payment gateway to use")
    transaction_type: TransactionTypeEnum = Field(TransactionTypeEnum.TRANSFER, description="Transaction type")
    description: Optional[str] = Field(None, max_length=500, description="Transaction description")
    callback_url: Optional[str] = Field(None, description="Callback URL for payment status updates")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    
    @validator('currency', 'source_currency', 'destination_currency')
    def validate_currency(cls, v) -> None:
        """Validate currency code format"""
        if not v.isupper():
            raise ValueError("Currency code must be uppercase")
        return v
    
    @validator('amount')
    def validate_amount(cls, v) -> None:
        """Validate amount precision"""
        if v.as_tuple().exponent < -2:
            raise ValueError("Amount can have at most 2 decimal places")
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "amount": "10000.00",
                "currency": "NGN",
                "source_currency": "NGN",
                "destination_currency": "NGN",
                "recipient_id": "user_456",
                "recipient_account": "0123456789",
                "gateway": "paystack",
                "transaction_type": "transfer",
                "description": "Remittance to family",
                "metadata": {"purpose": "family_support"}
            }
        }


class PaymentVerifyRequest(BaseModel):
    """Request schema for verifying a payment"""
    transaction_id: str = Field(..., description="Transaction ID to verify")
    
    class Config:
        schema_extra = {
            "example": {
                "transaction_id": "txn_abc123xyz"
            }
        }


class RefundInitiateRequest(BaseModel):
    """Request schema for initiating a refund"""
    transaction_id: str = Field(..., description="Original transaction ID")
    amount: Optional[Decimal] = Field(None, gt=0, description="Refund amount (None for full refund)")
    reason: Optional[str] = Field(None, max_length=500, description="Refund reason")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    
    @validator('amount')
    def validate_amount(cls, v) -> None:
        """Validate amount precision"""
        if v and v.as_tuple().exponent < -2:
            raise ValueError("Amount can have at most 2 decimal places")
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "transaction_id": "txn_abc123xyz",
                "amount": "5000.00",
                "reason": "Customer request"
            }
        }


class ExchangeRateRequest(BaseModel):
    """Request schema for getting exchange rate"""
    source_currency: str = Field(..., min_length=3, max_length=3, description="Source currency code")
    destination_currency: str = Field(..., min_length=3, max_length=3, description="Destination currency code")
    amount: Optional[Decimal] = Field(None, gt=0, description="Amount to convert (optional)")
    gateway: Optional[GatewayTypeEnum] = Field(None, description="Specific gateway to use")
    
    class Config:
        schema_extra = {
            "example": {
                "source_currency": "NGN",
                "destination_currency": "USD",
                "amount": "10000.00"
            }
        }


class FeeCalculationRequest(BaseModel):
    """Request schema for calculating transaction fee"""
    amount: Decimal = Field(..., gt=0, description="Transaction amount")
    currency: str = Field(..., min_length=3, max_length=3, description="Currency code")
    gateway: Optional[GatewayTypeEnum] = Field(None, description="Specific gateway to use")
    
    class Config:
        schema_extra = {
            "example": {
                "amount": "10000.00",
                "currency": "NGN",
                "gateway": "paystack"
            }
        }


class AccountValidationRequest(BaseModel):
    """Request schema for validating an account"""
    account_number: str = Field(..., description="Account number to validate")
    bank_code: Optional[str] = Field(None, description="Bank code (if applicable)")
    gateway: GatewayTypeEnum = Field(..., description="Gateway to use for validation")
    
    class Config:
        schema_extra = {
            "example": {
                "account_number": "0123456789",
                "bank_code": "058",
                "gateway": "paystack"
            }
        }


# Response Schemas
class PaymentInitiateResponse(BaseModel):
    """Response schema for payment initiation"""
    success: bool = Field(..., description="Whether the request was successful")
    transaction_id: str = Field(..., description="Unique transaction ID")
    gateway_reference: Optional[str] = Field(None, description="Gateway transaction reference")
    gateway: str = Field(..., description="Gateway used")
    status: PaymentStatusEnum = Field(..., description="Current transaction status")
    amount: Decimal = Field(..., description="Transaction amount")
    currency: str = Field(..., description="Currency code")
    fee: Optional[Decimal] = Field(None, description="Transaction fee")
    total_amount: Optional[Decimal] = Field(None, description="Total amount (amount + fee)")
    exchange_rate: Optional[Decimal] = Field(None, description="Exchange rate applied")
    payment_url: Optional[str] = Field(None, description="Payment URL (for redirect flows)")
    message: Optional[str] = Field(None, description="Status message")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    created_at: datetime = Field(..., description="Transaction creation timestamp")
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "transaction_id": "txn_abc123xyz",
                "gateway_reference": "ref_xyz789",
                "gateway": "paystack",
                "status": "pending",
                "amount": "10000.00",
                "currency": "NGN",
                "fee": "150.00",
                "total_amount": "10150.00",
                "payment_url": "https://checkout.paystack.com/abc123",
                "message": "Payment initiated successfully",
                "created_at": "2025-01-03T12:00:00Z"
            }
        }


class PaymentVerifyResponse(BaseModel):
    """Response schema for payment verification"""
    success: bool = Field(..., description="Whether the verification was successful")
    transaction_id: str = Field(..., description="Transaction ID")
    gateway_reference: Optional[str] = Field(None, description="Gateway transaction reference")
    status: PaymentStatusEnum = Field(..., description="Current transaction status")
    amount: Decimal = Field(..., description="Transaction amount")
    currency: str = Field(..., description="Currency code")
    fee: Optional[Decimal] = Field(None, description="Transaction fee")
    exchange_rate: Optional[Decimal] = Field(None, description="Exchange rate applied")
    sender_id: str = Field(..., description="Sender user ID")
    recipient_id: str = Field(..., description="Recipient user ID")
    description: Optional[str] = Field(None, description="Transaction description")
    initiated_at: datetime = Field(..., description="Transaction initiation timestamp")
    completed_at: Optional[datetime] = Field(None, description="Transaction completion timestamp")
    message: Optional[str] = Field(None, description="Status message")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "transaction_id": "txn_abc123xyz",
                "gateway_reference": "ref_xyz789",
                "status": "success",
                "amount": "10000.00",
                "currency": "NGN",
                "fee": "150.00",
                "sender_id": "user_123",
                "recipient_id": "user_456",
                "initiated_at": "2025-01-03T12:00:00Z",
                "completed_at": "2025-01-03T12:05:00Z",
                "message": "Payment completed successfully"
            }
        }


class RefundInitiateResponse(BaseModel):
    """Response schema for refund initiation"""
    success: bool = Field(..., description="Whether the refund was initiated successfully")
    refund_id: str = Field(..., description="Unique refund ID")
    transaction_id: str = Field(..., description="Original transaction ID")
    refund_amount: Decimal = Field(..., description="Refund amount")
    currency: str = Field(..., description="Currency code")
    status: PaymentStatusEnum = Field(..., description="Refund status")
    message: Optional[str] = Field(None, description="Status message")
    requested_at: datetime = Field(..., description="Refund request timestamp")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "refund_id": "ref_abc123",
                "transaction_id": "txn_abc123xyz",
                "refund_amount": "5000.00",
                "currency": "NGN",
                "status": "processing",
                "message": "Refund initiated successfully",
                "requested_at": "2025-01-03T12:00:00Z"
            }
        }


class ExchangeRateResponse(BaseModel):
    """Response schema for exchange rate"""
    success: bool = Field(..., description="Whether the request was successful")
    source_currency: str = Field(..., description="Source currency code")
    destination_currency: str = Field(..., description="Destination currency code")
    exchange_rate: Decimal = Field(..., description="Exchange rate (1 source = X destination)")
    converted_amount: Optional[Decimal] = Field(None, description="Converted amount (if amount was provided)")
    gateway: str = Field(..., description="Gateway used")
    timestamp: datetime = Field(..., description="Rate timestamp")
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "source_currency": "NGN",
                "destination_currency": "USD",
                "exchange_rate": "0.00125",
                "converted_amount": "12.50",
                "gateway": "flutterwave",
                "timestamp": "2025-01-03T12:00:00Z"
            }
        }


class FeeCalculationResponse(BaseModel):
    """Response schema for fee calculation"""
    success: bool = Field(..., description="Whether the calculation was successful")
    amount: Decimal = Field(..., description="Transaction amount")
    currency: str = Field(..., description="Currency code")
    fee: Decimal = Field(..., description="Calculated fee")
    total_amount: Decimal = Field(..., description="Total amount (amount + fee)")
    gateway: str = Field(..., description="Gateway used")
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "amount": "10000.00",
                "currency": "NGN",
                "fee": "150.00",
                "total_amount": "10150.00",
                "gateway": "paystack"
            }
        }


class AccountValidationResponse(BaseModel):
    """Response schema for account validation"""
    success: bool = Field(..., description="Whether the validation was successful")
    account_number: str = Field(..., description="Account number")
    account_name: Optional[str] = Field(None, description="Account holder name")
    bank_name: Optional[str] = Field(None, description="Bank name")
    bank_code: Optional[str] = Field(None, description="Bank code")
    is_valid: bool = Field(..., description="Whether the account is valid")
    message: Optional[str] = Field(None, description="Validation message")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "account_number": "0123456789",
                "account_name": "John Doe",
                "bank_name": "GTBank",
                "bank_code": "058",
                "is_valid": True,
                "message": "Account validated successfully"
            }
        }


class TransactionListResponse(BaseModel):
    """Response schema for transaction list"""
    success: bool = Field(..., description="Whether the request was successful")
    transactions: List[PaymentVerifyResponse] = Field(..., description="List of transactions")
    total: int = Field(..., description="Total number of transactions")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of items per page")
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "transactions": [],
                "total": 100,
                "page": 1,
                "page_size": 20
            }
        }


class GatewayBalanceResponse(BaseModel):
    """Response schema for gateway balance"""
    success: bool = Field(..., description="Whether the request was successful")
    gateway: str = Field(..., description="Gateway name")
    balances: Dict[str, Decimal] = Field(..., description="Balances by currency")
    last_updated: datetime = Field(..., description="Last update timestamp")
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "gateway": "paystack",
                "balances": {
                    "NGN": "1000000.00",
                    "GHS": "50000.00"
                },
                "last_updated": "2025-01-03T12:00:00Z"
            }
        }


class SupportedCurrenciesResponse(BaseModel):
    """Response schema for supported currencies"""
    success: bool = Field(..., description="Whether the request was successful")
    gateway: str = Field(..., description="Gateway name")
    currencies: List[str] = Field(..., description="List of supported currency codes")
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "gateway": "flutterwave",
                "currencies": ["NGN", "GHS", "KES", "UGX", "ZAR", "USD"]
            }
        }


class ErrorResponse(BaseModel):
    """Response schema for errors"""
    success: bool = Field(False, description="Always False for errors")
    error_code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    
    class Config:
        schema_extra = {
            "example": {
                "success": False,
                "error_code": "INSUFFICIENT_FUNDS",
                "message": "Insufficient funds in account",
                "details": {"available": "5000.00", "required": "10000.00"}
            }
        }


class WebhookEventSchema(BaseModel):
    """Schema for webhook events"""
    event_type: str = Field(..., description="Event type")
    gateway: str = Field(..., description="Gateway name")
    transaction_id: Optional[str] = Field(None, description="Transaction ID")
    gateway_reference: Optional[str] = Field(None, description="Gateway reference")
    status: Optional[PaymentStatusEnum] = Field(None, description="Transaction status")
    payload: Dict[str, Any] = Field(..., description="Event payload")
    timestamp: datetime = Field(..., description="Event timestamp")
    
    class Config:
        schema_extra = {
            "example": {
                "event_type": "charge.success",
                "gateway": "paystack",
                "transaction_id": "txn_abc123xyz",
                "gateway_reference": "ref_xyz789",
                "status": "success",
                "payload": {},
                "timestamp": "2025-01-03T12:00:00Z"
            }
        }
