import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Text, Index, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
import enum

# --- SQLAlchemy Base ---
Base = declarative_base()

# --- Enums ---
class MessageStatus(enum.Enum):
    """
    Enum for the status of a WhatsApp message.
    """
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    QUEUED = "queued"

class ActivityType(enum.Enum):
    """
    Enum for the type of activity in the log.
    """
    MESSAGE_SENT = "message_sent"
    MESSAGE_RECEIVED = "message_received"
    STATUS_UPDATE = "status_update"
    ERROR = "error"
    CONFIGURATION_CHANGE = "configuration_change"

# --- Database Models ---

class WhatsAppMessage(Base):
    """
    SQLAlchemy model for a WhatsApp message managed by the service.
    """
    __tablename__ = "whatsapp_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    external_message_id = Column(String, unique=True, nullable=True, doc="ID provided by the WhatsApp API")
    sender_phone_number = Column(String, nullable=False, index=True, doc="The sender's phone number (e.g., the service's number)")
    recipient_phone_number = Column(String, nullable=False, index=True, doc="The recipient's phone number")
    message_type = Column(String, nullable=False, default="text", doc="Type of message (e.g., text, image, template)")
    content = Column(Text, nullable=False, doc="The actual content of the message (text, media URL, template data)")
    status = Column(SQLEnum(MessageStatus), default=MessageStatus.QUEUED, nullable=False, index=True, doc="Current status of the message")
    is_incoming = Column(Boolean, default=False, nullable=False, doc="True if the message was received, False if sent")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    activity_logs = relationship("WhatsAppActivityLog", back_populates="message", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_whatsapp_message_status_created", status, created_at),
    )

class WhatsAppActivityLog(Base):
    """
    SQLAlchemy model for logging activities related to the WhatsApp service.
    """
    __tablename__ = "whatsapp_activity_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    message_id = Column(UUID(as_uuid=True), ForeignKey("whatsapp_messages.id"), nullable=True, index=True, doc="Foreign key to the related message")
    activity_type = Column(SQLEnum(ActivityType), nullable=False, index=True, doc="Type of activity logged")
    details = Column(Text, nullable=False, doc="Detailed description or JSON payload of the activity")
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    message = relationship("WhatsAppMessage", back_populates="activity_logs")

    __table_args__ = (
        Index("idx_whatsapp_log_type_timestamp", activity_type, timestamp),
    )

# --- Pydantic Schemas ---

# Base Schemas
class WhatsAppMessageBase(BaseModel):
    """Base schema for WhatsAppMessage."""
    sender_phone_number: str = Field(..., description="The sender's phone number.")
    recipient_phone_number: str = Field(..., description="The recipient's phone number.")
    message_type: str = Field("text", description="Type of message (e.g., text, image, template).")
    content: str = Field(..., description="The content of the message.")
    is_incoming: bool = Field(False, description="True if the message was received, False if sent.")

class WhatsAppActivityLogBase(BaseModel):
    """Base schema for WhatsAppActivityLog."""
    message_id: Optional[uuid.UUID] = Field(None, description="ID of the related message.")
    activity_type: ActivityType = Field(..., description="Type of activity logged.")
    details: str = Field(..., description="Detailed description or JSON payload of the activity.")

# Create Schemas
class WhatsAppMessageCreate(WhatsAppMessageBase):
    """Schema for creating a new WhatsAppMessage."""
    # external_message_id is typically set by the external API, so it's optional on creation
    external_message_id: Optional[str] = Field(None, description="ID provided by the WhatsApp API.")
    status: MessageStatus = Field(MessageStatus.QUEUED, description="Initial status of the message.")

class WhatsAppActivityLogCreate(WhatsAppActivityLogBase):
    """Schema for creating a new WhatsAppActivityLog."""
    pass

# Update Schemas
class WhatsAppMessageUpdate(BaseModel):
    """Schema for updating an existing WhatsAppMessage."""
    external_message_id: Optional[str] = Field(None, description="ID provided by the WhatsApp API.")
    status: Optional[MessageStatus] = Field(None, description="Current status of the message.")
    content: Optional[str] = Field(None, description="The content of the message.")
    message_type: Optional[str] = Field(None, description="Type of message.")

# Response Schemas
class WhatsAppMessageResponse(WhatsAppMessageBase):
    """Response schema for WhatsAppMessage."""
    id: uuid.UUID
    external_message_id: Optional[str]
    status: MessageStatus
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
        use_enum_values = True

class WhatsAppActivityLogResponse(WhatsAppActivityLogBase):
    """Response schema for WhatsAppActivityLog."""
    id: uuid.UUID
    timestamp: datetime

    class Config:
        orm_mode = True
        use_enum_values = True

class WhatsAppMessageWithLogsResponse(WhatsAppMessageResponse):
    """Response schema for WhatsAppMessage including its activity logs."""
    activity_logs: List[WhatsAppActivityLogResponse] = Field([], description="List of related activity logs.")

    class Config:
        orm_mode = True
        use_enum_values = True
