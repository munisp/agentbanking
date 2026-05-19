from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Boolean,
    ForeignKey,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship, declarative_base

# Base class for SQLAlchemy models
Base = declarative_base()


class NeuralNetworkModel(Base):
    """
    SQLAlchemy model for a deployed Neural Network Model.
    Includes multi-tenancy support via tenant_id.
    """

    __tablename__ = "neural_network_models"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, index=True, nullable=False, doc="Identifier for the tenant/customer.")
    name = Column(String, index=True, nullable=False, doc="Human-readable name for the model.")
    description = Column(Text, nullable=True, doc="Detailed description of the model's purpose and architecture.")
    model_config = Column(Text, nullable=False, doc="JSON string of the model's configuration (e.g., layers, hyperparameters).")
    model_path = Column(String, nullable=False, doc="File path or URI to the stored model artifact.")
    version = Column(String, nullable=False, default="1.0.0", doc="Version of the model.")
    is_active = Column(Boolean, default=True, doc="Flag to indicate if the model is currently active for inference.")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    activity_logs = relationship("ActivityLog", back_populates="model")

    # Constraints and Indexes
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_tenant_model_name"),
        Index("ix_model_version", "tenant_id", "version"),
    )


class ActivityLog(Base):
    """
    SQLAlchemy model for logging activities related to a Neural Network Model.
    """

    __tablename__ = "model_activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, ForeignKey("neural_network_models.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    activity_type = Column(String, nullable=False, doc="Type of activity (e.g., 'DEPLOY', 'INFERENCE', 'UPDATE').")
    details = Column(Text, nullable=True, doc="JSON string containing activity details.")
    user_id = Column(String, nullable=True, doc="ID of the user or system component that performed the action.")

    # Relationships
    model = relationship("NeuralNetworkModel", back_populates="activity_logs")


# Pydantic Schemas for Data Validation and Serialization

# Base Schemas
class NeuralNetworkModelBase(BaseModel):
    """Base schema for NeuralNetworkModel."""
    tenant_id: str = Field(..., description="Identifier for the tenant/customer.")
    name: str = Field(..., description="Human-readable name for the model.")
    description: Optional[str] = Field(None, description="Detailed description of the model's purpose and architecture.")
    model_config: str = Field(..., description="JSON string of the model's configuration.")
    model_path: str = Field(..., description="File path or URI to the stored model artifact.")
    version: str = Field("1.0.0", description="Version of the model.")
    is_active: bool = Field(True, description="Flag to indicate if the model is currently active for inference.")

    class Config:
        from_attributes = True


class ActivityLogBase(BaseModel):
    """Base schema for ActivityLog."""
    model_id: int = Field(..., description="ID of the associated neural network model.")
    activity_type: str = Field(..., description="Type of activity (e.g., 'DEPLOY', 'INFERENCE', 'UPDATE').")
    details: Optional[str] = Field(None, description="JSON string containing activity details.")
    user_id: Optional[str] = Field(None, description="ID of the user or system component that performed the action.")

    class Config:
        from_attributes = True


# CRUD Schemas
class NeuralNetworkModelCreate(NeuralNetworkModelBase):
    """Schema for creating a new NeuralNetworkModel."""
    # Inherits all fields from Base, no extra fields needed for creation
    pass


class NeuralNetworkModelUpdate(BaseModel):
    """Schema for updating an existing NeuralNetworkModel."""
    name: Optional[str] = None
    description: Optional[str] = None
    model_config: Optional[str] = None
    model_path: Optional[str] = None
    version: Optional[str] = None
    is_active: Optional[bool] = None

    class Config:
        from_attributes = True


# Response Schemas
class NeuralNetworkModelResponse(NeuralNetworkModelBase):
    """Schema for returning a NeuralNetworkModel, including read-only fields."""
    id: int
    created_at: datetime
    updated_at: datetime
    # Nested relationship for logs
    activity_logs: List["ActivityLogResponse"] = []


class ActivityLogResponse(ActivityLogBase):
    """Schema for returning an ActivityLog, including read-only fields."""
    id: int
    timestamp: datetime

    # Nested relationship for model (optional, to avoid circular dependency in main response)
    # model: NeuralNetworkModelResponse # Omitted to prevent circular reference in the main response

# Update forward references for nested schemas
NeuralNetworkModelResponse.model_rebuild()
