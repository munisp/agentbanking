import enum
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field
from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

# --- SQLAlchemy Base Setup (Minimal for models) ---
Base = declarative_base()


# --- Enums ---
class KYCStatus(enum.Enum):
    """
    Defines the possible statuses for a KYC application.
    """
    PENDING = "PENDING"
    IN_REVIEW = "IN_REVIEW"
    NEEDS_CORRECTION = "NEEDS_CORRECTION"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class DocumentType(enum.Enum):
    """
    Defines the types of documents that can be submitted for KYC.
    """
    PASSPORT = "PASSPORT"
    NATIONAL_ID = "NATIONAL_ID"
    DRIVING_LICENSE = "DRIVING_LICENSE"
    PROOF_OF_ADDRESS = "PROOF_OF_ADDRESS"
    OTHER = "OTHER"


class DocumentStatus(enum.Enum):
    """
    Defines the status of an individual document.
    """
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


# --- SQLAlchemy Models ---
class KYCApplication(Base):
    """
    Represents a single KYC application submitted by a user.
    """
    __tablename__ = "kyc_applications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    current_status = Column(Enum(KYCStatus), default=KYCStatus.PENDING, nullable=False)
    submission_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    reviewer_id = Column(Integer, index=True, nullable=True)
    rejection_reason = Column(Text, nullable=True)

    # Relationships
    documents = relationship("KYCDocument", back_populates="application", cascade="all, delete-orphan")
    status_history = relationship("KYCStatusHistory", back_populates="application", order_by="KYCStatusHistory.timestamp", cascade="all, delete-orphan")


class KYCDocument(Base):
    """
    Represents a document submitted as part of a KYC application.
    """
    __tablename__ = "kyc_documents"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("kyc_applications.id"), nullable=False)
    document_type = Column(Enum(DocumentType), nullable=False)
    file_url = Column(String(512), nullable=False)  # URL to the stored document file
    upload_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    document_status = Column(Enum(DocumentStatus), default=DocumentStatus.UPLOADED, nullable=False)
    verification_details = Column(Text, nullable=True) # Details from OCR/verification process

    # Relationships
    application = relationship("KYCApplication", back_populates="documents")


class KYCStatusHistory(Base):
    """
    Tracks the historical status changes for a KYC application.
    """
    __tablename__ = "kyc_status_history"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("kyc_applications.id"), nullable=False)
    status = Column(Enum(KYCStatus), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    notes = Column(Text, nullable=True)
    changed_by_id = Column(Integer, nullable=True) # User or Reviewer ID who made the change

    # Relationships
    application = relationship("KYCApplication", back_populates="status_history")


# --- Pydantic Schemas (Base) ---
class DocumentBase(BaseModel):
    """Base schema for document data."""
    document_type: DocumentType
    file_url: str = Field(..., max_length=512)


class ApplicationBase(BaseModel):
    """Base schema for KYC application data."""
    user_id: int


# --- Pydantic Schemas (Create/Update) ---
class DocumentCreate(DocumentBase):
    """Schema for creating a new document."""
    pass


class ApplicationCreate(ApplicationBase):
    """Schema for submitting a new KYC application."""
    documents: List[DocumentCreate]


class ApplicationUpdateStatus(BaseModel):
    """Schema for updating the status of a KYC application."""
    new_status: KYCStatus
    reviewer_id: int
    notes: Optional[str] = None
    rejection_reason: Optional[str] = None


class DocumentUpdateStatus(BaseModel):
    """Schema for updating the status of an individual document."""
    document_status: DocumentStatus
    verification_details: Optional[str] = None


# --- Pydantic Schemas (Read/Response) ---
class DocumentResponse(DocumentBase):
    """Schema for reading a document record."""
    id: int
    application_id: int
    upload_date: datetime
    document_status: DocumentStatus
    verification_details: Optional[str] = None

    class Config:
        orm_mode = True


class StatusHistoryResponse(BaseModel):
    """Schema for reading a status history record."""
    id: int
    application_id: int
    status: KYCStatus
    timestamp: datetime
    notes: Optional[str] = None
    changed_by_id: Optional[int] = None

    class Config:
        orm_mode = True


class ApplicationResponse(ApplicationBase):
    """Full schema for reading a KYC application record."""
    id: int
    current_status: KYCStatus
    submission_date: datetime
    last_updated: datetime
    reviewer_id: Optional[int] = None
    rejection_reason: Optional[str] = None
    
    documents: List[DocumentResponse] = []
    status_history: List[StatusHistoryResponse] = []

    class Config:
        orm_mode = True
