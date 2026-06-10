import datetime
from typing import List, Optional

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, JSON, Index
from sqlalchemy.orm import relationship
from pydantic import BaseModel, Field, root_validator

from .config import Base, engine

# --- SQLAlchemy Models ---

class GoogleAssistantConfig(Base):
    """
    SQLAlchemy Model for Google Assistant Configuration Profiles.
    Represents a specific configuration or state for a user/device interaction.
    """
    __tablename__ = "google_assistant_configs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True, nullable=False, doc="Identifier for the user associated with the config.")
    device_id = Column(String, index=True, nullable=False, doc="Identifier for the device associated with the config.")
    config_name = Column(String, nullable=False, doc="A human-readable name for the configuration.")
    config_data = Column(JSON, nullable=False, doc="JSON object containing the specific configuration details.")
    is_active = Column(Boolean, default=True, doc="Flag to indicate if the configuration is currently active.")
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    # Relationship to logs
    logs = relationship("GoogleAssistantLog", back_populates="config")

    __table_args__ = (
        Index('ix_google_assistant_config_user_device', 'user_id', 'device_id', unique=True),
    )

class GoogleAssistantLog(Base):
    """
    SQLAlchemy Model for Google Assistant Activity Logs.
    Records interactions, errors, or state changes related to a configuration.
    """
    __tablename__ = "google_assistant_logs"

    id = Column(Integer, primary_key=True, index=True)
    config_id = Column(Integer, ForeignKey("google_assistant_configs.id"), nullable=False, index=True)
    log_type = Column(String, nullable=False, doc="Type of log (e.g., 'INFO', 'ERROR', 'INTERACTION').")
    message = Column(Text, nullable=False, doc="Detailed log message.")
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, index=True)
    metadata_json = Column(JSON, nullable=True, doc="Optional JSON field for additional log metadata.")

    # Relationship to config
    config = relationship("GoogleAssistantConfig", back_populates="logs")

# --- Pydantic Schemas ---

class GoogleAssistantConfigBase(BaseModel):
    """Base schema for Google Assistant Configuration."""
    user_id: str = Field(..., description="Identifier for the user.")
    device_id: str = Field(..., description="Identifier for the device.")
    config_name: str = Field(..., description="A human-readable name for the configuration.")
    config_data: dict = Field(..., description="JSON object containing the specific configuration details.")
    is_active: bool = Field(True, description="Flag to indicate if the configuration is currently active.")

    class Config:
        orm_mode = True
        schema_extra = {
            "example": {
                "user_id": "user_123",
                "device_id": "device_abc",
                "config_name": "Living Room Speaker Config",
                "config_data": {"volume": 50, "language": "en-US"},
                "is_active": True
            }
        }

class GoogleAssistantConfigCreate(GoogleAssistantConfigBase):
    """Schema for creating a new Google Assistant Configuration."""
    pass

class GoogleAssistantConfigUpdate(GoogleAssistantConfigBase):
    """Schema for updating an existing Google Assistant Configuration."""
    user_id: Optional[str] = Field(None, description="Identifier for the user.")
    device_id: Optional[str] = Field(None, description="Identifier for the device.")
    config_name: Optional[str] = Field(None, description="A human-readable name for the configuration.")
    config_data: Optional[dict] = Field(None, description="JSON object containing the specific configuration details.")
    is_active: Optional[bool] = Field(None, description="Flag to indicate if the configuration is currently active.")

class GoogleAssistantConfigResponse(GoogleAssistantConfigBase):
    """Schema for returning a Google Assistant Configuration."""
    id: int = Field(..., description="Unique ID of the configuration.")
    created_at: datetime.datetime = Field(..., description="Timestamp of creation.")
    updated_at: datetime.datetime = Field(..., description="Timestamp of last update.")

    class Config:
        orm_mode = True

class GoogleAssistantLogBase(BaseModel):
    """Base schema for Google Assistant Activity Log."""
    config_id: int = Field(..., description="ID of the associated configuration.")
    log_type: str = Field(..., description="Type of log (e.g., 'INFO', 'ERROR', 'INTERACTION').")
    message: str = Field(..., description="Detailed log message.")
    metadata_json: Optional[dict] = Field(None, description="Optional JSON field for additional log metadata.")

    class Config:
        orm_mode = True
        schema_extra = {
            "example": {
                "config_id": 1,
                "log_type": "INTERACTION",
                "message": "User requested 'Turn off the lights'",
                "metadata_json": {"command": "lights_off", "status": "success"}
            }
        }

class GoogleAssistantLogCreate(GoogleAssistantLogBase):
    """Schema for creating a new Google Assistant Log entry."""
    pass

class GoogleAssistantLogResponse(GoogleAssistantLogBase):
    """Schema for returning a Google Assistant Log entry."""
    id: int = Field(..., description="Unique ID of the log entry.")
    timestamp: datetime.datetime = Field(..., description="Timestamp of the log entry.")

    class Config:
        orm_mode = True

# --- Database Initialization ---

def init_db():
    """
    Initializes the database by creating all defined tables.
    """
    # This is typically done in a migration tool, but for a simple service,
    # we can create tables directly.
    Base.metadata.create_all(bind=engine)
