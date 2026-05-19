from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, DateTime, func, Index, BigInteger
from sqlalchemy.orm import relationship
from pydantic import BaseModel, Field
from config import Base

# --- SQLAlchemy Models ---

class TikTokPost(Base):
    """
    SQLAlchemy model for a TikTok video post.
    """
    __tablename__ = "tiktok_posts"

    id = Column(Integer, primary_key=True, index=True)
    tiktok_id = Column(String, unique=True, nullable=False, index=True, doc="Unique ID of the post on TikTok")
    user_handle = Column(String, nullable=False, index=True, doc="The handle of the user who posted the video")
    caption = Column(String, nullable=True, doc="The caption or description of the video")
    
    # Engagement metrics
    views_count = Column(BigInteger, default=0, nullable=False, doc="Number of views")
    likes_count = Column(BigInteger, default=0, nullable=False, doc="Number of likes")
    comments_count = Column(BigInteger, default=0, nullable=False, doc="Number of comments")
    shares_count = Column(BigInteger, default=0, nullable=False, doc="Number of shares")

    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False, doc="Timestamp of record creation")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False, doc="Timestamp of last update")

    # Relationship to ActivityLog
    activity_logs = relationship("ActivityLog", back_populates="post")

    __table_args__ = (
        # Index for fast lookups by user handle and TikTok ID
        Index("ix_post_user_tiktok", user_handle, tiktok_id),
    )

class ActivityLog(Base):
    """
    SQLAlchemy model for logging activities related to TikTok posts.
    """
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, nullable=False, index=True, doc="Foreign key to the TikTokPost")
    activity_type = Column(String, nullable=False, doc="Type of activity (e.g., 'CREATE', 'UPDATE', 'DELETE', 'METRICS_REFRESH')")
    details = Column(String, nullable=True, doc="JSON string or simple text detailing the change")
    timestamp = Column(DateTime, default=func.now(), nullable=False, index=True, doc="Timestamp of the activity")

    # Relationship to TikTokPost
    post = relationship("TikTokPost", back_populates="activity_logs")

# --- Pydantic Schemas ---

class TikTokPostBase(BaseModel):
    """Base schema for TikTokPost, containing common fields."""
    tiktok_id: str = Field(..., description="Unique ID of the post on TikTok.")
    user_handle: str = Field(..., description="The handle of the user who posted the video.")
    caption: Optional[str] = Field(None, description="The caption or description of the video.")

class TikTokPostCreate(TikTokPostBase):
    """Schema for creating a new TikTokPost."""
    # No additional fields needed for creation beyond the base
    pass

class TikTokPostUpdate(BaseModel):
    """Schema for updating an existing TikTokPost."""
    caption: Optional[str] = Field(None, description="The new caption or description of the video.")
    views_count: Optional[int] = Field(None, ge=0, description="New number of views.")
    likes_count: Optional[int] = Field(None, ge=0, description="New number of likes.")
    comments_count: Optional[int] = Field(None, ge=0, description="New number of comments.")
    shares_count: Optional[int] = Field(None, ge=0, description="New number of shares.")

class TikTokPostResponse(TikTokPostBase):
    """Schema for returning a TikTokPost."""
    id: int = Field(..., description="Database primary key ID.")
    views_count: int = Field(..., ge=0, description="Number of views.")
    likes_count: int = Field(..., ge=0, description="Number of likes.")
    comments_count: int = Field(..., ge=0, description="Number of comments.")
    shares_count: int = Field(..., ge=0, description="Number of shares.")
    created_at: datetime = Field(..., description="Timestamp of record creation.")
    updated_at: datetime = Field(..., description="Timestamp of last update.")

    class Config:
        from_attributes = True

class ActivityLogResponse(BaseModel):
    """Schema for returning an ActivityLog entry."""
    id: int = Field(..., description="Database primary key ID.")
    post_id: int = Field(..., description="ID of the related TikTokPost.")
    activity_type: str = Field(..., description="Type of activity (e.g., 'CREATE', 'UPDATE').")
    details: Optional[str] = Field(None, description="Details of the activity.")
    timestamp: datetime = Field(..., description="Timestamp of the activity.")

    class Config:
        from_attributes = True
