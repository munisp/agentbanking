import datetime
from typing import List, Optional

from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, Index
from sqlalchemy.orm import relationship, declarative_base

# --- SQLAlchemy Base ---

Base = declarative_base()

# --- SQLAlchemy Models ---

class IntegrationConfig(Base):
    """
    SQLAlchemy model for storing configuration details of an external integration.
    """
    __tablename__ = "integration_configs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
    integration_type = Column(String, nullable=False)  # e.g., "CRM", "ERP", "Messaging"
    api_key_secret = Column(String, nullable=False)
    endpoint_url = Column(String, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    last_synced_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    # Relationship to activity logs
    activity_logs = relationship("IntegrationActivityLog", back_populates="config", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_integration_configs_type_active", integration_type, is_active),
    )

class IntegrationActivityLog(Base):
    """
    SQLAlchemy model for logging activities related to an integration configuration.
    """
    __tablename__ = "integration_activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    config_id = Column(Integer, ForeignKey("integration_configs.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, index=True)
    activity_type = Column(String, nullable=False)  # e.g., "SYNC_START", "SYNC_SUCCESS", "SYNC_FAILURE", "CONFIG_UPDATE"
    details = Column(Text, nullable=True)
    is_error = Column(Boolean, default=False, nullable=False)

    # Relationship back to the configuration
    config = relationship("IntegrationConfig", back_populates="activity_logs")

    __table_args__ = (
        Index("ix_activity_logs_config_type", config_id, activity_type),
    )

# --- Pydantic Schemas ---

# Base Schema for common fields
class IntegrationConfigBase(BaseModel):
    """Base Pydantic schema for IntegrationConfig."""
    name: str = Field(..., description="Unique name for the integration.")
    integration_type: str = Field(..., description="Type of external service (e.g., CRM, ERP).")
    api_key_secret: str = Field(..., description="API key or secret for the external service.")
    endpoint_url: str = Field(..., description="Base URL for the external service API.")
    is_active: bool = Field(True, description="Whether the integration is currently active.")

# Schema for creating a new configuration
class IntegrationConfigCreate(IntegrationConfigBase):
    """Pydantic schema for creating a new IntegrationConfig."""
    pass

# Schema for updating an existing configuration
class IntegrationConfigUpdate(IntegrationConfigBase):
    """Pydantic schema for updating an existing IntegrationConfig."""
    name: Optional[str] = Field(None, description="Unique name for the integration.")
    integration_type: Optional[str] = Field(None, description="Type of external service (e.g., CRM, ERP).")
    api_key_secret: Optional[str] = Field(None, description="API key or secret for the external service.")
    endpoint_url: Optional[str] = Field(None, description="Base URL for the external service API.")
    is_active: Optional[bool] = Field(None, description="Whether the integration is currently active.")

# Schema for the response model (includes database-generated fields)
class IntegrationConfigResponse(IntegrationConfigBase):
    """Pydantic schema for returning an IntegrationConfig."""
    id: int = Field(..., description="Unique identifier for the configuration.")
    last_synced_at: Optional[datetime.datetime] = Field(None, description="Timestamp of the last successful sync.")
    created_at: datetime.datetime = Field(..., description="Timestamp when the configuration was created.")
    updated_at: datetime.datetime = Field(..., description="Timestamp when the configuration was last updated.")

    class Config:
        from_attributes = True

# Schema for activity log response
class IntegrationActivityLogResponse(BaseModel):
    """Pydantic schema for returning an IntegrationActivityLog."""
    id: int
    config_id: int
    timestamp: datetime.datetime
    activity_type: str
    details: Optional[str]
    is_error: bool

    class Config:
        from_attributes = True

# Schema for creating an activity log (used internally, not exposed via API)
class IntegrationActivityLogCreate(BaseModel):
    """Pydantic schema for creating a new IntegrationActivityLog."""
    config_id: int
    activity_type: str
    details: Optional[str] = None
    is_error: bool = False
