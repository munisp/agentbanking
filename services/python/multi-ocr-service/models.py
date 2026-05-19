import enum
import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field
from sqlalchemy import (
    Column, DateTime, Enum, ForeignKey, Index, Integer, JSON, String, Text
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

# Base class for declarative class definitions
Base = declarative_base()

# --- Enums ---

class OcrJobStatus(str, enum.Enum):
    """Possible statuses for an OCR job."""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class OcrEngine(str, enum.Enum):
    """Supported OCR engines."""
    TESSERACT = "TESSERACT"
    GOOGLE_VISION = "GOOGLE_VISION"
    AZURE_COGNITIVE = "AZURE_COGNITIVE"
    OLMOCR = "OLMOCR"  # Advanced engine for document verification
    GOT_OCR2_0 = "GOT_OCR2_0" # Advanced engine for document verification

class ActivityType(str, enum.Enum):
    """Types of activities logged for an OCR job."""
    CREATED = "CREATED"
    STATUS_UPDATE = "STATUS_UPDATE"
    ENGINE_CHANGE = "ENGINE_CHANGE"
    RESULT_ADDED = "RESULT_ADDED"
    ERROR = "ERROR"

# --- SQLAlchemy Models ---

class OcrJob(Base):
    """
    Main model for an OCR processing job.
    """
    __tablename__ = "ocr_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    # Job details
    file_url = Column(String(512), nullable=False, doc="URL to the file to be processed (e.g., S3 link).")
    status = Column(Enum(OcrJobStatus), default=OcrJobStatus.PENDING, nullable=False, index=True, doc="Current status of the OCR job.")
    ocr_engine = Column(Enum(OcrEngine), nullable=False, doc="The specific OCR engine used for this job.")
    
    # Results
    result_text = Column(Text, nullable=True, doc="The extracted text from the document.")
    result_json = Column(JSON, nullable=True, doc="Structured data result from the OCR engine.")
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    activity_logs = relationship("OcrJobActivityLog", back_populates="job", cascade="all, delete-orphan", order_by="OcrJobActivityLog.timestamp")

    __table_args__ = (
        Index("idx_ocr_jobs_status_engine", status, ocr_engine),
    )

    def __repr__(self):
        return f"<OcrJob(id='{self.id}', status='{self.status}', engine='{self.ocr_engine}')>"

class OcrJobActivityLog(Base):
    """
    Activity log for changes and events related to an OcrJob.
    """
    __tablename__ = "ocr_job_activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey("ocr_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    activity_type = Column(Enum(ActivityType), nullable=False, doc="Type of activity logged.")
    details = Column(String(512), nullable=False, doc="A brief description of the activity.")
    metadata_json = Column(JSON, nullable=True, doc="Additional metadata for the activity (e.g., error trace).")

    # Relationships
    job = relationship("OcrJob", back_populates="activity_logs")

    def __repr__(self):
        return f"<OcrJobActivityLog(id={self.id}, job_id='{self.job_id}', type='{self.activity_type}')>"

# --- Pydantic Schemas ---

# Shared properties
class OcrJobBase(BaseModel):
    """Base schema for OCR job properties."""
    file_url: str = Field(..., max_length=512, description="URL to the file to be processed.")
    ocr_engine: OcrEngine = Field(..., description="The specific OCR engine to use.")

# Schema for creation
class OcrJobCreate(OcrJobBase):
    """Schema for creating a new OCR job."""
    pass

# Schema for updating
class OcrJobUpdate(BaseModel):
    """Schema for updating an existing OCR job."""
    status: Optional[OcrJobStatus] = Field(None, description="New status of the OCR job.")
    result_text: Optional[str] = Field(None, description="Extracted text result.")
    result_json: Optional[dict] = Field(None, description="Structured data result.")
    file_url: Optional[str] = Field(None, max_length=512, description="New file URL if the job is re-queued.")

# Schema for activity log response
class OcrJobActivityLogResponse(BaseModel):
    """Response schema for an activity log entry."""
    id: int
    job_id: uuid.UUID
    timestamp: datetime
    activity_type: ActivityType
    details: str
    metadata_json: Optional[dict] = None

    class Config:
        from_attributes = True

# Schema for response
class OcrJobResponse(OcrJobBase):
    """Response schema for an OCR job."""
    id: uuid.UUID
    status: OcrJobStatus
    result_text: Optional[str] = None
    result_json: Optional[dict] = None
    created_at: datetime
    updated_at: datetime
    
    # Nested relationship for logs
    activity_logs: List[OcrJobActivityLogResponse] = []

    class Config:
        from_attributes = True

# Schema for creating an activity log (internal use)
class OcrJobActivityLogCreate(BaseModel):
    """Schema for creating a new activity log entry."""
    activity_type: ActivityType
    details: str
    metadata_json: Optional[dict] = None
