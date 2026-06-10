from datetime import datetime
from typing import List, Optional
from enum import Enum

from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index, Text, Enum as SQLEnum, Numeric
from sqlalchemy.orm import relationship, DeclarativeBase
from sqlalchemy.sql import func

# --- SQLAlchemy Base and Models ---

class Base(DeclarativeBase):
    """Base class which provides automated table name and default columns."""
    __abstract__ = True

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class LoyaltyTier(str, Enum):
    """Enum for loyalty tiers."""
    BRONZE = "Bronze"
    SILVER = "Silver"
    GOLD = "Gold"
    PLATINUM = "Platinum"

class ActivityType(str, Enum):
    """Enum for loyalty activity types."""
    EARN = "EARN"
    SPEND = "SPEND"
    EXPIRE = "EXPIRE"
    ADJUST = "ADJUST"

class LoyaltyAccount(Base):
    """SQLAlchemy model for a user's loyalty account."""
    __tablename__ = "loyalty_accounts"

    user_id = Column(Integer, unique=True, nullable=False, index=True)
    current_points = Column(Numeric(10, 2), default=0.00, nullable=False)
    tier = Column(SQLEnum(LoyaltyTier), default=LoyaltyTier.BRONZE, nullable=False)
    last_activity_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    activities = relationship("LoyaltyActivity", back_populates="account", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_loyalty_account_user_id", "user_id"),
    )

class LoyaltyActivity(Base):
    """SQLAlchemy model for loyalty point transactions."""
    __tablename__ = "loyalty_activities"

    account_id = Column(Integer, ForeignKey("loyalty_accounts.id"), nullable=False)
    type = Column(SQLEnum(ActivityType), nullable=False)
    points_change = Column(Numeric(10, 2), nullable=False) # Can be positive or negative
    description = Column(Text, nullable=False)
    reference_id = Column(String(255), nullable=True, index=True) # e.g., order_id, campaign_id

    # Relationships
    account = relationship("LoyaltyAccount", back_populates="activities")

    __table_args__ = (
        Index("idx_loyalty_activity_account_id_type", "account_id", "type"),
    )

# --- Pydantic Schemas ---

# Shared Base Schemas
class LoyaltyAccountBase(BaseModel):
    """Base schema for LoyaltyAccount."""
    user_id: int = Field(..., description="The ID of the user associated with the loyalty account.")

class LoyaltyActivityBase(BaseModel):
    """Base schema for LoyaltyActivity."""
    type: ActivityType = Field(..., description="Type of the loyalty activity (EARN, SPEND, EXPIRE, ADJUST).")
    points_change: float = Field(..., gt=0, description="The change in points. Must be positive for EARN/ADJUST and will be interpreted as negative for SPEND/EXPIRE in business logic.")
    description: str = Field(..., max_length=500, description="A brief description of the activity.")
    reference_id: Optional[str] = Field(None, max_length=255, description="Optional reference ID (e.g., order ID, campaign ID).")

# LoyaltyAccount Schemas
class LoyaltyAccountCreate(LoyaltyAccountBase):
    """Schema for creating a new LoyaltyAccount."""
    # user_id is inherited and is the only required field for creation

class LoyaltyAccountUpdate(BaseModel):
    """Schema for updating an existing LoyaltyAccount."""
    # Updates are typically handled via activity logging, but we allow manual tier/point adjustment
    tier: Optional[LoyaltyTier] = Field(None, description="The new loyalty tier.")
    current_points: Optional[float] = Field(None, ge=0, description="Manual adjustment of current points. Use with caution.")

class LoyaltyAccountResponse(LoyaltyAccountBase):
    """Response schema for LoyaltyAccount."""
    id: int
    current_points: float = Field(..., description="The user's current loyalty points balance.")
    tier: LoyaltyTier
    last_activity_at: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            LoyaltyTier: lambda v: v.value,
        }

# LoyaltyActivity Schemas
class LoyaltyActivityCreate(LoyaltyActivityBase):
    """Schema for creating a new LoyaltyActivity."""
    # account_id is passed via path/logic, not in the body

class LoyaltyActivityResponse(LoyaltyActivityBase):
    """Response schema for LoyaltyActivity."""
    id: int
    account_id: int
    points_change: float # Overriding to allow negative values in response
    created_at: datetime

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            ActivityType: lambda v: v.value,
        }
