from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, Enum, ForeignKey, Index, Integer, String, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship

from .config import Base

# --- SQLAlchemy Models ---

class BackupJob(Base):
    """
    Represents a scheduled or executed backup job.
    """
    __tablename__ = "backup_jobs"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4, index=True)
    service_name = Column(String, index=True, nullable=False, doc="The name of the service being backed up (e.g., 'user-service').")
    resource_id = Column(String, index=True, nullable=True, doc="The ID of the specific resource being backed up (e.g., a database name or volume ID).")
    
    backup_type = Column(Enum("FULL", "INCREMENTAL", name="backup_type_enum"), nullable=False, default="FULL", doc="Type of backup: FULL or INCREMENTAL.")
    schedule_cron = Column(String, nullable=True, doc="CRON expression for scheduled backups.")
    
    last_run_at = Column(DateTime, nullable=True, doc="Timestamp of the last successful or attempted run.")
    next_run_at = Column(DateTime, nullable=True, doc="Timestamp of the next scheduled run.")
    is_active = Column(Boolean, default=True, nullable=False, doc="Whether the backup job is currently active.")
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationship to activity logs
    activities = relationship("BackupActivityLog", back_populates="job", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_backup_jobs_service_resource", "service_name", "resource_id"),
    )

class BackupActivityLog(Base):
    """
    Represents an activity log entry for a specific backup job execution.
    """
    __tablename__ = "backup_activity_logs"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4, index=True)
    job_id = Column(PG_UUID(as_uuid=True), ForeignKey("backup_jobs.id"), nullable=False, index=True)
    
    status = Column(Enum("PENDING", "RUNNING", "SUCCESS", "FAILED", "CANCELLED", name="activity_status_enum"), nullable=False, doc="Status of the backup activity.")
    start_time = Column(DateTime, default=datetime.utcnow, nullable=False)
    end_time = Column(DateTime, nullable=True)
    
    duration_seconds = Column(Integer, nullable=True, doc="Duration of the backup in seconds.")
    log_message = Column(Text, nullable=True, doc="Detailed log message or error description.")
    backup_location = Column(String, nullable=True, doc="Storage location of the backup file/snapshot.")
    
    # Relationship back to the job
    job = relationship("BackupJob", back_populates="activities")

    __table_args__ = (
        Index("ix_backup_activity_job_status", "job_id", "status"),
    )

# --- Pydantic Schemas ---

# Shared base schemas
class BackupJobBase(BaseModel):
    """Base schema for a backup job."""
    service_name: str = Field(..., description="The name of the service being backed up (e.g., 'user-service').")
    resource_id: Optional[str] = Field(None, description="The ID of the specific resource being backed up (e.g., a database name or volume ID).")
    backup_type: str = Field("FULL", description="Type of backup: FULL or INCREMENTAL.")
    schedule_cron: Optional[str] = Field(None, description="CRON expression for scheduled backups (e.g., '0 2 * * *' for 2 AM daily).")
    is_active: bool = Field(True, description="Whether the backup job is currently active.")

class BackupActivityLogBase(BaseModel):
    """Base schema for a backup activity log."""
    status: str = Field(..., description="Status of the backup activity (PENDING, RUNNING, SUCCESS, FAILED, CANCELLED).")
    log_message: Optional[str] = Field(None, description="Detailed log message or error description.")
    backup_location: Optional[str] = Field(None, description="Storage location of the backup file/snapshot.")

# BackupJob Schemas
class BackupJobCreate(BackupJobBase):
    """Schema for creating a new backup job."""
    pass

class BackupJobUpdate(BackupJobBase):
    """Schema for updating an existing backup job."""
    service_name: Optional[str] = None
    backup_type: Optional[str] = None
    is_active: Optional[bool] = None

class BackupJobResponse(BackupJobBase):
    """Schema for returning a backup job."""
    id: UUID
    last_run_at: Optional[datetime]
    next_run_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        json_encoders = {
            UUID: str,
        }

# BackupActivityLog Schemas
class BackupActivityLogCreate(BackupActivityLogBase):
    """Schema for creating a new backup activity log."""
    job_id: UUID = Field(..., description="The ID of the associated backup job.")
    start_time: datetime = Field(default_factory=datetime.utcnow)

class BackupActivityLogUpdate(BackupActivityLogBase):
    """Schema for updating an existing backup activity log."""
    status: Optional[str] = None
    end_time: Optional[datetime] = None
    duration_seconds: Optional[int] = None

class BackupActivityLogResponse(BackupActivityLogBase):
    """Schema for returning a backup activity log."""
    id: UUID
    job_id: UUID
    start_time: datetime
    end_time: Optional[datetime]
    duration_seconds: Optional[int]
    
    class Config:
        from_attributes = True
        json_encoders = {
            UUID: str,
        }

class BackupJobWithActivitiesResponse(BackupJobResponse):
    """Schema for returning a backup job with its associated activities."""
    activities: List[BackupActivityLogResponse] = []
    
    class Config:
        from_attributes = True
        json_encoders = {
            UUID: str,
        }
