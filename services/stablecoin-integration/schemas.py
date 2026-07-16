import datetime
from typing import Optional, List
from enum import Enum

from pydantic import BaseModel, Field, condecimal

# --- Enums ---

class TransactionType(str, Enum):
    DEPOSIT = "DEPOSIT"
    WITHDRAWAL = "WITHDRAWAL"
    TRANSFER = "TRANSFER"

class TransactionStatus(str, Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

# --- Stablecoin Schemas ---

class StablecoinBase(BaseModel):
    symbol: str = Field(..., max_length=10, description="The ticker symbol of the stablecoin (e.g., 'USDC').")
    name: str = Field(..., max_length=50, description="The full name of the stablecoin (e.g., 'USD Coin').")
    contract_address: str = Field(..., max_length=100, description="The blockchain contract address.")

class StablecoinCreate(StablecoinBase):
    is_active: bool = Field(True, description="Whether the stablecoin is currently active for use.")

class StablecoinUpdate(BaseModel):
    is_active: Optional[bool] = Field(None, description="Whether the stablecoin is currently active for use.")

class Stablecoin(StablecoinBase):
    id: int
    is_active: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True

# --- Account Schemas ---

class AccountBase(BaseModel):
    user_id: int = Field(..., description="The ID of the user in the main system.")
    stablecoin_id: int = Field(..., description="The ID of the associated stablecoin.")
    wallet_address: str = Field(..., max_length=100, description="The external wallet address associated with the account.")

class AccountCreate(AccountBase):
    pass

class AccountUpdate(BaseModel):
    is_locked: Optional[bool] = Field(None, description="Flag to lock the account for transactions.")

class Account(AccountBase):
    id: int
    balance: condecimal(max_digits=20, decimal_places=8) = Field(..., description="The current balance of the account.")
    is_locked: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True

# --- Transaction Schemas ---

class TransactionBase(BaseModel):
    account_id: int = Field(..., description="The ID of the account performing the transaction.")
    stablecoin_id: int = Field(..., description="The ID of the stablecoin involved.")
    transaction_type: TransactionType = Field(..., description="The type of transaction (DEPOSIT, WITHDRAWAL, TRANSFER).")
    amount: condecimal(max_digits=20, decimal_places=8) = Field(..., gt=0, description="The amount of stablecoin for the transaction.")

class TransactionCreate(TransactionBase):
    destination_address: Optional[str] = Field(None, max_length=100, description="The destination address for a WITHDRAWAL or TRANSFER.")

class TransactionUpdate(BaseModel):
    status: TransactionStatus = Field(..., description="The new status of the transaction.")
    tx_hash: Optional[str] = Field(None, max_length=100, description="The blockchain transaction hash.")
    completed_at: Optional[datetime.datetime] = Field(None, description="Timestamp when the transaction was completed.")

class Transaction(TransactionBase):
    id: int
    status: TransactionStatus
    tx_hash: Optional[str] = None
    destination_address: Optional[str] = None
    created_at: datetime.datetime
    completed_at: Optional[datetime.datetime] = None

    class Config:
        from_attributes = True

# --- Custom Exception Schemas ---

class HTTPError(BaseModel):
    detail: str = Field(..., description="A detailed message about the error.")