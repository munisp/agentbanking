import datetime
from typing import Optional, List
from enum import Enum

from pydantic import BaseModel, Field, conint, constr

# --- Enums ---

class TransactionType(str, Enum):
    EARN = "EARN"
    REDEEM = "REDEEM"
    ADJUST = "ADJUST"

# --- Reward Schemas ---

class RewardBase(BaseModel):
    name: constr(min_length=1, max_length=100) = Field(..., example="Free Coffee")
    description: Optional[str] = Field(None, example="Redeem 500 points for a free small coffee.")
    points_cost: conint(ge=1) = Field(..., example=500, description="The cost of the reward in points.")
    is_active: bool = Field(True, example=True)

class RewardCreate(RewardBase):
    pass

class RewardUpdate(RewardBase):
    name: Optional[constr(min_length=1, max_length=100)] = Field(None, example="Free Coffee")
    points_cost: Optional[conint(ge=1)] = Field(None, example=500)

class Reward(RewardBase):
    id: int = Field(..., example=1)
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True

# --- UserPoints Schemas ---

class UserPoints(BaseModel):
    id: int = Field(..., example=1)
    user_id: conint(ge=1) = Field(..., example=101, description="The ID of the user from the external Auth service.")
    points_balance: conint(ge=0) = Field(..., example=1500)
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True

# --- RewardTransaction Schemas ---

class RewardTransactionBase(BaseModel):
    transaction_type: TransactionType = Field(..., example=TransactionType.EARN)
    points_change: int = Field(..., example=100, description="Positive for EARN, negative for REDEEM/ADJUST.")
    description: Optional[str] = Field(None, example="Points earned from completing a survey.")

class RewardTransactionCreate(RewardTransactionBase):
    # This schema is used internally by the service layer, not directly by the router
    user_id: conint(ge=1) = Field(..., example=101)
    reward_id: Optional[conint(ge=1)] = Field(None, example=1)

class RewardTransaction(RewardTransactionBase):
    id: int = Field(..., example=1)
    user_points_id: int = Field(..., example=1)
    reward_id: Optional[int] = Field(None, example=1)
    created_at: datetime.datetime

    class Config:
        from_attributes = True

# --- Request Schemas for Business Logic ---

class PointsAdjustmentRequest(BaseModel):
    points_change: int = Field(..., example=50, description="The amount of points to add (positive) or subtract (negative).")
    description: Optional[str] = Field(None, example="Manual adjustment by admin.")

class RewardRedemptionRequest(BaseModel):
    reward_id: conint(ge=1) = Field(..., example=1, description="The ID of the reward to redeem.")
    # Quantity could be added here, but for simplicity, we'll assume quantity of 1