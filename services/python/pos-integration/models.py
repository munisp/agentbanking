import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Boolean,
    Float,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship, declarative_base

# --- SQLAlchemy Models ---

Base = declarative_base()


class POSIntegration(Base):
    """
    SQLAlchemy model for the main POS Integration entity.
    Represents a single integration configuration with a Point-of-Sale system.
    """

    __tablename__ = "pos_integrations"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False, index=True)
    integration_type = Column(String(50), nullable=False)  # e.g., 'Square', 'Toast', 'Custom'
    api_key = Column(String(255), nullable=False)
    secret_key = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    last_sync_at = Column(DateTime, nullable=True)
    sync_interval_minutes = Column(Integer, default=60, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
        nullable=False,
    )

    # Relationships
    activity_logs = relationship(
        "POSIntegrationActivityLog", back_populates="integration"
    )

    # Constraints and Indexes
    __table_args__ = (
        UniqueConstraint("name", name="uq_pos_integration_name"),
        Index("ix_pos_integration_type", "integration_type"),
    )

    def __repr__(self):
        return (
            f"<POSIntegration(id='{self.id}', name='{self.name}', "
            f"type='{self.integration_type}')>"
        )


class POSIntegrationActivityLog(Base):
    """
    SQLAlchemy model for logging activities related to a POS Integration.
    """

    __tablename__ = "pos_integration_activity_logs"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    integration_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("pos_integrations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    activity_type = Column(String(50), nullable=False)  # e.g., 'SYNC_START', 'SYNC_SUCCESS', 'ERROR'
    details = Column(Text, nullable=True)
    duration_seconds = Column(Float, nullable=True)

    # Relationships
    integration = relationship("POSIntegration", back_populates="activity_logs")

    def __repr__(self):
        return (
            f"<POSIntegrationActivityLog(id='{self.id}', "
            f"type='{self.activity_type}', integration_id='{self.integration_id}')>"
        )


# --- Pydantic Schemas ---


class POSIntegrationBase(BaseModel):
    """Base schema for POS Integration, containing common fields."""

    name: str = Field(..., description="A unique, human-readable name for the integration.")
    integration_type: str = Field(..., description="The type of POS system (e.g., 'Square', 'Toast').")
    api_key: str = Field(..., description="The API key for the POS system.")
    secret_key: Optional[str] = Field(None, description="The secret key or token for the POS system.")
    sync_interval_minutes: int = Field(60, gt=0, description="The synchronization interval in minutes.")


class POSIntegrationCreate(POSIntegrationBase):
    """Schema for creating a new POS Integration."""

    pass


class POSIntegrationUpdate(POSIntegrationBase):
    """Schema for updating an existing POS Integration."""

    name: Optional[str] = Field(None, description="A unique, human-readable name for the integration.")
    integration_type: Optional[str] = Field(None, description="The type of POS system (e.g., 'Square', 'Toast').")
    api_key: Optional[str] = Field(None, description="The API key for the POS system.")
    is_active: Optional[bool] = Field(None, description="Whether the integration is currently active.")
    secret_key: Optional[str] = Field(None, description="The secret key or token for the POS system.")
    sync_interval_minutes: Optional[int] = Field(None, gt=0, description="The synchronization interval in minutes.")


class POSIntegrationResponse(POSIntegrationBase):
    """Schema for returning a POS Integration entity."""

    id: UUID = Field(..., description="The unique identifier of the integration.")
    is_active: bool = Field(..., description="Whether the integration is currently active.")
    last_sync_at: Optional[datetime.datetime] = Field(None, description="Timestamp of the last successful synchronization.")
    created_at: datetime.datetime = Field(..., description="Timestamp of creation.")
    updated_at: datetime.datetime = Field(..., description="Timestamp of last update.")

    class Config:
        orm_mode = True


class POSIntegrationActivityLogBase(BaseModel):
    """Base schema for POS Integration Activity Log."""

    activity_type: str = Field(..., description="Type of activity (e.g., 'SYNC_START', 'ERROR').")
    details: Optional[str] = Field(None, description="Detailed description or error message.")
    duration_seconds: Optional[float] = Field(None, ge=0, description="Duration of the activity, if applicable.")


class POSIntegrationActivityLogResponse(POSIntegrationActivityLogBase):
    """Schema for returning an Activity Log entity."""

    id: UUID = Field(..., description="The unique identifier of the log entry.")
    integration_id: UUID = Field(..., description="The ID of the associated POS Integration.")
    timestamp: datetime.datetime = Field(..., description="Timestamp of the activity.")

    class Config:
        orm_mode = True


class POSIntegrationDetailResponse(POSIntegrationResponse):
    """Schema for returning a POS Integration entity with its activity logs."""

    activity_logs: List[POSIntegrationActivityLogResponse] = Field(
        [], description="List of recent activity logs for this integration."
    )
    
    class Config:
        orm_mode = True
