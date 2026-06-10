from datetime import datetime
from typing import List, Optional
from enum import Enum

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Index, Enum as SQLEnum
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from pydantic import BaseModel, Field

# --- SQLAlchemy Base ---

class Base(DeclarativeBase):
    """Base class which provides automated table name and default primary key column."""
    pass

# --- Enums for Document Status and Activity Type ---

class DocumentStatus(str, Enum):
    """Possible statuses for a processed document."""
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    OCR_COMPLETED = "OCR_COMPLETED"
    VERIFICATION_PENDING = "VERIFICATION_PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class ActivityType(str, Enum):
    """Types of activities logged for a document."""
    UPLOAD = "UPLOAD"
    PROCESSING_START = "PROCESSING_START"
    OCR_EXTRACTION = "OCR_EXTRACTION"
    VERIFICATION_RESULT = "VERIFICATION_RESULT"
    STATUS_UPDATE = "STATUS_UPDATE"
    ERROR = "ERROR"

# --- SQLAlchemy Models ---

class Document(Base):
    """
    Main model for a document being processed.
    """
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # Core document metadata
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False, comment="Internal storage path or URI")
    document_type: Mapped[str] = mapped_column(String(100), nullable=False, comment="e.g., 'ID_CARD', 'INVOICE', 'PASSPORT'")
    
    # Processing status
    status: Mapped[DocumentStatus] = mapped_column(
        SQLEnum(DocumentStatus, name="document_status_enum", create_type=True),
        default=DocumentStatus.UPLOADED,
        index=True
    )
    
    # Audit and tracking
    uploaded_by_user_id: Mapped[int] = mapped_column(Integer, index=True, comment="ID of the user who uploaded the document")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    activity_logs: Mapped[List["DocumentActivityLog"]] = relationship(
        "DocumentActivityLog", 
        back_populates="document", 
        cascade="all, delete-orphan",
        order_by="DocumentActivityLog.timestamp"
    )

    __table_args__ = (
        Index("idx_document_user_status", uploaded_by_user_id, status),
    )

class DocumentActivityLog(Base):
    """
    Activity log for tracking events related to a specific document.
    """
    __tablename__ = "document_activity_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # Relationship to Document
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    
    # Activity details
    activity_type: Mapped[ActivityType] = mapped_column(
        SQLEnum(ActivityType, name="activity_type_enum", create_type=True),
        nullable=False
    )
    details: Mapped[Optional[str]] = mapped_column(Text, comment="JSON or text details about the activity")
    
    # Audit
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="activity_logs")

# --- Pydantic Schemas ---

# Base Schemas
class DocumentBase(BaseModel):
    """Base schema for document data."""
    filename: str = Field(..., max_length=255, example="passport_scan.pdf")
    document_type: str = Field(..., max_length=100, example="PASSPORT")
    uploaded_by_user_id: int = Field(..., ge=1, example=101)

class DocumentActivityLogBase(BaseModel):
    """Base schema for document activity log data."""
    activity_type: ActivityType = Field(..., example=ActivityType.OCR_EXTRACTION)
    details: Optional[str] = Field(None, example='{"extracted_fields": ["name", "dob"]}')

# Create Schemas
class DocumentCreate(DocumentBase):
    """Schema for creating a new document entry."""
    file_path: str = Field(..., max_length=512, example="/storage/uploads/doc_123.pdf")

class DocumentActivityLogCreate(DocumentActivityLogBase):
    """Schema for creating a new document activity log entry."""
    document_id: int = Field(..., ge=1, example=1)

# Update Schemas
class DocumentUpdate(BaseModel):
    """Schema for updating an existing document entry."""
    status: Optional[DocumentStatus] = Field(None, example=DocumentStatus.PROCESSING)
    document_type: Optional[str] = Field(None, max_length=100, example="ID_CARD")
    filename: Optional[str] = Field(None, max_length=255, example="new_filename.pdf")

class DocumentActivityLogUpdate(DocumentActivityLogBase):
    """Schema for updating an existing document activity log entry (rarely used)."""
    pass

# Response Schemas
class DocumentActivityLogResponse(DocumentActivityLogBase):
    """Schema for returning a document activity log entry."""
    id: int
    document_id: int
    timestamp: datetime

    class Config:
        from_attributes = True

class DocumentResponse(DocumentBase):
    """Schema for returning a document entry with full details."""
    id: int
    file_path: str
    status: DocumentStatus
    created_at: datetime
    updated_at: datetime
    
    # Nested relationship
    activity_logs: List[DocumentActivityLogResponse] = []

    class Config:
        from_attributes = True

class DocumentSimpleResponse(DocumentBase):
    """Schema for returning a document entry without nested logs (e.g., for list views)."""
    id: int
    status: DocumentStatus
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
