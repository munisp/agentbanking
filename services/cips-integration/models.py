from sqlalchemy import Column, Integer, String, Float, DateTime, Enum, Index
from sqlalchemy.sql import func
from database import Base
import enum

class TransactionStatus(enum.Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REVERSED = "REVERSED"

class CipsTransaction(Base):
    __tablename__ = "cips_transactions"

    id = Column(Integer, primary_key=True, index=True)
    
    # Unique identifier for the transaction, likely from the CIPS system
    cips_transaction_id = Column(String, unique=True, nullable=False, index=True)
    
    # Payment details
    sender_bank_id = Column(String, nullable=False)
    receiver_bank_id = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String(3), nullable=False) # e.g., "CNY", "USD"
    
    # Status and timestamps
    status = Column(Enum(TransactionStatus), default=TransactionStatus.PENDING, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Add a composite index for common queries
    __table_args__ = (
        Index('idx_sender_receiver_status', "sender_bank_id", "receiver_bank_id", "status"),
    )
