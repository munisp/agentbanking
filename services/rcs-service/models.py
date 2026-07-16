from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field
from sqlalchemy import (
    Column, Integer, String, DateTime, Boolean, ForeignKey, Text, Index
)
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func

# --- SQLAlchemy Base ---
Base = declarative_base()

# --- SQLAlchemy Models ---

class RCSCampaign(Base):
    """
    SQLAlchemy model for an RCS Campaign.
    """
    __tablename__ = "rcs_campaigns"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    status = Column(String(50), default="draft", nullable=False) # e.g., 'draft', 'active', 'paused', 'completed'
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    template_id = Column(String(255), nullable=False, comment="External ID for the RCS template used")
    target_audience = Column(Text, nullable=True, comment="JSON or text describing the target audience criteria")
    is_archived = Column(Boolean, default=False, nullable=False)
    
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    activity_logs = relationship("RCSCampaignActivityLog", back_populates="campaign", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_rcs_campaigns_status_archived", "status", "is_archived"),
    )

class RCSCampaignActivityLog(Base):
    """
    SQLAlchemy model for logging activities related to an RCS Campaign.
    """
    __tablename__ = "rcs_campaign_activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("rcs_campaigns.id"), nullable=False)
    
    timestamp = Column(DateTime, server_default=func.now(), nullable=False, index=True)
    activity_type = Column(String(100), nullable=False) # e.g., 'created', 'updated', 'status_change', 'sent'
    details = Column(Text, nullable=True)
    user_id = Column(String(100), nullable=True, comment="ID of the user who performed the action")

    # Relationships
    campaign = relationship("RCSCampaign", back_populates="activity_logs")

    __table_args__ = (
        Index("ix_rcs_activity_campaign_type", "campaign_id", "activity_type"),
    )

# --- Pydantic Schemas ---

# Base Schema
class RCSCampaignBase(BaseModel):
    """Base Pydantic schema for RCS Campaign."""
    name: str = Field(..., max_length=255, description="Unique name for the RCS campaign.")
    status: str = Field("draft", max_length=50, description="Current status of the campaign (e.g., 'draft', 'active').")
    start_date: Optional[datetime] = Field(None, description="The date and time the campaign is scheduled to start.")
    end_date: Optional[datetime] = Field(None, description="The date and time the campaign is scheduled to end.")
    template_id: str = Field(..., max_length=255, description="External ID of the RCS message template to be used.")
    target_audience: Optional[str] = Field(None, description="Criteria defining the target audience (e.g., JSON string).")
    is_archived: bool = Field(False, description="Flag to indicate if the campaign is archived.")

# Schema for creating a new campaign
class RCSCampaignCreate(RCSCampaignBase):
    """Pydantic schema for creating a new RCS Campaign."""
    # name is required and will be checked for uniqueness in the router
    pass

# Schema for updating an existing campaign
class RCSCampaignUpdate(RCSCampaignBase):
    """Pydantic schema for updating an existing RCS Campaign."""
    name: Optional[str] = Field(None, max_length=255, description="Unique name for the RCS campaign.")
    status: Optional[str] = Field(None, max_length=50, description="Current status of the campaign (e.g., 'draft', 'active').")
    template_id: Optional[str] = Field(None, max_length=255, description="External ID of the RCS message template to be used.")
    # All fields are optional for update

# Schema for activity log response
class RCSCampaignActivityLogResponse(BaseModel):
    """Pydantic schema for an RCS Campaign Activity Log entry."""
    id: int
    campaign_id: int
    timestamp: datetime
    activity_type: str
    details: Optional[str]
    user_id: Optional[str]

    class Config:
        from_attributes = True

# Schema for campaign response (includes read-only fields)
class RCSCampaignResponse(RCSCampaignBase):
    """Pydantic schema for returning an RCS Campaign."""
    id: int
    created_at: datetime
    updated_at: datetime
    
    # Optional field to include logs in the response
    activity_logs: List[RCSCampaignActivityLogResponse] = Field([], description="List of recent activity logs for the campaign.")

    class Config:
        from_attributes = True
