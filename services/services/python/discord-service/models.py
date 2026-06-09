import datetime
from typing import List, Optional

from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Index
from sqlalchemy.orm import relationship, DeclarativeBase

# --- SQLAlchemy Base ---

class Base(DeclarativeBase):
    """Base class which provides automated table name
    and primary key column.
    """
    pass

# --- SQLAlchemy Models ---

class DiscordServer(Base):
    """
    SQLAlchemy model for a Discord Server managed by the service.
    """
    __tablename__ = "discord_servers"

    id = Column(Integer, primary_key=True, index=True)
    server_id = Column(String, unique=True, nullable=False, index=True, comment="The unique ID of the Discord server")
    server_name = Column(String, nullable=False, comment="The human-readable name of the Discord server")
    owner_id = Column(String, nullable=False, comment="The Discord user ID of the server owner")
    is_active = Column(Boolean, default=True, nullable=False, comment="Whether the service is currently active on this server")
    config_json = Column(Text, default="{}", comment="JSON string for service-specific configuration")
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    # Relationship to activity logs
    activity_logs = relationship("DiscordActivityLog", back_populates="server", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_server_owner_id", "owner_id"),
    )

class DiscordActivityLog(Base):
    """
    SQLAlchemy model for logging service activity on a Discord Server.
    """
    __tablename__ = "discord_activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    server_id = Column(Integer, ForeignKey("discord_servers.id", ondelete="CASCADE"), nullable=False, index=True)
    log_level = Column(String, nullable=False, comment="e.g., INFO, WARNING, ERROR")
    message = Column(Text, nullable=False, comment="The log message content")
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, index=True)
    
    # Relationship to DiscordServer
    server = relationship("DiscordServer", back_populates="activity_logs")

    __table_args__ = (
        Index("ix_log_level_timestamp", "log_level", "timestamp"),
    )

# --- Pydantic Schemas ---

# Base Schemas
class DiscordServerBase(BaseModel):
    """Base schema for DiscordServer data."""
    server_id: str = Field(..., description="The unique ID of the Discord server.")
    server_name: str = Field(..., description="The human-readable name of the Discord server.")
    owner_id: str = Field(..., description="The Discord user ID of the server owner.")
    is_active: bool = Field(True, description="Whether the service is currently active on this server.")
    config_json: str = Field("{}", description="JSON string for service-specific configuration.")

class DiscordActivityLogBase(BaseModel):
    """Base schema for DiscordActivityLog data."""
    log_level: str = Field(..., description="The severity level of the log (e.g., INFO, WARNING, ERROR).")
    message: str = Field(..., description="The content of the log message.")

# Create Schemas
class DiscordServerCreate(DiscordServerBase):
    """Schema for creating a new DiscordServer record."""
    pass

class DiscordActivityLogCreate(DiscordActivityLogBase):
    """Schema for creating a new DiscordActivityLog record."""
    server_id: int = Field(..., description="The internal ID of the associated Discord server.")

# Update Schemas
class DiscordServerUpdate(BaseModel):
    """Schema for updating an existing DiscordServer record."""
    server_name: Optional[str] = Field(None, description="The human-readable name of the Discord server.")
    is_active: Optional[bool] = Field(None, description="Whether the service is currently active on this server.")
    config_json: Optional[str] = Field(None, description="JSON string for service-specific configuration.")

# Response Schemas
class DiscordServerResponse(DiscordServerBase):
    """Schema for returning a DiscordServer record."""
    id: int = Field(..., description="Internal primary key ID.")
    created_at: datetime.datetime = Field(..., description="Timestamp of creation.")
    updated_at: datetime.datetime = Field(..., description="Timestamp of last update.")

    model_config = {"from_attributes": True}

class DiscordActivityLogResponse(DiscordActivityLogBase):
    """Schema for returning a DiscordActivityLog record."""
    id: int = Field(..., description="Internal primary key ID.")
    server_id: int = Field(..., description="The internal ID of the associated Discord server.")
    timestamp: datetime.datetime = Field(..., description="Timestamp of the log entry.")

    model_config = {"from_attributes": True}

class DiscordServerWithLogsResponse(DiscordServerResponse):
    """Schema for returning a DiscordServer record with its associated activity logs."""
    activity_logs: List[DiscordActivityLogResponse] = Field(..., description="List of activity logs for this server.")

    model_config = {"from_attributes": True}
