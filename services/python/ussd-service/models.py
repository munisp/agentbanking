import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field
from sqlalchemy import Column, String, DateTime, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, DeclarativeBase
from sqlalchemy.sql import func

# --- SQLAlchemy Base ---

class Base(DeclarativeBase):
    """Base class which provides automated table name
    and default primary key field.
    """
    pass

# --- SQLAlchemy Models ---

class UssdSession(Base):
    """
    Represents an active or completed USSD session.
    """
    __tablename__ = "ussd_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    session_id = Column(String, unique=True, nullable=False, index=True, doc="Unique ID from the USSD gateway.")
    phone_number = Column(String, nullable=False, index=True, doc="The user's phone number.")
    service_code = Column(String, nullable=False, doc="The USSD code dialed (e.g., *123#).")
    current_menu_level = Column(String, nullable=False, default="MAIN_MENU", doc="The current state/menu the user is in.")
    last_input = Column(String, nullable=True, doc="The last input received from the user.")
    session_data = Column(JSONB, nullable=False, default={}, doc="Stores arbitrary session data.")
    status = Column(String, nullable=False, default="ACTIVE", doc="Session status (e.g., 'ACTIVE', 'COMPLETED', 'CANCELED').")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), default=func.now())

    # Relationship
    logs = relationship("UssdSessionLog", back_populates="session", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<UssdSession(session_id='{self.session_id}', phone_number='{self.phone_number}', status='{self.status}')>"

class UssdSessionLog(Base):
    """
    Activity log for a specific USSD session.
    """
    __tablename__ = "ussd_session_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey("ussd_sessions.id"), nullable=False, index=True)
    log_type = Column(String, nullable=False, doc="Type of log (e.g., 'REQUEST', 'RESPONSE', 'ERROR').")
    message = Column(Text, nullable=False, doc="A description of the activity.")
    details = Column(JSONB, nullable=False, default={}, doc="Detailed payload of the request/response.")
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationship
    session = relationship("UssdSession", back_populates="logs")

    __table_args__ = (
        Index("idx_session_log_type_timestamp", session_id, log_type, timestamp.desc()),
    )

    def __repr__(self):
        return f"<UssdSessionLog(session_id='{self.session_id}', type='{self.log_type}', timestamp='{self.timestamp}')>"

# --- Pydantic Schemas ---

# Shared Schemas
class UssdSessionBase(BaseModel):
    """Base schema for USSD session data."""
    phone_number: str = Field(..., description="The user's phone number.")
    service_code: str = Field(..., description="The USSD code dialed (e.g., *123#).")
    current_menu_level: str = Field("MAIN_MENU", description="The current state/menu the user is in.")
    last_input: Optional[str] = Field(None, description="The last input received from the user.")
    session_data: dict = Field({}, description="Stores arbitrary session data.")
    status: str = Field("ACTIVE", description="Session status (e.g., 'ACTIVE', 'COMPLETED', 'CANCELED').")

# UssdSession Schemas
class UssdSessionCreate(UssdSessionBase):
    """Schema for creating a new USSD session."""
    session_id: str = Field(..., description="Unique ID from the USSD gateway.")

class UssdSessionUpdate(BaseModel):
    """Schema for updating an existing USSD session."""
    current_menu_level: Optional[str] = None
    last_input: Optional[str] = None
    session_data: Optional[dict] = None
    status: Optional[str] = None

class UssdSessionResponse(UssdSessionBase):
    """Schema for returning a USSD session."""
    id: uuid.UUID
    session_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# UssdSessionLog Schemas
class UssdSessionLogResponse(BaseModel):
    """Schema for returning a USSD session log entry."""
    id: uuid.UUID
    session_id: uuid.UUID
    log_type: str = Field(..., description="Type of log (e.g., 'REQUEST', 'RESPONSE', 'ERROR').")
    message: str = Field(..., description="A description of the activity.")
    details: dict = Field({}, description="Detailed payload of the request/response.")
    timestamp: datetime

    class Config:
        from_attributes = True

# USSD Gateway Interaction Schemas (Business-specific)
class UssdCallbackRequest(BaseModel):
    """Schema for the incoming request from the USSD gateway."""
    session_id: str = Field(..., description="Unique ID for the USSD session.")
    service_code: str = Field(..., description="The USSD code dialed.")
    phone_number: str = Field(..., description="The user's phone number.")
    text: str = Field("", description="The user's input. Empty for a new session.")

class UssdCallbackResponse(BaseModel):
    """Schema for the response sent back to the USSD gateway."""
    session_id: str = Field(..., description="Unique ID for the USSD session.")
    response_text: str = Field(..., description="The text to display to the user.")
    session_status: str = Field(..., description="The status of the session: 'CON' (Continue) or 'END' (End).")
    
    # Custom field for the service to process the response
    # This is not strictly required by all gateways but is good practice for internal tracking
    internal_status: str = Field(..., description="Internal status of the session (e.g., 'ACTIVE', 'COMPLETED').")
