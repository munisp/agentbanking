import enum
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field
from sqlalchemy import (
    Column, Integer, String, DateTime, Text, Enum, ForeignKey, Boolean, Index
)
from sqlalchemy.orm import relationship, declarative_base

# --- SQLAlchemy Base ---

Base = declarative_base()

# --- Enums ---

class JobType(str, enum.Enum):
    """Defines the type of GNN job."""
    TRAINING = "TRAINING"
    INFERENCE = "INFERENCE"
    EVALUATION = "EVALUATION"

class JobStatus(str, enum.Enum):
    """Defines the current status of a GNN job."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

# --- SQLAlchemy Models ---

class GNNJob(Base):
    """
    Represents a single Graph Neural Network (GNN) job, which could be for
    training a model or running inference on a graph dataset.
    """
    __tablename__ = "gnn_jobs"

    id = Column(Integer, primary_key=True, index=True)
    
    # Multi-tenancy and identification
    tenant_id = Column(String, nullable=False, index=True)
    job_name = Column(String, nullable=False)
    
    # Job configuration
    job_type = Column(Enum(JobType), nullable=False, default=JobType.INFERENCE)
    graph_source_uri = Column(String, nullable=False, comment="URI to the graph data source (e.g., S3 path)")
    model_config_json = Column(Text, nullable=False, comment="JSON configuration for the GNN model and hyperparameters")
    
    # Status and timestamps
    status = Column(Enum(JobStatus), nullable=False, default=JobStatus.PENDING, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Results and output
    output_uri = Column(String, nullable=True, comment="URI to the job output (e.g., trained model or inference results)")
    error_message = Column(Text, nullable=True)

    # Relationships
    logs = relationship("ActivityLog", back_populates="job", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_gnn_jobs_tenant_status", "tenant_id", "status"),
    )

class ActivityLog(Base):
    """
    Log of activities and events related to a GNN job.
    """
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("gnn_jobs.id"), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    level = Column(String, nullable=False, default="INFO") # e.g., INFO, WARNING, ERROR
    message = Column(Text, nullable=False)
    
    # Relationships
    job = relationship("GNNJob", back_populates="logs")

    __table_args__ = (
        Index("ix_activity_logs_job_timestamp", "job_id", "timestamp"),
    )

# --- Pydantic Schemas ---

# Base Schemas
class ActivityLogBase(BaseModel):
    """Base schema for ActivityLog."""
    level: str = Field(..., example="INFO")
    message: str = Field(..., example="Job started processing.")

class GNNJobBase(BaseModel):
    """Base schema for GNNJob, containing common fields."""
    tenant_id: str = Field(..., example="tenant-a1b2c3d4")
    job_name: str = Field(..., example="fraud_detection_training_v1")
    job_type: JobType = Field(..., example=JobType.TRAINING)
    graph_source_uri: str = Field(..., example="s3://data-lake/graphs/2023/q4/graph_data.parquet")
    model_config_json: str = Field(..., example='{"model_class": "GAT", "epochs": 50, "learning_rate": 0.001}')

# Create Schema
class GNNJobCreate(GNNJobBase):
    """Schema for creating a new GNNJob."""
    pass

# Update Schema
class GNNJobUpdate(BaseModel):
    """Schema for updating an existing GNNJob."""
    job_name: Optional[str] = Field(None, example="fraud_detection_training_v2")
    model_config_json: Optional[str] = Field(None, example='{"model_class": "GAT", "epochs": 100, "learning_rate": 0.0005}')
    status: Optional[JobStatus] = Field(None, example=JobStatus.CANCELLED)
    output_uri: Optional[str] = Field(None, example="s3://model-store/models/v2/model.pt")
    error_message: Optional[str] = Field(None, example="Memory allocation failed.")

# Response Schemas
class ActivityLogResponse(ActivityLogBase):
    """Response schema for ActivityLog."""
    id: int
    job_id: int
    timestamp: datetime

    class Config:
        from_attributes = True

class GNNJobResponse(GNNJobBase):
    """Response schema for GNNJob, including read-only fields and relationships."""
    id: int
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    output_uri: Optional[str] = None
    error_message: Optional[str] = None
    
    # Include logs in the response
    logs: List[ActivityLogResponse] = []

    class Config:
        from_attributes = True

class GNNJobListResponse(GNNJobResponse):
    """Simplified response for list view, excluding logs."""
    logs: List[ActivityLogResponse] = Field(default_factory=list, exclude=True)
