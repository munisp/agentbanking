import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, EmailStr, condecimal

# --- General Schemas ---

class HTTPError(BaseModel):
    """Schema for standard HTTP error responses."""
    detail: str = Field(..., example="Item not found")

    class Config:
        schema_extra = {
            "example": {"detail": "Account with ID 123 not found"},
        }

# --- User/Auth Schemas ---

class UserBase(BaseModel):
    email: EmailStr
    is_active: Optional[bool] = True
    is_superuser: Optional[bool] = False

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)

class UserInDB(UserBase):
    id: uuid.UUID
    
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str
    expires_at: datetime

class TokenData(BaseModel):
    user_id: Optional[uuid.UUID] = None

# --- Customer Schemas ---

class CustomerBase(BaseModel):
    first_name: str = Field(..., min_length=2, max_length=50)
    last_name: str = Field(..., min_length=2, max_length=50)
    date_of_birth: datetime
    address: str = Field(..., max_length=255)
    phone_number: str = Field(..., pattern=r"^\+?[0-9\s\-()]{7,20}$")

class CustomerCreate(CustomerBase):
    user_id: uuid.UUID

class CustomerUpdate(CustomerBase):
    first_name: Optional[str] = Field(None, min_length=2, max_length=50)
    last_name: Optional[str] = Field(None, min_length=2, max_length=50)
    date_of_birth: Optional[datetime] = None
    address: Optional[str] = Field(None, max_length=255)
    phone_number: Optional[str] = Field(None, pattern=r"^\+?[0-9\s\-()]{7,20}$")

class CustomerInDB(CustomerBase):
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# --- Account Schemas ---

class AccountBase(BaseModel):
    account_type: str = Field(..., pattern=r"^(SAVINGS|CHECKING)$")
    is_active: Optional[bool] = True

class AccountCreate(AccountBase):
    customer_id: uuid.UUID

class AccountUpdate(AccountBase):
    account_type: Optional[str] = Field(None, pattern=r"^(SAVINGS|CHECKING)$")
    is_active: Optional[bool] = None

class AccountInDB(AccountBase):
    id: uuid.UUID
    customer_id: uuid.UUID
    account_number: str
    balance: condecimal(ge=0, decimal_places=2)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# --- Transaction Schemas ---

class TransactionBase(BaseModel):
    amount: condecimal(gt=0, decimal_places=2)
    description: Optional[str] = Field(None, max_length=255)

class TransactionCreate(TransactionBase):
    transaction_type: str = Field(..., pattern=r"^(DEPOSIT|WITHDRAWAL|TRANSFER)$")
    account_id: uuid.UUID

class TransactionInDB(TransactionBase):
    id: uuid.UUID
    account_id: uuid.UUID
    transaction_type: str
    timestamp: datetime
    status: str

    class Config:
        from_attributes = True

# --- Nested Schemas for Read Operations ---

class AccountWithTransactions(AccountInDB):
    transactions: List[TransactionInDB] = []

class CustomerWithAccounts(CustomerInDB):
    accounts: List[AccountInDB] = []

class UserWithCustomer(UserInDB):
    customer: Optional[CustomerInDB] = None