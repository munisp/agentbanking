from datetime import datetime
from typing import List, Optional

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Index, Enum, Boolean
from sqlalchemy.orm import relationship, Mapped, mapped_column
from pydantic import BaseModel, Field
from enum import Enum as PyEnum

# --- SQLAlchemy Base and Utility ---
# Assuming a Base is defined elsewhere, for this task, we'll define a minimal one
# to make the file self-contained and functional.
from sqlalchemy.ext.declarative import declarative_base
Base = declarative_base()

class TimestampMixin:
    """Mixin for created_at and updated_at timestamps."""
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

# --- Enums ---
class CommunicationType(PyEnum):
    EMAIL = "email"
    SMS = "sms"
    NOTIFICATION = "notification"

class CommunicationStatus(PyEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    DELIVERED = "delivered"
    READ = "read"

# --- SQLAlchemy Models ---

class Communication(Base, TimestampMixin):
    __tablename__ = "communications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # Core fields
    type: Mapped[CommunicationType] = mapped_column(Enum(CommunicationType), nullable=False, index=True)
    recipient: Mapped[str] = mapped_column(String(255), nullable=False, index=True, comment="Email address, phone number, or user ID")
    sender: Mapped[str] = mapped_column(String(255), nullable=False, default="system", comment="Sender identifier (e.g., system, user_id, service_name)")
    subject: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Status and timing
    status: Mapped[CommunicationStatus] = mapped_column(Enum(CommunicationStatus), nullable=False, default=CommunicationStatus.PENDING, index=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    
    # Metadata
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="JSON string for extra metadata like template name, campaign ID, etc.")

    # Relationships
    logs: Mapped[List["CommunicationLog"]] = relationship("CommunicationLog", back_populates="communication", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_communications_type_status", type, status),
    )

class CommunicationLog(Base, TimestampMixin):
    __tablename__ = "communication_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # Foreign Key
    communication_id: Mapped[int] = mapped_column(ForeignKey("communications.id"), nullable=False, index=True)
    
    # Log details
    event: Mapped[str] = mapped_column(String(100), nullable=False, comment="e.g., 'created', 'attempted_send', 'delivery_success', 'hard_bounce'")
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="Detailed log message or error stack trace")
    
    # Relationship
    communication: Mapped["Communication"] = relationship("Communication", back_populates="logs")

    __table_args__ = (
        Index("ix_communication_logs_event", event),
    )

# --- Pydantic Schemas ---

# Base Schema for common fields
class CommunicationBase(BaseModel):
    type: CommunicationType = Field(..., description="Type of communication (email, sms, notification).")
    recipient: str = Field(..., max_length=255, description="Target address (email, phone number, or user ID).")
    sender: str = Field("system", max_length=255, description="Sender identifier.")
    subject: Optional[str] = Field(None, max_length=512, description="Subject line for the communication.")
    body: str = Field(..., description="The content/body of the communication.")
    metadata_json: Optional[str] = Field(None, description="JSON string for extra metadata.")

# Schema for creating a new communication
class CommunicationCreate(CommunicationBase):
    pass

# Schema for updating an existing communication
class CommunicationUpdate(BaseModel):
    status: Optional[CommunicationStatus] = Field(None, description="The current status of the communication.")
    subject: Optional[str] = Field(None, max_length=512, description="Subject line for the communication.")
    body: Optional[str] = Field(None, description="The content/body of the communication.")
    metadata_json: Optional[str] = Field(None, description="JSON string for extra metadata.")

# Schema for log response
class CommunicationLogResponse(BaseModel):
    id: int
    communication_id: int
    event: str
    details: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Schema for returning a communication record
class CommunicationResponse(CommunicationBase):
    id: int
    status: CommunicationStatus
    sent_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    logs: List[CommunicationLogResponse] = Field([], description="List of activity logs for this communication.")

    class Config:
        from_attributes = True

# Schema for sending a new communication (business-specific)
class CommunicationSend(CommunicationBase):
    # This schema is identical to CommunicationCreate but is named differently
    # to reflect its use in a business-specific endpoint (e.g., POST /send)
    pass
