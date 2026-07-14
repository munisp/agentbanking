from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
import enum

# --- Enums ---

class TransactionStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"

# --- Party Schemas ---

class PartyBase(BaseModel):
    name: str = Field(..., max_length=255, description="Full name of the party (sender or receiver).")
    country_code: str = Field(..., min_length=3, max_length=3, description="ISO 3166-1 alpha-3 country code.")
    currency_code: str = Field(..., min_length=3, max_length=3, description="ISO 4217 currency code.")
    bank_name: Optional[str] = Field(None, max_length=255)
    account_number: str = Field(..., max_length=50, description="Bank account number or equivalent identifier.")
    swift_bic: Optional[str] = Field(None, max_length=11, description="SWIFT/BIC code of the bank.")
    address: Optional[str] = Field(None, description="Full address of the party.")

class PartyCreate(PartyBase):
    pass

class PartyUpdate(PartyBase):
    name: Optional[str] = Field(None, max_length=255)
    country_code: Optional[str] = Field(None, min_length=3, max_length=3)
    currency_code: Optional[str] = Field(None, min_length=3, max_length=3)
    account_number: Optional[str] = Field(None, max_length=50)

class PartyRead(PartyBase):
    id: int
    is_verified: bool
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

# --- FXRate Schemas ---

class FXRateBase(BaseModel):
    from_currency: str = Field(..., min_length=3, max_length=3, description="Source currency (e.g., USD).")
    to_currency: str = Field(..., min_length=3, max_length=3, description="Target currency (e.g., NGN).")
    rate: Decimal = Field(..., gt=0, decimal_places=6, description="Exchange rate.")
    source: str = Field(..., max_length=50, description="Source of the FX rate.")
    strategy: str = Field(..., max_length=20, description="Routing strategy.")
    tenant_id: str = Field(..., max_length=50, description="Tenant identifier.")

class FXRateCreate(FXRateBase):
    pass

class FXRateRead(FXRateBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

# --- Transaction Schemas ---

class TransactionBase(BaseModel):
    source_amount: Decimal = Field(..., gt=0, decimal_places=4, description="Amount in source currency.")
    source_currency: str = Field(..., min_length=3, max_length=3, description="Source currency code.")
    target_currency: str = Field(..., min_length=3, max_length=3, description="Target currency code.")
    fee_amount: Decimal = Field(Decimal(0.0), ge=0, decimal_places=4, description="Fee charged for the transaction.")
    purpose_code: Optional[str] = Field(None, max_length=10, description="ISO 20022 purpose code.")

class TransactionCreate(TransactionBase):
    sender_id: int = Field(..., description="ID of the sending party.")
    receiver_id: int = Field(..., description="ID of the receiving party.")

class TransactionUpdate(BaseModel):
    status: Optional[TransactionStatus] = None
    status_detail: Optional[str] = Field(None, max_length=255)
    
class TransactionRead(TransactionBase):
    id: int
    reference_id: str
    target_amount: Decimal = Field(..., decimal_places=4, description="Amount in target currency after conversion.")
    fx_rate: Decimal = Field(..., decimal_places=6, description="FX rate used for conversion.")
    status: TransactionStatus
    status_detail: Optional[str]
    compliance_score: int
    created_at: datetime
    updated_at: Optional[datetime]
    
    # Nested party information for a complete view
    sender: PartyRead
    receiver: PartyRead

    class Config:
        from_attributes = True
        # Allow Decimal to be serialized as float for simplicity in JSON, though string is often better for finance
        json_encoders = {
            Decimal: lambda v: float(v) if v is not None else None
        }

# --- Response for List Operations ---
class PaginatedTransactionResponse(BaseModel):
    total: int
    page: int
    size: int
    items: List[TransactionRead]
    
class PaginatedPartyResponse(BaseModel):
    total: int
    page: int
    size: int
    items: List[PartyRead]
    
class PaginatedFXRateResponse(BaseModel):
    total: int
    page: int
    size: int
    items: List[FXRateRead]