import json
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import (
    Column, Integer, String, DateTime, Text, ForeignKey, Index, Enum, JSON, text
)
from sqlalchemy.orm import relationship, DeclarativeBase
from sqlalchemy.sql import func

# --- SQLAlchemy Base ---
class Base(DeclarativeBase):
    """Base class which provides automated table name
    and common utility methods.
    """
    pass

# --- Enums ---
class OCRStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RETRY = "RETRY"

# --- Database Models ---

class OCRResult(Base):
    """
    Represents the result of an Optical Character Recognition (OCR) job.
    """
    __tablename__ = "ocr_results"

    id = Column(Integer, primary_key=True, index=True)
    
    # Input file details
    file_name = Column(String(255), nullable=False, doc="Original name of the file submitted for OCR.")
    file_path = Column(String(512), nullable=False, doc="Storage path of the file.")
    
    # Processing status and results
    status = Column(Enum(OCRStatus), default=OCRStatus.PENDING, nullable=False, index=True, doc="Current status of the OCR job.")
    extracted_text = Column(Text, nullable=True, doc="The full text extracted by the OCR engine.")
    
    # Detailed metadata (e.g., bounding boxes, confidence scores)
    metadata = Column(JSON, nullable=True, doc="JSON field for detailed OCR metadata.")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    logs = relationship("OCRActivityLog", back_populates="ocr_result", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_ocr_results_file_name", file_name),
        # Example of a unique constraint if needed, e.g., unique on file_path
        # UniqueConstraint('file_path', name='uq_ocr_results_file_path'),
    )

class OCRActivityLog(Base):
    """
    Logs activities and state changes for an OCRResult.
    """
    __tablename__ = "ocr_activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    ocr_result_id = Column(Integer, ForeignKey("ocr_results.id", ondelete="CASCADE"), nullable=False)
    
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    activity_type = Column(String(100), nullable=False, doc="Type of activity, e.g., 'STATUS_CHANGE', 'ERROR', 'SUBMISSION'.")
    details = Column(JSON, nullable=True, doc="JSON details about the activity.")
    
    # Relationships
    ocr_result = relationship("OCRResult", back_populates="logs")

    __table_args__ = (
        Index("ix_ocr_logs_result_id_type", ocr_result_id, activity_type),
    )

# --- Pydantic Schemas ---

# Base Schema for common fields
class OCRResultBase(BaseModel):
    file_name: str = Field(..., description="Original name of the file.")
    file_path: str = Field(..., description="Storage path of the file.")
    
    model_config = ConfigDict(from_attributes=True)

# Schema for creating a new OCR job
class OCRResultCreate(OCRResultBase):
    # Status is defaulted in the DB, so we don't require it here
    pass

# Schema for updating an existing OCR job
class OCRResultUpdate(BaseModel):
    status: Optional[OCRStatus] = Field(None, description="New status of the OCR job.")
    extracted_text: Optional[str] = Field(None, description="The full text extracted by the OCR engine.")
    metadata: Optional[dict] = Field(None, description="Detailed OCR metadata (e.g., bounding boxes).")

# Schema for the response model (includes all fields)
class OCRResultResponse(OCRResultBase):
    id: int
    status: OCRStatus
    extracted_text: Optional[str] = None
    metadata: Optional[dict] = None
    created_at: datetime
    updated_at: datetime

# Schema for the activity log response
class OCRActivityLogResponse(BaseModel):
    id: int
    ocr_result_id: int
    timestamp: datetime
    activity_type: str
    details: Optional[dict] = None
    
    model_config = ConfigDict(from_attributes=True)

# Schema for a full response including logs
class OCRResultFullResponse(OCRResultResponse):
    logs: List[OCRActivityLogResponse] = Field(default_factory=list)
