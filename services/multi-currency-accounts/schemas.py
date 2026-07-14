from pydantic import BaseModel, Field, condecimal
from datetime import datetime
from typing import List, Optional

# --- Base Schemas ---

class CurrencyBalanceBase(BaseModel):
    currency_code: str = Field(..., min_length=3, max_length=3, pattern=r"^[A-Z]{3}$", example="USD")
    balance: condecimal(max_digits=18, decimal_places=4) = Field(..., ge=0, example=1000.50)

class AccountBase(BaseModel):
    account_name: str = Field(..., min_length=3, max_length=100, example="My Primary Account")
    # user_id is assumed to be handled by authentication/authorization layer, 
    # but included in creation for demonstration
    user_id: int = Field(..., ge=1, example=1) 

# --- Create Schemas ---

class CurrencyBalanceCreate(CurrencyBalanceBase):
    pass

class AccountCreate(AccountBase):
    initial_balances: List[CurrencyBalanceCreate] = Field(default_factory=list)

# --- Update Schemas ---

class CurrencyBalanceUpdate(CurrencyBalanceBase):
    # For updates, balance is the new absolute value
    pass

class AccountUpdate(BaseModel):
    account_name: Optional[str] = Field(None, min_length=3, max_length=100, example="My Updated Account Name")

# --- Response Schemas ---

class CurrencyBalance(CurrencyBalanceBase):
    id: int
    account_id: int
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

class Account(AccountBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime]
    balances: List[CurrencyBalance] = []

    class Config:
        from_attributes = True

# --- Custom Exception Schema ---

class HTTPError(BaseModel):
    detail: str = Field(..., example="Item not found")