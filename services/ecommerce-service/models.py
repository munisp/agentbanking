from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    Numeric,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import relationship, declarative_base

# --- SQLAlchemy Base ---
Base = declarative_base()

# --- Utility Mixin for Timestamps ---
class TimestampMixin:
    """Mixin for created_at and updated_at columns."""

    created_at = Column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
        index=True,
    )

# --- Database Models ---

class Product(Base, TimestampMixin):
    """
    SQLAlchemy model for an e-commerce product.
    """
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    price = Column(Numeric(10, 2), nullable=False)  # Price with 10 total digits, 2 decimal places
    stock_quantity = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    
    # Relationships
    logs = relationship("ActivityLog", back_populates="product")

    # Constraints and Indexes
    __table_args__ = (
        Index("ix_product_name_active", "name", "is_active"),
    )

    def __repr__(self):
        return f"<Product(id={self.id}, name='{self.name}', price={self.price})>"


class ActivityLog(Base, TimestampMixin):
    """
    SQLAlchemy model for logging activities related to the service.
    """
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    service_name = Column(String(100), nullable=False, index=True)
    entity_type = Column(String(100), nullable=False)
    entity_id = Column(Integer, nullable=False, index=True)
    action = Column(String(100), nullable=False, index=True)  # e.g., 'CREATE', 'UPDATE', 'DELETE', 'STOCK_CHANGE'
    details = Column(Text, nullable=True)
    user_id = Column(String(100), nullable=True) # Assuming user ID can be a string (e.g., UUID or username)

    # Foreign Key to Product (optional, for direct product-related logs)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True, index=True)
    product = relationship("Product", back_populates="logs")

    def __repr__(self):
        return f"<ActivityLog(id={self.id}, service='{self.service_name}', action='{self.action}')>"


# --- Pydantic Schemas ---

# Base Schema for shared attributes
class ProductBase(BaseModel):
    """Base schema for product data."""
    name: str = Field(..., max_length=255, description="The name of the product.")
    description: Optional[str] = Field(None, description="A detailed description of the product.")
    price: float = Field(..., gt=0, description="The price of the product. Must be greater than zero.")
    stock_quantity: int = Field(0, ge=0, description="The current stock quantity of the product.")
    is_active: bool = Field(True, description="Whether the product is currently active and visible.")


# Schema for creating a new product
class ProductCreate(ProductBase):
    """Schema for creating a new product."""
    pass


# Schema for updating an existing product
class ProductUpdate(ProductBase):
    """Schema for updating an existing product. All fields are optional."""
    name: Optional[str] = Field(None, max_length=255, description="The name of the product.")
    price: Optional[float] = Field(None, gt=0, description="The price of the product. Must be greater than zero.")
    stock_quantity: Optional[int] = Field(None, ge=0, description="The current stock quantity of the product.")
    is_active: Optional[bool] = Field(None, description="Whether the product is currently active and visible.")


# Schema for returning a product response
class ProductResponse(ProductBase):
    """Schema for returning a product, including database-generated fields."""
    id: int = Field(..., description="The unique identifier of the product.")
    created_at: datetime = Field(..., description="Timestamp of when the product was created.")
    updated_at: datetime = Field(..., description="Timestamp of the last update to the product.")

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda dt: dt.isoformat(),
        }


# Schema for Activity Log
class ActivityLogResponse(BaseModel):
    """Schema for returning an activity log entry."""
    id: int
    service_name: str
    entity_type: str
    entity_id: int
    action: str
    details: Optional[str]
    user_id: Optional[str]
    product_id: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda dt: dt.isoformat(),
        }
