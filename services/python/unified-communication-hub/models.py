import datetime
from typing import List, Optional

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    Index,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Session
from pydantic import BaseModel, Field
from enum import Enum as PyEnum

# --- SQLAlchemy Base Setup ---

Base = declarative_base()

# --- Enums ---

class EventType(str, PyEnum):
    """
    Defines the type of communication event.
    """
    MESSAGE = "message"
    CALL = "call"
    MEETING = "meeting"
    NOTIFICATION = "notification"

class EventStatus(str, PyEnum):
    """
    Defines the status of a communication event.
    """
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    SCHEDULED = "scheduled"

class LogAction(str, PyEnum):
    """
    Defines the type of action logged in the ActivityLog.
    """
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    STATUS_CHANGE = "status_change"
    ARCHIVE = "archive"

# --- SQLAlchemy Models ---

class CommunicationEvent(Base):
    """
    Represents a single communication event in the unified hub.
    """
    __tablename__ = "communication_events"

    id = Column(Integer, primary_key=True, index=True)
    
    event_type = Column(Enum(EventType), nullable=False, index=True, default=EventType.MESSAGE)
    
    sender_id = Column(Integer, nullable=False, index=True)
    recipient_id = Column(Integer, nullable=False, index=True)
    
    content = Column(Text, nullable=False)
    
    status = Column(Enum(EventStatus), nullable=False, default=EventStatus.SENT)
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    # Relationship to ActivityLog
    activity_logs = relationship("ActivityLog", back_populates="event", cascade="all, delete-orphan")

    # Composite Index for efficient querying of conversations between two users
    __table_args__ = (
        Index("idx_sender_recipient", "sender_id", "recipient_id"),
        Index("idx_recipient_sender", "recipient_id", "sender_id"),
    )

    def __repr__(self):
        return f"<CommunicationEvent(id={self.id}, type='{self.event_type}', status='{self.status}')>"


class ActivityLog(Base):
    """
    Tracks all significant actions and changes related to communication events.
    """
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    
    event_id = Column(Integer, ForeignKey("communication_events.id"), nullable=False, index=True)
    
    action = Column(Enum(LogAction), nullable=False)
    
    user_id = Column(Integer, nullable=False) # The user who performed the action
    
    details = Column(String(255), nullable=True)
    
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # Relationship back to CommunicationEvent
    event = relationship("CommunicationEvent", back_populates="activity_logs")

    def __repr__(self):
        return f"<ActivityLog(id={self.id}, action='{self.action}', event_id={self.event_id})>"

# --- Pydantic Schemas ---

# Base Schemas
class CommunicationEventBase(BaseModel):
    """Base schema for a communication event."""
    event_type: EventType = Field(..., description="The type of communication event.")
    sender_id: int = Field(..., gt=0, description="ID of the user who sent the event.")
    recipient_id: int = Field(..., gt=0, description="ID of the user who is the recipient.")
    content: str = Field(..., min_length=1, description="The content of the communication event.")

class ActivityLogBase(BaseModel):
    """Base schema for an activity log entry."""
    event_id: int = Field(..., gt=0, description="ID of the communication event this log relates to.")
    action: LogAction = Field(..., description="The action performed.")
    user_id: int = Field(..., gt=0, description="ID of the user who performed the action.")
    details: Optional[str] = Field(None, max_length=255, description="Additional details about the action.")

# Create Schemas (Input)
class CommunicationEventCreate(CommunicationEventBase):
    """Schema for creating a new communication event."""
    # Status can be optionally set on creation (e.g., for scheduled events)
    status: Optional[EventStatus] = EventStatus.SENT

class ActivityLogCreate(ActivityLogBase):
    """Schema for creating a new activity log entry."""
    pass

# Update Schemas (Input)
class CommunicationEventUpdate(BaseModel):
    """Schema for updating an existing communication event."""
    content: Optional[str] = Field(None, min_length=1, description="New content for the event.")
    status: Optional[EventStatus] = Field(None, description="New status for the event.")
    # Note: sender_id, recipient_id, and event_type are typically immutable after creation

# Response Schemas (Output)
class ActivityLogResponse(ActivityLogBase):
    """Schema for returning an activity log entry."""
    id: int
    timestamp: datetime.datetime

    class Config:
        from_attributes = True

class CommunicationEventResponse(CommunicationEventBase):
    """Schema for returning a communication event."""
    id: int
    status: EventStatus
    created_at: datetime.datetime
    updated_at: datetime.datetime
    
    # Optional field to include logs when requested
    activity_logs: List[ActivityLogResponse] = []

    class Config:
        from_attributes = True

# --- Utility Function for Database Initialization ---

def init_db(db_engine):
    """
    Initializes the database by creating all defined tables.
    """
    Base.metadata.create_all(bind=db_engine)
