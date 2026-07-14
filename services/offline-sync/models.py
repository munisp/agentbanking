from datetime import datetime
from typing import List, Optional

from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey, Index, JSON
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from pydantic import BaseModel, Field

# --- SQLAlchemy Base ---

class Base(DeclarativeBase):
    """Base class which provides automated table name
    and common columns."""
    pass

# --- SQLAlchemy Models ---

class OfflineSyncRecord(Base):
    """
    Represents a record of data pending synchronization in an offline-first system.
    """
    __tablename__ = "offline_sync_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # Identifier for the user or device that created the record
    user_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    
    # The type of entity being synchronized (e.g., 'order', 'customer', 'inventory')
    entity_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    
    # The unique identifier of the entity in the main system (can be null if it's a new creation)
    entity_id: Mapped[Optional[str]] = mapped_column(String(255), index=True, nullable=True)
    
    # The operation type: 'CREATE', 'UPDATE', 'DELETE'
    operation: Mapped[str] = mapped_column(String(10), nullable=False)
    
    # The actual data payload to be synchronized (JSON field)
    data_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    
    # Current status of the record: 'PENDING', 'IN_PROGRESS', 'SUCCESS', 'FAILED'
    status: Mapped[str] = mapped_column(String(20), default="PENDING", index=True, nullable=False)
    
    # Timestamp when the record was created
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Timestamp of the last update
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Number of times synchronization has been attempted
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # Relationship to the activity log
    activities: Mapped[List["SyncActivityLog"]] = relationship(back_populates="sync_record", cascade="all, delete-orphan")

    __table_args__ = (
        # Composite index for efficient querying of pending syncs for a specific entity type
        Index("idx_sync_entity_status", entity_type, status),
    )

class SyncActivityLog(Base):
    """
    Logs synchronization attempts and outcomes for an OfflineSyncRecord.
    """
    __tablename__ = "sync_activity_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # Foreign key to the OfflineSyncRecord
    sync_record_id: Mapped[int] = mapped_column(Integer, ForeignKey("offline_sync_records.id"), index=True, nullable=False)
    
    # The outcome of the attempt: 'ATTEMPTED', 'SUCCESS', 'FAILURE'
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    
    # Detailed message about the attempt or error
    message: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Timestamp of the activity
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationship back to the sync record
    sync_record: Mapped["OfflineSyncRecord"] = relationship(back_populates="activities")

# --- Pydantic Schemas (Base) ---

class OfflineSyncRecordBase(BaseModel):
    """Base schema for OfflineSyncRecord."""
    user_id: int = Field(..., description="ID of the user or device that created the record.")
    entity_type: str = Field(..., max_length=50, description="The type of entity being synchronized (e.g., 'order').")
    entity_id: Optional[str] = Field(None, max_length=255, description="The unique identifier of the entity in the main system.")
    operation: str = Field(..., max_length=10, description="The operation type: 'CREATE', 'UPDATE', 'DELETE'.")
    data_payload: dict = Field(..., description="The actual data payload to be synchronized.")

class SyncActivityLogBase(BaseModel):
    """Base schema for SyncActivityLog."""
    outcome: str = Field(..., max_length=20, description="The outcome of the attempt: 'ATTEMPTED', 'SUCCESS', 'FAILURE'.")
    message: str = Field(..., description="Detailed message about the attempt or error.")

# --- Pydantic Schemas (Create) ---

class OfflineSyncRecordCreate(OfflineSyncRecordBase):
    """Schema for creating a new OfflineSyncRecord."""
    pass

class SyncActivityLogCreate(SyncActivityLogBase):
    """Schema for creating a new SyncActivityLog."""
    sync_record_id: int = Field(..., description="ID of the associated OfflineSyncRecord.")

# --- Pydantic Schemas (Update) ---

class OfflineSyncRecordUpdate(BaseModel):
    """Schema for updating an existing OfflineSyncRecord."""
    status: Optional[str] = Field(None, max_length=20, description="New status of the record: 'PENDING', 'IN_PROGRESS', 'SUCCESS', 'FAILED'.")
    attempt_count: Optional[int] = Field(None, ge=0, description="New attempt count.")
    data_payload: Optional[dict] = Field(None, description="Updated data payload.")

# --- Pydantic Schemas (Response) ---

class SyncActivityLogResponse(SyncActivityLogBase):
    """Response schema for SyncActivityLog."""
    id: int
    sync_record_id: int
    timestamp: datetime

    class Config:
        from_attributes = True

class OfflineSyncRecordResponse(OfflineSyncRecordBase):
    """Response schema for OfflineSyncRecord."""
    id: int
    status: str
    created_at: datetime
    updated_at: datetime
    attempt_count: int
    activities: List[SyncActivityLogResponse] = Field(default_factory=list, description="List of synchronization activities.")

    class Config:
        from_attributes = True

# --- Utility for Database Initialization ---

def init_db(engine):
    """Initializes the database by creating all tables."""
    Base.metadata.create_all(bind=engine)

# Export for use in other modules
__all__ = [
    "Base", 
    "OfflineSyncRecord", 
    "SyncActivityLog", 
    "OfflineSyncRecordCreate", 
    "OfflineSyncRecordUpdate", 
    "OfflineSyncRecordResponse", 
    "SyncActivityLogCreate", 
    "SyncActivityLogResponse",
    "init_db"
]
