from datetime import datetime
from typing import List, Optional
from uuid import uuid4, UUID

from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Integer, Boolean, Numeric, Index
from sqlalchemy.orm import relationship, DeclarativeBase
from pydantic import BaseModel, Field

# --- Base Model for SQLAlchemy ---

class Base(DeclarativeBase):
    """Base class which provides automated table name and default primary key column."""
    pass

# --- SQLAlchemy Models ---

class LedgerAccount(Base):
    """
    Represents a Ledger Account managed by the tigerbeetle-zig service.
    This model is designed to store core account information for a double-entry accounting system.
    """
    __tablename__ = "ledger_accounts"

    id = Column(UUID, primary_key=True, default=uuid4, index=True)
    account_id = Column(String(255), unique=True, nullable=False, index=True, comment="Unique identifier for the account in the TigerBeetle system.")
    account_type = Column(String(50), nullable=False, comment="Type of account (e.g., 'asset', 'liability', 'equity', 'revenue', 'expense').")
    currency_code = Column(String(3), nullable=False, default="USD", comment="ISO 4217 currency code.")
    is_active = Column(Boolean, default=True, nullable=False, comment="Indicates if the account is currently active.")
    
    # Balance is stored as a decimal for precision
    current_balance = Column(Numeric(precision=18, scale=4), default=0.00, nullable=False, comment="The current balance of the account.")
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    activity_logs = relationship("ActivityLog", back_populates="account", cascade="all, delete-orphan")

    # Constraints and Indexes
    __table_args__ = (
        Index("idx_account_type_active", "account_type", "is_active"),
        # Unique constraint on account_id is already defined on the column
    )

    def __repr__(self):
        return f"<LedgerAccount(id='{self.id}', account_id='{self.account_id}', type='{self.account_type}')>"

class ActivityLog(Base):
    """
    Represents an activity or event log related to a LedgerAccount.
    """
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(UUID, ForeignKey("ledger_accounts.id", ondelete="CASCADE"), nullable=False)
    
    event_type = Column(String(100), nullable=False, comment="Type of event (e.g., 'CREATED', 'BALANCE_UPDATE', 'STATUS_CHANGE').")
    description = Column(Text, nullable=False, comment="Detailed description of the activity.")
    
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    account = relationship("LedgerAccount", back_populates="activity_logs")

    def __repr__(self):
        return f"<ActivityLog(id={self.id}, event_type='{self.event_type}', account_id='{self.account_id}')>"

# --- Pydantic Schemas ---

# Base Schema for common fields
class LedgerAccountBase(BaseModel):
    """Base Pydantic schema for LedgerAccount."""
    account_id: str = Field(..., description="Unique identifier for the account.")
    account_type: str = Field(..., description="Type of account (e.g., 'asset', 'liability').")
    currency_code: str = Field("USD", max_length=3, description="ISO 4217 currency code.")
    is_active: bool = Field(True, description="Indicates if the account is active.")
    current_balance: float = Field(0.00, description="The current balance of the account.")

    class Config:
        from_attributes = True

# Schema for creating a new account
class LedgerAccountCreate(LedgerAccountBase):
    """Schema for creating a new LedgerAccount."""
    # account_id is required and should be unique, so it remains here.
    pass

# Schema for updating an existing account
class LedgerAccountUpdate(BaseModel):
    """Schema for updating an existing LedgerAccount (all fields optional)."""
    account_type: Optional[str] = Field(None, description="Type of account.")
    currency_code: Optional[str] = Field(None, max_length=3, description="ISO 4217 currency code.")
    is_active: Optional[bool] = Field(None, description="Indicates if the account is active.")
    current_balance: Optional[float] = Field(None, description="The current balance of the account.")

    class Config:
        from_attributes = True

# Schema for the response model (includes generated fields)
class LedgerAccountResponse(LedgerAccountBase):
    """Schema for returning a LedgerAccount object."""
    id: UUID = Field(..., description="The UUID of the account.")
    created_at: datetime = Field(..., description="Timestamp of creation.")
    updated_at: datetime = Field(..., description="Timestamp of last update.")
    
    # Nested activity logs
    activity_logs: List["ActivityLogResponse"] = Field([], description="List of related activity logs.")

# Base Schema for ActivityLog
class ActivityLogBase(BaseModel):
    """Base Pydantic schema for ActivityLog."""
    event_type: str = Field(..., description="Type of event (e.g., 'CREATED', 'BALANCE_UPDATE').")
    description: str = Field(..., description="Detailed description of the activity.")

    class Config:
        from_attributes = True

# Schema for creating an ActivityLog (used internally or for specific endpoints)
class ActivityLogCreate(ActivityLogBase):
    """Schema for creating a new ActivityLog."""
    account_id: UUID = Field(..., description="The UUID of the associated LedgerAccount.")

# Schema for the response model (includes generated fields)
class ActivityLogResponse(ActivityLogBase):
    """Schema for returning an ActivityLog object."""
    id: int = Field(..., description="The ID of the log entry.")
    timestamp: datetime = Field(..., description="Timestamp of the event.")
    account_id: UUID = Field(..., description="The UUID of the associated LedgerAccount.")

# Update forward references for nested schemas
LedgerAccountResponse.model_rebuild()

# Export all necessary components
__all__ = [
    "Base",
    "LedgerAccount",
    "ActivityLog",
    "LedgerAccountCreate",
    "LedgerAccountUpdate",
    "LedgerAccountResponse",
    "ActivityLogCreate",
    "ActivityLogResponse",
]
