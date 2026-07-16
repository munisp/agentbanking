from datetime import datetime
from typing import List, Optional
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Index, Enum
from sqlalchemy.orm import relationship
from pydantic import BaseModel, Field
from .config import Base # Assuming config.py is in the same directory

# --- SQLAlchemy Models ---

class AmazonEbayIntegration(Base):
    """
    SQLAlchemy model for the main Amazon-eBay integration link.
    This table stores the mapping and status of a linked product.
    """
    __tablename__ = "amazon_ebay_integrations"

    id = Column(Integer, primary_key=True, index=True)
    
    # Amazon product identifier
    amazon_asin = Column(String, unique=True, index=True, nullable=False, doc="Amazon Standard Identification Number (ASIN)")
    
    # eBay product identifier
    ebay_item_id = Column(String, unique=True, index=True, nullable=False, doc="eBay Item ID")
    
    # Status of the integration link
    status = Column(Enum("active", "paused", "error", name="integration_status"), 
                    default="active", nullable=False, doc="Current status of the integration link")
    
    # Timestamps
    last_sync_at = Column(DateTime, nullable=True, doc="Timestamp of the last successful synchronization")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationship to activity logs
    logs = relationship("IntegrationActivityLog", back_populates="integration", cascade="all, delete-orphan")

    # Additional index for faster lookups on status
    __table_args__ = (
        Index("ix_integration_status", "status"),
    )

class IntegrationActivityLog(Base):
    """
    SQLAlchemy model for logging activities related to an integration link.
    """
    __tablename__ = "integration_activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign key to the main integration table
    integration_id = Column(Integer, ForeignKey("amazon_ebay_integrations.id"), nullable=False, index=True)
    
    # Type of activity (e.g., 'sync_success', 'price_update', 'inventory_error')
    activity_type = Column(String, nullable=False, doc="Type of activity performed")
    
    # Detailed message about the activity
    message = Column(Text, nullable=False, doc="Detailed log message")
    
    # Severity level (e.g., 'INFO', 'WARNING', 'ERROR')
    level = Column(Enum("INFO", "WARNING", "ERROR", name="log_level"), 
                   default="INFO", nullable=False, doc="Severity level of the log entry")
    
    # Timestamp of the activity
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationship back to the integration
    integration = relationship("AmazonEbayIntegration", back_populates="logs")

# --- Pydantic Schemas ---

# Base Schema for Integration
class AmazonEbayIntegrationBase(BaseModel):
    """Base Pydantic schema for AmazonEbayIntegration."""
    amazon_asin: str = Field(..., example="B07XXXXXXX", description="Amazon ASIN")
    ebay_item_id: str = Field(..., example="1234567890", description="eBay Item ID")
    status: str = Field("active", example="active", description="Status of the integration link (active, paused, error)")

# Schema for creating a new Integration
class AmazonEbayIntegrationCreate(AmazonEbayIntegrationBase):
    """Pydantic schema for creating a new AmazonEbayIntegration record."""
    pass

# Schema for updating an existing Integration
class AmazonEbayIntegrationUpdate(AmazonEbayIntegrationBase):
    """Pydantic schema for updating an existing AmazonEbayIntegration record."""
    amazon_asin: Optional[str] = Field(None, example="B07XXXXXXX", description="Amazon ASIN")
    ebay_item_id: Optional[str] = Field(None, example="1234567890", description="eBay Item ID")
    status: Optional[str] = Field(None, example="paused", description="Status of the integration link (active, paused, error)")

# Base Schema for Activity Log
class IntegrationActivityLogBase(BaseModel):
    """Base Pydantic schema for IntegrationActivityLog."""
    activity_type: str = Field(..., example="price_update", description="Type of activity performed")
    message: str = Field(..., example="Price updated from $10.00 to $10.50 on eBay.", description="Detailed log message")
    level: str = Field("INFO", example="INFO", description="Severity level of the log entry (INFO, WARNING, ERROR)")

# Response Schema for Activity Log
class IntegrationActivityLogResponse(IntegrationActivityLogBase):
    """Pydantic response schema for IntegrationActivityLog."""
    id: int
    integration_id: int
    timestamp: datetime

    class Config:
        orm_mode = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

# Response Schema for Integration
class AmazonEbayIntegrationResponse(AmazonEbayIntegrationBase):
    """Pydantic response schema for AmazonEbayIntegration."""
    id: int
    last_sync_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    logs: List[IntegrationActivityLogResponse] = Field([], description="List of recent activity logs for this integration")

    class Config:
        orm_mode = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

# Schema for listing integrations (without logs for brevity)
class AmazonEbayIntegrationListResponse(AmazonEbayIntegrationBase):
    """Pydantic response schema for listing AmazonEbayIntegration records."""
    id: int
    last_sync_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
