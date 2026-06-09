from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Enum, Text, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from database import Base

class CaseStatus(enum.Enum):
    PENDING = "PENDING"
    IN_REVIEW = "IN_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CLOSED = "CLOSED"

class RiskLevel(enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class EnhancedKYCCase(Base):
    __tablename__ = "enhanced_kyc_cases"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(String, index=True, nullable=False, unique=True, comment="ID of the customer being reviewed")
    risk_level = Column(Enum(RiskLevel), default=RiskLevel.MEDIUM, nullable=False)
    status = Column(Enum(CaseStatus), default=CaseStatus.PENDING, nullable=False)
    assigned_analyst_id = Column(String, index=True, nullable=True, comment="ID of the analyst handling the case")
    
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationship to EDD details
    details = relationship("EDDDetail", back_populates="kyc_case", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        # Unique constraint on customer_id to ensure only one active EDD case per customer
        # This can be relaxed if multiple cases are allowed, but for simplicity, we enforce uniqueness.
        # UniqueConstraint('customer_id', name='uq_customer_id'),
    )

class EDDDetail(Base):
    __tablename__ = "edd_details"

    id = Column(Integer, primary_key=True, index=True)
    kyc_case_id = Column(Integer, ForeignKey("enhanced_kyc_cases.id", ondelete="CASCADE"), nullable=False, unique=True)
    
    # Core EDD findings
    source_of_funds_verified = Column(Boolean, default=False, nullable=False)
    source_of_wealth_description = Column(Text, nullable=True)
    ubo_identified = Column(Boolean, default=False, nullable=False)
    ubo_details = Column(Text, nullable=True)
    
    # Screening results
    adverse_media_hits = Column(Integer, default=0, nullable=False)
    sanctions_list_hit = Column(Boolean, default=False, nullable=False)
    
    # Transaction monitoring summary
    suspicious_activity_report_filed = Column(Boolean, default=False, nullable=False)
    transaction_volume_anomaly_score = Column(Float, default=0.0, nullable=False)
    
    # Analyst conclusion
    analyst_notes = Column(Text, nullable=True)
    
    # Relationship back to the case
    kyc_case = relationship("EnhancedKYCCase", back_populates="details")

    __table_args__ = (
        # Ensure only one detail record per case
        # This is also enforced by the unique=True on kyc_case_id
    )