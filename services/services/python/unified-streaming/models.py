from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Index
from sqlalchemy.orm import relationship, DeclarativeBase
from sqlalchemy.sql import func

# --- SQLAlchemy Base ---

class Base(DeclarativeBase):
    """Base class which provides automated table name
    and default methods.
    """
    pass

# --- SQLAlchemy Models ---

class UnifiedStream(Base):
    """
    SQLAlchemy model for a Unified Stream configuration.
    Represents a single stream that is managed by the service.
    """
    __tablename__ = "unified_streams"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False, doc="Unique name for the stream")
    stream_type = Column(String, nullable=False, doc="Type of stream (e.g., 'live', 'vod', 'linear')")
    source_url = Column(String, nullable=False, doc="URL or path to the stream source")
    status = Column(String, default="inactive", doc="Current operational status of the stream")
    
    created_at = Column(DateTime, default=func.now(), index=True, nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # Relationship to activity logs
    activity_logs = relationship("UnifiedStreamActivityLog", back_populates="stream", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<UnifiedStream(id={self.id}, name='{self.name}', status='{self.status}')>"

class UnifiedStreamActivityLog(Base):
    """
    SQLAlchemy model for logging activities related to a Unified Stream.
    """
    __tablename__ = "unified_stream_activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    stream_id = Column(Integer, ForeignKey("unified_streams.id"), nullable=False, index=True)
    timestamp = Column(DateTime, default=func.now(), index=True, nullable=False)
    action = Column(String, nullable=False, doc="Action performed (e.g., 'created', 'updated', 'status_change')")
    details = Column(Text, doc="JSON string or text details about the action")
    user_id = Column(String, nullable=True, doc="ID of the user or system that performed the action")

    # Relationship to the stream
    stream = relationship("UnifiedStream", back_populates="activity_logs")

    # Composite index for faster lookups by stream and time
    __table_args__ = (
        Index("idx_stream_action_time", "stream_id", "action", "timestamp"),
    )

    def __repr__(self):
        return f"<UnifiedStreamActivityLog(id={self.id}, stream_id={self.stream_id}, action='{self.action}')>"

# --- Pydantic Schemas ---

# Base Schemas
class UnifiedStreamBase(BaseModel):
    """Base schema for UnifiedStream, containing common fields."""
    name: str = Field(..., description="Unique name for the stream.")
    stream_type: str = Field(..., description="Type of stream (e.g., 'live', 'vod', 'linear').")
    source_url: str = Field(..., description="URL or path to the stream source.")
    status: str = Field("inactive", description="Current operational status of the stream.")

    class Config:
        """Pydantic configuration."""
        from_attributes = True

class UnifiedStreamActivityLogBase(BaseModel):
    """Base schema for UnifiedStreamActivityLog."""
    action: str = Field(..., description="Action performed (e.g., 'created', 'updated', 'status_change').")
    details: Optional[str] = Field(None, description="JSON string or text details about the action.")
    user_id: Optional[str] = Field(None, description="ID of the user or system that performed the action.")

    class Config:
        """Pydantic configuration."""
        from_attributes = True

# Create Schemas
class UnifiedStreamCreate(UnifiedStreamBase):
    """Schema for creating a new UnifiedStream."""
    pass

class UnifiedStreamActivityLogCreate(UnifiedStreamActivityLogBase):
    """Schema for creating a new UnifiedStreamActivityLog."""
    stream_id: int = Field(..., description="ID of the stream this log entry belongs to.")

# Update Schemas
class UnifiedStreamUpdate(BaseModel):
    """Schema for updating an existing UnifiedStream."""
    name: Optional[str] = Field(None, description="Unique name for the stream.")
    stream_type: Optional[str] = Field(None, description="Type of stream (e.g., 'live', 'vod', 'linear').")
    source_url: Optional[str] = Field(None, description="URL or path to the stream source.")
    status: Optional[str] = Field(None, description="Current operational status of the stream.")

    class Config:
        """Pydantic configuration."""
        from_attributes = True

# Response Schemas
class UnifiedStreamActivityLogResponse(UnifiedStreamActivityLogBase):
    """Response schema for UnifiedStreamActivityLog."""
    id: int
    stream_id: int
    timestamp: datetime

class UnifiedStreamResponse(UnifiedStreamBase):
    """Response schema for UnifiedStream, including read-only fields."""
    id: int
    created_at: datetime
    updated_at: datetime
    activity_logs: List[UnifiedStreamActivityLogResponse] = Field([], description="List of activity logs for this stream.")
