import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Enum, Text
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class VerificationType(enum.Enum):
    KYC = "KYC"
    KYB = "KYB"

class VerificationStatus(enum.Enum):
    PENDING = "PENDING"
    IN_REVIEW = "IN_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"

class Partner(Base):
    __tablename__ = "partners"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False)
    api_key_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    requests = relationship("VerificationRequest", back_populates="partner")

class VerificationRequest(Base):
    __tablename__ = "verification_requests"

    id = Column(Integer, primary_key=True, index=True)
    partner_id = Column(Integer, ForeignKey("partners.id"), nullable=False)
    external_ref_id = Column(String(255), index=True, nullable=False) # ID from the partner's system
    verification_type = Column(Enum(VerificationType), nullable=False)
    status = Column(Enum(VerificationStatus), default=VerificationStatus.PENDING, nullable=False)
    subject_data = Column(Text, nullable=False) # JSON data about the subject (person/business)
    result_details = Column(Text, nullable=True) # JSON data about the verification result
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    partner = relationship("Partner", back_populates="requests")

    __table_args__ = (
        # Ensure a partner cannot submit the same external_ref_id twice
        # This is a critical business constraint for idempotency
        {"unique_together": ("partner_id", "external_ref_id")},
    )

# Note: For a full production system, you would likely have separate tables for
# KYCSubject and KYBSubject, and a Documents table. For this exercise,
# we'll keep the subject_data and result_details as JSON/Text fields
# in the VerificationRequest for simplicity and flexibility.