import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, EmailStr
from sqlalchemy import (
    Column,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

# Define the base class for declarative class definitions
Base = declarative_base()

# --- SQLAlchemy Models ---

class ZapierIntegration(Base):
    """
    SQLAlchemy model for a Zapier Integration record.
    Represents a single configured integration with Zapier.
    """
    __tablename__ = "zapier_integrations"

    id = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    user_id = Column(
        Integer,
        nullable=False,
        index=True,
        doc="ID of the user who owns this integration",
    )
    name = Column(
        String(255), nullable=False, doc="A user-friendly name for the integration"
    )
    api_key = Column(
        String(512),
        nullable=False,
        doc="The Zapier API key or webhook URL (should be encrypted in production)",
    )
    is_active = Column(
        Boolean, default=True, nullable=False, doc="Status of the integration"
    )
    created_at = Column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    logs = relationship(
        "ZapierIntegrationLog",
        back_populates="integration",
        cascade="all, delete-orphan",
    )

    # Constraints and Indexes
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_user_name"),
        Index("ix_zapier_integration_user_active", user_id, is_active),
    )

    def __repr__(self):
        return f"<ZapierIntegration(id={self.id}, name='{self.name}', user_id={self.user_id})>"


class ZapierIntegrationLog(Base):
    """
    SQLAlchemy model for logging activity related to a Zapier Integration.
    """
    __tablename__ = "zapier_integration_logs"

    id = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    integration_id = Column(
        UUID(as_uuid=True),
        ForeignKey("zapier_integrations.id"),
        nullable=False,
        index=True,
    )
    timestamp = Column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    level = Column(
        String(50), nullable=False, doc="Log level (e.g., INFO, ERROR, TRIGGER)"
    )
    message = Column(
        Text, nullable=False, doc="Detailed log message"
    )
    payload = Column(
        Text, nullable=True, doc="Optional JSON payload related to the event"
    )

    # Relationships
    integration = relationship(
        "ZapierIntegration", back_populates="logs"
    )

    def __repr__(self):
        return f"<ZapierIntegrationLog(id={self.id}, level='{self.level}', timestamp={self.timestamp})>"


# --- Pydantic Schemas ---

# Base Schemas
class ZapierIntegrationBase(BaseModel):
    """Base schema for Zapier Integration."""
    name: str = Field(..., min_length=3, max_length=255, description="User-friendly name for the integration.")
    api_key: str = Field(..., min_length=10, max_length=512, description="The Zapier API key or webhook URL.")
    is_active: bool = Field(True, description="Whether the integration is currently active.")

class ZapierIntegrationLogBase(BaseModel):
    """Base schema for Zapier Integration Log."""
    level: str = Field(..., description="Log level (e.g., INFO, ERROR, TRIGGER).")
    message: str = Field(..., description="Detailed log message.")
    payload: Optional[str] = Field(None, description="Optional JSON payload.")

# Create Schemas
class ZapierIntegrationCreate(ZapierIntegrationBase):
    """Schema for creating a new Zapier Integration."""
    user_id: int = Field(..., description="The ID of the user creating the integration.")

class ZapierIntegrationLogCreate(ZapierIntegrationLogBase):
    """Schema for creating a new Zapier Integration Log entry."""
    integration_id: uuid.UUID = Field(..., description="The ID of the integration this log belongs to.")

# Update Schemas
class ZapierIntegrationUpdate(BaseModel):
    """Schema for updating an existing Zapier Integration."""
    name: Optional[str] = Field(None, min_length=3, max_length=255, description="User-friendly name for the integration.")
    api_key: Optional[str] = Field(None, min_length=10, max_length=512, description="The Zapier API key or webhook URL.")
    is_active: Optional[bool] = Field(None, description="Whether the integration is currently active.")

# Response Schemas
class ZapierIntegrationLogResponse(ZapierIntegrationLogBase):
    """Response schema for a Zapier Integration Log entry."""
    id: uuid.UUID
    integration_id: uuid.UUID
    timestamp: datetime

    class Config:
        from_attributes = True

class ZapierIntegrationResponse(ZapierIntegrationBase):
    """Response schema for a Zapier Integration."""
    id: uuid.UUID
    user_id: int
    created_at: datetime
    updated_at: datetime
    # logs: List[ZapierIntegrationLogResponse] = [] # Optional: include logs in response

    class Config:
        from_attributes = True

# Response schema for listing integrations with logs
class ZapierIntegrationDetailResponse(ZapierIntegrationResponse):
    """Detailed response schema including logs."""
    logs: List[ZapierIntegrationLogResponse] = []

    class Config:
        from_attributes = True
