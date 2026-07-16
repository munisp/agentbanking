"""
Rate Limiting Database Models
"""

from sqlalchemy import Column, String, Integer, DateTime, Boolean, Text, Index, JSON, BigInteger
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import enum

Base = declarative_base()


class RateLimitType(str, enum.Enum):
    """Types of rate limits"""
    IP_BASED = "ip_based"
    USER_BASED = "user_based"
    API_KEY_BASED = "api_key_based"
    ENDPOINT_BASED = "endpoint_based"
    GLOBAL = "global"


class RateLimitWindow(str, enum.Enum):
    """Time window for rate limiting"""
    SECOND = "second"
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"


class RateLimitRule(Base):
    """Rate limit rules configuration"""
    __tablename__ = "rate_limit_rules"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    limit_type = Column(String(50), nullable=False)  # RateLimitType
    endpoint_pattern = Column(String(500))  # e.g., /api/v1/auth/*
    max_requests = Column(Integer, nullable=False)
    window_size = Column(Integer, nullable=False)  # Size in seconds
    window_type = Column(String(20), nullable=False)  # RateLimitWindow
    is_active = Column(Boolean, default=True, nullable=False)
    priority = Column(Integer, default=0)  # Higher priority rules checked first
    block_duration = Column(Integer, default=300)  # Seconds to block after limit exceeded
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String(255))
    updated_by = Column(String(255))
    
    __table_args__ = (
        Index('idx_type_active', 'limit_type', 'is_active'),
        Index('idx_priority', 'priority'),
    )


class RateLimitCounter(Base):
    """Rate limit counters (Redis alternative for persistence)"""
    __tablename__ = "rate_limit_counters"
    
    id = Column(BigInteger, primary_key=True, index=True)
    rule_id = Column(Integer, nullable=False, index=True)
    identifier = Column(String(255), nullable=False)  # IP, user_id, API key, etc.
    endpoint = Column(String(500), nullable=False)
    request_count = Column(Integer, default=0, nullable=False)
    window_start = Column(DateTime, nullable=False)
    window_end = Column(DateTime, nullable=False)
    last_request_at = Column(DateTime, default=datetime.utcnow)
    is_blocked = Column(Boolean, default=False, nullable=False)
    blocked_until = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_rule_identifier', 'rule_id', 'identifier'),
        Index('idx_window_end', 'window_end'),
        Index('idx_blocked', 'is_blocked', 'blocked_until'),
    )


class RateLimitViolation(Base):
    """Rate limit violations log"""
    __tablename__ = "rate_limit_violations"
    
    id = Column(BigInteger, primary_key=True, index=True)
    rule_id = Column(Integer, nullable=False, index=True)
    identifier = Column(String(255), nullable=False, index=True)
    endpoint = Column(String(500), nullable=False)
    request_count = Column(Integer, nullable=False)
    limit = Column(Integer, nullable=False)
    window_type = Column(String(20), nullable=False)
    ip_address = Column(String(45))
    user_agent = Column(Text)
    request_headers = Column(JSON)
    violation_time = Column(DateTime, default=datetime.utcnow, nullable=False)
    blocked = Column(Boolean, default=False, nullable=False)
    blocked_duration = Column(Integer)  # Seconds
    
    __table_args__ = (
        Index('idx_identifier_time', 'identifier', 'violation_time'),
        Index('idx_endpoint_time', 'endpoint', 'violation_time'),
    )


class RateLimitWhitelist(Base):
    """Whitelist for bypassing rate limits"""
    __tablename__ = "rate_limit_whitelist"
    
    id = Column(Integer, primary_key=True, index=True)
    identifier_type = Column(String(50), nullable=False)  # ip, user_id, api_key
    identifier = Column(String(255), nullable=False, unique=True, index=True)
    reason = Column(Text)
    is_active = Column(Boolean, default=True, nullable=False)
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String(255))
    
    __table_args__ = (
        Index('idx_type_identifier', 'identifier_type', 'identifier'),
        Index('idx_active_expires', 'is_active', 'expires_at'),
    )


class RateLimitStats(Base):
    """Aggregated rate limit statistics"""
    __tablename__ = "rate_limit_stats"
    
    id = Column(BigInteger, primary_key=True, index=True)
    rule_id = Column(Integer, nullable=False, index=True)
    endpoint = Column(String(500), nullable=False)
    date = Column(DateTime, nullable=False)  # Aggregated by hour/day
    total_requests = Column(BigInteger, default=0)
    blocked_requests = Column(BigInteger, default=0)
    unique_identifiers = Column(Integer, default=0)
    avg_requests_per_identifier = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        Index('idx_rule_date', 'rule_id', 'date'),
        Index('idx_endpoint_date', 'endpoint', 'date'),
    )
