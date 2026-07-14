from datetime import datetime
from typing import List, Optional
from enum import Enum

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, Index, UniqueConstraint
from sqlalchemy.orm import relationship, DeclarativeBase
from pydantic import BaseModel, Field, conint, constr

# --- Base Model ---

class Base(DeclarativeBase):
    """Base class which provides automated table name and common columns."""
    __abstract__ = True

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

# --- SQLAlchemy Models ---

class WorkflowStatus(str, Enum):
    """Enum for possible workflow statuses."""
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"

class Workflow(Base):
    """
    SQLAlchemy model for a Workflow.
    Represents a defined process or sequence of steps.
    """
    __tablename__ = "workflows"

    name = Column(String(255), unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(50), default=WorkflowStatus.DRAFT.value, nullable=False)
    
    # Stores the structure/definition of the workflow (e.g., a graph, a list of steps)
    definition = Column(JSON, nullable=False, default={}) 
    
    # Assuming an external 'user' service for owner_id
    owner_id = Column(Integer, index=True, nullable=False)

    # Relationships
    activity_logs = relationship("ActivityLog", back_populates="workflow", cascade="all, delete-orphan")

    # Constraints and Indexes
    __table_args__ = (
        Index("ix_workflow_owner_status", "owner_id", "status"),
    )

    def __repr__(self):
        return f"<Workflow(id={self.id}, name='{self.name}', status='{self.status}')>"

class ActivityLog(Base):
    """
    SQLAlchemy model for logging activities related to a Workflow.
    """
    __tablename__ = "workflow_activity_logs"

    workflow_id = Column(Integer, ForeignKey("workflows.id", ondelete="CASCADE"), index=True, nullable=False)
    
    activity_type = Column(String(100), nullable=False) # e.g., 'created', 'updated', 'status_change', 'execution_start'
    details = Column(JSON, nullable=True) # Additional context about the activity
    user_id = Column(Integer, index=True, nullable=True) # User who performed the action

    # Relationships
    workflow = relationship("Workflow", back_populates="activity_logs")

    def __repr__(self):
        return f"<ActivityLog(id={self.id}, workflow_id={self.workflow_id}, type='{self.activity_type}')>"

# --- Pydantic Schemas ---

# Base Schemas
class WorkflowBase(BaseModel):
    """Base schema for Workflow, containing common fields for creation and update."""
    name: constr(min_length=1, max_length=255) = Field(..., example="Customer Onboarding Flow")
    description: Optional[str] = Field(None, example="Automated process for new customer setup.")
    definition: dict = Field(..., example={"steps": [{"name": "Step 1", "action": "email"}]})
    owner_id: conint(ge=1) = Field(..., example=101, description="ID of the user who owns the workflow.")

class ActivityLogBase(BaseModel):
    """Base schema for ActivityLog."""
    activity_type: constr(min_length=1, max_length=100) = Field(..., example="status_change")
    details: Optional[dict] = Field(None, example={"old_status": "draft", "new_status": "active"})
    user_id: Optional[conint(ge=1)] = Field(None, example=101, description="ID of the user who performed the action.")

# Create Schemas
class WorkflowCreate(WorkflowBase):
    """Schema for creating a new Workflow."""
    status: WorkflowStatus = Field(WorkflowStatus.DRAFT, example=WorkflowStatus.DRAFT.value)

class ActivityLogCreate(ActivityLogBase):
    """Schema for creating a new ActivityLog entry."""
    workflow_id: conint(ge=1) = Field(..., example=1)

# Update Schemas
class WorkflowUpdate(BaseModel):
    """Schema for updating an existing Workflow. All fields are optional."""
    name: Optional[constr(min_length=1, max_length=255)] = Field(None, example="Updated Onboarding Flow")
    description: Optional[str] = Field(None, example="Revised automated process.")
    status: Optional[WorkflowStatus] = Field(None, example=WorkflowStatus.ACTIVE.value)
    definition: Optional[dict] = Field(None, example={"steps": [{"name": "Step 1", "action": "sms"}]})
    owner_id: Optional[conint(ge=1)] = Field(None, example=102)

# Response Schemas
class WorkflowResponse(WorkflowBase):
    """Schema for returning a Workflow object."""
    id: conint(ge=1)
    status: WorkflowStatus
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda dt: dt.isoformat(),
        }

class ActivityLogResponse(ActivityLogBase):
    """Schema for returning an ActivityLog object."""
    id: conint(ge=1)
    workflow_id: conint(ge=1)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda dt: dt.isoformat(),
        }

class WorkflowWithLogsResponse(WorkflowResponse):
    """Schema for returning a Workflow object including its activity logs."""
    activity_logs: List[ActivityLogResponse] = []
