from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum, Text, DECIMAL, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
import enum

Base = declarative_base()

class TransactionStatus(enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"

class PartyType(enum.Enum):
    SENDER = "SENDER"
    RECEIVER = "RECEIVER"

class Party(Base):
    __tablename__ = "parties"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    country_code = Column(String(3), nullable=False, index=True) # ISO 3166-1 alpha-3
    currency_code = Column(String(3), nullable=False) # ISO 4217
    bank_name = Column(String(255))
    account_number = Column(String(50), unique=True, index=True, nullable=False)
    swift_bic = Column(String(11))
    address = Column(Text)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    sender_transactions = relationship("Transaction", foreign_keys="[Transaction.sender_id]", back_populates="sender")
    receiver_transactions = relationship("Transaction", foreign_keys="[Transaction.receiver_id]", back_populates="receiver")

class FXRate(Base):
    __tablename__ = "fx_rates"

    id = Column(Integer, primary_key=True, index=True)
    base_currency = Column(String(3), nullable=False, index=True)
    target_currency = Column(String(3), nullable=False, index=True)
    rate = Column(DECIMAL(10, 6), nullable=False)
    source = Column(String(50))
    timestamp = Column(DateTime, server_default=func.now(), index=True)

    __table_args__ = (
        # Ensure only one rate per currency pair at a given timestamp (or close enough)
        # For simplicity, we'll just index the pair
        # UniqueConstraint('base_currency', 'target_currency', 'timestamp', name='_currency_pair_ts_uc'),
    )

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    reference_id = Column(String(100), unique=True, index=True, nullable=False) # Internal unique reference
    
    # Amount details
    source_amount = Column(DECIMAL(18, 4), nullable=False)
    source_currency = Column(String(3), nullable=False)
    target_amount = Column(DECIMAL(18, 4), nullable=False)
    target_currency = Column(String(3), nullable=False)
    
    # FX Details
    fx_rate = Column(DECIMAL(10, 6), nullable=False)
    fee_amount = Column(DECIMAL(18, 4), default=0.0)
    
    # Parties
    sender_id = Column(Integer, ForeignKey("parties.id"), nullable=False)
    receiver_id = Column(Integer, ForeignKey("parties.id"), nullable=False)
    
    # Status and Timestamps
    status = Column(Enum(TransactionStatus), default=TransactionStatus.PENDING, index=True)
    status_detail = Column(String(255))
    
    # Compliance/Regulatory
    purpose_code = Column(String(10)) # ISO 20022 purpose code
    compliance_score = Column(Integer, default=0)
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    sender = relationship("Party", foreign_keys=[sender_id], back_populates="sender_transactions")
    receiver = relationship("Party", foreign_keys=[receiver_id], back_populates="receiver_transactions")

    __table_args__ = (
        # Check constraint to ensure source and target currencies are different for cross-border
        # CheckConstraint('source_currency != target_currency', name='cc_cross_border'),
    )