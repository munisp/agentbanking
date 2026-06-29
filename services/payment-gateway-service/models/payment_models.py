"""
Payment Gateway Models

SQLAlchemy models for payment transactions, gateways, and related entities.
"""

from sqlalchemy import (
    Column, String, Numeric, DateTime, Boolean, Text, JSON,
    ForeignKey, Index, CheckConstraint, Enum as SQLEnum
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from decimal import Decimal
from datetime import datetime
import enum

from ...shared.database import Base


class PaymentStatus(str, enum.Enum):
    """Payment transaction status"""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    EXPIRED = "expired"


class TransactionType(str, enum.Enum):
    """Transaction type"""
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    TRANSFER = "transfer"
    REFUND = "refund"


class GatewayType(str, enum.Enum):
    """Payment gateway type"""
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


class PaymentTransaction(Base):
    """Payment transaction model"""
    __tablename__ = "payment_transactions"
    
    # Primary key
    id = Column(String(36), primary_key=True)
    
    # Transaction details
    transaction_reference = Column(String(100), unique=True, nullable=False, index=True)
    gateway_reference = Column(String(255), index=True)
    gateway_type = Column(SQLEnum(GatewayType), nullable=False, index=True)
    transaction_type = Column(SQLEnum(TransactionType), nullable=False, default=TransactionType.TRANSFER)
    status = Column(SQLEnum(PaymentStatus), nullable=False, default=PaymentStatus.PENDING, index=True)
    
    # Amount and currency
    amount = Column(Numeric(20, 2), nullable=False)
    currency = Column(String(3), nullable=False)
    source_currency = Column(String(3), nullable=False)
    destination_currency = Column(String(3), nullable=False)
    exchange_rate = Column(Numeric(20, 6))
    fee = Column(Numeric(20, 2), default=Decimal("0.00"))
    total_amount = Column(Numeric(20, 2))  # amount + fee
    
    # Parties involved
    sender_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    recipient_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    sender_account = Column(String(255))
    recipient_account = Column(String(255))
    
    # Additional details
    description = Column(Text)
    payment_url = Column(Text)
    callback_url = Column(Text)
    metadata = Column(JSON)
    
    # Status tracking
    initiated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True))
    failed_at = Column(DateTime(timezone=True))
    cancelled_at = Column(DateTime(timezone=True))
    
    # Error handling
    error_code = Column(String(50))
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)
    
    # Audit
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(String(36))
    updated_by = Column(String(36))
    
    # Relationships
    sender = relationship("User", foreign_keys=[sender_id], backref="sent_payments")
    recipient = relationship("User", foreign_keys=[recipient_id], backref="received_payments")
    refunds = relationship("PaymentRefund", back_populates="transaction")
    webhooks = relationship("PaymentWebhook", back_populates="transaction")
    
    # Indexes
    __table_args__ = (
        Index("idx_payment_sender_status", "sender_id", "status"),
        Index("idx_payment_recipient_status", "recipient_id", "status"),
        Index("idx_payment_gateway_status", "gateway_type", "status"),
        Index("idx_payment_created_at", "created_at"),
        CheckConstraint("amount > 0", name="check_amount_positive"),
        CheckConstraint("fee >= 0", name="check_fee_non_negative"),
    )
    
    def __repr__(self):
        return f"<PaymentTransaction(id={self.id}, ref={self.transaction_reference}, status={self.status})>"


class PaymentRefund(Base):
    """Payment refund model"""
    __tablename__ = "payment_refunds"
    
    # Primary key
    id = Column(String(36), primary_key=True)
    
    # Refund details
    refund_reference = Column(String(100), unique=True, nullable=False, index=True)
    transaction_id = Column(String(36), ForeignKey("payment_transactions.id"), nullable=False, index=True)
    gateway_refund_id = Column(String(255))
    
    # Amount
    refund_amount = Column(Numeric(20, 2), nullable=False)
    currency = Column(String(3), nullable=False)
    refund_fee = Column(Numeric(20, 2), default=Decimal("0.00"))
    
    # Status
    status = Column(SQLEnum(PaymentStatus), nullable=False, default=PaymentStatus.PENDING)
    reason = Column(Text)
    
    # Metadata
    metadata = Column(JSON)
    
    # Timestamps
    requested_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True))
    
    # Error handling
    error_code = Column(String(50))
    error_message = Column(Text)
    
    # Audit
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    requested_by = Column(String(36), ForeignKey("users.id"))
    
    # Relationships
    transaction = relationship("PaymentTransaction", back_populates="refunds")
    requester = relationship("User")
    
    # Indexes
    __table_args__ = (
        Index("idx_refund_transaction", "transaction_id"),
        Index("idx_refund_status", "status"),
        CheckConstraint("refund_amount > 0", name="check_refund_amount_positive"),
    )
    
    def __repr__(self):
        return f"<PaymentRefund(id={self.id}, ref={self.refund_reference}, status={self.status})>"


class PaymentGatewayConfig(Base):
    """Payment gateway configuration model"""
    __tablename__ = "payment_gateway_configs"
    
    # Primary key
    id = Column(String(36), primary_key=True)
    
    # Gateway details
    gateway_type = Column(SQLEnum(GatewayType), unique=True, nullable=False)
    gateway_name = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_test_mode = Column(Boolean, default=False, nullable=False)
    
    # Configuration (encrypted)
    api_key = Column(Text, nullable=False)  # Encrypted
    secret_key = Column(Text, nullable=False)  # Encrypted
    merchant_id = Column(String(255))
    base_url = Column(String(500))
    webhook_url = Column(String(500))
    
    # Capabilities
    supported_currencies = Column(JSON)  # List of currency codes
    supported_countries = Column(JSON)  # List of country codes
    min_transaction_amount = Column(Numeric(20, 2))
    max_transaction_amount = Column(Numeric(20, 2))
    
    # Fee structure
    fixed_fee = Column(Numeric(20, 2), default=Decimal("0.00"))
    percentage_fee = Column(Numeric(5, 4), default=Decimal("0.0000"))  # e.g., 0.015 = 1.5%
    
    # Limits
    daily_limit = Column(Numeric(20, 2))
    monthly_limit = Column(Numeric(20, 2))
    
    # Priority (lower number = higher priority)
    priority = Column(Integer, default=100)
    
    # Metadata
    metadata = Column(JSON)
    
    # Audit
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(String(36))
    updated_by = Column(String(36))
    
    def __repr__(self):
        return f"<PaymentGatewayConfig(gateway={self.gateway_type}, active={self.is_active})>"


class PaymentWebhook(Base):
    """Payment webhook event model"""
    __tablename__ = "payment_webhooks"
    
    # Primary key
    id = Column(String(36), primary_key=True)
    
    # Webhook details
    transaction_id = Column(String(36), ForeignKey("payment_transactions.id"), index=True)
    gateway_type = Column(SQLEnum(GatewayType), nullable=False)
    event_type = Column(String(100), nullable=False)
    
    # Payload
    payload = Column(JSON, nullable=False)
    headers = Column(JSON)
    signature = Column(Text)
    
    # Processing
    is_processed = Column(Boolean, default=False, nullable=False)
    processed_at = Column(DateTime(timezone=True))
    processing_error = Column(Text)
    
    # Retry
    retry_count = Column(Integer, default=0)
    
    # Timestamps
    received_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    transaction = relationship("PaymentTransaction", back_populates="webhooks")
    
    # Indexes
    __table_args__ = (
        Index("idx_webhook_transaction", "transaction_id"),
        Index("idx_webhook_gateway_event", "gateway_type", "event_type"),
        Index("idx_webhook_processed", "is_processed"),
        Index("idx_webhook_received_at", "received_at"),
    )
    
    def __repr__(self):
        return f"<PaymentWebhook(id={self.id}, gateway={self.gateway_type}, event={self.event_type})>"


class PaymentGatewayBalance(Base):
    """Payment gateway balance tracking model"""
    __tablename__ = "payment_gateway_balances"
    
    # Primary key
    id = Column(String(36), primary_key=True)
    
    # Gateway and currency
    gateway_type = Column(SQLEnum(GatewayType), nullable=False)
    currency = Column(String(3), nullable=False)
    
    # Balance
    available_balance = Column(Numeric(20, 2), default=Decimal("0.00"), nullable=False)
    pending_balance = Column(Numeric(20, 2), default=Decimal("0.00"), nullable=False)
    total_balance = Column(Numeric(20, 2), default=Decimal("0.00"), nullable=False)
    
    # Timestamps
    last_updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_synced_at = Column(DateTime(timezone=True))
    
    # Audit
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Indexes
    __table_args__ = (
        Index("idx_balance_gateway_currency", "gateway_type", "currency", unique=True),
    )
    
    def __repr__(self):
        return f"<PaymentGatewayBalance(gateway={self.gateway_type}, currency={self.currency}, balance={self.available_balance})>"
