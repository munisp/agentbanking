import datetime
from typing import List, Optional
from enum import Enum

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Index, UniqueConstraint, Boolean
from sqlalchemy.orm import relationship, DeclarativeBase
from pydantic import BaseModel, Field

# --- SQLAlchemy Base ---

class Base(DeclarativeBase):
    """Base class which provides automated table name
    and common utility methods.
    """
    pass

# --- Enums ---

class WorkflowStatus(str, Enum):
    """Possible statuses for a compliance workflow."""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"

class EntityType(str, Enum):
    """Types of entities a workflow can be applied to."""
    USER = "USER"
    BUSINESS = "BUSINESS"
    TRANSACTION = "TRANSACTION"
    DOCUMENT = "DOCUMENT"

class LogLevel(str, Enum):
    """Logging levels for activity log entries."""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    DEBUG = "DEBUG"

# --- SQLAlchemy Models ---

class ComplianceWorkflow(Base):
    """
    Represents a single compliance workflow instance.
    """
    __tablename__ = "compliance_workflows"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(50), default=WorkflowStatus.PENDING.value, nullable=False)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Relationships
    activity_logs = relationship("ActivityLog", back_populates="workflow", cascade="all, delete-orphan")

    # Constraints and Indexes
    __table_args__ = (
        UniqueConstraint('entity_type', 'entity_id', name='uq_entity_workflow'),
        Index('ix_workflow_status', status),
        Index('ix_workflow_entity', entity_type, entity_id),
    )

class ActivityLog(Base):
    """
    Represents an activity log entry for a specific compliance workflow.
    """
    __tablename__ = "workflow_activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, ForeignKey("compliance_workflows.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    log_level = Column(String(50), default=LogLevel.INFO.value, nullable=False)
    message = Column(Text, nullable=False)
    details = Column(Text, nullable=True) # JSON string or detailed text
    
    # Relationships
    workflow = relationship("ComplianceWorkflow", back_populates="activity_logs")

    # Indexes
    __table_args__ = (
        Index('ix_log_workflow_id', workflow_id),
        Index('ix_log_timestamp', timestamp),
    )

# --- Pydantic Schemas ---

# Base Schemas
class ActivityLogBase(BaseModel):
    """Base schema for an activity log entry."""
    log_level: LogLevel = Field(..., description="The severity level of the log entry.")
    message: str = Field(..., description="A concise message describing the activity.")
    details: Optional[str] = Field(None, description="Detailed information, potentially a JSON string.")

class ComplianceWorkflowBase(BaseModel):
    """Base schema for a compliance workflow."""
    name: str = Field(..., max_length=255, description="The name of the compliance workflow.")
    description: Optional[str] = Field(None, description="A detailed description of the workflow.")
    status: WorkflowStatus = Field(WorkflowStatus.PENDING, description="The current status of the workflow.")
    entity_type: EntityType = Field(..., description="The type of entity the workflow applies to.")
    entity_id: str = Field(..., max_length=255, description="The unique identifier of the entity.")
    is_active: bool = Field(True, description="Whether the workflow is currently active.")

# Create Schemas
class ActivityLogCreate(ActivityLogBase):
    """Schema for creating a new activity log entry."""
    pass

class ComplianceWorkflowCreate(ComplianceWorkflowBase):
    """Schema for creating a new compliance workflow."""
    pass

# Update Schemas
class ComplianceWorkflowUpdate(BaseModel):
    """Schema for updating an existing compliance workflow."""
    name: Optional[str] = Field(None, max_length=255, description="The name of the compliance workflow.")
    description: Optional[str] = Field(None, description="A detailed description of the workflow.")
    status: Optional[WorkflowStatus] = Field(None, description="The current status of the workflow.")
    is_active: Optional[bool] = Field(None, description="Whether the workflow is currently active.")

# Response Schemas
class ActivityLogResponse(ActivityLogBase):
    """Schema for returning an activity log entry."""
    id: int
    workflow_id: int
    timestamp: datetime.datetime

    class Config:
        from_attributes = True

class ComplianceWorkflowResponse(ComplianceWorkflowBase):
    """Schema for returning a compliance workflow."""
    id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime
    
    # Include logs in the response for convenience
    activity_logs: List[ActivityLogResponse] = []

    class Config:
        from_attributes = True
