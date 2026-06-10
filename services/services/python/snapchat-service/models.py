import datetime
from typing import List, Optional

from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Index, Enum, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .config import Base

# ----------------------------------------------------------------------
# SQLAlchemy Models
# ----------------------------------------------------------------------

class Snap(Base):
    """
    SQLAlchemy model for a Snap, the core entity of the service.
    """
    __tablename__ = "snaps"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True, doc="ID of the user who created the snap.")
    media_url = Column(String(255), nullable=False, doc="URL of the media content (image/video).")
    caption = Column(Text, nullable=True, doc="Optional text caption for the snap.")
    duration_seconds = Column(Integer, default=5, doc="Duration the snap is viewable in seconds.")
    is_viewed = Column(Boolean, default=False, doc="Flag to track if the snap has been viewed by the recipient.")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True, doc="Timestamp when the snap expires and is deleted.")

    # Relationships
    activity_logs = relationship("SnapActivityLog", back_populates="snap", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_snaps_user_id_created_at", "user_id", "created_at"),
    )

    def __repr__(self):
        return f"<Snap(id={self.id}, user_id={self.user_id}, created_at={self.created_at})>"


class SnapActivityLog(Base):
    """
    SQLAlchemy model for logging activities related to Snaps (e.g., view, delete).
    """
    __tablename__ = "snap_activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    snap_id = Column(Integer, ForeignKey("snaps.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True, doc="ID of the user performing the activity.")
    
    activity_type = Column(Enum("CREATED", "VIEWED", "DELETED", name="activity_type"), nullable=False)
    
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    snap = relationship("Snap", back_populates="activity_logs")

    __table_args__ = (
        Index("ix_snap_activity_log_snap_id_type", "snap_id", "activity_type"),
    )

    def __repr__(self):
        return f"<SnapActivityLog(id={self.id}, snap_id={self.snap_id}, type={self.activity_type})>"


# ----------------------------------------------------------------------
# Pydantic Schemas
# ----------------------------------------------------------------------

# Base Schema
class SnapBase(BaseModel):
    """Base schema for a Snap."""
    media_url: str = Field(..., description="URL of the media content (image/video).")
    caption: Optional[str] = Field(None, max_length=500, description="Optional text caption for the snap.")
    duration_seconds: int = Field(5, ge=1, le=10, description="Duration the snap is viewable in seconds (1-10).")

    class Config:
        from_attributes = True


# Create Schema
class SnapCreate(SnapBase):
    """Schema for creating a new Snap."""
    user_id: int = Field(..., description="ID of the user creating the snap.")
    # In a real application, recipient_user_id would be here, but for a simple CRUD, we focus on the core entity.


# Update Schema
class SnapUpdate(SnapBase):
    """Schema for updating an existing Snap."""
    # Only allow updating caption and duration before it's sent/viewed, 
    # but for simplicity, we'll allow updating these fields.
    caption: Optional[str] = Field(None, max_length=500, description="Optional text caption for the snap.")
    duration_seconds: Optional[int] = Field(None, ge=1, le=10, description="Duration the snap is viewable in seconds (1-10).")


# Response Schema
class SnapResponse(SnapBase):
    """Schema for returning a Snap object."""
    id: int
    user_id: int
    is_viewed: bool
    created_at: datetime.datetime
    expires_at: datetime.datetime

    class Config:
        # Allows ORM models to be converted to Pydantic models
        from_attributes = True


# Activity Log Schemas
class SnapActivityLogResponse(BaseModel):
    """Schema for returning a SnapActivityLog object."""
    id: int
    snap_id: int
    user_id: int
    activity_type: str
    timestamp: datetime.datetime

    class Config:
        from_attributes = True
