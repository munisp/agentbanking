from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Index
from sqlalchemy.orm import relationship
from .config import Base

# --- SQLAlchemy Models ---

class VoiceAssistantSession(Base):
    """
    Represents a single voice assistant interaction session.
    """
    __tablename__ = "voice_assistant_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    start_time = Column(DateTime, default=datetime.utcnow, nullable=False)
    end_time = Column(DateTime, nullable=True)
    status = Column(String(50), default="active", nullable=False)  # e.g., 'active', 'completed', 'terminated'
    session_token = Column(String(255), unique=True, index=True, nullable=False)
    model_used = Column(String(100), nullable=True)

    # Relationship to ActivityLog
    activities = relationship("ActivityLog", back_populates="session", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_session_user_status", "user_id", "status"),
    )

class ActivityLog(Base):
    """
    Logs individual interactions or events within a voice assistant session.
    """
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("voice_assistant_sessions.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    activity_type = Column(String(100), nullable=False)  # e.g., 'user_query', 'assistant_response', 'tool_call'
    details = Column(Text, nullable=True)
    
    # Relationship to VoiceAssistantSession
    session = relationship("VoiceAssistantSession", back_populates="activities")

    __table_args__ = (
        Index("idx_activity_session_type", "session_id", "activity_type"),
    )

# --- Pydantic Schemas for VoiceAssistantSession ---

class VoiceAssistantSessionBase(BaseModel):
    """Base schema for a voice assistant session."""
    user_id: int = Field(..., description="ID of the user who initiated the session.")
    status: str = Field("active", description="Current status of the session (e.g., 'active', 'completed').")
    model_used: Optional[str] = Field(None, description="The AI model used for the session.")

class VoiceAssistantSessionCreate(VoiceAssistantSessionBase):
    """Schema for creating a new voice assistant session."""
    session_token: str = Field(..., description="Unique token for the session.")

class VoiceAssistantSessionUpdate(BaseModel):
    """Schema for updating an existing voice assistant session."""
    status: Optional[str] = Field(None, description="New status of the session.")
    end_time: Optional[datetime] = Field(None, description="Timestamp when the session ended.")
    model_used: Optional[str] = Field(None, description="The AI model used for the session.")

class VoiceAssistantSessionResponse(VoiceAssistantSessionBase):
    """Schema for returning a voice assistant session."""
    id: int
    start_time: datetime
    end_time: Optional[datetime] = None
    session_token: str
    
    class Config:
        from_attributes = True

# --- Pydantic Schemas for ActivityLog ---

class ActivityLogBase(BaseModel):
    """Base schema for an activity log entry."""
    activity_type: str = Field(..., description="Type of activity (e.g., 'user_query', 'assistant_response').")
    details: Optional[str] = Field(None, description="Detailed content of the activity.")

class ActivityLogCreate(ActivityLogBase):
    """Schema for creating a new activity log entry."""
    session_id: int = Field(..., description="ID of the session this activity belongs to.")

class ActivityLogResponse(ActivityLogBase):
    """Schema for returning an activity log entry."""
    id: int
    session_id: int
    timestamp: datetime

    class Config:
        from_attributes = True

class VoiceAssistantSessionWithActivities(VoiceAssistantSessionResponse):
    """Schema for returning a voice assistant session including its activities."""
    activities: List[ActivityLogResponse] = []
