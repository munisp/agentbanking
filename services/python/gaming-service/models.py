from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, Integer, String, Text, ForeignKey, Index, func
from sqlalchemy.orm import relationship, declarative_base

# --- SQLAlchemy Base ---
Base = declarative_base()

# --- SQLAlchemy Models ---

class GameSession(Base):
    """
    Represents a single gaming session.
    """
    __tablename__ = "game_sessions"

    id = Column(UUID, primary_key=True, default=uuid4)
    user_id = Column(UUID, nullable=False, index=True)
    game_title = Column(String(255), nullable=False)
    score = Column(Integer, default=0)
    start_time = Column(DateTime, default=datetime.utcnow, index=True)
    end_time = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, default=0)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship to ActivityLog
    logs = relationship("ActivityLog", back_populates="session", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_user_game_session", "user_id", "game_title"),
    )

class ActivityLog(Base):
    """
    Represents an activity log entry for a game session.
    """
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(UUID, ForeignKey("game_sessions.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    activity_type = Column(String(50), nullable=False) # e.g., "ACHIEVEMENT_UNLOCKED", "LEVEL_UP", "PURCHASE"
    details = Column(Text, nullable=True)

    # Relationship to GameSession
    session = relationship("GameSession", back_populates="logs")

# --- Pydantic Schemas ---

# Base Schemas
class GameSessionBase(BaseModel):
    """Base schema for a game session."""
    user_id: UUID = Field(..., description="The ID of the user who played the session.")
    game_title: str = Field(..., max_length=255, description="The title of the game played.")

class ActivityLogBase(BaseModel):
    """Base schema for an activity log entry."""
    activity_type: str = Field(..., max_length=50, description="Type of activity (e.g., 'LEVEL_UP').")
    details: Optional[str] = Field(None, description="Detailed description of the activity.")

# Create Schemas
class GameSessionCreate(GameSessionBase):
    """Schema for creating a new game session."""
    # start_time is set by the server by default, but can be provided
    start_time: Optional[datetime] = Field(None, description="The start time of the session. Defaults to now.")

class ActivityLogCreate(ActivityLogBase):
    """Schema for creating a new activity log entry."""
    pass

# Update Schemas
class GameSessionUpdate(BaseModel):
    """Schema for updating an existing game session."""
    score: Optional[int] = Field(None, ge=0, description="The final score of the session.")
    end_time: Optional[datetime] = Field(None, description="The end time of the session.")
    duration_seconds: Optional[int] = Field(None, ge=0, description="The duration of the session in seconds.")
    game_title: Optional[str] = Field(None, max_length=255, description="The title of the game played.")

# Response Schemas
class ActivityLogResponse(ActivityLogBase):
    """Response schema for an activity log entry."""
    id: int
    session_id: UUID
    timestamp: datetime

    model_config = SettingsConfigDict(from_attributes=True)

class GameSessionResponse(GameSessionBase):
    """Response schema for a game session."""
    id: UUID
    score: int
    start_time: datetime
    end_time: Optional[datetime]
    duration_seconds: int
    created_at: datetime
    updated_at: datetime
    
    # Nested logs
    logs: List[ActivityLogResponse] = []

    model_config = SettingsConfigDict(from_attributes=True)

# Pydantic Settings for model_config
from pydantic_settings import SettingsConfigDict
GameSessionResponse.model_config = SettingsConfigDict(from_attributes=True)
ActivityLogResponse.model_config = SettingsConfigDict(from_attributes=True)
