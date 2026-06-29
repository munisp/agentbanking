import datetime
from typing import List, Optional

from pydantic import BaseModel, Field
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Boolean,
    ForeignKey,
    Text,
    Index,
)
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func

# Base class for models
Base = declarative_base()


class TelegramChat(Base):
    """
    SQLAlchemy model for storing Telegram chat information.
    Represents a user, group, or channel that the bot interacts with.
    """

    __tablename__ = "telegram_chats"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(
        String, unique=True, nullable=False, index=True, comment="Unique Telegram chat ID"
    )
    chat_type = Column(
        String, nullable=False, comment="Type of chat (e.g., 'private', 'group', 'channel')"
    )
    title = Column(
        String, nullable=True, comment="Title for group/channel, or full name for private chat"
    )
    username = Column(
        String, nullable=True, index=True, comment="Username of the chat (if available)"
    )
    is_active = Column(
        Boolean, default=True, nullable=False, comment="Whether the bot is currently active in the chat"
    )
    settings_json = Column(
        Text, default="{}", nullable=False, comment="JSON string for custom chat settings"
    )
    created_at = Column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationship to activity log
    activities = relationship(
        "ActivityLog", back_populates="chat", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_telegram_chats_chat_id_type", chat_id, chat_type),
    )


class ActivityLog(Base):
    """
    SQLAlchemy model for logging activities related to Telegram chats.
    """

    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(
        Integer, ForeignKey("telegram_chats.id"), nullable=False, index=True
    )
    activity_type = Column(
        String, nullable=False, comment="Type of activity (e.g., 'MESSAGE_RECEIVED', 'BOT_ADDED', 'SETTINGS_UPDATED')"
    )
    description = Column(
        Text, nullable=True, comment="Detailed description or payload of the activity"
    )
    timestamp = Column(
        DateTime(timezone=True), default=func.now(), nullable=False, index=True
    )

    # Relationship to TelegramChat
    chat = relationship("TelegramChat", back_populates="activities")


# --- Pydantic Schemas for TelegramChat ---

class TelegramChatBase(BaseModel):
    """Base schema for TelegramChat, containing common fields."""
    chat_id: str = Field(..., description="Unique Telegram chat ID.")
    chat_type: str = Field(..., description="Type of chat (e.g., 'private', 'group', 'channel').")
    title: Optional[str] = Field(None, description="Title for group/channel, or full name for private chat.")
    username: Optional[str] = Field(None, description="Username of the chat (if available).")
    is_active: bool = Field(True, description="Whether the bot is currently active in the chat.")
    settings_json: str = Field("{}", description="JSON string for custom chat settings.")


class TelegramChatCreate(TelegramChatBase):
    """Schema for creating a new TelegramChat record."""
    # Inherits all fields from TelegramChatBase
    pass


class TelegramChatUpdate(BaseModel):
    """Schema for updating an existing TelegramChat record."""
    title: Optional[str] = Field(None, description="Title for group/channel, or full name for private chat.")
    username: Optional[str] = Field(None, description="Username of the chat (if available).")
    is_active: Optional[bool] = Field(None, description="Whether the bot is currently active in the chat.")
    settings_json: Optional[str] = Field(None, description="JSON string for custom chat settings.")


class TelegramChatResponse(TelegramChatBase):
    """Schema for returning a TelegramChat record."""
    id: int = Field(..., description="Internal database ID.")
    created_at: datetime.datetime = Field(..., description="Timestamp of creation.")
    updated_at: datetime.datetime = Field(..., description="Timestamp of last update.")

    class Config:
        from_attributes = True


# --- Pydantic Schemas for ActivityLog ---

class ActivityLogBase(BaseModel):
    """Base schema for ActivityLog."""
    chat_id: int = Field(..., description="Foreign key to the TelegramChat ID.")
    activity_type: str = Field(..., description="Type of activity (e.g., 'MESSAGE_RECEIVED').")
    description: Optional[str] = Field(None, description="Detailed description or payload of the activity.")


class ActivityLogCreate(ActivityLogBase):
    """Schema for creating a new ActivityLog record."""
    pass


class ActivityLogResponse(ActivityLogBase):
    """Schema for returning an ActivityLog record."""
    id: int = Field(..., description="Internal database ID.")
    timestamp: datetime.datetime = Field(..., description="Timestamp of the activity.")

    class Config:
        from_attributes = True


class TelegramChatWithActivitiesResponse(TelegramChatResponse):
    """Schema for returning a TelegramChat record with its associated activities."""
    activities: List[ActivityLogResponse] = Field(..., description="List of associated activity logs.")
