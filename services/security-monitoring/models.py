import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field
from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

# Base class for declarative class definitions
Base = declarative_base()

# --- Enums for better type safety and database constraints ---

class AlertSeverity(str, Enum):
    """Severity levels for security alerts."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"

class AlertStatus(str, Enum):
    """Processing status for security alerts."""
    NEW = "NEW"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    FALSE_POSITIVE = "FALSE_POSITIVE"
    ARCHIVED = "ARCHIVED"

class LogAction(str, Enum):
    """Types of actions recorded in the activity log."""
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    STATUS_CHANGE = "STATUS_CHANGE"
    COMMENT = "COMMENT"
    ASSIGN = "ASSIGN"

# --- SQLAlchemy Models ---

class SecurityAlert(Base):
    """
    Represents a security alert detected by the monitoring system.
    """
    __tablename__ = "security_alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alert_id = Column(String, unique=True, nullable=False, index=True, doc="Unique identifier from the source system (e.g., Wazuh ID, custom hash).")
    source = Column(String(50), nullable=False, doc="The system or rule that generated the alert (e.g., Wazuh, Openappsec, CustomRule).")
    severity = Column(Enum(AlertSeverity), nullable=False, index=True)
    status = Column(Enum(AlertStatus), nullable=False, default=AlertStatus.NEW, index=True)
    description = Column(Text, nullable=False)
    
    # Contextual data about the alert, stored as JSONB
    context_data = Column(JSONB, nullable=True, doc="Additional structured data related to the alert (e.g., affected user, IP address, rule ID).")
    
    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    activity_logs = relationship("SecurityActivityLog", back_populates="alert", cascade="all, delete-orphan")

    __table_args__ = (
        # Index for fast lookups by source and severity
        Index("idx_alert_source_severity", "source", "severity"),
        # Constraint to ensure alert_id is unique
        {"comment": "Table to store and track security alerts."}
    )

    def __repr__(self):
        return f"<SecurityAlert(id='{self.id}', alert_id='{self.alert_id}', severity='{self.severity}', status='{self.status}')>"


class SecurityActivityLog(Base):
    """
    Represents an activity log entry related to a specific security alert.
    """
    __tablename__ = "security_activity_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alert_id = Column(UUID(as_uuid=True), ForeignKey("security_alerts.id"), nullable=False, index=True)
    
    action = Column(Enum(LogAction), nullable=False, doc="The type of action performed (e.g., STATUS_CHANGE, COMMENT).")
    user_id = Column(String(50), nullable=False, doc="The ID of the user who performed the action.")
    details = Column(JSONB, nullable=True, doc="Structured details about the action (e.g., old_status, new_status, comment_text).")
    
    timestamp = Column(DateTime, default=func.now(), nullable=False)

    # Relationships
    alert = relationship("SecurityAlert", back_populates="activity_logs")

    __table_args__ = (
        # Index for fast lookups by user and action
        Index("idx_log_user_action", "user_id", "action"),
        {"comment": "Table to log all activities related to security alerts."}
    )

    def __repr__(self):
        return f"<SecurityActivityLog(id='{self.id}', alert_id='{self.alert_id}', action='{self.action}', user_id='{self.user_id}')>"


# --- Pydantic Schemas ---

# Base Schemas
class SecurityAlertBase(BaseModel):
    """Base schema for SecurityAlert, containing common fields."""
    alert_id: str = Field(..., description="Unique identifier from the source system.")
    source: str = Field(..., max_length=50, description="The system that generated the alert.")
    severity: AlertSeverity = Field(..., description="Severity level of the alert.")
    description: str = Field(..., description="Detailed description of the security event.")
    context_data: Optional[dict] = Field(None, description="Additional structured data about the alert.")

class SecurityActivityLogBase(BaseModel):
    """Base schema for SecurityActivityLog."""
    action: LogAction = Field(..., description="The type of action performed.")
    user_id: str = Field(..., max_length=50, description="The ID of the user who performed the action.")
    details: Optional[dict] = Field(None, description="Structured details about the action.")


# Create Schemas (Input for POST)
class SecurityAlertCreate(SecurityAlertBase):
    """Schema for creating a new SecurityAlert."""
    # status is optional on creation, defaults to NEW in the model
    pass

class SecurityActivityLogCreate(SecurityActivityLogBase):
    """Schema for creating a new SecurityActivityLog entry."""
    alert_id: uuid.UUID = Field(..., description="The ID of the alert this log entry belongs to.")


# Update Schemas (Input for PUT/PATCH)
class SecurityAlertUpdate(BaseModel):
    """Schema for updating an existing SecurityAlert."""
    status: Optional[AlertStatus] = Field(None, description="New processing status for the alert.")
    severity: Optional[AlertSeverity] = Field(None, description="Updated severity level.")
    description: Optional[str] = Field(None, description="Updated description.")
    context_data: Optional[dict] = Field(None, description="Updated context data.")


# Response Schemas (Output for GET)
class SecurityActivityLogResponse(SecurityActivityLogBase):
    """Response schema for SecurityActivityLog, including database-generated fields."""
    id: uuid.UUID
    alert_id: uuid.UUID
    timestamp: datetime

    class Config:
        from_attributes = True
        use_enum_values = True


class SecurityAlertResponse(SecurityAlertBase):
    """Response schema for SecurityAlert, including database-generated fields and logs."""
    id: uuid.UUID
    status: AlertStatus
    created_at: datetime
    updated_at: datetime
    
    # Nested relationship for logs
    activity_logs: List[SecurityActivityLogResponse] = Field(
        [], description="List of activity logs associated with this alert."
    )

    class Config:
        from_attributes = True
        use_enum_values = True
