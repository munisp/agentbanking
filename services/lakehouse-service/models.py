import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Text, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, declarative_base
from pydantic import BaseModel, Field

# --- SQLAlchemy Base Setup ---
Base = declarative_base()

# --- SQLAlchemy Models ---

class DataAsset(Base):
    __tablename__ = "data_assets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String, nullable=False, index=True)
    asset_type = Column(String, nullable=False)  # e.g., 'table', 'file', 'stream'
    storage_path = Column(String, nullable=False, unique=True)  # e.g., s3://bucket/path/
    schema_definition = Column(JSONB, nullable=True)  # Stores the schema in JSON format
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationship to ActivityLog
    activity_logs = relationship("ActivityLog", back_populates="data_asset", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_data_assets_name_type", "name", "asset_type"),
    )

class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    data_asset_id = Column(UUID(as_uuid=True), ForeignKey("data_assets.id"), nullable=False)
    action = Column(String, nullable=False)  # e.g., 'CREATE', 'UPDATE_SCHEMA', 'DELETE'
    user_id = Column(String, nullable=False)  # Identifier for the user/system performing the action
    details = Column(JSONB, nullable=True)  # Additional details about the action
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationship to DataAsset
    data_asset = relationship("DataAsset", back_populates="activity_logs")

# --- Pydantic Schemas ---

# Base Schema for DataAsset
class DataAssetBase(BaseModel):
    name: str = Field(..., example="customer_data_table")
    asset_type: str = Field(..., example="table", description="Type of the asset (e.g., table, file, stream)")
    storage_path: str = Field(..., example="s3://data-lake/raw/customer_data/")
    schema_definition: Optional[dict] = Field(None, example={"fields": [{"name": "id", "type": "int"}]})

    class Config:
        from_attributes = True

# Schema for creating a new DataAsset
class DataAssetCreate(DataAssetBase):
    pass

# Schema for updating an existing DataAsset
class DataAssetUpdate(DataAssetBase):
    name: Optional[str] = None
    asset_type: Optional[str] = None
    storage_path: Optional[str] = None
    is_active: Optional[bool] = None
    schema_definition: Optional[dict] = None

# Schema for responding with a DataAsset
class DataAssetResponse(DataAssetBase):
    id: uuid.UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    # Nested schema for logs can be added here if needed, but for simplicity, we'll keep it flat for now.

# Base Schema for ActivityLog
class ActivityLogBase(BaseModel):
    data_asset_id: uuid.UUID
    action: str = Field(..., example="CREATE")
    user_id: str = Field(..., example="system_etl_job_123")
    details: Optional[dict] = Field(None, example={"old_path": "...", "new_path": "..."})

    class Config:
        from_attributes = True

# Schema for responding with an ActivityLog
class ActivityLogResponse(ActivityLogBase):
    id: uuid.UUID
    timestamp: datetime

# Schema for listing DataAssets with their logs (optional, but good for completeness)
class DataAssetWithLogsResponse(DataAssetResponse):
    activity_logs: List[ActivityLogResponse] = []
