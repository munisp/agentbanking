from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, Index
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

# Define the base class for declarative class definitions
Base = declarative_base()

# --- 1. Main Model Table: AnalyticsEvent ---
class AnalyticsEvent(Base):
    """
    Represents a single analytics event, such as a page view, button click, or custom action.
    """
    __tablename__ = "analytics_events"

    # Primary Key and Metadata
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Core Event Data
    event_name = Column(String(128), nullable=False, index=True)
    user_id = Column(String(64), nullable=True, index=True, comment="Identifier for the user who triggered the event")
    session_id = Column(String(64), nullable=True, index=True, comment="Identifier for the user's session")
    
    # Contextual Data
    source_ip = Column(String(45), nullable=True, comment="IP address of the client")
    user_agent = Column(Text, nullable=True, comment="User-Agent string of the client")
    url = Column(Text, nullable=True, comment="URL where the event occurred")
    
    # Custom Properties (using JSONB for flexibility)
    properties = Column(JSONB, nullable=True, comment="Custom key-value properties for the event")

    # Relationship to ActivityLog
    activity_logs = relationship("ActivityLog", back_populates="event", cascade="all, delete-orphan")

    # Indexes and Constraints
    __table_args__ = (
        Index("idx_event_user_time", event_name, user_id, created_at),
    )

    def __repr__(self):
        return f"<AnalyticsEvent(event_name='{self.event_name}', user_id='{self.user_id}', created_at='{self.created_at}')>"

# --- 2. Activity Log Table ---
class ActivityLog(Base):
    """
    Represents a log entry for changes or significant actions related to an AnalyticsEvent.
    While less common for pure analytics, it adheres to the requirement for an activity log table.
    """
    __tablename__ = "analytics_activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(PG_UUID(as_uuid=True), ForeignKey("analytics_events.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    action = Column(String(128), nullable=False, comment="e.g., 'event_created', 'event_processed', 'data_anonymized'")
    details = Column(Text, nullable=True)
    
    # Relationship back to AnalyticsEvent
    event = relationship("AnalyticsEvent", back_populates="activity_logs")

    def __repr__(self):
        return f"<ActivityLog(action='{self.action}', event_id='{self.event_id}', timestamp='{self.timestamp}')>"

# --- 3. Pydantic Schemas ---

# Base Schema for shared attributes
class AnalyticsEventBase(BaseModel):
    """Base schema for analytics event data."""
    event_name: str = Field(..., example="page_view")
    user_id: Optional[str] = Field(None, example="user-12345")
    session_id: Optional[str] = Field(None, example="sess-abcde")
    source_ip: Optional[str] = Field(None, example="192.168.1.1")
    user_agent: Optional[str] = Field(None, example="Mozilla/5.0...")
    url: Optional[str] = Field(None, example="/products/item-a")
    properties: Optional[dict] = Field(None, example={"product_id": 5, "referrer": "google"})

# Schema for creating a new event (input)
class AnalyticsEventCreate(AnalyticsEventBase):
    """Schema for creating a new analytics event."""
    # All fields are inherited and optional for creation, as some might be auto-generated on the server
    pass

# Schema for updating an event (input) - not typically used for analytics events, but included for completeness
class AnalyticsEventUpdate(AnalyticsEventBase):
    """Schema for updating an existing analytics event."""
    event_name: Optional[str] = None # Allow partial updates

# Schema for response (output)
class AnalyticsEventResponse(AnalyticsEventBase):
    """Schema for returning an analytics event."""
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        json_encoders = {
            UUID: str,
            datetime: lambda dt: dt.isoformat(),
        }

# Schema for Activity Log Response
class ActivityLogResponse(BaseModel):
    """Schema for returning an activity log entry."""
    id: int
    event_id: UUID
    timestamp: datetime
    action: str
    details: Optional[str]

    class Config:
        from_attributes = True
        json_encoders = {
            UUID: str,
            datetime: lambda dt: dt.isoformat(),
        }

# Schema for a full event response including logs
class AnalyticsEventFullResponse(AnalyticsEventResponse):
    """Schema for returning an analytics event with its associated activity logs."""
    activity_logs: List[ActivityLogResponse] = []
    
    class Config:
        from_attributes = True
        json_encoders = {
            UUID: str,
            datetime: lambda dt: dt.isoformat(),
        }
