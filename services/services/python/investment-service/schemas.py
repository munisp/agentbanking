"""Investment Service Schemas"""
from pydantic import BaseModel, Field
from typing import Optional

class InvestmentBase(BaseModel):
    product_id: str
    amount: float = Field(..., gt=0)
    currency: str = Field(default="NGN", max_length=3)

class InvestmentCreate(InvestmentBase):
    user_id: str
    source_goal: Optional[str] = None

class InvestmentUpdate(BaseModel):
    amount: Optional[float] = None
    status: Optional[str] = None

class InvestmentResponse(InvestmentBase):
    id: str
    user_id: str
    status: str
    invested_at: str
    returns: Optional[float] = None
