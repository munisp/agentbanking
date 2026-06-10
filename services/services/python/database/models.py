import datetime
from typing import List, Optional

from pydantic import BaseModel as PydanticBaseModel
from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Text, Index
from sqlalchemy.orm import relationship, declarative_base, Session
from sqlalchemy.sql import func

# --- SQLAlchemy Base Setup ---
Base = declarative_base()

# --- SQLAlchemy Models ---

class DatabaseItem(Base):
    """
    Represents a generic item managed by the database service.
    """
    __tablename__ = "database_items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    value = Column(Float, default=0.0)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # Relationship to ActivityLog
    activity_logs = relationship("ActivityLog", back_populates="item", cascade="all, delete-orphan")

    # Constraint to ensure name is unique
    __table_args__ = (
        Index('ix_database_items_name_lower', func.lower(name)),
    )

    def __repr__(self):
        return f"<DatabaseItem(id={self.id}, name='{self.name}')>"

class ActivityLog(Base):
    """
    Represents an activity log entry related to a DatabaseItem.
    """
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("database_items.id"), nullable=False, index=True)
    action = Column(String(100), nullable=False)  # e.g., 'CREATE', 'UPDATE', 'DELETE'
    details = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=func.now(), nullable=False, index=True)

    # Relationship back to DatabaseItem
    item = relationship("DatabaseItem", back_populates="activity_logs")

    def __repr__(self):
        return f"<ActivityLog(id={self.id}, action='{self.action}', item_id={self.item_id})>"

# --- Pydantic Schemas ---

class BaseModel(PydanticBaseModel):
    """Base Pydantic model for common configuration."""
    class Config:
        from_attributes = True  # Use orm_mode = True for Pydantic v1, from_attributes = True for Pydantic v2

class DatabaseItemBase(BaseModel):
    """Base schema for DatabaseItem."""
    name: str
    description: Optional[str] = None
    value: Optional[float] = 0.0

class DatabaseItemCreate(DatabaseItemBase):
    """Schema for creating a new DatabaseItem."""
    pass

class DatabaseItemUpdate(DatabaseItemBase):
    """Schema for updating an existing DatabaseItem."""
    name: Optional[str] = None
    description: Optional[str] = None
    value: Optional[float] = None

class ActivityLogResponse(BaseModel):
    """Response schema for ActivityLog."""
    id: int
    item_id: int
    action: str
    details: Optional[str] = None
    timestamp: datetime.datetime

class DatabaseItemResponse(DatabaseItemBase):
    """Response schema for DatabaseItem, including read-only fields."""
    id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime
    
    # Optional field to include logs in the response
    activity_logs: List[ActivityLogResponse] = []

# --- Database Initialization Function ---

def init_db(engine):
    """
    Initializes the database by creating all defined tables.
    """
    Base.metadata.create_all(bind=engine)

# Helper functions for CRUD operations (optional, but good practice)

def get_item(db: Session, item_id: int) -> Optional[DatabaseItem]:
    """Retrieve a single DatabaseItem by ID."""
    return db.query(DatabaseItem).filter(DatabaseItem.id == item_id).first()

def get_items(db: Session, skip: int = 0, limit: int = 100) -> List[DatabaseItem]:
    """Retrieve a list of DatabaseItems."""
    return db.query(DatabaseItem).offset(skip).limit(limit).all()

def create_item(db: Session, item: DatabaseItemCreate) -> DatabaseItem:
    """Create a new DatabaseItem and log the action."""
    db_item = DatabaseItem(**item.model_dump())
    db.add(db_item)
    db.flush() # Flush to get the ID for the log
    
    log_entry = ActivityLog(
        item_id=db_item.id,
        action="CREATE",
        details=f"Item '{db_item.name}' created."
    )
    db.add(log_entry)
    db.commit()
    db.refresh(db_item)
    return db_item

def update_item(db: Session, item_id: int, item: DatabaseItemUpdate) -> Optional[DatabaseItem]:
    """Update an existing DatabaseItem and log the action."""
    db_item = get_item(db, item_id)
    if db_item:
        update_data = item.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_item, key, value)
        
        log_entry = ActivityLog(
            item_id=db_item.id,
            action="UPDATE",
            details=f"Item '{db_item.name}' updated with changes: {list(update_data.keys())}"
        )
        db.add(log_entry)
        db.commit()
        db.refresh(db_item)
    return db_item

def delete_item(db: Session, item_id: int) -> Optional[DatabaseItem]:
    """Delete a DatabaseItem and log the action."""
    db_item = get_item(db, item_id)
    if db_item:
        # Log before deletion, as cascade will remove logs after commit
        log_entry = ActivityLog(
            item_id=db_item.id,
            action="DELETE",
            details=f"Item '{db_item.name}' is being deleted."
        )
        db.add(log_entry)
        db.delete(db_item)
        db.commit()
        return db_item
    return None

def get_item_activity_logs(db: Session, item_id: int, skip: int = 0, limit: int = 100) -> List[ActivityLog]:
    """Retrieve activity logs for a specific DatabaseItem."""
    return db.query(ActivityLog).filter(ActivityLog.item_id == item_id).order_by(ActivityLog.timestamp.desc()).offset(skip).limit(limit).all()

def get_all_activity_logs(db: Session, skip: int = 0, limit: int = 100) -> List[ActivityLog]:
    """Retrieve all activity logs."""
    return db.query(ActivityLog).order_by(ActivityLog.timestamp.desc()).offset(skip).limit(limit).all()
