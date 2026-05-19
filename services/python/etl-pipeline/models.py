import enum
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Enum, Text, Index
from sqlalchemy.orm import relationship, DeclarativeBase
from sqlalchemy.ext.declarative import declared_attr
from pydantic import BaseModel, Field
from pydantic.alias_generators import to_camel

# --- SQLAlchemy Base Setup ---

class Base(DeclarativeBase):
    """Base class which provides automated table name
    and common utility methods.
    """
    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower() + "s"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

# --- Enums ---

class PipelineStatus(str, enum.Enum):
    """Status of the ETL Pipeline."""
    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"
    FAILED = "failed"
    RUNNING = "running"

class ActivityType(str, enum.Enum):
    """Type of activity logged."""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    EXECUTE = "execute"
    FAIL = "fail"
    SUCCESS = "success"

# --- SQLAlchemy Models ---

class ETLPipeline(Base):
    """
    Main model for an ETL Pipeline configuration.
    """
    __tablename__ = "etl_pipelines"

    name = Column(String(255), unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    source_system = Column(String(100), nullable=False)
    target_system = Column(String(100), nullable=False)
    schedule = Column(String(50), default="manual", nullable=False, comment="e.g., 'daily', 'hourly', 'cron expression'")
    status = Column(Enum(PipelineStatus), default=PipelineStatus.DRAFT, nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)

    # Relationships
    activity_logs = relationship("ETLPipelineActivityLog", back_populates="pipeline", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index("ix_etl_pipelines_source_target", "source_system", "target_system"),
    )

class ETLPipelineActivityLog(Base):
    """
    Activity log for changes and executions of an ETL Pipeline.
    """
    __tablename__ = "etl_pipeline_activity_logs"

    pipeline_id = Column(Integer, ForeignKey("etl_pipelines.id"), nullable=False)
    activity_type = Column(Enum(ActivityType), nullable=False)
    details = Column(Text, nullable=True)
    user_id = Column(String(50), nullable=True, comment="ID of the user who performed the action")
    
    # Relationships
    pipeline = relationship("ETLPipeline", back_populates="activity_logs")

    # Indexes
    __table_args__ = (
        Index("ix_activity_log_pipeline_type", "pipeline_id", "activity_type"),
    )

# --- Pydantic Schemas ---

class Config(BaseModel):
    """Base configuration for Pydantic models."""
    class Config:
        alias_generator = to_camel
        populate_by_name = True
        from_attributes = True

# Schemas for ETLPipeline
class ETLPipelineBase(Config):
    """Base schema for ETL Pipeline."""
    name: str = Field(..., max_length=255, description="Unique name of the ETL pipeline.")
    description: Optional[str] = Field(None, description="Detailed description of the pipeline's function.")
    source_system: str = Field(..., max_length=100, description="The source system for the data (e.g., 'S3', 'Postgres', 'Salesforce').")
    target_system: str = Field(..., max_length=100, description="The target system for the data (e.g., 'Snowflake', 'Redshift', 'API').")
    schedule: str = Field("manual", max_length=50, description="The execution schedule (e.g., 'daily', '0 8 * * *' for cron).")

class ETLPipelineCreate(ETLPipelineBase):
    """Schema for creating a new ETL Pipeline."""
    pass

class ETLPipelineUpdate(ETLPipelineBase):
    """Schema for updating an existing ETL Pipeline."""
    name: Optional[str] = Field(None, max_length=255, description="Unique name of the ETL pipeline.")
    source_system: Optional[str] = Field(None, max_length=100, description="The source system for the data.")
    target_system: Optional[str] = Field(None, max_length=100, description="The target system for the data.")
    schedule: Optional[str] = Field(None, max_length=50, description="The execution schedule.")
    status: Optional[PipelineStatus] = Field(None, description="The current status of the pipeline.")

class ETLPipelineResponse(ETLPipelineBase):
    """Schema for returning an ETL Pipeline."""
    id: int
    status: PipelineStatus
    is_deleted: bool
    created_at: datetime
    updated_at: datetime

# Schemas for ETLPipelineActivityLog
class ETLPipelineActivityLogBase(Config):
    """Base schema for ETL Pipeline Activity Log."""
    pipeline_id: int = Field(..., description="ID of the associated ETL pipeline.")
    activity_type: ActivityType = Field(..., description="Type of activity logged.")
    details: Optional[str] = Field(None, description="Detailed description of the activity.")
    user_id: Optional[str] = Field(None, description="ID of the user who performed the action.")

class ETLPipelineActivityLogResponse(ETLPipelineActivityLogBase):
    """Schema for returning an ETL Pipeline Activity Log."""
    id: int
    created_at: datetime
    updated_at: datetime

    # Nested response for the related pipeline (optional, for detailed views)
    # pipeline: Optional[ETLPipelineResponse] = None

class ETLPipelineDetailResponse(ETLPipelineResponse):
    """Schema for returning an ETL Pipeline with its activity logs."""
    activity_logs: List[ETLPipelineActivityLogResponse] = Field(default_factory=list)
