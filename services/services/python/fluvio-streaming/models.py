import datetime
from typing import List, Optional

from pydantic import BaseModel, Field
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Index
)
from sqlalchemy.orm import relationship

from .config import Base, engine

# --- SQLAlchemy Models ---

class FluvioStreaming(Base):
    """
    SQLAlchemy Model for the main Fluvio Streaming configuration.
    Represents a configured streaming resource.
    """
    __tablename__ = "fluvio_streaming"

    id = Column(Integer, primary_key=True, index=True)
    
    # Configuration details
    name = Column(String, unique=True, index=True, nullable=False, doc="Unique name for the streaming configuration")
    stream_type = Column(String, nullable=False, doc="Type of the stream (e.g., 'kafka', 'kinesis', 'custom')")
    endpoint_url = Column(String, nullable=False, doc="The connection endpoint URL")
    
    # Status and metadata
    is_active = Column(Boolean, default=True, nullable=False, doc="Whether the streaming configuration is currently active")
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    # Relationships
    activity_logs = relationship("FluvioStreamingActivityLog", back_populates="streaming_config", cascade="all, delete-orphan")

    __table_args__ = (
        # Index for faster lookups on active status and stream type
        Index("ix_fluvio_streaming_active_type", "is_active", "stream_type"),
    )

class FluvioStreamingActivityLog(Base):
    """
    SQLAlchemy Model for logging activities related to Fluvio Streaming configurations.
    """
    __tablename__ = "fluvio_streaming_activity_log"

    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign Key to the main configuration
    config_id = Column(Integer, ForeignKey("fluvio_streaming.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Log details
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, index=True)
    action = Column(String, nullable=False, doc="The action performed (e.g., 'CREATE', 'UPDATE', 'DELETE', 'STATUS_CHANGE')")
    details = Column(Text, doc="Detailed description of the activity")
    
    # Relationship
    streaming_config = relationship("FluvioStreaming", back_populates="activity_logs")

    __table_args__ = (
        # Index for faster lookups on config_id and action
        Index("ix_fluvio_streaming_log_config_action", "config_id", "action"),
    )

# Create tables if they don't exist
Base.metadata.create_all(bind=engine)

# --- Pydantic Schemas ---

class FluvioStreamingBase(BaseModel):
    """Base schema for FluvioStreaming, containing common fields."""
    name: str = Field(..., description="Unique name for the streaming configuration.")
    stream_type: str = Field(..., description="Type of the stream (e.g., 'kafka', 'kinesis', 'custom').")
    endpoint_url: str = Field(..., description="The connection endpoint URL.")
    is_active: bool = Field(True, description="Whether the configuration is active.")

class FluvioStreamingCreate(FluvioStreamingBase):
    """Schema for creating a new FluvioStreaming configuration."""
    # Inherits all fields from FluvioStreamingBase
    pass

class FluvioStreamingUpdate(BaseModel):
    """Schema for updating an existing FluvioStreaming configuration."""
    name: Optional[str] = Field(None, description="Unique name for the streaming configuration.")
    stream_type: Optional[str] = Field(None, description="Type of the stream (e.g., 'kafka', 'kinesis', 'custom').")
    endpoint_url: Optional[str] = Field(None, description="The connection endpoint URL.")
    is_active: Optional[bool] = Field(None, description="Whether the configuration is active.")

class FluvioStreamingActivityLogResponse(BaseModel):
    """Response schema for FluvioStreamingActivityLog."""
    id: int
    config_id: int
    timestamp: datetime.datetime
    action: str
    details: str

    class Config:
        from_attributes = True

class FluvioStreamingResponse(FluvioStreamingBase):
    """Response schema for FluvioStreaming, including database-generated fields."""
    id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime
    
    # Nested relationship for activity logs
    activity_logs: List[FluvioStreamingActivityLogResponse] = []

    class Config:
        from_attributes = True
