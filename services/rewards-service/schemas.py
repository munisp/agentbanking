"""
Rewards Service Schemas
Pydantic schemas for rewards service
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime

class RewardsServiceBase(BaseModel):
    """Base schema for rewards service"""
    user_id: str
    points: int = 0
    tier: str = "bronze"
    pass

class RewardsServiceCreate(RewardsServiceBase):
    """Schema for creating rewards service"""
    pass

class RewardsServiceUpdate(BaseModel):
    """Schema for updating rewards service"""
    points: Optional[int] = None
    tier: Optional[str] = None
    pass

class RewardsServiceResponse(RewardsServiceBase):
    """Schema for rewards service response"""
    id: str
    created_at: datetime
    updated_at: datetime
    status: str
    
    class Config:
        from_attributes = True
