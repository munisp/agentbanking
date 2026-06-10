import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship

# Assume a declarative base is available from a common utility or config
# For this task, we'll define a minimal Base
from sqlalchemy.ext.declarative import declarative_base
Base = declarative_base()

# --- SQLAlchemy Models ---

class ServiceMetric(Base):
    """
    Represents a single analytical metric recorded by the service.
    This could be a performance counter, a usage statistic, or a business metric.
    """
    __tablename__ = "service_metrics"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Contextual fields
    service_name = Column(String(100), nullable=False, index=True)
    metric_name = Column(String(100), nullable=False, index=True)
    
    # Metric value and type
    metric_value = Column(Float, nullable=False)
    metric_unit = Column(String(50), nullable=True)
    
    # Time and source
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, index=True)
    source_id = Column(String(255), nullable=True, comment="ID of the entity that generated the metric (e.g., user ID, transaction ID)")
    
    # Additional metadata as a simple text field (could be JSONB in a real app)
    metadata_json = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_service_metric_name_ts", "service_name", "metric_name", "timestamp"),
        # Enforce uniqueness on metric name and service name for a given source_id within a short time frame
        # This is a placeholder constraint, real-world constraints would be more complex
        # UniqueConstraint('service_name', 'metric_name', 'source_id', name='uq_metric_source'),
    )

    def __repr__(self):
        return f"<ServiceMetric(metric_name='{self.metric_name}', value={self.metric_value}, timestamp='{self.timestamp}')>"

class ActivityLog(Base):
    """
    Represents a log of user or system activity within the service.
    """
    __tablename__ = "activity_logs"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Context
    user_id = Column(String(255), nullable=True, index=True, comment="ID of the user who performed the action")
    action = Column(String(100), nullable=False, index=True, comment="The action performed (e.g., 'CREATE_METRIC', 'VIEW_DASHBOARD')")
    
    # Details
    resource_type = Column(String(100), nullable=True, comment="Type of resource affected (e.g., 'ServiceMetric', 'Report')")
    resource_id = Column(String(255), nullable=True, comment="ID of the resource affected")
    details = Column(Text, nullable=True, comment="Detailed description or JSON payload of the activity")
    
    # Time
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, index=True)

    __table_args__ = (
        Index("idx_activity_user_action_ts", "user_id", "action", "timestamp"),
    )

    def __repr__(self):
        return f"<ActivityLog(action='{self.action}', user_id='{self.user_id}', timestamp='{self.timestamp}')>"

# --- Pydantic Schemas for ServiceMetric ---

class ServiceMetricBase(BaseModel):
    """Base schema for ServiceMetric."""
    service_name: str = Field(..., max_length=100, description="The name of the service reporting the metric.")
    metric_name: str = Field(..., max_length=100, description="The specific name of the metric (e.g., 'request_latency', 'fraud_score_avg').")
    metric_value: float = Field(..., description="The numerical value of the metric.")
    metric_unit: Optional[str] = Field(None, max_length=50, description="The unit of the metric (e.g., 'ms', 'count', 'score').")
    source_id: Optional[str] = Field(None, max_length=255, description="ID of the entity that generated the metric (e.g., user ID, transaction ID).")
    metadata_json: Optional[str] = Field(None, description="Additional metadata as a JSON string.")

class ServiceMetricCreate(ServiceMetricBase):
    """Schema for creating a new ServiceMetric."""
    timestamp: Optional[datetime.datetime] = Field(None, description="The time the metric was recorded. Defaults to now.")

class ServiceMetricUpdate(ServiceMetricBase):
    """Schema for updating an existing ServiceMetric (all fields optional)."""
    service_name: Optional[str] = Field(None, max_length=100)
    metric_name: Optional[str] = Field(None, max_length=100)
    metric_value: Optional[float] = Field(None)
    metric_unit: Optional[str] = Field(None, max_length=50)
    source_id: Optional[str] = Field(None, max_length=255)
    metadata_json: Optional[str] = Field(None)

class ServiceMetricResponse(ServiceMetricBase):
    """Schema for returning a ServiceMetric."""
    id: UUID
    timestamp: datetime.datetime

    class Config:
        orm_mode = True

# --- Pydantic Schemas for ActivityLog ---

class ActivityLogBase(BaseModel):
    """Base schema for ActivityLog."""
    user_id: Optional[str] = Field(None, max_length=255, description="ID of the user who performed the action.")
    action: str = Field(..., max_length=100, description="The action performed (e.g., 'CREATE_METRIC').")
    resource_type: Optional[str] = Field(None, max_length=100, description="Type of resource affected.")
    resource_id: Optional[str] = Field(None, max_length=255, description="ID of the resource affected.")
    details: Optional[str] = Field(None, description="Detailed description or JSON payload of the activity.")

class ActivityLogCreate(ActivityLogBase):
    """Schema for creating a new ActivityLog."""
    timestamp: Optional[datetime.datetime] = Field(None, description="The time the activity was logged. Defaults to now.")

class ActivityLogResponse(ActivityLogBase):
    """Schema for returning an ActivityLog."""
    id: UUID
    timestamp: datetime.datetime

    class Config:
        orm_mode = True

# --- Utility Schemas ---

class PaginatedResponse(BaseModel):
    """Generic schema for paginated list responses."""
    total: int = Field(..., description="Total number of items matching the query.")
    page: int = Field(..., description="The current page number.")
    size: int = Field(..., description="The number of items per page.")
    items: List[ServiceMetricResponse] # This will be specialized in the router
