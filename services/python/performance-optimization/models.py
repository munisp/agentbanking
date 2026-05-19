import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Enum, Text
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
import enum

Base = declarative_base()

class MetricType(enum.Enum):
    LATENCY = "latency"
    CPU_USAGE = "cpu_usage"
    MEMORY_USAGE = "memory_usage"
    DISK_IO = "disk_io"
    NETWORK_THROUGHPUT = "network_throughput"
    CUSTOM = "custom"

class TaskStatus(enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    DEFERRED = "deferred"

class PerformanceMetric(Base):
    __tablename__ = "performance_metrics"

    id = Column(Integer, primary_key=True, index=True)
    system_name = Column(String, index=True, nullable=False)
    metric_type = Column(Enum(MetricType), index=True, nullable=False)
    value = Column(Float, nullable=False)
    unit = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    
    __table_args__ = (
        # Unique constraint to prevent duplicate metric entries for the same system, type, and timestamp
        # Though for time-series data, this is less critical, it's good practice for a simple model.
        # For a real-world scenario, we'd likely use a time-series database.
        # UniqueConstraint('system_name', 'metric_type', 'timestamp', name='_system_metric_ts_uc'),
    )

class OptimizationTask(Base):
    __tablename__ = "optimization_tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True, nullable=False)
    description = Column(Text, nullable=True)
    priority = Column(Integer, default=5, nullable=False) # 1 (highest) to 10 (lowest)
    status = Column(Enum(TaskStatus), default=TaskStatus.PENDING, nullable=False)
    assigned_to = Column(String, nullable=True)
    target_metric = Column(String, nullable=True) # e.g., "P95 Latency"
    target_value = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)
    
    # Relationship to track related metrics (optional, but good for a comprehensive model)
    # metrics = relationship("PerformanceMetric", back_populates="task")
    
    __table_args__ = (
        # Index on status and priority for efficient querying of pending/high-priority tasks
        {"sqlite_autoincrement": True}
    )
