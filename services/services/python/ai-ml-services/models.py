import uuid
from datetime import datetime
from typing import List, Optional
from enum import Enum

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean, Index
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from pydantic import BaseModel, Field, ConfigDict

# Assuming Base is imported from config.py
from config import Base, engine

# --- Enums for Model Fields ---

class ModelType(str, Enum):
    """Defines the type of the machine learning model."""
    GNN = "GNN"
    DEEP_LEARNING = "DEEP_LEARNING"
    TRADITIONAL_ML = "TRADITIONAL_ML"
    RULE_BASED = "RULE_BASED"
    ENSEMBLE = "ENSEMBLE"

class ModelStatus(str, Enum):
    """Defines the deployment status of the machine learning model."""
    TRAINING = "Training"
    READY = "Ready"
    DEPLOYED = "Deployed"
    FAILED = "Failed"
    ARCHIVED = "Archived"

class LogAction(str, Enum):
    """Defines the type of action recorded in the activity log."""
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DEPLOY = "DEPLOY"
    ARCHIVE = "ARCHIVE"
    SCORE = "SCORE"
    ERROR = "ERROR"

# --- SQLAlchemy Models ---

class MLModel(Base):
    """
    SQLAlchemy Model for a registered Machine Learning Model.
    This model tracks metadata about deployed or in-training ML models.
    """
    __tablename__ = "ml_models"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False, comment="Identifier for the multi-tenant environment")
    name: Mapped[str] = mapped_column(String(255), index=True, nullable=False, comment="Human-readable name of the model")
    version: Mapped[str] = mapped_column(String(50), nullable=False, comment="Version string of the model (e.g., v1.0.1)")
    model_type: Mapped[ModelType] = mapped_column(String(50), nullable=False, comment="Type of the model (e.g., GNN, DEEP_LEARNING)")
    status: Mapped[ModelStatus] = mapped_column(String(50), default=ModelStatus.TRAINING, nullable=False, comment="Current status of the model")
    description: Mapped[Optional[str]] = mapped_column(Text, comment="Detailed description of the model and its purpose")
    model_uri: Mapped[Optional[str]] = mapped_column(String(512), comment="URI or path to the stored model artifact")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, comment="Flag to indicate if the model is currently active for use")
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    activity_logs: Mapped[List["MLModelActivityLog"]] = relationship("MLModelActivityLog", back_populates="model", cascade="all, delete-orphan")

    # Constraints and Indexes
    __table_args__ = (
        Index("ix_ml_models_tenant_name_version", "tenant_id", "name", "version", unique=True),
    )

    def __repr__(self) -> str:
        return f"<MLModel(id={self.id}, name='{self.name}', version='{self.version}', status='{self.status}')>"

class MLModelActivityLog(Base):
    """
    SQLAlchemy Model for logging activities related to a specific MLModel.
    """
    __tablename__ = "ml_model_activity_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    model_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ml_models.id"), nullable=False, index=True)
    action: Mapped[LogAction] = mapped_column(String(50), nullable=False, comment="The action performed (e.g., DEPLOY, UPDATE)")
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), index=True, comment="ID of the user who performed the action")
    details: Mapped[Optional[str]] = mapped_column(Text, comment="JSON or text details about the activity")
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    model: Mapped["MLModel"] = relationship("MLModel", back_populates="activity_logs")

    def __repr__(self) -> str:
        return f"<MLModelActivityLog(id={self.id}, model_id={self.model_id}, action='{self.action}')>"

# --- Pydantic Schemas ---

# Base Schema for shared attributes
class MLModelBase(BaseModel):
    """Base Pydantic schema for MLModel."""
    name: str = Field(..., max_length=255, description="Human-readable name of the model.")
    version: str = Field(..., max_length=50, description="Version string of the model (e.g., v1.0.1).")
    model_type: ModelType = Field(..., description="Type of the model (e.g., GNN, DEEP_LEARNING).")
    description: Optional[str] = Field(None, description="Detailed description of the model and its purpose.")
    model_uri: Optional[str] = Field(None, max_length=512, description="URI or path to the stored model artifact.")
    is_active: bool = Field(True, description="Flag to indicate if the model is currently active for use.")

# Schema for creating a new model
class MLModelCreate(MLModelBase):
    """Pydantic schema for creating a new MLModel."""
    tenant_id: uuid.UUID = Field(..., description="Identifier for the multi-tenant environment.")
    # Status is typically set by the system upon creation (e.g., TRAINING) but can be overridden
    status: ModelStatus = Field(ModelStatus.TRAINING, description="Current status of the model.")

# Schema for updating an existing model
class MLModelUpdate(MLModelBase):
    """Pydantic schema for updating an existing MLModel."""
    name: Optional[str] = Field(None, max_length=255, description="Human-readable name of the model.")
    version: Optional[str] = Field(None, max_length=50, description="Version string of the model (e.g., v1.0.1).")
    model_type: Optional[ModelType] = Field(None, description="Type of the model (e.g., GNN, DEEP_LEARNING).")
    status: Optional[ModelStatus] = Field(None, description="Current status of the model.")
    is_active: Optional[bool] = Field(None, description="Flag to indicate if the model is currently active for use.")

# Schema for model response (includes read-only fields)
class MLModelResponse(MLModelBase):
    """Pydantic schema for returning an MLModel instance."""
    id: uuid.UUID
    tenant_id: uuid.UUID
    status: ModelStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

# Schema for activity log response
class MLModelActivityLogResponse(BaseModel):
    """Pydantic schema for returning an MLModelActivityLog instance."""
    id: int
    model_id: uuid.UUID
    action: LogAction
    user_id: Optional[uuid.UUID]
    details: Optional[str]
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)

# --- Database Initialization (Optional, but useful for quick setup) ---

def create_db_and_tables():
    """Creates the database tables based on the defined models."""
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    # This block is for testing and initial setup
    print("Creating database and tables...")
    create_db_and_tables()
    print("Database and tables created successfully.")
