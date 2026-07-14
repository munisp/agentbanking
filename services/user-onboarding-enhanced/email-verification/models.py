import enum
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Boolean,
    Float,
    Text,
    JSON,
    Enum,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship, declarative_base, Mapped, mapped_column

# --- Base and Mixins ---

Base = declarative_base()

class TimestampMixin:
    """Mixin for created_at and updated_at timestamps."""
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

class SoftDeleteMixin:
    """Mixin for soft deletion support."""
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None)

class AuditMixin:
    """Mixin for created_by and updated_by audit fields."""
    created_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, doc="User or system that created the record.")
    updated_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, doc="User or system that last updated the record.")

# --- Enums ---

class ServiceStatus(enum.Enum):
    """Possible operational statuses for a service."""
    OPERATIONAL = "operational"
    DEGRADED_PERFORMANCE = "degraded_performance"
    PARTIAL_OUTAGE = "partial_outage"
    MAJOR_OUTAGE = "major_outage"
    MAINTENANCE = "maintenance"

class HealthCheckStatus(enum.Enum):
    """Possible outcomes of a health check."""
    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"
    TIMEOUT = "timeout"

class AlertSeverity(enum.Enum):
    """Severity levels for an alert."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"

class IncidentStatus(enum.Enum):
    """Lifecycle statuses for an incident."""
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    CLOSED = "closed"

# --- Models ---

class Service(Base, TimestampMixin, SoftDeleteMixin, AuditMixin):
    """
    Represents a production service being monitored.
    """
    __tablename__ = "services"
    __table_args__ = (
        UniqueConstraint("name", name="uq_service_name"),
        Index("ix_services_status", "status"),
        {"comment": "Core table for all monitored production services."}
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, doc="Unique, human-readable name of the service.")
    description: Mapped[Optional[str]] = mapped_column(Text, doc="Detailed description of the service and its function.")
    url: Mapped[Optional[str]] = mapped_column(String(512), doc="Primary URL or endpoint for the service.")
    status: Mapped[ServiceStatus] = mapped_column(
        Enum(ServiceStatus),
        default=ServiceStatus.OPERATIONAL,
        nullable=False,
        doc="Current operational status of the service."
    )
    owner_team: Mapped[Optional[str]] = mapped_column(String(100), doc="Team responsible for the service.")
    
    # Relationships
    health_checks: Mapped[List["HealthCheck"]] = relationship("HealthCheck", back_populates="service", cascade="all, delete-orphan")
    metrics: Mapped[List["Metric"]] = relationship("Metric", back_populates="service", cascade="all, delete-orphan")
    alerts: Mapped[List["Alert"]] = relationship("Alert", back_populates="service", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Service(id={self.id}, name='{self.name}', status='{self.status.value}')>"

class HealthCheck(Base, TimestampMixin, SoftDeleteMixin, AuditMixin):
    """
    Records the result of a single health check execution for a service.
    """
    __tablename__ = "health_checks"
    __table_args__ = (
        Index("ix_health_checks_service_id_created_at", "service_id", "created_at", unique=False),
        {"comment": "Records of periodic health checks for services."}
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    service_id: Mapped[int] = mapped_column(
        ForeignKey("services.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Foreign key to the Service being checked."
    )
    status: Mapped[HealthCheckStatus] = mapped_column(
        Enum(HealthCheckStatus),
        nullable=False,
        doc="Outcome of the health check (PASS, FAIL, WARN, TIMEOUT)."
    )
    response_time_ms: Mapped[Optional[float]] = mapped_column(Float, doc="Response time in milliseconds.")
    details: Mapped[Optional[dict]] = mapped_column(JSON, doc="Additional check details, e.g., error message or payload.")
    
    # Relationships
    service: Mapped["Service"] = relationship("Service", back_populates="health_checks")

    def __repr__(self):
        return f"<HealthCheck(id={self.id}, service_id={self.service_id}, status='{self.status.value}')>"

class Metric(Base, TimestampMixin, SoftDeleteMixin, AuditMixin):
    """
    Stores time-series metric data collected from a service.
    """
    __tablename__ = "metrics"
    __table_args__ = (
        Index("ix_metrics_service_id_name_created_at", "service_id", "name", "created_at", unique=False),
        {"comment": "Time-series metric data collected from services."}
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    service_id: Mapped[int] = mapped_column(
        ForeignKey("services.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Foreign key to the Service the metric belongs to."
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, doc="Name of the metric (e.g., 'cpu_usage', 'request_count').")
    value: Mapped[float] = mapped_column(Float, nullable=False, doc="The recorded value of the metric.")
    unit: Mapped[Optional[str]] = mapped_column(String(50), doc="Unit of the metric (e.g., 'percent', 'count', 'ms').")
    tags: Mapped[Optional[dict]] = mapped_column(JSON, doc="Key-value tags for metric filtering and aggregation.")
    
    # Relationships
    service: Mapped["Service"] = relationship("Service", back_populates="metrics")

    def __repr__(self):
        return f"<Metric(id={self.id}, service_id={self.service_id}, name='{self.name}', value={self.value})>"

class Alert(Base, TimestampMixin, SoftDeleteMixin, AuditMixin):
    """
    Represents a triggered alert based on health checks or metric thresholds.
    """
    __tablename__ = "alerts"
    __table_args__ = (
        Index("ix_alerts_service_id_severity_created_at", "service_id", "severity", "created_at", unique=False),
        {"comment": "Records of triggered alerts for services."}
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    service_id: Mapped[int] = mapped_column(
        ForeignKey("services.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Foreign key to the Service that triggered the alert."
    )
    severity: Mapped[AlertSeverity] = mapped_column(
        Enum(AlertSeverity),
        nullable=False,
        doc="Severity level of the alert."
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False, doc="A brief summary of the alert.")
    description: Mapped[Optional[str]] = mapped_column(Text, doc="Detailed description of the alert condition and trigger.")
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, doc="True if the underlying issue has been resolved.")
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, doc="Timestamp when the alert was resolved.")
    
    # Relationships
    service: Mapped["Service"] = relationship("Service", back_populates="alerts")
    incident: Mapped[Optional["Incident"]] = relationship("Incident", back_populates="alert", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Alert(id={self.id}, service_id={self.service_id}, severity='{self.severity.value}', resolved={self.is_resolved})>"

class Incident(Base, TimestampMixin, SoftDeleteMixin, AuditMixin):
    """
    Represents a major service disruption, typically created from a critical alert.
    """
    __tablename__ = "incidents"
    __table_args__ = (
        UniqueConstraint("alert_id", name="uq_incident_alert_id"),
        Index("ix_incidents_status_created_at", "status", "created_at", unique=False),
        {"comment": "Records of major service incidents."}
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    alert_id: Mapped[int] = mapped_column(
        ForeignKey("alerts.id", ondelete="RESTRICT"), # RESTRICT to prevent deleting an alert that caused an incident
        nullable=False,
        index=True,
        doc="Foreign key to the originating Alert."
    )
    status: Mapped[IncidentStatus] = mapped_column(
        Enum(IncidentStatus),
        default=IncidentStatus.OPEN,
        nullable=False,
        doc="Current status of the incident lifecycle."
    )
    summary: Mapped[str] = mapped_column(String(512), nullable=False, doc="A short summary of the incident.")
    root_cause: Mapped[Optional[str]] = mapped_column(Text, doc="Post-mortem analysis of the root cause.")
    resolution_details: Mapped[Optional[str]] = mapped_column(Text, doc="Steps taken to resolve the incident.")
    
    # Relationships
    alert: Mapped["Alert"] = relationship("Alert", back_populates="incident")

    def __repr__(self):
        return f"<Incident(id={self.id}, status='{self.status.value}', alert_id={self.alert_id})>"

# Optional: Add a helper function to create tables for testing/setup
def create_tables(engine) -> None:
    """Creates all tables defined in the Base metadata."""
    Base.metadata.create_all(engine)

if __name__ == '__main__':
    # Example usage for demonstration/testing
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    # Use an in-memory SQLite database for demonstration
    engine = create_engine("sqlite:///:memory:")
    
    print("Creating tables...")
    create_tables(engine)
    print("Tables created successfully.")

    Session = sessionmaker(bind=engine)
    session = Session()

    # 1. Create a new service
    new_service = Service(
        name="API Gateway",
        description="Handles all incoming client requests.",
        url="https://api.example.com",
        owner_team="Platform",
        created_by="system_setup"
    )
    session.add(new_service)
    session.commit()
    print(f"Created service: {new_service}")

    # 2. Record a health check
    check = HealthCheck(
        service_id=new_service.id,
        status=HealthCheckStatus.PASS,
        response_time_ms=45.2,
        created_by="health_checker"
    )
    session.add(check)
    session.commit()
    print(f"Recorded health check: {check}")

    # 3. Record a metric
    metric = Metric(
        service_id=new_service.id,
        name="p95_latency",
        value=120.5,
        unit="ms",
        tags={"region": "us-east-1"},
        created_by="prometheus"
    )
    session.add(metric)
    session.commit()
    print(f"Recorded metric: {metric}")

    # 4. Trigger a critical alert
    alert = Alert(
        service_id=new_service.id,
        severity=AlertSeverity.CRITICAL,
        title="High Latency Spike",
        description="P95 latency exceeded 100ms threshold for 5 minutes.",
        created_by="alert_manager"
    )
    session.add(alert)
    session.commit()
    print(f"Triggered alert: {alert}")

    # 5. Create an incident from the alert
    incident = Incident(
        alert_id=alert.id,
        summary="API Gateway Major Outage due to high load.",
        created_by="incident_commander"
    )
    session.add(incident)
    session.commit()
    print(f"Created incident: {incident}")

    # 6. Resolve the incident and alert
    incident.status = IncidentStatus.RESOLVED
    incident.root_cause = "Misconfigured load balancer."
    incident.resolution_details = "Load balancer configuration corrected and traffic normalized."
    incident.updated_by = "incident_commander"
    
    alert.is_resolved = True
    alert.resolved_at = datetime.utcnow()
    alert.updated_by = "incident_commander"

    session.commit()
    print(f"Resolved incident: {incident}")
    print(f"Resolved alert: {alert}")

    session.close()
    print("\nDemonstration complete.")
