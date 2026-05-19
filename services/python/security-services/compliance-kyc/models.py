from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey, Float, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import enum

class KYCStatus(enum.Enum):
    PENDING = "PENDING"
    IN_REVIEW = "IN_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ON_HOLD = "ON_HOLD"

class DocumentType(enum.Enum):
    PASSPORT = "PASSPORT"
    DRIVERS_LICENSE = "DRIVERS_LICENSE"
    NATIONAL_ID = "NATIONAL_ID"
    PROOF_OF_ADDRESS = "PROOF_OF_ADDRESS"
    OTHER = "OTHER"

class CheckType(enum.Enum):
    IDENTITY_VERIFICATION = "IDENTITY_VERIFICATION"
    SANCTIONS_SCREENING = "SANCTIONS_SCREENING"
    PEP_SCREENING = "PEP_SCREENING"
    ADDRESS_VERIFICATION = "ADDRESS_VERIFICATION"
    DOCUMENT_VERIFICATION = "DOCUMENT_VERIFICATION"

class CheckStatus(enum.Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    PENDING = "PENDING"
    ERROR = "ERROR"

class KYCRecord(Base):
    __tablename__ = "kyc_records"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(String, index=True, unique=True, nullable=False, comment="External ID of the customer being verified")
    status = Column(Enum(KYCStatus), default=KYCStatus.PENDING, nullable=False)
    risk_score = Column(Float, default=0.0, nullable=False)
    reviewer_id = Column(String, nullable=True, comment="ID of the internal reviewer")
    rejection_reason = Column(String, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    documents = relationship("KYCDocument", back_populates="kyc_record", cascade="all, delete-orphan")
    checks = relationship("KYCCheck", back_populates="kyc_record", cascade="all, delete-orphan")

    __table_args__ = (
        # Example of a composite index for faster lookups
        # Index('ix_kyc_customer_status', customer_id, status),
    )

class KYCDocument(Base):
    __tablename__ = "kyc_documents"

    id = Column(Integer, primary_key=True, index=True)
    kyc_record_id = Column(Integer, ForeignKey("kyc_records.id"), nullable=False)
    document_type = Column(Enum(DocumentType), nullable=False)
    file_url = Column(String, nullable=False, comment="URL to the stored document file")
    verification_status = Column(Enum(CheckStatus), default=CheckStatus.PENDING, nullable=False)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationship
    kyc_record = relationship("KYCRecord", back_populates="documents")

class KYCCheck(Base):
    __tablename__ = "kyc_checks"

    id = Column(Integer, primary_key=True, index=True)
    kyc_record_id = Column(Integer, ForeignKey("kyc_records.id"), nullable=False)
    check_type = Column(Enum(CheckType), nullable=False)
    check_status = Column(Enum(CheckStatus), default=CheckStatus.PENDING, nullable=False)
    provider_response = Column(String, nullable=True, comment="Raw response from the external check provider")
    is_manual_override = Column(Boolean, default=False, nullable=False)
    performed_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    kyc_record = relationship("KYCRecord", back_populates="checks")