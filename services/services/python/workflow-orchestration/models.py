import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Index, Enum, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, DeclarativeBase

# --- SQLAlchemy Base ---

class Base(DeclarativeBase):
    """Base class which provides automated table name and common columns."""
    __abstract__ = True

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

# --- Workflow Status Enum ---

class WorkflowStatus(str, Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

# --- Database Models ---

class Workflow(Base):
    """
    Represents a defined workflow, which is a template for execution.
    """
    __tablename__ = "workflows"

    name = Column(String, unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(Enum(WorkflowStatus), default=WorkflowStatus.DRAFT, nullable=False)
    # The actual workflow definition (e.g., a graph, a sequence of steps)
    definition = Column(JSONB, nullable=False)
    is_template = Column(Boolean, default=False, nullable=False)

    # Relationships
    activity_logs = relationship("WorkflowActivityLog", back_populates="workflow", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_workflows_status_name", "status", "name"),
    )

class WorkflowActivityLog(Base):
    """
    Logs significant events and state changes for a specific workflow instance.
    """
    __tablename__ = "workflow_activity_logs"

    workflow_id = Column(UUID(as_uuid=True), ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(String, nullable=False) # e.g., 'CREATED', 'STARTED', 'STEP_COMPLETED', 'ERROR'
    details = Column(JSONB, nullable=True) # Detailed information about the event
    
    # Relationships
    workflow = relationship("Workflow", back_populates="activity_logs")

    __table_args__ = (
        Index("ix_activity_log_workflow_id_created_at", "workflow_id", "created_at", postgresql_using="btree"),
    )

# --- Pydantic Schemas ---

# Base Schemas (common fields)
class WorkflowBase(BaseModel):
    """Base schema for Workflow, containing common fields."""
    name: str = Field(..., example="data_ingestion_pipeline")
    description: Optional[str] = Field(None, example="Workflow to ingest and process daily sales data.")
    definition: dict = Field(..., example={"steps": [{"name": "fetch_data", "type": "http"}, {"name": "transform", "type": "script"}]})
    is_template: bool = Field(False, example=False)

# Create Schema
class WorkflowCreate(WorkflowBase):
    """Schema for creating a new Workflow."""
    pass

# Update Schema
class WorkflowUpdate(WorkflowBase):
    """Schema for updating an existing Workflow."""
    name: Optional[str] = None
    definition: Optional[dict] = None
    status: Optional[WorkflowStatus] = Field(None, example=WorkflowStatus.ACTIVE)

# Response Schema
class WorkflowResponse(WorkflowBase):
    """Schema for returning a Workflow object."""
    id: uuid.UUID
    status: WorkflowStatus
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        json_encoders = {
            uuid.UUID: str,
            datetime: lambda dt: dt.isoformat(),
        }

# Activity Log Schemas
class WorkflowActivityLogBase(BaseModel):
    """Base schema for WorkflowActivityLog."""
    event_type: str = Field(..., example="WORKFLOW_STARTED")
    details: Optional[dict] = Field(None, example={"run_id": "abc-123", "trigger": "manual"})

class WorkflowActivityLogResponse(WorkflowActivityLogBase):
    """Schema for returning a WorkflowActivityLog object."""
    id: uuid.UUID
    workflow_id: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True
        json_encoders = {
            uuid.UUID: str,
            datetime: lambda dt: dt.isoformat(),
        }

# Schema for listing a workflow with its logs
class WorkflowWithLogsResponse(WorkflowResponse):
    """Schema for returning a Workflow object including its activity logs."""
    activity_logs: List[WorkflowActivityLogResponse] = []
    
    class Config:
        from_attributes = True
        json_encoders = {
            uuid.UUID: str,
            datetime: lambda dt: dt.isoformat(),
        }
