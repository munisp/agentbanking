"""
Refund Service Schemas
Pydantic schemas for refund service
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime

class RefundServiceBase(BaseModel):
    """Base schema for refund service"""
    amount: float
    currency: str = "NGN"
    reason: str
    transaction_id: str
    pass

class RefundServiceCreate(RefundServiceBase):
    """Schema for creating refund service"""
    pass

class RefundServiceUpdate(BaseModel):
    """Schema for updating refund service"""
    status: Optional[str] = None
    notes: Optional[str] = None
    pass

class RefundServiceResponse(RefundServiceBase):
    """Schema for refund service response"""
    id: str
    created_at: datetime
    updated_at: datetime
    status: str
    
    class Config:
        from_attributes = True
