from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Index, Text
from sqlalchemy.orm import relationship, DeclarativeBase

# --- SQLAlchemy Base ---

class Base(DeclarativeBase):
    """Base class which provides automated table name
    and common columns like id and created_at.
    """
    __abstract__ = True

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

# --- SQLAlchemy Models ---

class SyncManager(Base):
    """
    Main model for the sync-manager service. Represents a single synchronization job or configuration.
    """
    __tablename__ = "sync_managers"

    # Core fields
    name = Column(String(255), unique=True, index=True, nullable=False, doc="A unique name for the synchronization job.")
    source_system = Column(String(100), nullable=False, doc="The source system for the sync (e.g., 'CRM', 'ERP').")
    target_system = Column(String(100), nullable=False, doc="The target system for the sync (e.g., 'DataWarehouse', 'MarketingTool').")
    sync_frequency = Column(String(50), nullable=False, default="daily", doc="How often the sync runs (e.g., 'hourly', 'daily', 'on-demand').")
    is_active = Column(Boolean, default=True, nullable=False, doc="Whether the synchronization job is currently active.")
    last_sync_time = Column(DateTime, nullable=True, doc="Timestamp of the last successful synchronization run.")
    
    # Configuration details (e.g., JSON string or a simple text field for configuration)
    configuration = Column(Text, nullable=True, doc="Detailed configuration for the sync job, potentially in JSON format.")

    # Relationships
    activities = relationship("SyncActivityLog", back_populates="sync_manager", cascade="all, delete-orphan")

    # Indexes and Constraints
    __table_args__ = (
        Index("idx_source_target", "source_system", "target_system"),
    )

    def __repr__(self):
        return f"<SyncManager(id={self.id}, name='{self.name}', is_active={self.is_active})>"

class SyncActivityLog(Base):
    """
    Activity log table for tracking individual synchronization runs.
    """
    __tablename__ = "sync_activity_logs"

    # Foreign Key
    sync_manager_id = Column(Integer, ForeignKey("sync_managers.id"), nullable=False, index=True)

    # Core fields
    status = Column(String(50), nullable=False, doc="Status of the sync run (e.g., 'SUCCESS', 'FAILED', 'RUNNING').")
    start_time = Column(DateTime, nullable=False, doc="Time the sync run started.")
    end_time = Column(DateTime, nullable=True, doc="Time the sync run ended.")
    duration_seconds = Column(Integer, nullable=True, doc="Duration of the sync run in seconds.")
    records_processed = Column(Integer, default=0, nullable=False, doc="Number of records processed during the run.")
    error_message = Column(Text, nullable=True, doc="Detailed error message if the sync failed.")

    # Relationships
    sync_manager = relationship("SyncManager", back_populates="activities")

    # Indexes and Constraints
    __table_args__ = (
        Index("idx_sync_status", "sync_manager_id", "status"),
    )

    def __repr__(self):
        return f"<SyncActivityLog(id={self.id}, sync_manager_id={self.sync_manager_id}, status='{self.status}')>"

# --- Pydantic Schemas ---

# Base Schemas for common fields
class SyncManagerBase(BaseModel):
    """Base schema for SyncManager."""
    name: str = Field(..., max_length=255, description="Unique name for the synchronization job.")
    source_system: str = Field(..., max_length=100, description="The source system for the sync (e.g., 'CRM', 'ERP').")
    target_system: str = Field(..., max_length=100, description="The target system for the sync (e.g., 'DataWarehouse', 'MarketingTool').")
    sync_frequency: str = Field("daily", max_length=50, description="How often the sync runs (e.g., 'hourly', 'daily', 'on-demand').")
    is_active: bool = Field(True, description="Whether the synchronization job is currently active.")
    configuration: Optional[str] = Field(None, description="Detailed configuration for the sync job, potentially in JSON format.")

class SyncActivityLogBase(BaseModel):
    """Base schema for SyncActivityLog."""
    status: str = Field(..., max_length=50, description="Status of the sync run (e.g., 'SUCCESS', 'FAILED', 'RUNNING').")
    start_time: datetime = Field(..., description="Time the sync run started.")
    end_time: Optional[datetime] = Field(None, description="Time the sync run ended.")
    duration_seconds: Optional[int] = Field(None, description="Duration of the sync run in seconds.")
    records_processed: int = Field(0, description="Number of records processed during the run.")
    error_message: Optional[str] = Field(None, description="Detailed error message if the sync failed.")

# Create Schemas
class SyncManagerCreate(SyncManagerBase):
    """Schema for creating a new SyncManager."""
    pass

class SyncActivityLogCreate(SyncActivityLogBase):
    """Schema for creating a new SyncActivityLog entry."""
    sync_manager_id: int = Field(..., description="ID of the associated SyncManager.")

# Update Schemas
class SyncManagerUpdate(SyncManagerBase):
    """Schema for updating an existing SyncManager."""
    name: Optional[str] = Field(None, max_length=255, description="Unique name for the synchronization job.")
    source_system: Optional[str] = Field(None, max_length=100, description="The source system for the sync.")
    target_system: Optional[str] = Field(None, max_length=100, description="The target system for the sync.")
    sync_frequency: Optional[str] = Field(None, max_length=50, description="How often the sync runs.")
    is_active: Optional[bool] = Field(None, description="Whether the synchronization job is currently active.")
    configuration: Optional[str] = Field(None, description="Detailed configuration for the sync job.")

class SyncActivityLogUpdate(SyncActivityLogBase):
    """Schema for updating an existing SyncActivityLog entry."""
    status: Optional[str] = Field(None, max_length=50, description="Status of the sync run.")
    start_time: Optional[datetime] = Field(None, description="Time the sync run started.")
    end_time: Optional[datetime] = Field(None, description="Time the sync run ended.")
    duration_seconds: Optional[int] = Field(None, description="Duration of the sync run in seconds.")
    records_processed: Optional[int] = Field(None, description="Number of records processed during the run.")
    error_message: Optional[str] = Field(None, description="Detailed error message if the sync failed.")

# Response Schemas (include ID and timestamps)
class SyncActivityLogResponse(SyncActivityLogBase):
    """Response schema for SyncActivityLog."""
    id: int
    sync_manager_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class SyncManagerResponse(SyncManagerBase):
    """Response schema for SyncManager."""
    id: int
    last_sync_time: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    activities: List[SyncActivityLogResponse] = Field([], description="List of associated sync activities.")

    class Config:
        from_attributes = True

# Response Schema without nested activities for list/simple views
class SyncManagerSimpleResponse(SyncManagerBase):
    """Simple response schema for SyncManager, without nested activities."""
    id: int
    last_sync_time: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
