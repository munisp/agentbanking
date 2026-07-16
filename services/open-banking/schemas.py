from pydantic import BaseModel, Field, EmailStr, ConfigDict
from datetime import datetime
from typing import Optional, List
from decimal import Decimal
from models import AccountStatus, BalanceType, CreditDebitIndicator, TransactionStatus

# --- Base Schemas ---

class CoreModel(BaseModel):
    """Base model for common configurations."""
    model_config = ConfigDict(from_attributes=True)

class TimeStampedModel(CoreModel):
    created_at: datetime = Field(..., description="Timestamp of creation.")
    updated_at: datetime = Field(..., description="Timestamp of last update.")

# --- User Schemas ---

class UserBase(CoreModel):
    email: EmailStr = Field(..., description="User's email address.")

class UserCreate(UserBase):
    password: str = Field(..., min_length=8, description="User's password.")

class UserResponse(UserBase, TimeStampedModel):
    id: str = Field(..., description="Unique identifier for the user.")
    is_active: bool = Field(True, description="Whether the user account is active.")

# --- Account Schemas ---

class AccountBase(CoreModel):
    currency: str = Field(..., min_length=3, max_length=3, description="Currency code (e.g., 'GBP', 'USD').")
    nickname: str = Field(..., description="User-defined nickname for the account.")

class AccountCreate(AccountBase):
    pass

class AccountUpdate(CoreModel):
    nickname: Optional[str] = Field(None, description="New nickname for the account.")
    status: Optional[AccountStatus] = Field(None, description="New status for the account.")

class AccountResponse(AccountBase, TimeStampedModel):
    id: str = Field(..., description="Unique identifier for the account.")
    owner_id: str = Field(..., description="ID of the user who owns the account.")
    status: AccountStatus = Field(..., description="Current status of the account.")

# --- Balance Schemas ---

class BalanceResponse(CoreModel):
    id: str = Field(..., description="Unique identifier for the balance record.")
    account_id: str = Field(..., description="ID of the associated account.")
    amount: Decimal = Field(..., max_digits=19, decimal_places=4, description="The balance amount.")
    currency: str = Field(..., min_length=3, max_length=3, description="Currency code.")
    type: BalanceType = Field(..., description="Type of balance (e.g., ClosingAvailable).")
    credit_debit_indicator: CreditDebitIndicator = Field(..., description="Indicates if the balance is credit or debit.")
    datetime: datetime = Field(..., description="The date and time of the balance snapshot.")

# --- Transaction Schemas ---

class TransactionResponse(CoreModel):
    id: str = Field(..., description="Unique identifier for the transaction.")
    account_id: str = Field(..., description="ID of the associated account.")
    transaction_reference: Optional[str] = Field(None, description="Optional reference for reconciliation.")
    amount: Decimal = Field(..., max_digits=19, decimal_places=4, description="The transaction amount.")
    currency: str = Field(..., min_length=3, max_length=3, description="Currency code.")
    credit_debit_indicator: CreditDebitIndicator = Field(..., description="Indicates if the amount is a credit or a debit.")
    status: TransactionStatus = Field(..., description="Status of the transaction (e.g., Booked, Pending).")
    booking_date_time: datetime = Field(..., description="When the transaction was posted.")
    transaction_information: Optional[str] = Field(None, description="Narrative/details of the transaction.")

# --- List Schemas ---

class AccountListResponse(CoreModel):
    accounts: List[AccountResponse]

class TransactionListResponse(CoreModel):
    transactions: List[TransactionResponse]

# --- Security Schemas ---

class Token(CoreModel):
    access_token: str
    token_type: str

class TokenData(CoreModel):
    email: Optional[str] = None
