import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field
from sqlalchemy import (
    Column,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

# --- SQLAlchemy Base Setup ---

Base = declarative_base()

# --- Enums ---

class DisputeStatus(str, Enum):
    """Possible statuses for a dispute."""
    OPEN = "OPEN"
    IN_REVIEW = "IN_REVIEW"
    AWAITING_EVIDENCE = "AWAITING_EVIDENCE"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"

class ActivityType(str, Enum):
    """Types of activities that can occur on a dispute."""
    CREATED = "CREATED"
    STATUS_UPDATE = "STATUS_UPDATE"
    COMMENT = "COMMENT"
    EVIDENCE_ADDED = "EVIDENCE_ADDED"
    ASSIGNED = "ASSIGNED"
    RESOLUTION_APPLIED = "RESOLUTION_APPLIED"

# --- SQLAlchemy Models ---

class Dispute(Base):
    """
    Main model for a dispute.
    """
    __tablename__ = "disputes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    status = Column(SQLEnum(DisputeStatus), default=DisputeStatus.OPEN, nullable=False, index=True)
    category = Column(String(100), nullable=False, index=True)
    
    # Foreign Keys to hypothetical external services (e.g., User/Account service)
    submitter_id = Column(Integer, nullable=False, index=True)
    assigned_to_id = Column(Integer, nullable=True, index=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    resolved_at = Column(DateTime, nullable=True)

    # Relationship to activity log
    activity_log = relationship(
        "DisputeActivityLog", 
        back_populates="dispute", 
        cascade="all, delete-orphan", 
        order_by="DisputeActivityLog.created_at"
    )

    __table_args__ = (
        # Unique constraint on title (optional, but good for business context)
        # UniqueConstraint('title', name='uq_dispute_title'),
        # Index for efficient lookup by submitter and status
        Index('ix_submitter_status', 'submitter_id', 'status'),
    )

class DisputeActivityLog(Base):
    """
    Activity log for tracking changes and events related to a dispute.
    """
    __tablename__ = "dispute_activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    dispute_id = Column(UUID(as_uuid=True), ForeignKey("disputes.id"), nullable=False, index=True)
    
    activity_type = Column(SQLEnum(ActivityType), nullable=False)
    details = Column(Text, nullable=True) # JSON or text details about the activity
    
    # Foreign Key to hypothetical external service (e.g., User/Account service)
    actor_id = Column(Integer, nullable=False, index=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationship back to the dispute
    dispute = relationship("Dispute", back_populates="activity_log")

    __table_args__ = (
        # Index for efficient lookup of activities for a specific dispute
        Index('ix_dispute_activity_log', 'dispute_id', 'created_at'),
    )

# --- Pydantic Schemas ---

# Base Schemas (Shared properties)
class DisputeBase(BaseModel):
    """Base schema for Dispute, containing common fields."""
    title: str = Field(..., max_length=255, description="A concise title for the dispute.")
    description: str = Field(..., description="Detailed description of the dispute.")
    category: str = Field(..., max_length=100, description="The category of the dispute (e.g., PAYMENT, SERVICE).")

# Create Schema (Properties received on creation)
class DisputeCreate(DisputeBase):
    """Schema for creating a new Dispute."""
    submitter_id: int = Field(..., description="ID of the user submitting the dispute.")
    # assigned_to_id is optional on creation

# Update Schema (Properties received on update)
class DisputeUpdate(DisputeBase):
    """Schema for updating an existing Dispute."""
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    category: Optional[str] = Field(None, max_length=100)
    status: Optional[DisputeStatus] = None
    assigned_to_id: Optional[int] = None

# Activity Log Schemas
class DisputeActivityLogBase(BaseModel):
    """Base schema for DisputeActivityLog."""
    activity_type: ActivityType
    details: Optional[str] = None
    actor_id: int = Field(..., description="ID of the user who performed the activity.")

class DisputeActivityLogResponse(DisputeActivityLogBase):
    """Response schema for DisputeActivityLog."""
    id: int
    dispute_id: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True

# Response Schema (Properties returned to client)
class DisputeResponse(DisputeBase):
    """Full response schema for a Dispute."""
    id: uuid.UUID
    status: DisputeStatus
    submitter_id: int
    assigned_to_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None
    
    # Nested relationship
    activity_log: List[DisputeActivityLogResponse] = []

    class Config:
        from_attributes = True
        # Allow population by field name for UUIDs
        json_encoders = {
            uuid.UUID: str
        }

# Schema for updating only the status
class DisputeStatusUpdate(BaseModel):
    """Schema for updating only the status of a Dispute."""
    status: DisputeStatus = Field(..., description="The new status of the dispute.")
    actor_id: int = Field(..., description="ID of the user performing the status update.")
    details: Optional[str] = Field(None, description="Optional details about the status change.")
