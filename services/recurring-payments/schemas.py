"""Recurring Payments Schemas"""
from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum

class FrequencyEnum(str, Enum):
    daily = "daily"
    weekly = "weekly"
    biweekly = "biweekly"
    monthly = "monthly"

class RecurringPaymentBase(BaseModel):
    amount: float = Field(..., gt=0)
    currency: str = Field(default="NGN", max_length=3)
    recipient: str
    frequency: FrequencyEnum = FrequencyEnum.monthly
    start_date: str

class RecurringPaymentCreate(RecurringPaymentBase):
    user_id: str

class RecurringPaymentUpdate(BaseModel):
    amount: Optional[float] = None
    currency: Optional[str] = None
    recipient: Optional[str] = None
    frequency: Optional[FrequencyEnum] = None

class RecurringPaymentResponse(RecurringPaymentBase):
    id: str
    user_id: str
    status: str
    next_execution: Optional[str] = None
    execution_count: int = 0
    created_at: str
