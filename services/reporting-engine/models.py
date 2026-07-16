from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    Boolean,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship, declarative_base

# --- SQLAlchemy Base ---
Base = declarative_base()


# --- SQLAlchemy Models ---
class ReportTemplate(Base):
    """
    SQLAlchemy Model for Report Templates.
    Defines the structure and content of a report.
    """

    __tablename__ = "report_templates"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    template_content = Column(Text, nullable=False)  # e.g., Jinja2 template, Markdown, etc.
    data_source_query = Column(Text, nullable=True)  # SQL query or API endpoint to fetch data
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    schedules = relationship(
        "ReportSchedule", back_populates="template", cascade="all, delete-orphan"
    )
    instances = relationship(
        "ReportInstance", back_populates="template", cascade="all, delete-orphan"
    )


class ReportSchedule(Base):
    """
    SQLAlchemy Model for Report Schedules.
    Defines when and how often a report should be generated.
    """

    __tablename__ = "report_schedules"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    template_id = Column(
        PG_UUID(as_uuid=True), ForeignKey("report_templates.id"), nullable=False
    )
    schedule_type = Column(
        Enum("DAILY", "WEEKLY", "MONTHLY", "ONCE", name="schedule_type"),
        nullable=False,
    )
    cron_expression = Column(
        String(100), nullable=True
    )  # For more complex scheduling
    is_active = Column(Boolean, default=True, nullable=False)
    last_run_at = Column(DateTime, nullable=True)
    next_run_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    template = relationship("ReportTemplate", back_populates="schedules")


class ReportInstance(Base):
    """
    SQLAlchemy Model for Report Instances.
    Represents a generated report (the output file).
    """

    __tablename__ = "report_instances"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    template_id = Column(
        PG_UUID(as_uuid=True), ForeignKey("report_templates.id"), nullable=False
    )
    schedule_id = Column(
        PG_UUID(as_uuid=True), ForeignKey("report_schedules.id"), nullable=True
    )
    status = Column(
        Enum("PENDING", "GENERATING", "COMPLETED", "FAILED", name="instance_status"),
        default="PENDING",
        nullable=False,
    )
    output_format = Column(
        Enum("PDF", "CSV", "JSON", "HTML", name="output_format"), nullable=False
    )
    file_path = Column(String(512), nullable=True)  # Path to the generated file
    generated_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)

    # Relationships
    template = relationship("ReportTemplate", back_populates="instances")
    schedule = relationship("ReportSchedule")


# --- Pydantic Schemas (Base) ---
class ReportTemplateBase(BaseModel):
    name: str = Field(..., max_length=255, description="Unique name for the report template.")
    description: Optional[str] = Field(None, description="Detailed description of the report template.")
    template_content: str = Field(..., description="The content of the report template (e.g., Jinja2).")
    data_source_query: Optional[str] = Field(None, description="Query or endpoint to fetch data for the report.")

    class Config:
        from_attributes = True


class ReportScheduleBase(BaseModel):
    template_id: UUID = Field(..., description="ID of the report template to schedule.")
    schedule_type: str = Field(..., description="Type of schedule (DAILY, WEEKLY, MONTHLY, ONCE).")
    cron_expression: Optional[str] = Field(None, description="Optional CRON expression for complex scheduling.")
    is_active: bool = Field(True, description="Whether the schedule is currently active.")

    class Config:
        from_attributes = True


class ReportInstanceBase(BaseModel):
    template_id: UUID = Field(..., description="ID of the report template used.")
    schedule_id: Optional[UUID] = Field(None, description="ID of the schedule that triggered this instance.")
    output_format: str = Field(..., description="Desired output format (PDF, CSV, JSON, HTML).")

    class Config:
        from_attributes = True


# --- Pydantic Schemas (Create/Update) ---
class ReportTemplateCreate(ReportTemplateBase):
    """Schema for creating a new ReportTemplate."""
    pass


class ReportTemplateUpdate(ReportTemplateBase):
    """Schema for updating an existing ReportTemplate."""
    name: Optional[str] = Field(None, max_length=255)
    template_content: Optional[str] = None


class ReportScheduleCreate(ReportScheduleBase):
    """Schema for creating a new ReportSchedule."""
    pass


class ReportScheduleUpdate(ReportScheduleBase):
    """Schema for updating an existing ReportSchedule."""
    template_id: Optional[UUID] = None
    schedule_type: Optional[str] = None
    is_active: Optional[bool] = None


# --- Pydantic Schemas (Read) ---
class ReportTemplateRead(ReportTemplateBase):
    """Schema for reading a ReportTemplate."""
    id: UUID
    created_at: datetime
    updated_at: datetime


class ReportScheduleRead(ReportScheduleBase):
    """Schema for reading a ReportSchedule."""
    id: UUID
    last_run_at: Optional[datetime]
    next_run_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class ReportInstanceRead(ReportInstanceBase):
    """Schema for reading a ReportInstance."""
    id: UUID
    status: str
    file_path: Optional[str]
    generated_at: datetime
    completed_at: Optional[datetime]
    error_message: Optional[str]
    
    # Optional nested data for relationships
    template: Optional[ReportTemplateRead] = None
    schedule: Optional[ReportScheduleRead] = None


# --- Pydantic Schemas (Service-specific) ---
class ReportGenerationRequest(BaseModel):
    """Schema for an on-demand report generation request."""
    template_id: UUID = Field(..., description="ID of the report template to use.")
    output_format: str = Field(..., description="Desired output format (PDF, CSV, JSON, HTML).")
    # Optional parameters to override template data source or provide runtime data
    runtime_data: Optional[dict] = Field(None, description="Runtime data to pass to the template engine.")
