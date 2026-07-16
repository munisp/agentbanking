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
    UniqueConstraint,
    Index,
    Boolean,
)
from sqlalchemy.orm import relationship, declarative_base

# --- SQLAlchemy Base ---
Base = declarative_base()

# --- Enums ---

class OnboardingStatus(str, enum.Enum):
    """
    Represents the current status of the tenant onboarding application.
    """
    PENDING_SUBMISSION = "PENDING_SUBMISSION"
    SUBMITTED = "SUBMITTED"
    IN_REVIEW = "IN_REVIEW"
    KYB_PENDING = "KYB_PENDING"
    KYB_FAILED = "KYB_FAILED"
    KYB_PASSED = "KYB_PASSED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ONBOARDED = "ONBOARDED"

class ActivityType(str, enum.Enum):
    """
    Represents the type of activity logged for an onboarding application.
    """
    STATUS_CHANGE = "STATUS_CHANGE"
    DATA_UPDATE = "DATA_UPDATE"
    DOCUMENT_UPLOAD = "DOCUMENT_UPLOAD"
    SYSTEM_ACTION = "SYSTEM_ACTION"
    USER_ACTION = "USER_ACTION"

# --- SQLAlchemy Models ---

class TenantOnboarding(Base):
    """
    Main model for a tenant's onboarding application.
    """
    __tablename__ = "tenant_onboarding"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, unique=True, index=True, nullable=False, doc="Unique identifier for the tenant, once onboarded.")
    
    # Application details
    company_name = Column(String, index=True, nullable=False)
    contact_email = Column(String, unique=True, nullable=False)
    contact_phone = Column(String)
    business_type = Column(String)
    
    # Status and Timestamps
    status = Column(Enum(OnboardingStatus), default=OnboardingStatus.PENDING_SUBMISSION, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    activity_log = relationship("OnboardingActivityLog", back_populates="application", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_tenant_onboarding_company_name_status", company_name, status),
    )

class OnboardingActivityLog(Base):
    """
    Activity log for tracking state changes and actions on an onboarding application.
    """
    __tablename__ = "onboarding_activity_log"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("tenant_onboarding.id"), nullable=False)
    
    activity_type = Column(Enum(ActivityType), nullable=False)
    description = Column(Text, nullable=False, doc="Detailed description of the activity.")
    
    # Contextual data
    actor = Column(String, nullable=False, doc="User or system responsible for the action.")
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Optional fields for status changes
    old_status = Column(Enum(OnboardingStatus), nullable=True)
    new_status = Column(Enum(OnboardingStatus), nullable=True)

    # Relationships
    application = relationship("TenantOnboarding", back_populates="activity_log")

    __table_args__ = (
        Index("ix_activity_log_application_type", application_id, activity_type),
    )

# --- Pydantic Schemas ---

# Base Schemas
class TenantOnboardingBase(BaseModel):
    """Base schema for tenant onboarding data."""
    company_name: str = Field(..., example="Acme Corp")
    contact_email: str = Field(..., example="contact@acmecorp.com")
    contact_phone: Optional[str] = Field(None, example="+1-555-123-4567")
    business_type: Optional[str] = Field(None, example="Software Development")

# Create Schema
class TenantOnboardingCreate(TenantOnboardingBase):
    """Schema for creating a new tenant onboarding application."""
    pass

# Update Schema
class TenantOnboardingUpdate(TenantOnboardingBase):
    """Schema for updating an existing tenant onboarding application."""
    company_name: Optional[str] = Field(None, example="Acme Corp")
    contact_email: Optional[str] = Field(None, example="contact@acmecorp.com")

# Response Schema
class TenantOnboardingResponse(TenantOnboardingBase):
    """Schema for returning a tenant onboarding application."""
    id: int = Field(..., example=1)
    tenant_id: str = Field(..., example="T-12345")
    status: OnboardingStatus = Field(..., example=OnboardingStatus.IN_REVIEW)
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True
        use_enum_values = True

# Activity Log Schemas
class OnboardingActivityLogBase(BaseModel):
    """Base schema for an activity log entry."""
    activity_type: ActivityType
    description: str
    actor: str
    old_status: Optional[OnboardingStatus] = None
    new_status: Optional[OnboardingStatus] = None

class OnboardingActivityLogResponse(OnboardingActivityLogBase):
    """Schema for returning an activity log entry."""
    id: int
    application_id: int
    timestamp: datetime

    class Config:
        orm_mode = True
        use_enum_values = True

# Business-specific Schemas
class StatusUpdate(BaseModel):
    """Schema for updating the status of an onboarding application."""
    new_status: OnboardingStatus = Field(..., example=OnboardingStatus.KYB_PASSED)
    actor: str = Field(..., example="system_kyb_check")
    reason: Optional[str] = Field(None, example="All documents verified successfully.")

class TenantIdAssignment(BaseModel):
    """Schema for assigning a final tenant ID upon successful onboarding."""
    tenant_id: str = Field(..., example="T-98765")
    actor: str = Field(..., example="system_final_approval")
