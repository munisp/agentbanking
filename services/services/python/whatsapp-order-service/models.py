import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field
from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

# --- SQLAlchemy Base ---
Base = declarative_base()

# --- Enums ---
class OrderStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"

# --- SQLAlchemy Models ---

class WhatsAppOrder(Base):
    """
    Represents a WhatsApp-initiated order.
    """
    __tablename__ = "whatsapp_orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    whatsapp_user_id = Column(String, nullable=False, index=True, doc="The unique identifier for the WhatsApp user (e.g., phone number).")
    order_status = Column(Enum(OrderStatus), default=OrderStatus.PENDING, nullable=False, index=True)
    total_amount = Column(Float, nullable=False, doc="Total monetary amount of the order.")
    currency = Column(String(10), nullable=False, default="USD", doc="Currency code (e.g., USD, EUR).")
    items_json = Column(JSONB, nullable=False, doc="JSON array of order items (e.g., [{'name': 'Product A', 'qty': 1, 'price': 10.0}]).")
    customer_name = Column(String(255), nullable=True)
    customer_phone = Column(String(50), nullable=True, index=True)
    shipping_address = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    activities = relationship("WhatsAppOrderActivity", back_populates="order", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_whatsapp_order_user_status", whatsapp_user_id, order_status),
    )

class WhatsAppOrderActivity(Base):
    """
    Activity log for changes to a WhatsAppOrder.
    """
    __tablename__ = "whatsapp_order_activities"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(UUID(as_uuid=True), ForeignKey("whatsapp_orders.id"), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    activity_type = Column(String(50), nullable=False, doc="Type of activity, e.g., 'STATUS_CHANGE', 'ITEM_UPDATE'.")
    description = Column(Text, nullable=False, doc="Detailed description of the activity.")
    
    # Relationships
    order = relationship("WhatsAppOrder", back_populates="activities")

    __table_args__ = (
        Index("idx_whatsapp_order_activity_order_timestamp", order_id, timestamp.desc()),
    )

# --- Pydantic Schemas ---

# Base Schemas
class WhatsAppOrderBase(BaseModel):
    whatsapp_user_id: str = Field(..., description="The unique identifier for the WhatsApp user (e.g., phone number).")
    total_amount: float = Field(..., gt=0, description="Total monetary amount of the order.")
    currency: str = Field("USD", max_length=10, description="Currency code (e.g., USD, EUR).")
    items_json: List[dict] = Field(..., description="List of order items, e.g., [{'name': 'Product A', 'qty': 1, 'price': 10.0}].")
    customer_name: Optional[str] = Field(None, max_length=255)
    customer_phone: Optional[str] = Field(None, max_length=50)
    shipping_address: Optional[str] = None

class WhatsAppOrderActivityBase(BaseModel):
    activity_type: str = Field(..., max_length=50, description="Type of activity, e.g., 'STATUS_CHANGE'.")
    description: str = Field(..., description="Detailed description of the activity.")

# Create Schemas
class WhatsAppOrderCreate(WhatsAppOrderBase):
    pass

class WhatsAppOrderActivityCreate(WhatsAppOrderActivityBase):
    pass

# Update Schemas
class WhatsAppOrderUpdate(BaseModel):
    order_status: Optional[OrderStatus] = None
    total_amount: Optional[float] = Field(None, gt=0)
    currency: Optional[str] = Field(None, max_length=10)
    items_json: Optional[List[dict]] = None
    customer_name: Optional[str] = Field(None, max_length=255)
    customer_phone: Optional[str] = Field(None, max_length=50)
    shipping_address: Optional[str] = None

# Response Schemas
class WhatsAppOrderActivityResponse(WhatsAppOrderActivityBase):
    id: int
    order_id: uuid.UUID
    timestamp: datetime

    class Config:
        from_attributes = True

class WhatsAppOrderResponse(WhatsAppOrderBase):
    id: uuid.UUID
    order_status: OrderStatus
    created_at: datetime
    updated_at: datetime
    activities: List[WhatsAppOrderActivityResponse] = []

    class Config:
        from_attributes = True
