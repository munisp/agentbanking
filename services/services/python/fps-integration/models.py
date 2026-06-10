from sqlalchemy import Column, Integer, String, Numeric, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

class FPSTransaction(Base):
    __tablename__ = "fps_transactions"

    id = Column(Integer, primary_key=True, index=True)
    
    # Core transaction details
    transaction_ref = Column(String(50), unique=True, index=True, nullable=False)
    fps_payment_id = Column(String(50), unique=True, index=True, nullable=True)
    
    # Payment details
    sender_account = Column(String(34), nullable=False)
    receiver_account = Column(String(34), nullable=False)
    amount = Column(Numeric(18, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="GBP")
    
    # Status and logging
    status = Column(String(20), nullable=False, default="PENDING")
    status_detail = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True, nullable=False)

    # Relationship to webhook logs
    webhook_logs = relationship("FPSWebhookLog", back_populates="transaction")

    def __repr__(self):
        return f"<FPSTransaction(id={self.id}, ref='{self.transaction_ref}', status='{self.status}')>"

class FPSWebhookLog(Base):
    __tablename__ = "fps_webhook_logs"

    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign key to FPSTransaction
    transaction_id = Column(Integer, ForeignKey("fps_transactions.id"), index=True, nullable=True)
    
    # Webhook details
    event_type = Column(String(50), nullable=False)
    # Using Text for payload for simplicity, but JSONB would be better in PostgreSQL
    payload = Column(Text, nullable=False) 
    
    # Timestamps
    received_at = Column(DateTime(timezone=True), server_default=func.now(), index=True, nullable=False)

    # Relationship to FPSTransaction
    transaction = relationship("FPSTransaction", back_populates="webhook_logs")

    def __repr__(self):
        return f"<FPSWebhookLog(id={self.id}, event='{self.event_type}', transaction_id={self.transaction_id})>"

# Add a check constraint for amount to be positive (optional, but good practice)
Index('idx_amount_positive', FPSTransaction.amount, postgresql_where=FPSTransaction.amount > 0)
