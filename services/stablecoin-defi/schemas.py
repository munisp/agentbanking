from typing import Optional
from datetime import datetime
from uuid import UUID
from enum import Enum as PyEnum

from pydantic import BaseModel, Field

# --- Enums ---

class TransactionType(str, PyEnum):
    deposit = "DEPOSIT"
    withdraw = "WITHDRAW"
    borrow = "BORROW"
    repay = "REPAY"

# --- Base Schemas ---

class StablecoinBase(BaseModel):
    symbol: str = Field(..., example="USDC", max_length=10)
    name: str = Field(..., example="USD Coin", max_length=50)
    peg_asset: str = Field("USD", example="USD", max_length=10)
    collateral_ratio: float = Field(1.0, ge=0.0, example=1.0)
    is_active: int = Field(1, ge=0, le=1, example=1)

class UserBase(BaseModel):
    username: str = Field(..., example="defi_user_1", max_length=50)
    email: str = Field(..., example="user@example.com", max_length=100)

class AccountBase(BaseModel):
    stablecoin_id: int = Field(..., example=1)
    balance: float = Field(0.0, ge=0.0, example=1000.50)
    deposit_rate: float = Field(0.0, ge=0.0, example=0.05)
    borrow_rate: float = Field(0.0, ge=0.0, example=0.08)

class TransactionBase(BaseModel):
    account_id: UUID
    stablecoin_id: int
    type: TransactionType
    amount: float = Field(..., gt=0.0, example=500.00)
    rate_at_time: float = Field(..., ge=0.0, example=0.05)

# --- Create Schemas ---

class StablecoinCreate(StablecoinBase):
    pass

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)

class AccountCreate(BaseModel):
    stablecoin_id: int = Field(..., example=1)

class TransactionCreate(BaseModel):
    type: TransactionType
    amount: float = Field(..., gt=0.0, example=500.00)

# --- Update Schemas ---

class StablecoinUpdate(StablecoinBase):
    symbol: Optional[str] = None
    name: Optional[str] = None
    peg_asset: Optional[str] = None
    collateral_ratio: Optional[float] = None
    is_active: Optional[int] = None

class UserUpdate(UserBase):
    username: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = Field(None, min_length=8)
    is_active: Optional[int] = None

class AccountUpdate(BaseModel):
    deposit_rate: Optional[float] = Field(None, ge=0.0, example=0.05)
    borrow_rate: Optional[float] = Field(None, ge=0.0, example=0.08)

# --- Full Schemas (for response) ---

class Stablecoin(StablecoinBase):
    id: int
    
    class Config:
        from_attributes = True

class User(UserBase):
    id: UUID
    is_active: int
    created_at: datetime

    class Config:
        from_attributes = True

class Account(AccountBase):
    id: UUID
    user_id: UUID
    last_updated: datetime
    
    user: Optional[User] = None
    stablecoin: Optional[Stablecoin] = None

    class Config:
        from_attributes = True

class Transaction(TransactionBase):
    id: UUID
    timestamp: datetime

    class Config:
        from_attributes = True

# --- Schemas for Authentication ---

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None