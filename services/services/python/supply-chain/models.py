from datetime import datetime
from typing import List, Optional
from enum import Enum

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Float, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from pydantic import BaseModel, Field
from pydantic.alias_generators import to_camel

from .config import Base

# --- Enums ---

class ItemStatus(str, Enum):
    """
    Defines the possible statuses for a supply chain item.
    """
    PENDING = "PENDING"
    IN_TRANSIT = "IN_TRANSIT"
    RECEIVED = "RECEIVED"
    DAMAGED = "DAMAGED"
    LOST = "LOST"
    DELIVERED = "DELIVERED"

# --- SQLAlchemy Models ---

class SupplyChainItem(Base):
    """
    Represents a single item or batch in the supply chain.
    """
    __tablename__ = "supply_chain_items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    sku = Column(String(100), nullable=False, unique=True, index=True)
    quantity = Column(Integer, nullable=False, default=1)
    unit_cost = Column(Float, nullable=False, default=0.0)
    
    # Supply Chain specific fields
    current_location = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False, default=ItemStatus.PENDING.value)
    supplier_id = Column(Integer, index=True) # Could be a foreign key to a 'suppliers' table in a real system
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship to ActivityLog
    activity_logs = relationship("ActivityLog", back_populates="item", cascade="all, delete-orphan")

    __table_args__ = (
        # Index for faster lookups by status and location
        Index("idx_status_location", "status", "current_location"),
    )

class ActivityLog(Base):
    """
    Logs significant events or status changes for a SupplyChainItem.
    """
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("supply_chain_items.id"), nullable=False, index=True)
    
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    activity_type = Column(String(100), nullable=False) # e.g., "STATUS_UPDATE", "LOCATION_CHANGE", "INSPECTION"
    details = Column(Text, nullable=True)
    
    # Relationship back to SupplyChainItem
    item = relationship("SupplyChainItem", back_populates="activity_logs")

    __table_args__ = (
        # Unique constraint to prevent duplicate logs for the same item at the exact same time/type (optional, but good practice)
        UniqueConstraint("item_id", "timestamp", "activity_type", name="uq_item_timestamp_type"),
    )

# --- Pydantic Schemas ---

class Config(BaseModel):
    """
    Configuration for Pydantic models to use camelCase for JSON output.
    """
    model_config = {
        "alias_generator": to_camel,
        "populate_by_name": True,
        "from_attributes": True,
    }

# --- Base Schemas ---

class ActivityLogBase(Config):
    """Base schema for ActivityLog."""
    activity_type: str = Field(..., description="Type of activity (e.g., STATUS_UPDATE, LOCATION_CHANGE).")
    details: Optional[str] = Field(None, description="Detailed description of the activity.")

class SupplyChainItemBase(Config):
    """Base schema for SupplyChainItem."""
    name: str = Field(..., max_length=255, description="Name of the supply chain item or product.")
    sku: str = Field(..., max_length=100, description="Stock Keeping Unit (SKU) for the item.")
    quantity: int = Field(1, ge=1, description="Number of units in this batch/item.")
    unit_cost: float = Field(0.0, ge=0.0, description="Cost per unit.")
    current_location: str = Field(..., max_length=255, description="Current physical location of the item.")
    status: ItemStatus = Field(ItemStatus.PENDING, description="Current status of the item in the supply chain.")
    supplier_id: int = Field(..., description="ID of the supplier.")

# --- Create Schemas ---

class ActivityLogCreate(ActivityLogBase):
    """Schema for creating a new ActivityLog entry."""
    item_id: int = Field(..., description="ID of the SupplyChainItem this log belongs to.")

class SupplyChainItemCreate(SupplyChainItemBase):
    """Schema for creating a new SupplyChainItem."""
    pass # Inherits all fields from Base

# --- Update Schemas ---

class SupplyChainItemUpdate(SupplyChainItemBase):
    """Schema for updating an existing SupplyChainItem."""
    name: Optional[str] = None
    sku: Optional[str] = None
    quantity: Optional[int] = None
    unit_cost: Optional[float] = None
    current_location: Optional[str] = None
    status: Optional[ItemStatus] = None
    supplier_id: Optional[int] = None

# --- Response Schemas ---

class ActivityLogResponse(ActivityLogBase):
    """Response schema for ActivityLog, including generated fields."""
    id: int
    timestamp: datetime
    item_id: int

class SupplyChainItemResponse(SupplyChainItemBase):
    """Response schema for SupplyChainItem, including generated fields and logs."""
    id: int
    created_at: datetime
    updated_at: datetime
    
    # Nested relationship
    activity_logs: List[ActivityLogResponse] = Field(..., description="List of all activity logs for this item.")

class SupplyChainItemSimpleResponse(SupplyChainItemBase):
    """Simplified response schema for list views."""
    id: int
    created_at: datetime
    updated_at: datetime
