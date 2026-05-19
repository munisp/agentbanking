import datetime
from typing import List, Optional

from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, Index
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.ext.declarative import declarative_base
from pydantic import BaseModel, Field

# --- SQLAlchemy Base and Models ---

Base = declarative_base()

class FalkorDBServiceEntity(Base):
    """
    SQLAlchemy Model for the main entity of the falkordb-service.
    Represents a configuration or instance related to FalkorDB.
    """
    __tablename__ = "falkordb_service_entities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    falkordb_connection_string: Mapped[str] = mapped_column(String(512), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    # Relationship to the activity log
    activities: Mapped[List["FalkorDBServiceActivityLog"]] = relationship(
        "FalkorDBServiceActivityLog", back_populates="entity", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_falkordb_service_entity_name", "name"),
        # Example of a constraint: ensure connection string is not empty
        # CheckConstraint(falkordb_connection_string != '', name='check_connection_string_not_empty')
    )

class FalkorDBServiceActivityLog(Base):
    """
    SQLAlchemy Model for logging activities related to a FalkorDBServiceEntity.
    """
    __tablename__ = "falkordb_service_activity_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    entity_id: Mapped[int] = mapped_column(Integer, ForeignKey("falkordb_service_entities.id"), nullable=False)
    activity_type: Mapped[str] = mapped_column(String(100), nullable=False) # e.g., 'CREATE', 'UPDATE', 'CONNECTION_TEST'
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # Relationship back to the main entity
    entity: Mapped["FalkorDBServiceEntity"] = relationship(
        "FalkorDBServiceEntity", back_populates="activities"
    )

    __table_args__ = (
        Index("idx_activity_entity_id", "entity_id"),
        Index("idx_activity_timestamp", "timestamp"),
    )

# --- Pydantic Schemas ---

class FalkorDBServiceEntityBase(BaseModel):
    """Base Pydantic schema for FalkorDBServiceEntity."""
    name: str = Field(..., description="Unique name for the FalkorDB service entity.")
    description: Optional[str] = Field(None, description="A brief description of the entity.")
    falkordb_connection_string: str = Field(..., description="The connection string for the FalkorDB instance.")
    is_active: bool = Field(True, description="Status indicating if the entity is active.")

    class Config:
        from_attributes = True

class FalkorDBServiceEntityCreate(FalkorDBServiceEntityBase):
    """Pydantic schema for creating a new FalkorDBServiceEntity."""
    # Inherits all fields from Base, no additional fields needed for creation
    pass

class FalkorDBServiceEntityUpdate(FalkorDBServiceEntityBase):
    """Pydantic schema for updating an existing FalkorDBServiceEntity."""
    name: Optional[str] = Field(None, description="Unique name for the FalkorDB service entity.")
    falkordb_connection_string: Optional[str] = Field(None, description="The connection string for the FalkorDB instance.")
    # All fields are optional for update, except those inherited from Base which are made optional here.
    # Note: description and is_active are already optional in Base.

class FalkorDBServiceActivityLogResponse(BaseModel):
    """Pydantic schema for responding with an activity log entry."""
    id: int
    entity_id: int
    activity_type: str
    details: Optional[str]
    timestamp: datetime.datetime

    class Config:
        from_attributes = True

class FalkorDBServiceEntityResponse(FalkorDBServiceEntityBase):
    """Pydantic schema for responding with a FalkorDBServiceEntity."""
    id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime
    activities: List[FalkorDBServiceActivityLogResponse] = Field([], description="List of recent activities for this entity.")

    class Config:
        from_attributes = True
