import uuid
from datetime import datetime
from typing import Optional, List

from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Index, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, declarative_base
from pydantic import BaseModel, Field

# --- SQLAlchemy Base ---

Base = declarative_base()

# --- SQLAlchemy Models ---

class CommunicationEvent(Base):
    """
    Represents a single communication event in the unified communication service.
    This could be a chat message, a call log entry, an email record, etc.
    """
    __tablename__ = "communication_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    event_type = Column(String(50), nullable=False, doc="Type of communication (e.g., CHAT, CALL, EMAIL)")
    sender_id = Column(UUID(as_uuid=True), nullable=False, index=True, doc="ID of the sender/initiator")
    recipient_id = Column(UUID(as_uuid=True), nullable=False, index=True, doc="ID of the recipient/target")
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True, doc="Time the event occurred")
    content = Column(Text, nullable=True, doc="The main content or details of the event (e.g., message text, call duration)")
    status = Column(String(50), nullable=False, default="SENT", doc="Current status of the event (e.g., SENT, DELIVERED, READ, FAILED)")
    is_archived = Column(Boolean, default=False, nullable=False, doc="Flag to soft-delete or archive the event")

    # Relationship to activity log
    logs = relationship("CommunicationActivityLog", back_populates="event", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_event_sender_recipient", sender_id, recipient_id),
    )

class CommunicationActivityLog(Base):
    """
    Activity log for tracking changes or important milestones for a CommunicationEvent.
    """
    __tablename__ = "communication_activity_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(UUID(as_uuid=True), ForeignKey("communication_events.id"), nullable=False, index=True)
    activity_type = Column(String(100), nullable=False, doc="Type of activity (e.g., STATUS_UPDATE, CONTENT_EDIT)")
    details = Column(Text, nullable=True, doc="Detailed description of the activity")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    # Relationship back to the main event
    event = relationship("CommunicationEvent", back_populates="logs")

# --- Pydantic Schemas ---

# Base Schema
class CommunicationEventBase(BaseModel):
    """Base schema for communication event data."""
    event_type: str = Field(..., max_length=50, description="Type of communication (e.g., CHAT, CALL, EMAIL)")
    sender_id: uuid.UUID = Field(..., description="ID of the sender/initiator")
    recipient_id: uuid.UUID = Field(..., description="ID of the recipient/target")
    content: Optional[str] = Field(None, description="The main content or details of the event")
    status: str = Field("SENT", max_length=50, description="Current status of the event")

# Schema for creating a new event
class CommunicationEventCreate(CommunicationEventBase):
    """Schema for creating a new communication event."""
    pass

# Schema for updating an existing event
class CommunicationEventUpdate(CommunicationEventBase):
    """Schema for updating an existing communication event."""
    event_type: Optional[str] = Field(None, max_length=50)
    sender_id: Optional[uuid.UUID] = None
    recipient_id: Optional[uuid.UUID] = None
    status: Optional[str] = Field(None, max_length=50)
    is_archived: Optional[bool] = False

# Schema for the activity log response
class CommunicationActivityLogResponse(BaseModel):
    """Response schema for an activity log entry."""
    id: uuid.UUID
    event_id: uuid.UUID
    activity_type: str
    details: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

# Response Schema
class CommunicationEventResponse(CommunicationEventBase):
    """Full response schema for a communication event."""
    id: uuid.UUID
    timestamp: datetime
    is_archived: bool
    logs: List[CommunicationActivityLogResponse] = Field([], description="List of related activity logs")

    class Config:
        from_attributes = True
