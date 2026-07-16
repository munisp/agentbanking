import datetime
from typing import List, Optional

from pydantic import BaseModel, Field
from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

# --- SQLAlchemy Base and Models ---

Base = declarative_base()

class PushNotification(Base):
    """
    SQLAlchemy model for a Push Notification record.
    """
    __tablename__ = "push_notifications"

    id = Column(Integer, primary_key=True, index=True)
    
    # Target information
    user_id = Column(Integer, nullable=False, index=True, doc="ID of the target user.")
    device_token = Column(String(255), nullable=False, doc="The device token for the push notification service (e.g., FCM, APNS).")
    platform = Column(Enum("ios", "android", "web", name="platform_enum"), nullable=False, doc="The target platform for the notification.")
    
    # Notification content
    title = Column(String(255), nullable=False, doc="The title of the notification.")
    body = Column(Text, nullable=False, doc="The main content/body of the notification.")
    data = Column(JSONB, nullable=True, doc="Additional JSON payload data for the notification.")
    
    # Status and timestamps
    status = Column(Enum("pending", "sent", "failed", "delivered", "read", name="status_enum"), default="pending", nullable=False, index=True, doc="Current status of the notification.")
    sent_at = Column(DateTime(timezone=True), nullable=True, doc="Timestamp when the notification was successfully sent to the provider.")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    logs = relationship("PushNotificationLog", back_populates="notification", cascade="all, delete-orphan")

    # Constraints and Indexes
    __table_args__ = (
        Index("ix_push_notification_user_platform", user_id, platform),
    )

    def __repr__(self):
        return f"<PushNotification(id={self.id}, user_id={self.user_id}, status='{self.status}')>"

class PushNotificationLog(Base):
    """
    SQLAlchemy model for logging activities related to a Push Notification.
    """
    __tablename__ = "push_notification_logs"

    id = Column(Integer, primary_key=True, index=True)
    notification_id = Column(Integer, ForeignKey("push_notifications.id"), nullable=False, index=True)
    
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    event = Column(String(100), nullable=False, doc="The type of event (e.g., 'send_attempt', 'provider_response', 'delivery_receipt').")
    details = Column(JSONB, nullable=True, doc="Detailed information about the event, such as error messages or provider IDs.")
    
    # Relationships
    notification = relationship("PushNotification", back_populates="logs")

    def __repr__(self):
        return f"<PushNotificationLog(id={self.id}, notification_id={self.notification_id}, event='{self.event}')>"

# --- Pydantic Schemas ---

# Base Schemas
class PushNotificationBase(BaseModel):
    """Base schema for PushNotification."""
    user_id: int = Field(..., description="ID of the target user.")
    device_token: str = Field(..., max_length=255, description="The device token for the push notification service.")
    platform: str = Field(..., description="The target platform for the notification.", pattern="^(ios|android|web)$")
    title: str = Field(..., max_length=255, description="The title of the notification.")
    body: str = Field(..., description="The main content/body of the notification.")
    data: Optional[dict] = Field(None, description="Additional JSON payload data.")

class PushNotificationLogBase(BaseModel):
    """Base schema for PushNotificationLog."""
    event: str = Field(..., max_length=100, description="The type of event.")
    details: Optional[dict] = Field(None, description="Detailed information about the event.")

# Create Schemas
class PushNotificationCreate(PushNotificationBase):
    """Schema for creating a new PushNotification."""
    # Status is typically 'pending' on creation, but allow override if needed
    status: Optional[str] = Field("pending", description="Initial status of the notification.")

class PushNotificationLogCreate(PushNotificationLogBase):
    """Schema for creating a new PushNotificationLog."""
    notification_id: int = Field(..., description="ID of the associated PushNotification.")

# Update Schemas
class PushNotificationUpdate(BaseModel):
    """Schema for updating an existing PushNotification."""
    device_token: Optional[str] = Field(None, max_length=255, description="The device token for the push notification service.")
    title: Optional[str] = Field(None, max_length=255, description="The title of the notification.")
    body: Optional[str] = Field(None, description="The main content/body of the notification.")
    data: Optional[dict] = Field(None, description="Additional JSON payload data.")
    status: Optional[str] = Field(None, description="Current status of the notification.", pattern="^(pending|sent|failed|delivered|read)$")
    sent_at: Optional[datetime.datetime] = Field(None, description="Timestamp when the notification was successfully sent.")

# Response Schemas
class PushNotificationResponse(PushNotificationBase):
    """Schema for returning a PushNotification."""
    id: int
    status: str
    sent_at: Optional[datetime.datetime]
    created_at: datetime.datetime
    updated_at: datetime.datetime
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime.datetime: lambda dt: dt.isoformat(),
        }

class PushNotificationLogResponse(PushNotificationLogBase):
    """Schema for returning a PushNotificationLog."""
    id: int
    notification_id: int
    timestamp: datetime.datetime

    class Config:
        from_attributes = True
        json_encoders = {
            datetime.datetime: lambda dt: dt.isoformat(),
        }

class PushNotificationWithLogsResponse(PushNotificationResponse):
    """Schema for returning a PushNotification with its associated logs."""
    logs: List[PushNotificationLogResponse] = []
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime.datetime: lambda dt: dt.isoformat(),
        }

# Utility function to create tables (for initial setup)
def create_all_tables(engine):
    """Creates all tables defined in Base metadata."""
    Base.metadata.create_all(bind=engine)
