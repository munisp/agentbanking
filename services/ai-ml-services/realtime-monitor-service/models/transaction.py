"""
Transaction Database Models
Nigerian Remittance Platform
"""

from sqlalchemy import Column, String, Float, DateTime, Enum, ForeignKey, JSON, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum
from db.base import Base


class TransactionStatus(str, enum.Enum):
    """Transaction status enumeration"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class TransactionType(str, enum.Enum):
    """Transaction type enumeration"""
    SEND = "send"
    RECEIVE = "receive"
    WITHDRAW = "withdraw"
    DEPOSIT = "deposit"
    EXCHANGE = "exchange"


class Transaction(Base):
    """Transaction model"""
    __tablename__ = "transactions"

    id = Column(String(36), primary_key=True, index=True)
    amount = Column(Float, nullable=False)
    currency = Column(String(3), nullable=False, index=True)
    status = Column(Enum(TransactionStatus), nullable=False, index=True, default=TransactionStatus.PENDING)
    type = Column(Enum(TransactionType), nullable=False, index=True)
    
    # User references
    sender_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    recipient_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    
    # Transaction details
    payment_method = Column(String(50), nullable=False)
    reference = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(String(500), nullable=True)
    
    # Metadata
    metadata = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Processing time in seconds
    processing_time = Column(Float, nullable=True)
    
    # Fee information
    fee_amount = Column(Float, nullable=True)
    fee_currency = Column(String(3), nullable=True)
    
    # Exchange rate (if applicable)
    exchange_rate = Column(Float, nullable=True)
    
    # Relationships
    sender = relationship("User", foreign_keys=[sender_id], back_populates="sent_transactions")
    recipient = relationship("User", foreign_keys=[recipient_id], back_populates="received_transactions")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_status_created', 'status', 'created_at'),
        Index('idx_sender_created', 'sender_id', 'created_at'),
        Index('idx_recipient_created', 'recipient_id', 'created_at'),
        Index('idx_currency_created', 'currency', 'created_at'),
    )

    def __repr__(self):
        return f"<Transaction {self.id} {self.status} {self.amount} {self.currency}>"

    def to_dict(self):
        """Convert to dictionary"""
        return {
            "id": self.id,
            "amount": self.amount,
            "currency": self.currency,
            "status": self.status.value,
            "type": self.type.value,
            "sender": self.sender.to_dict() if self.sender else None,
            "recipient": self.recipient.to_dict() if self.recipient else None,
            "payment_method": self.payment_method,
            "reference": self.reference,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "metadata": self.metadata
        }


class User(Base):
    """User model (simplified)"""
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=True)
    avatar = Column(String(500), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    sent_transactions = relationship("Transaction", foreign_keys="Transaction.sender_id", back_populates="sender")
    received_transactions = relationship("Transaction", foreign_keys="Transaction.recipient_id", back_populates="recipient")

    def to_dict(self):
        """Convert to dictionary"""
        return {
            "id": self.id,
            "email": self.email,
            "full_name": self.full_name,
            "phone": self.phone,
            "avatar": self.avatar
        }
