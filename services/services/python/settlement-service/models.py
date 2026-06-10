from datetime import datetime
from typing import List, Optional
from enum import Enum

from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Index, Text
from sqlalchemy.orm import relationship, declarative_base
from pydantic import BaseModel, Field

# --- SQLAlchemy Base ---
Base = declarative_base()

# --- Enums ---

class SettlementStatus(str, Enum):
    """Possible statuses for a financial settlement."""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class LogLevel(str, Enum):
    """Logging levels for activity log."""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    DEBUG = "DEBUG"

# --- SQLAlchemy Models ---

class Settlement(Base):
    """
    Represents a financial settlement record.
    """
    __tablename__ = "settlements"

    id = Column(Integer, primary_key=True, index=True)
    
    # Core settlement details
    settlement_date = Column(DateTime, nullable=False, index=True, doc="The date the settlement is effective.")
    status = Column(String(50), nullable=False, default=SettlementStatus.PENDING.value, index=True, doc="Current status of the settlement.")
    amount = Column(Float, nullable=False, doc="Total settled amount.")
    currency = Column(String(3), nullable=False, doc="Currency of the settlement (e.g., USD, EUR).")
    transaction_count = Column(Integer, nullable=False, default=0, doc="Number of transactions included in the settlement.")
    
    # External reference
    external_reference_id = Column(String(255), unique=True, nullable=True, index=True, doc="ID from an external system for reconciliation.")

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    logs = relationship("SettlementLog", back_populates="settlement", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_settlement_date_status", "settlement_date", "status"),
    )

class SettlementLog(Base):
    """
    Activity log for changes and events related to a specific settlement.
    """
    __tablename__ = "settlement_logs"

    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign Key to Settlement
    settlement_id = Column(Integer, ForeignKey("settlements.id"), nullable=False, index=True)
    
    # Log details
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    level = Column(String(50), nullable=False, default=LogLevel.INFO.value, doc="Severity level of the log entry.")
    message = Column(Text, nullable=False, doc="Detailed log message.")
    details = Column(Text, nullable=True, doc="Optional JSON or text details about the event.")

    # Relationships
    settlement = relationship("Settlement", back_populates="logs")

# --- Pydantic Schemas ---

# Base Schemas
class SettlementBase(BaseModel):
    """Base schema for Settlement data."""
    settlement_date: datetime = Field(..., description="The date the settlement is effective.")
    amount: float = Field(..., gt=0, description="Total settled amount.")
    currency: str = Field(..., min_length=3, max_length=3, description="Currency of the settlement (e.g., USD, EUR).")
    transaction_count: int = Field(0, ge=0, description="Number of transactions included in the settlement.")
    external_reference_id: Optional[str] = Field(None, max_length=255, description="ID from an external system for reconciliation.")

class SettlementLogBase(BaseModel):
    """Base schema for SettlementLog data."""
    level: LogLevel = LogLevel.INFO
    message: str = Field(..., description="Detailed log message.")
    details: Optional[str] = Field(None, description="Optional JSON or text details about the event.")

# Create Schemas
class SettlementCreate(SettlementBase):
    """Schema for creating a new Settlement."""
    # Status can be optionally set on creation, defaults to PENDING in model
    status: SettlementStatus = SettlementStatus.PENDING

class SettlementLogCreate(SettlementLogBase):
    """Schema for creating a new SettlementLog entry."""
    pass

# Update Schemas
class SettlementUpdate(BaseModel):
    """Schema for updating an existing Settlement."""
    status: Optional[SettlementStatus] = Field(None, description="New status of the settlement.")
    amount: Optional[float] = Field(None, gt=0, description="Updated settled amount.")
    transaction_count: Optional[int] = Field(None, ge=0, description="Updated number of transactions.")
    external_reference_id: Optional[str] = Field(None, max_length=255, description="Updated external reference ID.")

# Response Schemas
class SettlementLogResponse(SettlementLogBase):
    """Response schema for a SettlementLog entry."""
    id: int
    settlement_id: int
    timestamp: datetime

    class Config:
        from_attributes = True

class SettlementResponse(SettlementBase):
    """Response schema for a Settlement record."""
    id: int
    status: SettlementStatus
    created_at: datetime
    updated_at: datetime
    
    # Include logs in the response for detail view
    logs: List[SettlementLogResponse] = []

    class Config:
        from_attributes = True
        use_enum_values = True # Use string values for enums in response
