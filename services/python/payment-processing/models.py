import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Numeric, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base

# --- Enums ---

class TransactionStatus(str, Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"
    CANCELED = "CANCELED"

class PaymentMethodType(str, Enum):
    CARD = "CARD"
    BANK_ACCOUNT = "BANK_ACCOUNT"
    WALLET = "WALLET"

# --- Models ---

class Merchant(Base):
    __tablename__ = "merchants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, index=True)
    api_key_hash = Column(String, nullable=False) # Hashed API key for merchant authentication
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    transactions = relationship("Transaction", back_populates="merchant")

    def __repr__(self):
        return f"<Merchant(id={self.id}, name='{self.name}')>"

class PaymentMethod(Base):
    __tablename__ = "payment_methods"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), index=True, nullable=True) # User ID from an external service
    type = Column(String, nullable=False) # Stored as string, but should be validated against PaymentMethodType
    last_four = Column(String(4), nullable=False)
    token = Column(String, nullable=False, unique=True) # Secure token from PSP
    is_default = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    transactions = relationship("Transaction", back_populates="payment_method")

    __table_args__ = (
        Index('idx_payment_method_user_type', user_id, type),
    )

    def __repr__(self):
        return f"<PaymentMethod(id={self.id}, type='{self.type}', last_four='{self.last_four}')>"

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    merchant_id = Column(UUID(as_uuid=True), ForeignKey("merchants.id"), nullable=False, index=True)
    payment_method_id = Column(UUID(as_uuid=True), ForeignKey("payment_methods.id"), nullable=False)
    
    amount = Column(Numeric(10, 2), nullable=False) # 10 total digits, 2 after decimal
    currency = Column(String(3), nullable=False) # e.g., 'USD', 'EUR'
    
    status = Column(String, default=TransactionStatus.PENDING.value, nullable=False, index=True) # Stored as string, validated against enum
    
    processor_transaction_id = Column(String, nullable=True, unique=True) # ID from external PSP
    
    fee = Column(Numeric(10, 2), default=0.00, nullable=False)
    net_amount = Column(Numeric(10, 2), nullable=False) # amount - fee
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    merchant = relationship("Merchant", back_populates="transactions")
    payment_method = relationship("PaymentMethod", back_populates="transactions")
    refunds = relationship("Refund", back_populates="transaction")

    __table_args__ = (
        Index('idx_transaction_merchant_status', merchant_id, status),
    )

    def __repr__(self):
        return f"<Transaction(id={self.id}, amount={self.amount}, status='{self.status}')>"

class Refund(Base):
    __tablename__ = "refunds"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id = Column(UUID(as_uuid=True), ForeignKey("transactions.id"), nullable=False, index=True)
    
    amount = Column(Numeric(10, 2), nullable=False)
    status = Column(String, default=TransactionStatus.PENDING.value, nullable=False, index=True)
    
    processor_refund_id = Column(String, nullable=True, unique=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    transaction = relationship("Transaction", back_populates="refunds")

    def __repr__(self):
        return f"<Refund(id={self.id}, amount={self.amount}, status='{self.status}')>"
