"""
Data models for beneficiary-service
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum

class Status(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"

class BaseEntity(BaseModel):
    id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    status: Status = Status.PENDING

class BeneficiaryServiceModel(BaseEntity):
    user_id: str
    amount: Optional[float] = 0.0
    currency: str = "NGN"
    metadata: Optional[dict] = {}
    
    class Config:
        orm_mode = True
