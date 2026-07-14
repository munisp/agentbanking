from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    Index,
)
from sqlalchemy.orm import relationship, declarative_base
from pydantic import BaseModel, Field
from pydantic.alias_generators import to_camel

# --- SQLAlchemy Base and Utility ---

Base = declarative_base()

class TimestampMixin:
    """Mixin for adding created_at and updated_at columns."""

    created_at = Column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

# --- SQLAlchemy Models ---

class SharedCommunicationItem(Base, TimestampMixin):
    """
    Represents a piece of content or resource intended for shared communication.
    This could be a shared link, a common message template, or a document.
    """

    __tablename__ = "shared_communication_items"

    id = Column(Integer, primary_key=True, index=True)
    
    # Type of the shared item (e.g., 'link', 'template', 'document')
    item_type = Column(String(50), nullable=False, index=True)
    
    title = Column(String(255), nullable=False, index=True)
    
    # Main content, can be a URL, text, or a JSON string
    content = Column(Text, nullable=False)
    
    # ID of the user or system that created the item
    created_by_user_id = Column(Integer, nullable=False, index=True)
    
    # Flag to indicate if the item is currently active/usable
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    # Relationship to activity log
    activities = relationship(
        "CommunicationActivityLog", back_populates="item", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_shared_item_type_active", item_type, is_active),
    )


class CommunicationActivityLog(Base, TimestampMixin):
    """
    Logs activities related to a SharedCommunicationItem, such as access,
    modification, or sharing events.
    """

    __tablename__ = "communication_activity_log"

    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign key to the shared item
    item_id = Column(
        Integer,
        ForeignKey("shared_communication_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Type of activity (e.g., 'view', 'update', 'share', 'delete')
    activity_type = Column(String(50), nullable=False, index=True)
    
    # ID of the user who performed the activity
    performed_by_user_id = Column(Integer, nullable=False, index=True)
    
    # Additional details about the activity (e.g., IP address, new value)
    details = Column(Text, nullable=True)

    # Relationship back to the shared item
    item = relationship("SharedCommunicationItem", back_populates="activities")

    __table_args__ = (
        Index("ix_activity_item_user", item_id, performed_by_user_id),
    )


# --- Pydantic Schemas ---

class ConfigBase(BaseModel):
    """Base configuration for Pydantic models."""
    class Config:
        alias_generator = to_camel
        populate_by_name = True
        from_attributes = True

# --- SharedCommunicationItem Schemas ---

class SharedCommunicationItemBase(ConfigBase):
    """Base schema for shared communication item data."""
    item_type: str = Field(..., max_length=50, description="Type of the shared item (e.g., 'link', 'template').")
    title: str = Field(..., max_length=255, description="Title of the shared item.")
    content: str = Field(..., description="The main content, which can be text, a URL, or a JSON string.")
    is_active: bool = Field(True, description="Flag to indicate if the item is currently active/usable.")

class SharedCommunicationItemCreate(SharedCommunicationItemBase):
    """Schema for creating a new shared communication item."""
    # created_by_user_id will be set by the router from the authenticated user
    pass

class SharedCommunicationItemUpdate(SharedCommunicationItemBase):
    """Schema for updating an existing shared communication item."""
    item_type: Optional[str] = Field(None, max_length=50)
    title: Optional[str] = Field(None, max_length=255)
    content: Optional[str] = Field(None)
    is_active: Optional[bool] = Field(None)

class SharedCommunicationItemResponse(SharedCommunicationItemBase):
    """Schema for returning a shared communication item."""
    id: int
    created_by_user_id: int
    created_at: datetime
    updated_at: datetime

    # Nested schema for activities (optional for a simple response)
    # activities: List["CommunicationActivityLogResponse"] = []

# --- CommunicationActivityLog Schemas ---

class CommunicationActivityLogBase(ConfigBase):
    """Base schema for communication activity log data."""
    item_id: int = Field(..., description="ID of the shared communication item.")
    activity_type: str = Field(..., max_length=50, description="Type of activity (e.g., 'view', 'update').")
    performed_by_user_id: int = Field(..., description="ID of the user who performed the activity.")
    details: Optional[str] = Field(None, description="Additional details about the activity.")

class CommunicationActivityLogCreate(CommunicationActivityLogBase):
    """Schema for creating a new activity log entry."""
    pass

class CommunicationActivityLogResponse(CommunicationActivityLogBase):
    """Schema for returning an activity log entry."""
    id: int
    created_at: datetime
    updated_at: datetime

# Update forward references for nested schemas
# SharedCommunicationItemResponse.model_rebuild()
