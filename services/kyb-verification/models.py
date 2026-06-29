import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, declarative_base

# --- SQLAlchemy Base Setup ---

Base = declarative_base()

# --- Enums ---

class VerificationStatus(str, Enum):
    """
    Possible statuses for a KYB verification record.
    """
    PENDING = "PENDING"
    IN_REVIEW = "IN_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    ON_HOLD = "ON_HOLD"

# --- SQLAlchemy Models ---

class KybVerification(Base):
    """
    Main model for Know Your Business (KYB) verification records.
    """
    __tablename__ = "kyb_verifications"

    id = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    business_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        doc="ID of the business entity being verified (external reference)",
    )
    status = Column(
        String,
        nullable=False,
        default=VerificationStatus.PENDING.value,
        doc="Current status of the verification process",
    )
    verification_type = Column(
        String,
        nullable=False,
        default="STANDARD",
        doc="Type of verification (e.g., STANDARD, ENHANCED)",
    )
    business_name = Column(String, nullable=False, doc="Legal name of the business")
    registration_number = Column(
        String, nullable=False, unique=True, doc="Business registration number"
    )
    country_code = Column(String(2), nullable=False, doc="ISO 3166-1 alpha-2 country code")
    
    # Timestamps
    created_at = Column(
        DateTime(timezone=True), nullable=False, default=func.now(), doc="Record creation timestamp"
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        onupdate=func.now(),
        doc="Record last update timestamp",
    )
    
    # Relationships
    activity_logs = relationship(
        "KybVerificationActivityLog",
        back_populates="verification",
        cascade="all, delete-orphan",
        order_by="KybVerificationActivityLog.created_at.desc()",
    )

    __table_args__ = (
        Index(
            "ix_kyb_verifications_business_id_status",
            "business_id",
            "status",
        ),
    )

class KybVerificationActivityLog(Base):
    """
    Activity log for changes and events related to a KYB verification record.
    """
    __tablename__ = "kyb_verification_activity_logs"

    id = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    verification_id = Column(
        UUID(as_uuid=True),
        ForeignKey("kyb_verifications.id"),
        nullable=False,
        index=True,
        doc="Foreign key to the KybVerification record",
    )
    timestamp = Column(
        DateTime(timezone=True), nullable=False, default=func.now(), doc="Timestamp of the activity"
    )
    actor = Column(
        String, nullable=False, doc="User or system that performed the action"
    )
    action = Column(
        String, nullable=False, doc="Type of action (e.g., STATUS_CHANGE, DOCUMENT_UPLOAD, COMMENT)"
    )
    details = Column(
        Text, nullable=True, doc="JSON or text details about the action"
    )

    # Relationships
    verification = relationship(
        "KybVerification", back_populates="activity_logs"
    )

# --- Pydantic Schemas ---

# Base Schemas
class KybVerificationBase(BaseModel):
    """Base schema for KYB verification data."""
    business_id: uuid.UUID = Field(..., description="ID of the business entity.")
    verification_type: str = Field("STANDARD", description="Type of verification (e.g., STANDARD, ENHANCED).")
    business_name: str = Field(..., description="Legal name of the business.")
    registration_number: str = Field(..., description="Business registration number.")
    country_code: str = Field(..., min_length=2, max_length=2, description="ISO 3166-1 alpha-2 country code.")

class KybVerificationActivityLogBase(BaseModel):
    """Base schema for KYB verification activity log data."""
    actor: str = Field(..., description="User or system that performed the action.")
    action: str = Field(..., description="Type of action (e.g., STATUS_CHANGE, DOCUMENT_UPLOAD).")
    details: Optional[str] = Field(None, description="JSON or text details about the action.")

# Create Schemas
class KybVerificationCreate(KybVerificationBase):
    """Schema for creating a new KYB verification record."""
    pass

class KybVerificationActivityLogCreate(KybVerificationActivityLogBase):
    """Schema for creating a new activity log entry."""
    pass

# Update Schemas
class KybVerificationUpdate(BaseModel):
    """Schema for updating an existing KYB verification record."""
    status: Optional[VerificationStatus] = Field(None, description="New status of the verification.")
    verification_type: Optional[str] = Field(None, description="New type of verification.")
    business_name: Optional[str] = Field(None, description="New legal name of the business.")
    country_code: Optional[str] = Field(None, min_length=2, max_length=2, description="New ISO 3166-1 alpha-2 country code.")
    # registration_number is typically immutable, so it's excluded from update

# Response Schemas
class KybVerificationActivityLogResponse(KybVerificationActivityLogBase):
    """Response schema for an activity log entry."""
    id: uuid.UUID
    verification_id: uuid.UUID
    timestamp: datetime

    class Config:
        from_attributes = True

class KybVerificationResponse(KybVerificationBase):
    """Response schema for a KYB verification record."""
    id: uuid.UUID
    status: VerificationStatus
    created_at: datetime
    updated_at: datetime
    
    activity_logs: List[KybVerificationActivityLogResponse] = Field(
        [], description="List of activity logs for this verification."
    )

    class Config:
        from_attributes = True
        use_enum_values = True
