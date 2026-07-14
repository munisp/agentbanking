"""
Password Security Database Models
"""

from sqlalchemy import Column, String, Integer, DateTime, Boolean, Text, Index, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
import enum

Base = declarative_base()


class PasswordStrengthLevel(str, enum.Enum):
    """Password strength levels"""
    VERY_WEAK = "very_weak"
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"
    VERY_STRONG = "very_strong"


class PasswordHistory(Base):
    """Password history for users"""
    __tablename__ = "password_history"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(255), nullable=False, index=True)
    password_hash = Column(Text, nullable=False)
    strength_score = Column(Integer, nullable=False)  # 0-100
    strength_level = Column(String(20), nullable=False)  # PasswordStrengthLevel
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_by = Column(String(255))
    
    __table_args__ = (
        Index('idx_user_created', 'user_id', 'created_at'),
    )


class PasswordResetToken(Base):
    """Password reset tokens"""
    __tablename__ = "password_reset_tokens"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(255), nullable=False, index=True)
    token = Column(String(255), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False, nullable=False)
    used_at = Column(DateTime)
    ip_address = Column(String(45))  # IPv6 compatible
    user_agent = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        Index('idx_token_expires', 'token', 'expires_at'),
        Index('idx_user_used', 'user_id', 'used'),
    )


class PasswordBreachCheck(Base):
    """Password breach check results"""
    __tablename__ = "password_breach_checks"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(255), nullable=False, index=True)
    password_hash_prefix = Column(String(10), nullable=False)  # First 5 chars of SHA-1
    is_breached = Column(Boolean, default=False, nullable=False)
    breach_count = Column(Integer, default=0)  # Number of times seen in breaches
    checked_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    api_response = Column(JSON)  # Full API response for audit
    
    __table_args__ = (
        Index('idx_user_checked', 'user_id', 'checked_at'),
    )


class PasswordPolicy(Base):
    """Password policy configuration"""
    __tablename__ = "password_policies"
    
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(String(255), index=True)  # Null for global policy
    min_length = Column(Integer, default=8, nullable=False)
    require_uppercase = Column(Boolean, default=True, nullable=False)
    require_lowercase = Column(Boolean, default=True, nullable=False)
    require_numbers = Column(Boolean, default=True, nullable=False)
    require_special_chars = Column(Boolean, default=True, nullable=False)
    min_strength_score = Column(Integer, default=60, nullable=False)  # 0-100
    password_history_count = Column(Integer, default=5, nullable=False)  # Prevent reuse
    max_age_days = Column(Integer, default=90)  # Force password change
    check_breach = Column(Boolean, default=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String(255))
    updated_by = Column(String(255))
    
    __table_args__ = (
        Index('idx_org_active', 'organization_id', 'is_active'),
    )


class PasswordChangeLog(Base):
    """Audit log for password changes"""
    __tablename__ = "password_change_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(255), nullable=False, index=True)
    change_type = Column(String(50), nullable=False)  # reset, change, force_change
    old_strength_score = Column(Integer)
    new_strength_score = Column(Integer)
    ip_address = Column(String(45))
    user_agent = Column(Text)
    success = Column(Boolean, default=True, nullable=False)
    failure_reason = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        Index('idx_user_created', 'user_id', 'created_at'),
        Index('idx_type_success', 'change_type', 'success'),
    )
