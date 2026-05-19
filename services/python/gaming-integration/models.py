from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship, declarative_base
from pydantic import BaseModel, Field, root_validator

# Define the base class for declarative class definitions
Base = declarative_base()

# --- SQLAlchemy Models ---

class GamingIntegration(Base):
    """
    SQLAlchemy model for a Gaming Integration configuration.
    Represents a connection to an external gaming platform or service.
    """
    __tablename__ = "gaming_integrations"

    id = Column(Integer, primary_key=True, index=True)
    platform_name = Column(String(100), nullable=False, index=True, unique=True)
    api_key_hash = Column(String(255), nullable=False, comment="Hashed API key or secret token")
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_sync_at = Column(DateTime, nullable=True, comment="Timestamp of the last successful data synchronization")

    # Relationships
    activity_logs = relationship(
        "IntegrationActivityLog", 
        back_populates="integration", 
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<GamingIntegration(id={self.id}, platform_name='{self.platform_name}')>"

    __table_args__ = (
        # Enforce uniqueness on platform_name
        UniqueConstraint("platform_name", name="uq_platform_name"),
        # Index on is_active for quick filtering of active integrations
        Index("ix_is_active", "is_active"),
    )


class IntegrationActivityLog(Base):
    """
    SQLAlchemy model for logging activities related to a Gaming Integration.
    """
    __tablename__ = "integration_activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    integration_id = Column(Integer, ForeignKey("gaming_integrations.id"), nullable=False, index=True)
    
    activity_type = Column(String(50), nullable=False, index=True, comment="e.g., 'SYNC_START', 'SYNC_SUCCESS', 'SYNC_FAILURE', 'UPDATE'")
    message = Column(Text, nullable=False, comment="Detailed log message")
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    integration = relationship("GamingIntegration", back_populates="activity_logs")

    def __repr__(self):
        return (
            f"<IntegrationActivityLog(id={self.id}, integration_id={self.integration_id}, "
            f"activity_type='{self.activity_type}')>"
        )


# --- Pydantic Schemas ---

# Base Schema for common fields
class GamingIntegrationBase(BaseModel):
    """Base Pydantic schema for GamingIntegration."""
    platform_name: str = Field(..., max_length=100, description="The name of the gaming platform (e.g., 'Steam', 'Xbox Live').")
    is_active: bool = Field(True, description="Whether the integration is currently active.")

    class Config:
        orm_mode = True


# Schema for creating a new integration
class GamingIntegrationCreate(GamingIntegrationBase):
    """Pydantic schema for creating a new GamingIntegration."""
    # Note: api_key is required for creation, but not stored directly in the model
    # The router/service layer will hash this before storing it as api_key_hash
    api_key: str = Field(..., description="The secret API key or token for the platform.")


# Schema for updating an existing integration
class GamingIntegrationUpdate(GamingIntegrationBase):
    """Pydantic schema for updating an existing GamingIntegration."""
    platform_name: Optional[str] = Field(None, max_length=100, description="The name of the gaming platform.")
    is_active: Optional[bool] = Field(None, description="Whether the integration is currently active.")
    # Optional new API key for update
    api_key: Optional[str] = Field(None, description="A new secret API key or token for the platform.")


# Schema for the response model (excludes sensitive fields like api_key_hash)
class GamingIntegrationResponse(GamingIntegrationBase):
    """Pydantic schema for returning a GamingIntegration object."""
    id: int
    created_at: datetime
    updated_at: datetime
    last_sync_at: Optional[datetime] = None
    
    # Exclude api_key_hash from the response model


# Base Schema for Activity Log
class IntegrationActivityLogBase(BaseModel):
    """Base Pydantic schema for IntegrationActivityLog."""
    activity_type: str = Field(..., max_length=50, description="Type of activity (e.g., 'SYNC_SUCCESS').")
    message: str = Field(..., description="Detailed log message.")

    class Config:
        orm_mode = True


# Schema for creating a new log entry
class IntegrationActivityLogCreate(IntegrationActivityLogBase):
    """Pydantic schema for creating a new IntegrationActivityLog entry."""
    # integration_id is passed via the path/function call, not the body


# Schema for the response model
class IntegrationActivityLogResponse(IntegrationActivityLogBase):
    """Pydantic schema for returning an IntegrationActivityLog object."""
    id: int
    integration_id: int
    timestamp: datetime
