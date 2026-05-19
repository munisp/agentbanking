"""
PostgreSQL Database Models
Production-ready SQLAlchemy models with full schema
"""

from sqlalchemy import (
    Column, String, Integer, BigInteger, Boolean, DateTime,
    ForeignKey, Index, Text, DECIMAL, Enum as SQLEnum, UniqueConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime
import uuid
import enum

Base = declarative_base()


class KYCStatus(enum.Enum):
    """KYC verification status"""
    PENDING = "pending"
    IN_REVIEW = "in_review"
    VERIFIED = "verified"
    REJECTED = "rejected"
    EXPIRED = "expired"


class PIXKeyType(enum.Enum):
    """PIX key types"""
    EMAIL = "email"
    PHONE = "phone"
    CPF = "cpf"
    CNPJ = "cnpj"
    RANDOM = "random"


class TransferStatus(enum.Enum):
    """Transfer status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class User(Base):
    """User profile and metadata"""
    __tablename__ = 'users'
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # TigerBeetle integration
    tigerbeetle_account_id = Column(BigInteger, unique=True, nullable=False, index=True)
    
    # User information
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone = Column(String(50), unique=True, nullable=True, index=True)
    full_name = Column(String(255), nullable=False)
    
    # Location
    country_code = Column(String(3), nullable=False, index=True)
    state_province = Column(String(100))
    city = Column(String(100))
    
    # KYC
    kyc_status = Column(SQLEnum(KYCStatus), default=KYCStatus.PENDING, nullable=False, index=True)
    kyc_verified_at = Column(DateTime, nullable=True)
    kyc_data = Column(JSONB, nullable=True)
    
    # Compliance
    aml_risk_score = Column(Integer, default=0)
    sanctions_checked_at = Column(DateTime, nullable=True)
    pep_status = Column(Boolean, default=False)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    is_blocked = Column(Boolean, default=False, nullable=False)
    blocked_reason = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_login_at = Column(DateTime, nullable=True)
    
    # Relationships
    pix_keys = relationship("PIXKey", back_populates="user", cascade="all, delete-orphan")
    transfer_metadata = relationship("TransferMetadata", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_users_country_kyc', 'country_code', 'kyc_status'),
        Index('idx_users_active_created', 'is_active', 'created_at'),
    )
    
    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, tb_account={self.tigerbeetle_account_id})>"


class PIXKey(Base):
    """PIX key mappings to TigerBeetle accounts"""
    __tablename__ = 'pix_keys'
    
    # Primary key
    pix_key = Column(String(255), primary_key=True)
    
    # Foreign key
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # TigerBeetle integration
    tigerbeetle_account_id = Column(BigInteger, nullable=False, index=True)
    
    # PIX key details
    key_type = Column(SQLEnum(PIXKeyType), nullable=False)
    is_primary = Column(Boolean, default=False, nullable=False)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    verified_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="pix_keys")
    
    # Indexes
    __table_args__ = (
        Index('idx_pix_keys_user_active', 'user_id', 'is_active'),
        Index('idx_pix_keys_type', 'key_type'),
    )
    
    def __repr__(self):
        return f"<PIXKey(key={self.pix_key}, type={self.key_type}, tb_account={self.tigerbeetle_account_id})>"


class TransferMetadata(Base):
    """Transfer metadata (NO financial amounts - those are in TigerBeetle)"""
    __tablename__ = 'transfer_metadata'
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # TigerBeetle integration
    tigerbeetle_transfer_id = Column(BigInteger, unique=True, nullable=False, index=True)
    
    # User reference
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    
    # Transfer details (NO amounts)
    from_pix_key = Column(String(255), nullable=True)
    to_pix_key = Column(String(255), nullable=True)
    currency_code = Column(String(3), nullable=False)
    corridor = Column(String(50), nullable=False, index=True)  # PAPSS, CIPS, PIX, UPI, MOJALOOP
    
    # Status
    status = Column(SQLEnum(TransferStatus), default=TransferStatus.PENDING, nullable=False, index=True)
    
    # Compliance
    aml_checked = Column(Boolean, default=False, nullable=False)
    sanctions_checked = Column(Boolean, default=False, nullable=False)
    fraud_score = Column(Integer, default=0)
    compliance_notes = Column(Text, nullable=True)
    
    # Additional metadata
    description = Column(Text, nullable=True)
    reference_number = Column(String(100), unique=True, nullable=True, index=True)
    external_id = Column(String(255), nullable=True, index=True)
    metadata = Column(JSONB, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="transfer_metadata")
    
    # Indexes
    __table_args__ = (
        Index('idx_transfer_corridor_status', 'corridor', 'status'),
        Index('idx_transfer_created', 'created_at'),
        Index('idx_transfer_user_created', 'user_id', 'created_at'),
    )
    
    def __repr__(self):
        return f"<TransferMetadata(id={self.id}, tb_transfer={self.tigerbeetle_transfer_id}, status={self.status})>"


class AuditLog(Base):
    """Comprehensive audit trail"""
    __tablename__ = 'audit_logs'
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # User reference
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    
    # Event details
    event_type = Column(String(100), nullable=False, index=True)
    event_category = Column(String(50), nullable=False, index=True)  # AUTH, TRANSFER, KYC, COMPLIANCE
    action = Column(String(100), nullable=False)
    
    # Context
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    session_id = Column(String(255), nullable=True, index=True)
    
    # Details
    details = Column(JSONB, nullable=True)
    result = Column(String(50), nullable=False)  # SUCCESS, FAILURE, PENDING
    error_message = Column(Text, nullable=True)
    
    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    user = relationship("User", back_populates="audit_logs")
    
    # Indexes
    __table_args__ = (
        Index('idx_audit_event_created', 'event_type', 'created_at'),
        Index('idx_audit_category_created', 'event_category', 'created_at'),
        Index('idx_audit_user_created', 'user_id', 'created_at'),
    )
    
    def __repr__(self):
        return f"<AuditLog(id={self.id}, event={self.event_type}, result={self.result})>"


class ComplianceRecord(Base):
    """Compliance and regulatory records"""
    __tablename__ = 'compliance_records'
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Entity reference
    entity_type = Column(String(50), nullable=False, index=True)  # USER, TRANSFER
    entity_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    # Compliance check
    check_type = Column(String(100), nullable=False, index=True)  # AML, SANCTIONS, KYC, PEP
    check_provider = Column(String(100), nullable=True)
    
    # Results
    status = Column(String(50), nullable=False, index=True)  # PASS, FAIL, REVIEW, ERROR
    risk_score = Column(Integer, default=0)
    risk_level = Column(String(50), nullable=True)  # LOW, MEDIUM, HIGH, CRITICAL
    
    # Details
    findings = Column(JSONB, nullable=True)
    recommendations = Column(Text, nullable=True)
    reviewed_by = Column(String(255), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=True)
    
    # Indexes
    __table_args__ = (
        Index('idx_compliance_entity', 'entity_type', 'entity_id'),
        Index('idx_compliance_check_status', 'check_type', 'status'),
        Index('idx_compliance_risk', 'risk_level', 'created_at'),
    )
    
    def __repr__(self):
        return f"<ComplianceRecord(id={self.id}, type={self.check_type}, status={self.status})>"


class CDCEvent(Base):
    """Change Data Capture events from TigerBeetle"""
    __tablename__ = 'cdc_events'
    
    # Primary key
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # Event details
    event_type = Column(String(50), nullable=False, index=True)  # ACCOUNT_CREATED, TRANSFER_COMPLETED
    tigerbeetle_id = Column(BigInteger, nullable=False, index=True)
    
    # Event data
    event_data = Column(JSONB, nullable=False)
    
    # Processing
    processed = Column(Boolean, default=False, nullable=False, index=True)
    processed_at = Column(DateTime, nullable=True)
    processing_error = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    
    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Indexes
    __table_args__ = (
        Index('idx_cdc_processed_created', 'processed', 'created_at'),
        Index('idx_cdc_type_processed', 'event_type', 'processed'),
    )
    
    def __repr__(self):
        return f"<CDCEvent(id={self.id}, type={self.event_type}, processed={self.processed})>"
