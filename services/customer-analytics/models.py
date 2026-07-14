"""
SQLAlchemy models and Pydantic schemas for the customer-analytics service.
"""
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Column, Integer, String, DateTime, Float, Text, ForeignKey, Index
from sqlalchemy.orm import relationship, DeclarativeBase
from pydantic import BaseModel, Field, conint

# --- SQLAlchemy Base ---

class Base(DeclarativeBase):
    """Base class which provides automated table name and common columns."""
    pass

# --- SQLAlchemy Models ---

class CustomerAnalytic(Base):
    """
    Represents a key customer analytics record, such as a segment, score, or metric.
    """
    __tablename__ = "customer_analytics"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, index=True, nullable=False, comment="ID of the customer this analytic belongs to")
    analytic_type = Column(String(50), index=True, nullable=False, comment="Type of analytic (e.g., LTV, Churn_Risk, Segment)")
    value_numeric = Column(Float, nullable=True, comment="Numeric value of the analytic (e.g., LTV score)")
    value_string = Column(String(255), nullable=True, comment="String value of the analytic (e.g., High-Value Segment)")
    last_calculated_at = Column(DateTime, default=datetime.utcnow, comment="Timestamp of when the analytic was last calculated")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship to ActivityLog
    activity_logs = relationship("AnalyticActivityLog", back_populates="analytic", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_customer_analytic_customer_type", "customer_id", "analytic_type", unique=True),
    )

class AnalyticActivityLog(Base):
    """
    Represents an activity log entry related to a specific customer analytic record.
    """
    __tablename__ = "analytic_activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    analytic_id = Column(Integer, ForeignKey("customer_analytics.id"), nullable=False)
    activity_type = Column(String(50), nullable=False, comment="Type of activity (e.g., Recalculated, Manually_Overridden, Archived)")
    details = Column(Text, nullable=True, comment="Detailed description or JSON payload of the activity")
    timestamp = Column(DateTime, default=datetime.utcnow)

    # Relationship back to CustomerAnalytic
    analytic = relationship("CustomerAnalytic", back_populates="activity_logs")

    __table_args__ = (
        Index("ix_analytic_activity_analytic_id", "analytic_id"),
    )

# --- Pydantic Schemas (Base) ---

class CustomerAnalyticBase(BaseModel):
    """Base schema for customer analytic data."""
    customer_id: conint(ge=1) = Field(..., description="ID of the customer.")
    analytic_type: str = Field(..., max_length=50, description="Type of analytic (e.g., LTV, Churn_Risk).")
    value_numeric: Optional[float] = Field(None, description="Numeric value of the analytic.")
    value_string: Optional[str] = Field(None, max_length=255, description="String value of the analytic.")

class AnalyticActivityLogBase(BaseModel):
    """Base schema for analytic activity log data."""
    activity_type: str = Field(..., max_length=50, description="Type of activity (e.g., Recalculated).")
    details: Optional[str] = Field(None, description="Detailed description of the activity.")

# --- Pydantic Schemas (Create/Update) ---

class CustomerAnalyticCreate(CustomerAnalyticBase):
    """Schema for creating a new customer analytic record."""
    pass

class CustomerAnalyticUpdate(CustomerAnalyticBase):
    """Schema for updating an existing customer analytic record."""
    customer_id: Optional[conint(ge=1)] = Field(None, description="ID of the customer.")
    analytic_type: Optional[str] = Field(None, max_length=50, description="Type of analytic.")

class AnalyticActivityLogCreate(AnalyticActivityLogBase):
    """Schema for creating a new activity log entry."""
    analytic_id: conint(ge=1) = Field(..., description="ID of the customer analytic record.")

# --- Pydantic Schemas (Response) ---

class AnalyticActivityLogResponse(AnalyticActivityLogBase):
    """Response schema for an analytic activity log entry."""
    id: int
    analytic_id: int
    timestamp: datetime

    class Config:
        from_attributes = True

class CustomerAnalyticResponse(CustomerAnalyticBase):
    """Response schema for a customer analytic record."""
    id: int
    last_calculated_at: datetime
    created_at: datetime
    updated_at: datetime
    
    # Nested relationship
    activity_logs: List[AnalyticActivityLogResponse] = []

    class Config:
        from_attributes = True

