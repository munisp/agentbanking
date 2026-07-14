import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from config import Base

# --- SQLAlchemy Models ---

class TigerBeetleSync(Base):
    """
    SQLAlchemy model for a TigerBeetle Synchronization configuration.
    Represents a record of a specific sync job or configuration.
    """

    __tablename__ = "tigerbeetle_sync"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
        nullable=False,
        doc="Unique identifier for the sync configuration.",
    )
    sync_name = Column(
        String(255),
        nullable=False,
        index=True,
        doc="Human-readable name for the synchronization job.",
    )
    source_system = Column(
        String(255),
        nullable=False,
        doc="Identifier for the source system being synchronized.",
    )
    last_synced_at = Column(
        DateTime(timezone=True),
        nullable=True,
        doc="Timestamp of the last successful synchronization.",
    )
    status = Column(
        String(50),
        nullable=False,
        default="ACTIVE",
        doc="Current status of the sync (e.g., ACTIVE, PAUSED, ERROR).",
    )
    sync_frequency = Column(
        String(100),
        nullable=False,
        doc="Frequency of the sync (e.g., 'DAILY', 'HOURLY', 'CRON: 0 0 * * *').",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        doc="Timestamp when the record was created.",
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        doc="Timestamp when the record was last updated.",
    )

    # Relationship to the activity log
    activity_logs = relationship(
        "TigerBeetleSyncActivityLog",
        back_populates="sync_config",
        cascade="all, delete-orphan",
        order_by="TigerBeetleSyncActivityLog.timestamp.desc()",
    )

    __table_args__ = (
        Index(
            "idx_sync_source_status",
            "source_system",
            "status",
        ),
    )


class TigerBeetleSyncActivityLog(Base):
    """
    SQLAlchemy model for logging activities related to a TigerBeetleSync job.
    """

    __tablename__ = "tigerbeetle_sync_activity_log"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
        doc="Unique identifier for the activity log entry.",
    )
    sync_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tigerbeetle_sync.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Foreign key to the associated TigerBeetleSync configuration.",
    )
    timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        doc="Timestamp of the activity.",
    )
    log_level = Column(
        String(50),
        nullable=False,
        doc="Severity level of the log (e.g., INFO, WARNING, ERROR).",
    )
    message = Column(
        Text,
        nullable=False,
        doc="Detailed message of the activity.",
    )
    details = Column(
        Text,
        nullable=True,
        doc="Optional JSON or text details about the activity.",
    )

    # Relationship back to the sync configuration
    sync_config = relationship(
        "TigerBeetleSync", back_populates="activity_logs"
    )


# --- Pydantic Schemas ---

# Base Schemas
class TigerBeetleSyncBase(BaseModel):
    """Base Pydantic schema for TigerBeetleSync."""
    sync_name: str = Field(..., max_length=255, description="Human-readable name for the synchronization job.")
    source_system: str = Field(..., max_length=255, description="Identifier for the source system being synchronized.")
    status: str = Field("ACTIVE", max_length=50, description="Current status of the sync (e.g., ACTIVE, PAUSED, ERROR).")
    sync_frequency: str = Field(..., max_length=100, description="Frequency of the sync (e.g., 'DAILY', 'HOURLY', 'CRON: 0 0 * * *').")

    class Config:
        from_attributes = True


class TigerBeetleSyncActivityLogBase(BaseModel):
    """Base Pydantic schema for TigerBeetleSyncActivityLog."""
    log_level: str = Field(..., max_length=50, description="Severity level of the log (e.g., INFO, WARNING, ERROR).")
    message: str = Field(..., description="Detailed message of the activity.")
    details: Optional[str] = Field(None, description="Optional JSON or text details about the activity.")

    class Config:
        from_attributes = True


# Create Schemas
class TigerBeetleSyncCreate(TigerBeetleSyncBase):
    """Pydantic schema for creating a new TigerBeetleSync record."""
    # Inherits all fields from TigerBeetleSyncBase
    pass


class TigerBeetleSyncActivityLogCreate(TigerBeetleSyncActivityLogBase):
    """Pydantic schema for creating a new TigerBeetleSyncActivityLog record."""
    sync_id: uuid.UUID = Field(..., description="The ID of the associated sync configuration.")


# Update Schemas
class TigerBeetleSyncUpdate(TigerBeetleSyncBase):
    """Pydantic schema for updating an existing TigerBeetleSync record."""
    sync_name: Optional[str] = Field(None, max_length=255, description="Human-readable name for the synchronization job.")
    source_system: Optional[str] = Field(None, max_length=255, description="Identifier for the source system being synchronized.")
    status: Optional[str] = Field(None, max_length=50, description="Current status of the sync (e.g., ACTIVE, PAUSED, ERROR).")
    sync_frequency: Optional[str] = Field(None, max_length=100, description="Frequency of the sync.")
    last_synced_at: Optional[datetime] = Field(None, description="Timestamp of the last successful synchronization.")


# Response Schemas
class TigerBeetleSyncActivityLogResponse(TigerBeetleSyncActivityLogBase):
    """Pydantic schema for responding with a TigerBeetleSyncActivityLog record."""
    id: int = Field(..., description="Unique identifier for the activity log entry.")
    sync_id: uuid.UUID = Field(..., description="The ID of the associated sync configuration.")
    timestamp: datetime = Field(..., description="Timestamp of the activity.")


class TigerBeetleSyncResponse(TigerBeetleSyncBase):
    """Pydantic schema for responding with a TigerBeetleSync record."""
    id: uuid.UUID = Field(..., description="Unique identifier for the sync configuration.")
    last_synced_at: Optional[datetime] = Field(None, description="Timestamp of the last successful synchronization.")
    created_at: datetime = Field(..., description="Timestamp when the record was created.")
    updated_at: datetime = Field(..., description="Timestamp when the record was last updated.")
    
    # Include activity logs in the response
    activity_logs: List[TigerBeetleSyncActivityLogResponse] = Field(
        [], description="List of recent activity logs for this sync configuration."
    )
