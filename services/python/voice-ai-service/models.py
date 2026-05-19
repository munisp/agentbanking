import datetime
from typing import List, Optional

from pydantic import BaseModel, Field
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Text,
    ForeignKey,
    Boolean,
    Float,
    Index,
)
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func

# --- SQLAlchemy Base and Model Definitions ---

Base = declarative_base()


class VoiceJob(Base):
    """
    SQLAlchemy model for a Voice AI processing job.
    Represents a single task like transcription or speech synthesis.
    """

    __tablename__ = "voice_jobs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    job_type = Column(String(50), nullable=False, index=True)  # e.g., 'transcription', 'synthesis'
    status = Column(String(50), default="pending", index=True)  # e.g., 'pending', 'processing', 'completed', 'failed'
    input_file_url = Column(String, nullable=False)
    output_file_url = Column(String, nullable=True)
    model_used = Column(String(100), nullable=False)
    duration_seconds = Column(Float, nullable=True)
    is_public = Column(Boolean, default=False)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationship to ActivityLog
    logs = relationship("ActivityLog", back_populates="job", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_voice_jobs_user_status", user_id, status),
    )


class ActivityLog(Base):
    """
    SQLAlchemy model for logging activities related to a VoiceJob.
    """

    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("voice_jobs.id"), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    activity_type = Column(String(50), nullable=False)  # e.g., 'status_change', 'file_upload', 'error'
    details = Column(Text, nullable=True)

    # Relationship to VoiceJob
    job = relationship("VoiceJob", back_populates="logs")


# --- Pydantic Schemas ---


class VoiceJobBase(BaseModel):
    """Base schema for VoiceJob, containing common fields."""

    user_id: int = Field(..., description="ID of the user who initiated the job.")
    job_type: str = Field(..., description="Type of the voice AI job (e.g., 'transcription', 'synthesis').")
    input_file_url: str = Field(..., description="URL or path to the input audio file.")
    model_used: str = Field(..., description="The AI model used for processing (e.g., 'whisper-large-v3').")
    is_public: bool = Field(False, description="Whether the job result is publicly accessible.")


class VoiceJobCreate(VoiceJobBase):
    """Schema for creating a new VoiceJob."""

    pass


class VoiceJobUpdate(BaseModel):
    """Schema for updating an existing VoiceJob."""

    status: Optional[str] = Field(None, description="Current status of the job.")
    output_file_url: Optional[str] = Field(None, description="URL or path to the output file.")
    duration_seconds: Optional[float] = Field(None, description="Processing duration in seconds.")
    error_message: Optional[str] = Field(None, description="Error message if the job failed.")
    is_public: Optional[bool] = Field(None, description="Whether the job result is publicly accessible.")


class VoiceJobResponse(VoiceJobBase):
    """Schema for returning a VoiceJob response."""

    id: int
    status: str
    output_file_url: Optional[str] = None
    duration_seconds: Optional[float] = None
    error_message: Optional[str] = None
    created_at: datetime.datetime
    updated_at: Optional[datetime.datetime] = None

    class Config:
        from_attributes = True


class ActivityLogBase(BaseModel):
    """Base schema for ActivityLog."""

    job_id: int
    activity_type: str = Field(..., description="Type of activity (e.g., 'status_change', 'error').")
    details: Optional[str] = None


class ActivityLogCreate(ActivityLogBase):
    """Schema for creating a new ActivityLog entry."""

    pass


class ActivityLogResponse(ActivityLogBase):
    """Schema for returning an ActivityLog response."""

    id: int
    timestamp: datetime.datetime

    class Config:
        from_attributes = True
