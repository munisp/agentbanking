"""
CDP Database Models
SQLAlchemy ORM models for CDP-related tables
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Numeric, Text, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import INET, JSONB

from app.core.database import Base

class CDPUser(Base):
    """CDP User model"""
    __tablename__ = "cdp_users"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    cdp_user_id = Column(String(255), unique=True, nullable=False, index=True)
    wallet_address = Column(String(42), unique=True, nullable=False, index=True)
    email = Column(String(255), nullable=False, index=True)
    email_verified = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login_at = Column(DateTime(timezone=True))
    
    # Relationships
    devices = relationship("CDPDevice", back_populates="cdp_user", cascade="all, delete-orphan")
    sessions = relationship("CDPSession", back_populates="cdp_user", cascade="all, delete-orphan")
    transactions = relationship("CDPWalletTransaction", back_populates="cdp_user", cascade="all, delete-orphan")
    audit_logs = relationship("CDPAuditLog", back_populates="cdp_user")
    
    __table_args__ = (
        Index('ix_cdp_users_user_wallet', 'user_id', 'wallet_address'),
    )

class CDPDevice(Base):
    """CDP Device model for multi-device support"""
    __tablename__ = "cdp_devices"
    
    id = Column(Integer, primary_key=True, index=True)
    cdp_user_id = Column(Integer, ForeignKey("cdp_users.id", ondelete="CASCADE"), nullable=False)
    device_id = Column(String(255), unique=True, nullable=False, index=True)
    device_name = Column(String(255))
    device_type = Column(String(50))  # ios, android, web
    device_fingerprint = Column(Text)
    is_active = Column(Boolean, default=True)
    last_used_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationship
    cdp_user = relationship("CDPUser", back_populates="devices")
    
    __table_args__ = (
        Index('ix_active_devices', 'cdp_user_id', postgresql_where=(is_active == True)),
    )

class CDPSession(Base):
    """CDP Session model"""
    __tablename__ = "cdp_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    cdp_user_id = Column(Integer, ForeignKey("cdp_users.id", ondelete="CASCADE"), nullable=False)
    device_id = Column(Integer, ForeignKey("cdp_devices.id", ondelete="SET NULL"))
    session_token = Column(String(255), unique=True, nullable=False, index=True)
    refresh_token = Column(String(255), unique=True)
    ip_address = Column(INET)
    user_agent = Column(Text)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    revoked_at = Column(DateTime(timezone=True))
    
    # Relationship
    cdp_user = relationship("CDPUser", back_populates="sessions")
    
    __table_args__ = (
        Index('ix_active_sessions', 'cdp_user_id', postgresql_where=(revoked_at == None)),
        Index('ix_cdp_sessions_user_expires', 'cdp_user_id', 'expires_at'),
    )

class CDPOTP(Base):
    """CDP OTP model"""
    __tablename__ = "cdp_otps"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), nullable=False, index=True)
    otp_hash = Column(String(255), nullable=False)
    salt = Column(String(255), nullable=False)
    purpose = Column(String(50), nullable=False)  # login, signup, verify_email
    attempts = Column(Integer, default=0)
    max_attempts = Column(Integer, default=3)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    verified_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (
        Index('ix_cdp_otps_email_expires', 'email', 'expires_at', postgresql_where=(verified_at == None)),
    )

class CDPWalletTransaction(Base):
    """CDP Wallet Transaction model"""
    __tablename__ = "cdp_wallet_transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    cdp_user_id = Column(Integer, ForeignKey("cdp_users.id", ondelete="CASCADE"), nullable=False)
    transaction_hash = Column(String(66), unique=True, nullable=False, index=True)
    from_address = Column(String(42), nullable=False, index=True)
    to_address = Column(String(42), nullable=False, index=True)
    value = Column(Numeric(78, 0), nullable=False)  # Wei amount
    token_address = Column(String(42))  # NULL for ETH
    network = Column(String(50), nullable=False)  # base-mainnet, base-sepolia
    status = Column(String(50), nullable=False, index=True)  # pending, confirmed, failed
    block_number = Column(Integer)
    gas_used = Column(Integer)
    gas_price = Column(Numeric(78, 0))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    confirmed_at = Column(DateTime(timezone=True))
    
    # Relationship
    cdp_user = relationship("CDPUser", back_populates="transactions")
    
    __table_args__ = (
        Index('ix_pending_transactions', 'cdp_user_id', postgresql_where=(status == 'pending')),
    )

class CDPAuditLog(Base):
    """CDP Audit Log model"""
    __tablename__ = "cdp_audit_log"
    
    id = Column(Integer, primary_key=True, index=True)
    cdp_user_id = Column(Integer, ForeignKey("cdp_users.id", ondelete="SET NULL"))
    action = Column(String(100), nullable=False, index=True)
    details = Column(JSONB)
    ip_address = Column(INET)
    user_agent = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Relationship
    cdp_user = relationship("CDPUser", back_populates="audit_logs")
