"""
Two-Factor Authentication Database Models
"""

from sqlalchemy import Column, String, Integer, DateTime, Boolean, Text, Index, JSON
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import enum

Base = declarative_base()


class TwoFactorMethod(str, enum.Enum):
    """2FA methods"""
    TOTP = "totp"  # Time-based OTP (Google Authenticator, Authy)
    SMS = "sms"
    EMAIL = "email"
    BACKUP_CODE = "backup_code"


class TwoFactorConfig(Base):
    """User 2FA configuration"""
    __tablename__ = "two_factor_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(255), unique=True, nullable=False, index=True)
    is_enabled = Column(Boolean, default=False, nullable=False)
    primary_method = Column(String(50))  # TwoFactorMethod
    totp_secret = Column(Text)  # Encrypted TOTP secret
    totp_verified = Column(Boolean, default=False)
    sms_phone = Column(String(20))
    sms_verified = Column(Boolean, default=False)
    email_address = Column(String(255))
    email_verified = Column(Boolean, default=False)
    backup_codes_generated = Column(Boolean, default=False)
    backup_codes_count = Column(Integer, default=0)
    last_used_at = Column(DateTime)
    last_used_method = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_enabled', 'is_enabled'),
    )


class BackupCode(Base):
    """2FA backup codes"""
    __tablename__ = "backup_codes"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(255), nullable=False, index=True)
    code_hash = Column(String(255), nullable=False, unique=True)  # Hashed backup code
    is_used = Column(Boolean, default=False, nullable=False)
    used_at = Column(DateTime)
    used_ip = Column(String(45))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime)  # Optional expiry
    
    __table_args__ = (
        Index('idx_user_used', 'user_id', 'is_used'),
    )


class RecoveryCode(Base):
    """2FA recovery codes (different from backup codes)"""
    __tablename__ = "recovery_codes"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(255), nullable=False, index=True)
    code_hash = Column(String(255), nullable=False, unique=True)
    is_used = Column(Boolean, default=False, nullable=False)
    used_at = Column(DateTime)
    used_ip = Column(String(45))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        Index('idx_user_used', 'user_id', 'is_used'),
    )


class TrustedDevice(Base):
    """Trusted devices for 2FA bypass"""
    __tablename__ = "trusted_devices"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(255), nullable=False, index=True)
    device_id = Column(String(255), nullable=False, unique=True, index=True)
    device_name = Column(String(255))
    device_type = Column(String(50))  # mobile, desktop, tablet
    browser = Column(String(100))
    os = Column(String(100))
    ip_address = Column(String(45))
    is_trusted = Column(Boolean, default=True, nullable=False)
    trust_expires_at = Column(DateTime)  # Trust for N days
    last_used_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_user_trusted', 'user_id', 'is_trusted'),
        Index('idx_device_trusted', 'device_id', 'is_trusted'),
    )


class TwoFactorAttempt(Base):
    """2FA verification attempts"""
    __tablename__ = "two_factor_attempts"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(255), nullable=False, index=True)
    method = Column(String(50), nullable=False)  # TwoFactorMethod
    code_provided = Column(String(10))  # For audit (hashed or masked)
    success = Column(Boolean, default=False, nullable=False)
    failure_reason = Column(String(255))
    ip_address = Column(String(45))
    user_agent = Column(Text)
    device_id = Column(String(255))
    attempted_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        Index('idx_user_attempted', 'user_id', 'attempted_at'),
        Index('idx_success', 'success'),
    )


class TwoFactorSettings(Base):
    """Global 2FA settings"""
    __tablename__ = "two_factor_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(String(255), index=True)  # Null for global
    require_2fa = Column(Boolean, default=False, nullable=False)
    allowed_methods = Column(JSON)  # List of allowed TwoFactorMethod
    totp_issuer = Column(String(255), default="Nigerian Remittance")
    totp_digits = Column(Integer, default=6)
    totp_period = Column(Integer, default=30)  # Seconds
    backup_codes_count = Column(Integer, default=10)
    recovery_codes_count = Column(Integer, default=5)
    trust_device_days = Column(Integer, default=30)
    max_failed_attempts = Column(Integer, default=5)
    lockout_duration = Column(Integer, default=900)  # Seconds (15 min)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_org_active', 'organization_id', 'is_active'),
    )
