import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey, Date, Float, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

if TYPE_CHECKING:
    from typing import List # noqa: F401

Base = declarative_base()

class OnboardingStatus(enum.Enum):
    INITIATED = "initiated"
    BASIC_INFO_COLLECTED = "basic_info_collected"
    IDENTITY_INFO_COLLECTED = "identity_info_collected"
    DOCUMENTS_UPLOADED = "documents_uploaded"
    VERIFICATION_PENDING = "verification_pending"
    VERIFICATION_FAILED = "verification_failed"
    VERIFICATION_SUCCESS = "verification_success"
    ONBOARDING_COMPLETE = "onboarding_complete"

class DocumentType(enum.Enum):
    PASSPORT = "passport"
    DRIVER_LICENSE = "driver_license"
    NATIONAL_ID = "national_id"
    UTILITY_BILL = "utility_bill"
    BANK_STATEMENT = "bank_statement"

class VerificationStatus(enum.Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"
    PROCESSING = "processing"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    phone_number = Column(String(50), nullable=True)
    onboarding_status = Column(Enum(OnboardingStatus), nullable=False, default=OnboardingStatus.INITIATED)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    kyc_profile = relationship("KYCProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', status='{self.onboarding_status.value}')>"


class KYCProfile(Base):
    __tablename__ = "kyc_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    date_of_birth = Column(Date, nullable=False)
    address_line_1 = Column(String(255), nullable=False)
    city = Column(String(100), nullable=False)
    country = Column(String(100), nullable=False)
    nationality = Column(String(100), nullable=False)
    risk_score = Column(Float, nullable=False, default=0.0)
    last_reviewed_at = Column(DateTime, nullable=True)
    
    user = relationship("User", back_populates="kyc_profile")

    def __repr__(self):
        return f"<KYCProfile(id={self.id}, user_id={self.user_id}, country='{self.country}')>"


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    document_type = Column(Enum(DocumentType), nullable=False)
    file_path = Column(String(512), nullable=False) # In a real app, this would be a secure S3/storage URL
    upload_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    verification_status = Column(Enum(VerificationStatus), nullable=False, default=VerificationStatus.PENDING)
    rejection_reason = Column(String(512), nullable=True)

    user = relationship("User", back_populates="documents")

    def __repr__(self):
        return f"<Document(id={self.id}, type='{self.document_type.value}', status='{self.verification_status.value}')>"