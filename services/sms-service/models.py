from datetime import datetime
from typing import Optional, List
from enum import Enum

from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, Index
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from pydantic import BaseModel, Field

# Assuming Base is imported from config.py, but for a standalone file, we define it here
# In a real project, this would be imported from a shared config/db file.
Base = declarative_base()

class SMSStatus(str, Enum):
    """
    Enum for the status of an SMS message.
    """
    PENDING = "PENDING"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"

class SMSMessage(Base):
    """
    SQLAlchemy model for an SMS message.
    """
    __tablename__ = "sms_messages"

    id = Column(Integer, primary_key=True, index=True)
    recipient_number = Column(String(20), nullable=False, index=True)
    sender_id = Column(String(50), nullable=True) # e.g., a short code or alphanumeric sender ID
    message_body = Column(Text, nullable=False)
    status = Column(String(20), default=SMSStatus.PENDING.value, nullable=False, index=True)
    scheduled_time = Column(DateTime, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationship to activity log
    logs = relationship("SMSActivityLog", back_populates="sms_message", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_sms_recipient_status", "recipient_number", "status"),
    )

class SMSActivityLog(Base):
    """
    SQLAlchemy model for logging activities related to an SMS message.
    """
    __tablename__ = "sms_activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    sms_message_id = Column(Integer, ForeignKey("sms_messages.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    activity_type = Column(String(50), nullable=False) # e.g., "STATUS_UPDATE", "CREATION", "ERROR"
    details = Column(Text, nullable=True)

    # Relationship to SMSMessage
    sms_message = relationship("SMSMessage", back_populates="logs")

    __table_args__ = (
        Index("idx_log_sms_id_type", "sms_message_id", "activity_type"),
    )

# --- Pydantic Schemas ---

class SMSMessageBase(BaseModel):
    """Base schema for SMS message data."""
    recipient_number: str = Field(..., max_length=20, example="+15551234567")
    sender_id: Optional[str] = Field(None, max_length=50, example="MyCompany")
    message_body: str = Field(..., example="Your verification code is 12345.")
    scheduled_time: Optional[datetime] = Field(None, example="2025-11-05T10:00:00")

class SMSMessageCreate(SMSMessageBase):
    """Schema for creating a new SMS message."""
    pass

class SMSMessageUpdate(BaseModel):
    """Schema for updating an existing SMS message."""
    status: Optional[SMSStatus] = Field(None, example=SMSStatus.CANCELED)
    scheduled_time: Optional[datetime] = Field(None, example="2025-11-05T11:00:00")
    
    class Config:
        use_enum_values = True

class SMSActivityLogResponse(BaseModel):
    """Response schema for an SMS activity log entry."""
    id: int
    sms_message_id: int
    timestamp: datetime
    activity_type: str
    details: Optional[str]

    class Config:
        from_attributes = True

class SMSMessageResponse(SMSMessageBase):
    """Response schema for a full SMS message object."""
    id: int
    status: SMSStatus
    sent_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    logs: List[SMSActivityLogResponse] = []

    class Config:
        from_attributes = True
        use_enum_values = True
