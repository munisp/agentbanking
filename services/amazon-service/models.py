from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, Index
)
from sqlalchemy.orm import relationship, DeclarativeBase
from pydantic import BaseModel, Field

# --- SQLAlchemy Base ---

class Base(DeclarativeBase):
    """Base class which provides automated table name
    and common utility methods."""
    pass

# --- SQLAlchemy Models ---

class AmazonListing(Base):
    """
    Represents a single product listing on Amazon.
    """
    __tablename__ = "amazon_listings"

    id = Column(Integer, primary_key=True, index=True)
    asin = Column(String(10), unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    price = Column(Float, nullable=False)
    currency = Column(String(3), default="USD", nullable=False)
    seller_id = Column(String(50), nullable=False, index=True)
    is_prime = Column(Boolean, default=False, nullable=False)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationship to ActivityLog
    logs = relationship("ActivityLog", back_populates="listing")

    # Composite index for efficient querying by seller and prime status
    __table_args__ = (
        Index("idx_seller_prime", "seller_id", "is_prime"),
    )

class ActivityLog(Base):
    """
    Represents an activity log entry for an AmazonListing.
    """
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    listing_id = Column(Integer, ForeignKey("amazon_listings.id"), nullable=False, index=True)
    action = Column(String(50), nullable=False)  # e.g., "CREATED", "UPDATED", "PRICE_CHANGE"
    details = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationship back to AmazonListing
    listing = relationship("AmazonListing", back_populates="logs")

# --- Pydantic Schemas ---

# Base Schema for common fields
class AmazonListingBase(BaseModel):
    """Base schema for AmazonListing."""
    asin: str = Field(..., min_length=10, max_length=10, description="Amazon Standard Identification Number (ASIN)")
    title: str = Field(..., max_length=255, description="Product title")
    price: float = Field(..., gt=0, description="Current price of the listing")
    currency: str = Field("USD", min_length=3, max_length=3, description="Currency code (e.g., USD)")
    seller_id: str = Field(..., max_length=50, description="Identifier of the seller")
    is_prime: bool = Field(False, description="Whether the listing is Prime eligible")

# Schema for creating a new listing
class AmazonListingCreate(AmazonListingBase):
    """Schema for creating a new AmazonListing."""
    pass

# Schema for updating an existing listing
class AmazonListingUpdate(BaseModel):
    """Schema for updating an existing AmazonListing."""
    title: Optional[str] = Field(None, max_length=255)
    price: Optional[float] = Field(None, gt=0)
    currency: Optional[str] = Field(None, min_length=3, max_length=3)
    seller_id: Optional[str] = Field(None, max_length=50)
    is_prime: Optional[bool] = None

# Schema for the response model
class AmazonListingResponse(AmazonListingBase):
    """Schema for the response model of an AmazonListing."""
    id: int
    last_updated: datetime
    created_at: datetime

    class Config:
        from_attributes = True

# Schema for ActivityLog
class ActivityLogResponse(BaseModel):
    """Schema for the response model of an ActivityLog."""
    id: int
    listing_id: int
    action: str
    details: Optional[str]
    timestamp: datetime

    class Config:
        from_attributes = True

# Schema for a listing with its activity logs
class AmazonListingWithLogs(AmazonListingResponse):
    """Schema for an AmazonListing including its activity logs."""
    logs: List[ActivityLogResponse] = []
    
    class Config:
        from_attributes = True
