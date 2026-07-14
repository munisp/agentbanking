from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum as PyEnum

# --- Enums ---

class MetricType(str, PyEnum):
    LATENCY = "latency"
    CPU_USAGE = "cpu_usage"
    MEMORY_USAGE = "memory_usage"
    DISK_IO = "disk_io"
    NETWORK_THROUGHPUT = "network_throughput"
    CUSTOM = "custom"

class TaskStatus(str, PyEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    DEFERRED = "deferred"

# --- PerformanceMetric Schemas ---

class PerformanceMetricBase(BaseModel):
    system_name: str = Field(..., example="web_server_01")
    metric_type: MetricType = Field(..., example=MetricType.LATENCY)
    value: float = Field(..., example=150.5)
    unit: str = Field(..., example="ms")

class PerformanceMetricCreate(PerformanceMetricBase):
    # Timestamp can be optionally provided, otherwise set by the model default
    timestamp: Optional[datetime] = Field(None, example=datetime.utcnow().isoformat())
    pass

class PerformanceMetricUpdate(PerformanceMetricBase):
    system_name: Optional[str] = None
    metric_type: Optional[MetricType] = None
    value: Optional[float] = None
    unit: Optional[str] = None

class PerformanceMetric(PerformanceMetricBase):
    id: int
    timestamp: datetime

    class Config:
        from_attributes = True

# --- OptimizationTask Schemas ---

class OptimizationTaskBase(BaseModel):
    title: str = Field(..., example="Optimize database query for user profile load")
    description: Optional[str] = Field(None, example="The query to fetch user profile data is taking 500ms on average. Need to add an index.")
    priority: int = Field(5, ge=1, le=10, example=3) # 1 (highest) to 10 (lowest)
    status: TaskStatus = Field(TaskStatus.PENDING, example=TaskStatus.IN_PROGRESS)
    assigned_to: Optional[str] = Field(None, example="john.doe")
    target_metric: Optional[str] = Field(None, example="P95 Latency")
    target_value: Optional[float] = Field(None, example=100.0)

class OptimizationTaskCreate(OptimizationTaskBase):
    pass

class OptimizationTaskUpdate(OptimizationTaskBase):
    title: Optional[str] = None
    priority: Optional[int] = Field(None, ge=1, le=10)
    status: Optional[TaskStatus] = None

class OptimizationTask(OptimizationTaskBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
