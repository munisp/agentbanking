import enum
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Enum, ForeignKey, Index, text
)
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.ext.declarative import declared_attr

# --- SQLAlchemy Setup ---

class Base:
    """Base class which provides automated table name and primary key column."""
    
    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower() + "s"

    id = Column(Integer, primary_key=True, index=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

Base = declarative_base(cls=Base)

# --- Enums ---

class TranslationStatus(enum.Enum):
    """Status of a translation request."""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class LogLevel(enum.Enum):
    """Log level for activity logging."""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    DEBUG = "DEBUG"

# --- Database Models ---

class TranslationRequest(Base):
    """
    Represents a request for translation.
    """
    __tablename__ = "translation_requests"
    
    source_text = Column(Text, nullable=False, doc="The original text to be translated.")
    source_language = Column(String(10), nullable=False, index=True, doc="The source language code (e.g., 'en').")
    target_language = Column(String(10), nullable=False, index=True, doc="The target language code (e.g., 'es').")
    
    translated_text = Column(Text, nullable=True, doc="The resulting translated text.")
    status = Column(Enum(TranslationStatus), default=TranslationStatus.PENDING, nullable=False, index=True, doc="The current status of the translation request.")
    
    # Relationships
    activity_logs = relationship("ActivityLog", back_populates="request", cascade="all, delete-orphan")
    
    # Constraints and Indexes
    __table_args__ = (
        Index("ix_translation_request_lang_pair", "source_language", "target_language"),
    )

class ActivityLog(Base):
    """
    Represents an activity log entry for a specific translation request.
    """
    __tablename__ = "activity_logs"
    
    level = Column(Enum(LogLevel), default=LogLevel.INFO, nullable=False, doc="The severity level of the log entry.")
    message = Column(String(512), nullable=False, doc="A brief description of the activity.")
    details = Column(Text, nullable=True, doc="Detailed information about the activity.")
    
    # Foreign Key
    request_id = Column(Integer, ForeignKey("translation_requests.id"), nullable=False, index=True)
    
    # Relationships
    request = relationship("TranslationRequest", back_populates="activity_logs")

# --- Pydantic Schemas ---

# Shared Schemas
class TranslationRequestBase(BaseModel):
    """Base schema for translation request data."""
    source_text: str = Field(..., description="The original text to be translated.")
    source_language: str = Field(..., max_length=10, description="The source language code (e.g., 'en').")
    target_language: str = Field(..., max_length=10, description="The target language code (e.g., 'es').")

# Create Schema
class TranslationRequestCreate(TranslationRequestBase):
    """Schema for creating a new translation request."""
    pass

# Update Schema
class TranslationRequestUpdate(BaseModel):
    """Schema for updating an existing translation request."""
    source_text: Optional[str] = Field(None, description="The original text to be translated.")
    source_language: Optional[str] = Field(None, max_length=10, description="The source language code (e.g., 'en').")
    target_language: Optional[str] = Field(None, max_length=10, description="The target language code (e.g., 'es').")
    translated_text: Optional[str] = Field(None, description="The resulting translated text.")
    status: Optional[TranslationStatus] = Field(None, description="The current status of the translation request.")

# Activity Log Schemas
class ActivityLogResponse(BaseModel):
    """Response schema for an activity log entry."""
    id: int
    level: LogLevel
    message: str
    details: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

# Response Schema
class TranslationRequestResponse(TranslationRequestBase):
    """Response schema for a translation request."""
    id: int
    translated_text: Optional[str] = None
    status: TranslationStatus
    created_at: datetime
    updated_at: datetime
    
    activity_logs: List[ActivityLogResponse] = Field(default_factory=list, description="List of activity logs for this request.")
    
    class Config:
        from_attributes = True

# Utility to create all tables (used for initial setup)
def create_all_tables(engine):
    """Creates all defined tables in the database."""
    Base.metadata.create_all(bind=engine)
