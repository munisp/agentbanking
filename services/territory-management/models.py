import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field
from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Index, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, declarative_base

# --- SQLAlchemy Base ---

Base = declarative_base()

# --- SQLAlchemy Models ---

class Territory(Base):
    """
    SQLAlchemy model for a Territory.
    Represents a defined geographical or administrative area.
    """
    __tablename__ = "territories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, unique=True, nullable=False, index=True)
    territory_type = Column(String, nullable=False, index=True)  # e.g., 'Region', 'District', 'Zone'
    boundary_geojson = Column(Text, nullable=True)  # Store GeoJSON string for boundary
    status = Column(String, default="Active", nullable=False)  # e.g., 'Active', 'Inactive', 'Pending Review'
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)

    # Relationships
    activity_logs = relationship("TerritoryActivityLog", back_populates="territory", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_territories_status_type", "status", "territory_type"),
    )

    def __repr__(self):
        return f"<Territory(id='{self.id}', name='{self.name}', type='{self.territory_type}')>"

class TerritoryActivityLog(Base):
    """
    SQLAlchemy model for logging activities related to a Territory.
    """
    __tablename__ = "territory_activity_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    territory_id = Column(UUID(as_uuid=True), ForeignKey("territories.id"), nullable=False, index=True)
    action = Column(String, nullable=False)  # e.g., 'CREATED', 'UPDATED', 'STATUS_CHANGE', 'BOUNDARY_UPDATE'
    details = Column(Text, nullable=True)  # JSON string or text detailing the change
    user_id = Column(String, nullable=False)  # ID of the user who performed the action
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    territory = relationship("Territory", back_populates="activity_logs")

    def __repr__(self):
        return f"<TerritoryActivityLog(id='{self.id}', territory_id='{self.territory_id}', action='{self.action}')>"

# --- Pydantic Schemas ---

# Base Schemas
class TerritoryBase(BaseModel):
    """Base schema for Territory data."""
    name: str = Field(..., description="The unique name of the territory.")
    territory_type: str = Field(..., description="The type of the territory (e.g., Region, District, Zone).")
    boundary_geojson: Optional[str] = Field(None, description="GeoJSON string representing the territory boundary.")
    status: str = Field("Active", description="The current status of the territory.")

# Create Schema
class TerritoryCreate(TerritoryBase):
    """Schema for creating a new Territory."""
    pass

# Update Schema
class TerritoryUpdate(TerritoryBase):
    """Schema for updating an existing Territory."""
    name: Optional[str] = Field(None, description="The unique name of the territory.")
    territory_type: Optional[str] = Field(None, description="The type of the territory.")
    status: Optional[str] = Field(None, description="The current status of the territory.")

# Response Schema
class TerritoryResponse(TerritoryBase):
    """Schema for returning Territory data."""
    id: uuid.UUID = Field(..., description="The unique identifier of the territory.")
    created_at: datetime = Field(..., description="Timestamp of creation.")
    updated_at: datetime = Field(..., description="Timestamp of last update.")
    is_deleted: bool = Field(..., description="Flag indicating if the territory is soft-deleted.")

    class Config:
        from_attributes = True

# Activity Log Schemas
class TerritoryActivityLogBase(BaseModel):
    """Base schema for TerritoryActivityLog data."""
    territory_id: uuid.UUID = Field(..., description="The ID of the territory the log belongs to.")
    action: str = Field(..., description="The action performed (e.g., CREATED, UPDATED).")
    details: Optional[str] = Field(None, description="Details of the action, often a JSON string of changes.")
    user_id: str = Field(..., description="The ID of the user who performed the action.")

class TerritoryActivityLogResponse(TerritoryActivityLogBase):
    """Schema for returning TerritoryActivityLog data."""
    id: uuid.UUID = Field(..., description="The unique identifier of the log entry.")
    timestamp: datetime = Field(..., description="Timestamp of the action.")

    class Config:
        from_attributes = True

# List Response Schema
class TerritoryListResponse(BaseModel):
    """Schema for listing multiple Territories."""
    territories: List[TerritoryResponse]
    total: int
    page: int
    size: int
