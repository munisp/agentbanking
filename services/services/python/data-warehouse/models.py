from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Index, UniqueConstraint, Boolean
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func

# --- SQLAlchemy Base ---
Base = declarative_base()

# --- SQLAlchemy Models ---

class DataWarehouse(Base):
    """
    Main model for the Data Warehouse service. Represents a single data asset
    or a logical grouping of data within the warehouse.
    """
    __tablename__ = "data_warehouse"

    id = Column(Integer, primary_key=True, index=True)
    
    # Core attributes
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    data_source_uri = Column(String(512), nullable=False, comment="URI or path to the actual data source (e.g., S3 path, database connection string)")
    
    # Metadata
    owner_id = Column(Integer, nullable=False, index=True, comment="ID of the user or service that owns this data asset")
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), default=func.now(), nullable=False)

    # Relationships
    activity_logs = relationship("DataWarehouseActivityLog", back_populates="data_warehouse", cascade="all, delete-orphan")

    # Constraints and Indexes
    __table_args__ = (
        UniqueConstraint('name', name='uq_data_warehouse_name'),
        Index('ix_data_warehouse_owner_active', owner_id, is_active),
    )

    def __repr__(self):
        return f"<DataWarehouse(id={self.id}, name='{self.name}', owner_id={self.owner_id})>"

class DataWarehouseActivityLog(Base):
    """
    Activity log for operations performed on a DataWarehouse asset.
    """
    __tablename__ = "data_warehouse_activity_log"

    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign Key to the main asset
    data_warehouse_id = Column(Integer, ForeignKey("data_warehouse.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Log details
    activity_type = Column(String(100), nullable=False, comment="Type of activity, e.g., 'CREATE', 'UPDATE', 'ACCESS', 'DELETE'")
    details = Column(Text, nullable=True, comment="Detailed description or JSON payload of the change/activity")
    performed_by_user_id = Column(Integer, nullable=False, index=True, comment="ID of the user or service that performed the action")
    
    # Timestamps
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    data_warehouse = relationship("DataWarehouse", back_populates="activity_logs")

    def __repr__(self):
        return f"<ActivityLog(id={self.id}, type='{self.activity_type}', dw_id={self.data_warehouse_id})>"

# --- Pydantic Schemas ---

# Base Schema for DataWarehouse
class DataWarehouseBase(BaseModel):
    name: str = Field(..., max_length=255, description="A unique, human-readable name for the data asset.")
    description: Optional[str] = Field(None, description="Detailed description of the data asset and its contents.")
    data_source_uri: str = Field(..., max_length=512, description="URI or path to the actual data source (e.g., S3 path, database connection string).")
    owner_id: int = Field(..., description="ID of the user or service that owns this data asset.")
    is_active: bool = Field(True, description="Flag to indicate if the data asset is currently active and available.")

# Schema for creating a new DataWarehouse asset
class DataWarehouseCreate(DataWarehouseBase):
    pass

# Schema for updating an existing DataWarehouse asset
class DataWarehouseUpdate(DataWarehouseBase):
    name: Optional[str] = Field(None, max_length=255, description="A unique, human-readable name for the data asset.")
    owner_id: Optional[int] = Field(None, description="ID of the user or service that owns this data asset.")
    # is_active is already optional in DataWarehouseBase, but we make all fields optional for update
    pass

# Schema for the response model (includes database-generated fields)
class DataWarehouseResponse(DataWarehouseBase):
    id: int = Field(..., description="The unique identifier of the data asset.")
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# Base Schema for Activity Log
class DataWarehouseActivityLogBase(BaseModel):
    data_warehouse_id: int = Field(..., description="ID of the DataWarehouse asset this log entry is for.")
    activity_type: str = Field(..., max_length=100, description="Type of activity, e.g., 'CREATE', 'UPDATE', 'ACCESS', 'DELETE'.")
    details: Optional[str] = Field(None, description="Detailed description or JSON payload of the change/activity.")
    performed_by_user_id: int = Field(..., description="ID of the user or service that performed the action.")

# Schema for the response model for Activity Log
class DataWarehouseActivityLogResponse(DataWarehouseActivityLogBase):
    id: int
    timestamp: datetime
    
    class Config:
        from_attributes = True

# Schema to include logs in the main response if needed
class DataWarehouseWithLogsResponse(DataWarehouseResponse):
    activity_logs: List[DataWarehouseActivityLogResponse] = []
    
    class Config:
        from_attributes = True
