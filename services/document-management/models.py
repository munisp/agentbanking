import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import String, Integer, DateTime, Text, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pydantic import BaseModel, Field, ConfigDict

from .config import DB_Base

# --- SQLAlchemy Models ---

class Document(DB_Base):
    """
    SQLAlchemy model for a Document.
    Represents a single document record in the document management system.
    """
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[int] = mapped_column(Integer, index=True, comment="User ID who owns the document")
    
    filename: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False, unique=True, comment="Absolute or relative path to the stored file")
    document_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True, comment="e.g., 'ID_CARD', 'INVOICE', 'CONTRACT'")
    
    status: Mapped[str] = mapped_column(String(50), default="UPLOADED", comment="e.g., 'UPLOADED', 'PROCESSING', 'VERIFIED', 'REJECTED'")
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    activity_logs: Mapped[List["DocumentActivityLog"]] = relationship(
        "DocumentActivityLog", 
        back_populates="document", 
        cascade="all, delete-orphan"
    )

    # Table constraints and indexes
    __table_args__ = (
        Index("idx_document_owner_type", owner_id, document_type),
    )

    def __repr__(self) -> str:
        return f"Document(id={self.id}, filename='{self.filename}', status='{self.status}')"


class DocumentActivityLog(DB_Base):
    """
    SQLAlchemy model for logging activities related to a Document.
    """
    __tablename__ = "document_activity_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), 
        index=True, 
        nullable=False
    )
    
    action: Mapped[str] = mapped_column(String(100), nullable=False, comment="e.g., 'CREATED', 'UPDATED', 'DOWNLOADED', 'VERIFIED'")
    details: Mapped[Optional[str]] = mapped_column(Text, comment="Additional details about the action")
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="activity_logs")

    def __repr__(self) -> str:
        return f"DocumentActivityLog(id={self.id}, document_id={self.document_id}, action='{self.action}')"

# --- Pydantic Schemas ---

class DocumentBase(BaseModel):
    """Base schema for document data."""
    filename: str = Field(..., max_length=255, description="The name of the file.")
    file_path: str = Field(..., max_length=512, description="The storage path of the file.")
    document_type: str = Field(..., max_length=50, description="The category of the document (e.g., INVOICE, CONTRACT).")
    owner_id: int = Field(..., description="The ID of the user who owns the document.")

class DocumentCreate(DocumentBase):
    """Schema for creating a new document."""
    # Status can be optionally set on creation, defaults to 'UPLOADED' in the model
    status: Optional[str] = Field(None, max_length=50, description="Initial status of the document.")

class DocumentUpdate(BaseModel):
    """Schema for updating an existing document."""
    filename: Optional[str] = Field(None, max_length=255, description="New filename.")
    document_type: Optional[str] = Field(None, max_length=50, description="New document type.")
    status: Optional[str] = Field(None, max_length=50, description="New status of the document.")
    # file_path and owner_id are typically immutable after creation

class DocumentResponse(DocumentBase):
    """Schema for returning a document object."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="Unique identifier for the document.")
    status: str = Field(..., max_length=50, description="Current status of the document.")
    created_at: datetime = Field(..., description="Timestamp of document creation.")
    updated_at: datetime = Field(..., description="Timestamp of last update.")

class DocumentActivityLogResponse(BaseModel):
    """Schema for returning an activity log object."""
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Unique identifier for the log entry.")
    document_id: uuid.UUID = Field(..., description="ID of the related document.")
    action: str = Field(..., max_length=100, description="The action performed (e.g., CREATED, DOWNLOADED).")
    details: Optional[str] = Field(None, description="Additional details about the action.")
    timestamp: datetime = Field(..., description="Timestamp of the action.")

class DocumentWithLogsResponse(DocumentResponse):
    """Schema for returning a document object along with its activity logs."""
    activity_logs: List[DocumentActivityLogResponse] = Field(..., description="List of all activity logs for this document.")
