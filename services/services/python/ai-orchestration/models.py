from datetime import datetime
from typing import List, Optional
from enum import Enum

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.schema import Index
from pydantic import BaseModel, Field

# --- SQLAlchemy Base ---
Base = declarative_base()

# --- Enums ---

class TaskStatus(str, Enum):
    """
    Defines the possible states for an Orchestration Task.
    """
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

# --- SQLAlchemy Models ---

class OrchestrationTask(Base):
    """
    Represents a single AI orchestration task, which may involve multiple steps
    or a complex pipeline.
    """
    __tablename__ = "orchestration_tasks"

    id = Column(Integer, primary_key=True, index=True)
    
    # Core task details
    name = Column(String(255), index=True, nullable=False, doc="Human-readable name for the task.")
    description = Column(Text, nullable=True, doc="Detailed description of the task and its goal.")
    
    # Orchestration specific fields
    status = Column(String(50), default=TaskStatus.PENDING.value, nullable=False, doc="Current status of the task (e.g., PENDING, RUNNING, COMPLETED).")
    pipeline_definition = Column(JSON, nullable=False, doc="JSON structure defining the steps and flow of the AI pipeline.")
    input_data = Column(JSON, nullable=True, doc="Initial input data for the task.")
    output_data = Column(JSON, nullable=True, doc="Final output data from the completed task.")
    current_step = Column(String(255), nullable=True, doc="Identifier of the step currently being executed.")
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    logs = relationship("ActivityLog", back_populates="task", cascade="all, delete-orphan")

    # Constraints and Indexes
    __table_args__ = (
        Index("ix_task_status_created_at", "status", "created_at"),
    )

    def __repr__(self):
        return f"<OrchestrationTask(id={self.id}, name='{self.name}', status='{self.status}')>"

class ActivityLog(Base):
    """
    A log of activities and events related to an Orchestration Task.
    """
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    
    # Relationship to the task
    task_id = Column(Integer, ForeignKey("orchestration_tasks.id"), nullable=False, index=True)
    
    # Log details
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    level = Column(String(50), nullable=False, doc="Log level (e.g., INFO, WARNING, ERROR).")
    message = Column(Text, nullable=False, doc="The log message or event description.")
    details = Column(JSON, nullable=True, doc="Optional JSON field for structured log details.")
    
    # Relationship
    task = relationship("OrchestrationTask", back_populates="logs")

    def __repr__(self):
        return f"<ActivityLog(id={self.id}, task_id={self.task_id}, level='{self.level}')>"

# --- Pydantic Schemas ---

class ActivityLogBase(BaseModel):
    """Base schema for ActivityLog."""
    level: str = Field(..., description="Log level (e.g., INFO, WARNING, ERROR).")
    message: str = Field(..., description="The log message or event description.")
    details: Optional[dict] = Field(None, description="Optional JSON field for structured log details.")

class ActivityLogResponse(ActivityLogBase):
    """Response schema for ActivityLog."""
    id: int
    task_id: int
    timestamp: datetime

    class Config:
        from_attributes = True

class OrchestrationTaskBase(BaseModel):
    """Base schema for OrchestrationTask."""
    name: str = Field(..., max_length=255, description="Human-readable name for the task.")
    description: Optional[str] = Field(None, description="Detailed description of the task and its goal.")
    pipeline_definition: dict = Field(..., description="JSON structure defining the steps and flow of the AI pipeline.")
    input_data: Optional[dict] = Field(None, description="Initial input data for the task.")

class OrchestrationTaskCreate(OrchestrationTaskBase):
    """Schema for creating a new OrchestrationTask."""
    # status is defaulted in the model, so it's not required for creation
    pass

class OrchestrationTaskUpdate(OrchestrationTaskBase):
    """Schema for updating an existing OrchestrationTask."""
    name: Optional[str] = Field(None, max_length=255, description="Human-readable name for the task.")
    pipeline_definition: Optional[dict] = Field(None, description="JSON structure defining the steps and flow of the AI pipeline.")
    status: Optional[TaskStatus] = Field(None, description="Current status of the task.")
    output_data: Optional[dict] = Field(None, description="Final output data from the completed task.")
    current_step: Optional[str] = Field(None, max_length=255, description="Identifier of the step currently being executed.")

class OrchestrationTaskResponse(OrchestrationTaskBase):
    """Response schema for OrchestrationTask."""
    id: int
    status: TaskStatus
    output_data: Optional[dict] = None
    current_step: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    # Include logs in the response for a full view
    logs: List[ActivityLogResponse] = []

    class Config:
        from_attributes = True
        use_enum_values = True
