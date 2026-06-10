import enum
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field
from sqlalchemy import (
    Column, Integer, String, DateTime, Boolean, ForeignKey, Enum, Text, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

# Base for SQLAlchemy models
Base = declarative_base()

# --- Enums ---

class MessageStatus(enum.Enum):
    """
    Status of a message.
    """
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"

class ActivityType(enum.Enum):
    """
    Type of activity logged.
    """
    MESSAGE_CREATED = "message_created"
    MESSAGE_UPDATED = "message_updated"
    MESSAGE_DELETED = "message_deleted"
    STATUS_CHANGED = "status_changed"
    SYSTEM_EVENT = "system_event"

# --- SQLAlchemy Models ---

class Message(Base):
    """
    Represents a single message in the messenger service.
    """
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, nullable=False, index=True, doc="ID of the user who sent the message")
    recipient_id = Column(Integer, nullable=False, index=True, doc="ID of the user who is the primary recipient")
    content = Column(Text, nullable=False, doc="The text content of the message")
    status = Column(Enum(MessageStatus), default=MessageStatus.SENT, nullable=False, doc="Current status of the message")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, doc="Timestamp of message creation")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False, doc="Timestamp of last update")
    is_deleted = Column(Boolean, default=False, nullable=False, doc="Soft delete flag")

    # Relationships
    activity_logs = relationship("ActivityLog", back_populates="message", cascade="all, delete-orphan")

    # Constraints and Indexes
    __table_args__ = (
        Index('idx_sender_recipient_created', sender_id, recipient_id, created_at.desc()),
    )

    def __repr__(self):
        return f"<Message(id={self.id}, sender_id={self.sender_id}, recipient_id={self.recipient_id}, status='{self.status.value}')>"

class ActivityLog(Base):
    """
    Logs activities related to messages, such as status changes.
    """
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("messages.id"), nullable=False, index=True, doc="Foreign key to the Message table")
    activity_type = Column(Enum(ActivityType), nullable=False, doc="Type of activity")
    details = Column(String(512), nullable=True, doc="Additional details about the activity")
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, doc="Timestamp of the activity")
    
    # Relationships
    message = relationship("Message", back_populates="activity_logs")

    def __repr__(self):
        return f"<ActivityLog(id={self.id}, message_id={self.message_id}, type='{self.activity_type.value}')>"

# --- Pydantic Schemas ---

class MessageBase(BaseModel):
    """Base schema for message data."""
    sender_id: int = Field(..., description="ID of the user who sent the message.")
    recipient_id: int = Field(..., description="ID of the user who is the primary recipient.")
    content: str = Field(..., description="The text content of the message.")

class MessageCreate(MessageBase):
    """Schema for creating a new message."""
    pass

class MessageUpdate(BaseModel):
    """Schema for updating an existing message."""
    content: Optional[str] = Field(None, description="New text content of the message.")
    status: Optional[MessageStatus] = Field(None, description="New status of the message.")

class MessageResponse(MessageBase):
    """Schema for returning a message response."""
    id: int
    status: MessageStatus
    created_at: datetime
    updated_at: datetime
    is_deleted: bool

    class Config:
        from_attributes = True
        use_enum_values = True

class ActivityLogResponse(BaseModel):
    """Schema for returning an activity log entry."""
    id: int
    message_id: int
    activity_type: ActivityType
    details: Optional[str]
    timestamp: datetime

    class Config:
        from_attributes = True
        use_enum_values = True

class MessageWithLogsResponse(MessageResponse):
    """Schema for returning a message with its activity logs."""
    activity_logs: List[ActivityLogResponse] = Field(..., description="List of activity logs for this message.")
