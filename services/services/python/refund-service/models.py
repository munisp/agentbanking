"""
Refund Service Models
Database models for refund service
"""

from sqlalchemy import Column, String, DateTime, Integer, Float, Boolean, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import uuid

Base = declarative_base()

class RefundService(Base):
    """
    Refund Service model
    """
    __tablename__ = "refund_service"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    status = Column(String, default="active", nullable=False)
    
    amount = Column(Float, nullable=False)
    currency = Column(String(3), default="NGN")
    reason = Column(String(500))
    transaction_id = Column(String(50))
    status = Column(String(20), default="pending")
    
    def __repr__(self):
        return f"<RefundService(id={self.id})>"
