"""Database Models for Monitor"""
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, JSON, ForeignKey, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
import uuid

Base = declarative_base()

class StatusEnum(enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"

class Monitor(Base):
    __tablename__ = "monitor"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=True, index=True)
    status = Column(Enum(StatusEnum), default=StatusEnum.ACTIVE, nullable=False)
    data = Column(JSON, nullable=True)
    metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_by = Column(String(36), nullable=True)
    updated_by = Column(String(36), nullable=True)
    
    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "status": self.status.value if self.status else None,
            "data": self.data,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "created_by": self.created_by,
            "updated_by": self.updated_by
        }

class MonitorTransaction(Base):
    __tablename__ = "monitor_transactions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    monitor_id = Column(String(36), ForeignKey("monitor.id"), nullable=False)
    transaction_type = Column(String(50), nullable=False)
    amount = Column(Float, nullable=True)
    currency = Column(String(3), nullable=True)
    status = Column(Enum(StatusEnum), default=StatusEnum.PENDING, nullable=False)
    reference = Column(String(100), unique=True, nullable=True)
    data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    
    def to_dict(self):
        return {
            "id": self.id,
            "monitor_id": self.monitor_id,
            "transaction_type": self.transaction_type,
            "amount": self.amount,
            "currency": self.currency,
            "status": self.status.value if self.status else None,
            "reference": self.reference,
            "data": self.data,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }
