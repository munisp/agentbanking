import datetime
from typing import List, Optional

from pydantic import BaseModel as PydanticBaseModel
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Boolean,
    Index,
)
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

# --- SQLAlchemy Setup ---
Base = declarative_base()

# --- Database Models ---

class HierarchyNode(Base):
    """
    Represents a node in the organizational or logical hierarchy.
    Uses a self-referential relationship to establish parent-child links.
    """
    __tablename__ = "hierarchy_nodes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    node_type = Column(String(50), nullable=False, default="Generic")
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Self-referential relationship for hierarchy
    parent_id = Column(Integer, ForeignKey("hierarchy_nodes.id"), nullable=True, index=True)
    
    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    parent = relationship(
        "HierarchyNode", remote_side=[id], backref="children", uselist=False
    )
    
    # Activity Log relationship
    activities = relationship("HierarchyActivityLog", back_populates="node")

    __table_args__ = (
        Index("ix_hierarchy_node_name_type", "name", "node_type"),
    )

    def __repr__(self):
        return f"<HierarchyNode(id={self.id}, name='{self.name}', parent_id={self.parent_id})>"


class HierarchyActivityLog(Base):
    """
    Logs all significant activities related to a HierarchyNode.
    """
    __tablename__ = "hierarchy_activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    node_id = Column(Integer, ForeignKey("hierarchy_nodes.id"), nullable=False, index=True)
    action = Column(String(100), nullable=False)  # e.g., 'CREATE', 'UPDATE', 'DELETE', 'MOVE'
    details = Column(Text, nullable=True)
    user_id = Column(String(50), nullable=True)  # ID of the user who performed the action
    
    # Timestamps
    timestamp = Column(DateTime, default=func.now(), nullable=False, index=True)

    # Relationships
    node = relationship("HierarchyNode", back_populates="activities")

    def __repr__(self):
        return f"<HierarchyActivityLog(id={self.id}, node_id={self.node_id}, action='{self.action}')>"


# --- Pydantic Schemas ---

class BaseModel(PydanticBaseModel):
    """Base Pydantic model configuration."""
    class Config:
        from_attributes = True
        json_encoders = {
            datetime.datetime: lambda dt: dt.isoformat(),
        }

# HierarchyNode Schemas

class HierarchyNodeBase(BaseModel):
    """Base schema for a hierarchy node."""
    name: str
    description: Optional[str] = None
    node_type: str
    is_active: Optional[bool] = True
    parent_id: Optional[int] = None

class HierarchyNodeCreate(HierarchyNodeBase):
    """Schema for creating a new hierarchy node."""
    pass

class HierarchyNodeUpdate(HierarchyNodeBase):
    """Schema for updating an existing hierarchy node."""
    name: Optional[str] = None
    node_type: Optional[str] = None

class HierarchyNodeResponse(HierarchyNodeBase):
    """Schema for responding with a hierarchy node."""
    id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime
    
    # Nested children for simple tree representation
    children: List["HierarchyNodeResponse"] = []

# Activity Log Schemas

class HierarchyActivityLogResponse(BaseModel):
    """Schema for responding with an activity log entry."""
    id: int
    node_id: int
    action: str
    details: Optional[str] = None
    user_id: Optional[str] = None
    timestamp: datetime.datetime

# Update the forward reference for the recursive schema
HierarchyNodeResponse.model_rebuild()

# Business-specific Schemas

class HierarchyMove(BaseModel):
    """Schema for moving a node to a new parent."""
    new_parent_id: Optional[int] = None
    user_id: Optional[str] = "system"

class HierarchyTreeResponse(BaseModel):
    """Schema for a full tree response, where the root is a single node."""
    root: HierarchyNodeResponse
