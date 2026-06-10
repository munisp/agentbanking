"""
SQLAlchemy models and Pydantic schemas for the rule-engine service.
"""
from datetime import datetime
from typing import Optional, List

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Index, Boolean, JSON
from sqlalchemy.orm import relationship
from pydantic import BaseModel, Field
from enum import Enum

from .config import Base

# --- Enums ---

class RuleStatus(str, Enum):
    """Possible statuses for a rule."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    DRAFT = "draft"
    ARCHIVED = "archived"

class RuleType(str, Enum):
    """Possible types of rules."""
    SIMPLE = "simple"
    COMPLEX = "complex"
    ML_TRIGGER = "ml_trigger"
    TIME_BASED = "time_based"

# --- SQLAlchemy Models ---

class Rule(Base):
    """
    Represents a single rule in the rule engine.
    """
    __tablename__ = "rules"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, index=True, nullable=False, doc="Identifier for the tenant/client.")
    
    name = Column(String, unique=True, index=True, nullable=False, doc="Unique name for the rule.")
    description = Column(Text, nullable=True, doc="Detailed description of the rule's purpose.")
    
    rule_type = Column(String, default=RuleType.SIMPLE.value, nullable=False, doc="Type of the rule (e.g., simple, complex, ml_trigger).")
    status = Column(String, default=RuleStatus.DRAFT.value, nullable=False, doc="Current status of the rule (e.g., active, inactive, draft).")
    
    priority = Column(Integer, default=100, index=True, nullable=False, doc="Execution priority, lower number means higher priority.")
    is_enabled = Column(Boolean, default=True, nullable=False, doc="Flag to quickly enable/disable the rule.")
    
    condition_json = Column(JSON, nullable=False, doc="JSON structure defining the rule's condition logic.")
    action_json = Column(JSON, nullable=False, doc="JSON structure defining the action to execute when the rule fires.")
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationship to ActivityLog
    activity_logs = relationship("ActivityLog", back_populates="rule")

    __table_args__ = (
        # Ensure a tenant cannot have two rules with the same name
        Index('ix_tenant_rule_name', tenant_id, name, unique=True),
    )

class ActivityLog(Base):
    """
    Logs significant activities related to rules, such as creation, update, or execution.
    """
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    rule_id = Column(Integer, ForeignKey("rules.id"), index=True, nullable=False)
    
    timestamp = Column(DateTime, default=datetime.utcnow, index=True, nullable=False)
    activity_type = Column(String, nullable=False, doc="Type of activity (e.g., 'RULE_CREATED', 'RULE_UPDATED', 'RULE_FIRED').")
    details = Column(JSON, nullable=True, doc="JSON payload with specific details about the activity.")
    user_id = Column(String, nullable=True, doc="ID of the user who performed the action, if applicable.")

    # Relationship back to Rule
    rule = relationship("Rule", back_populates="activity_logs")

# --- Pydantic Schemas ---

# Base Schemas
class RuleBase(BaseModel):
    """Base schema for Rule, containing common fields."""
    tenant_id: str = Field(..., description="Identifier for the tenant/client.")
    name: str = Field(..., description="Unique name for the rule.")
    description: Optional[str] = Field(None, description="Detailed description of the rule's purpose.")
    rule_type: RuleType = Field(RuleType.SIMPLE, description="Type of the rule.")
    status: RuleStatus = Field(RuleStatus.DRAFT, description="Current status of the rule.")
    priority: int = Field(100, ge=1, le=1000, description="Execution priority (1 is highest).")
    is_enabled: bool = Field(True, description="Flag to quickly enable/disable the rule.")
    condition_json: dict = Field(..., description="JSON structure defining the rule's condition logic.")
    action_json: dict = Field(..., description="JSON structure defining the action to execute.")

class ActivityLogBase(BaseModel):
    """Base schema for ActivityLog."""
    activity_type: str = Field(..., description="Type of activity (e.g., 'RULE_CREATED', 'RULE_UPDATED').")
    details: Optional[dict] = Field(None, description="JSON payload with specific details about the activity.")
    user_id: Optional[str] = Field(None, description="ID of the user who performed the action.")

# Create Schemas
class RuleCreate(RuleBase):
    """Schema for creating a new Rule."""
    pass

class ActivityLogCreate(ActivityLogBase):
    """Schema for creating a new ActivityLog entry."""
    rule_id: int = Field(..., description="ID of the rule associated with the activity.")

# Update Schemas
class RuleUpdate(BaseModel):
    """Schema for updating an existing Rule. All fields are optional."""
    name: Optional[str] = Field(None, description="Unique name for the rule.")
    description: Optional[str] = Field(None, description="Detailed description of the rule's purpose.")
    rule_type: Optional[RuleType] = Field(None, description="Type of the rule.")
    status: Optional[RuleStatus] = Field(None, description="Current status of the rule.")
    priority: Optional[int] = Field(None, ge=1, le=1000, description="Execution priority (1 is highest).")
    is_enabled: Optional[bool] = Field(None, description="Flag to quickly enable/disable the rule.")
    condition_json: Optional[dict] = Field(None, description="JSON structure defining the rule's condition logic.")
    action_json: Optional[dict] = Field(None, description="JSON structure defining the action to execute.")

# Response Schemas
class RuleResponse(RuleBase):
    """Schema for returning a Rule, including database-generated fields."""
    id: int = Field(..., description="The unique ID of the rule.")
    created_at: datetime
    updated_at: datetime

    class Config:
        """Pydantic configuration to enable ORM mode."""
        from_attributes = True

class ActivityLogResponse(ActivityLogBase):
    """Schema for returning an ActivityLog entry."""
    id: int
    rule_id: int
    timestamp: datetime

    class Config:
        """Pydantic configuration to enable ORM mode."""
        from_attributes = True

class RuleWithLogsResponse(RuleResponse):
    """Schema for returning a Rule along with its activity logs."""
    activity_logs: List[ActivityLogResponse] = []
    
    class Config:
        """Pydantic configuration to enable ORM mode."""
        from_attributes = True
