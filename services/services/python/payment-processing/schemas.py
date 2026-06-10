import uuid
from datetime import datetime
from typing import Optional, List
from decimal import Decimal

from pydantic import BaseModel, Field, condecimal, constr

from models import TransactionStatus, PaymentMethodType

# --- Base Schemas ---

class BaseSchema(BaseModel):
    """Base schema for common configuration."""
    class Config:
        from_attributes = True
        json_encoders = {
            Decimal: lambda v: str(v)
        }

# --- Merchant Schemas ---

class MerchantBase(BaseSchema):
    name: constr(min_length=1, max_length=100) = Field(..., example="Acme Corp")
    is_active: bool = Field(True, example=True)

class MerchantCreate(MerchantBase):
    # api_key_hash is handled internally by the service layer
    pass

class MerchantUpdate(MerchantBase):
    name: Optional[constr(min_length=1, max_length=100)] = None
    is_active: Optional[bool] = None

class MerchantOut(MerchantBase):
    id: uuid.UUID = Field(..., example=uuid.uuid4())
    api_key_hash: str = Field(..., description="Hashed API key (not the key itself)")
    created_at: datetime
    updated_at: datetime

# --- Payment Method Schemas ---

class PaymentMethodBase(BaseSchema):
    user_id: Optional[uuid.UUID] = Field(None, example=uuid.uuid4(), description="External User ID")
    type: PaymentMethodType = Field(..., example=PaymentMethodType.CARD)
    last_four: constr(min_length=4, max_length=4) = Field(..., example="4242")
    is_default: bool = Field(False, example=False)

class PaymentMethodCreate(PaymentMethodBase):
    token: constr(min_length=1) = Field(..., description="Secure token from PSP (e.g., Stripe token)")

class PaymentMethodOut(PaymentMethodBase):
    id: uuid.UUID = Field(..., example=uuid.uuid4())
    created_at: datetime
    updated_at: datetime
    # token is sensitive and should not be returned in the Out schema

# --- Transaction Schemas ---

class TransactionBase(BaseSchema):
    amount: condecimal(ge=Decimal('0.01'), decimal_places=2) = Field(..., example=Decimal("19.99"))
    currency: constr(min_length=3, max_length=3) = Field(..., example="USD")

class TransactionCreate(TransactionBase):
    merchant_id: uuid.UUID = Field(..., example=uuid.uuid4())
    payment_method_id: uuid.UUID = Field(..., example=uuid.uuid4(), description="ID of the stored PaymentMethod")
    # Alternatively, could accept a one-time token here, but we'll use stored methods for simplicity

class TransactionOut(TransactionBase):
    id: uuid.UUID = Field(..., example=uuid.uuid4())
    merchant_id: uuid.UUID
    payment_method_id: uuid.UUID
    status: TransactionStatus = Field(..., example=TransactionStatus.PENDING)
    processor_transaction_id: Optional[str] = Field(None, example="txn_123abc")
    fee: condecimal(ge=Decimal('0.00'), decimal_places=2) = Field(..., example=Decimal("0.50"))
    net_amount: condecimal(ge=Decimal('0.00'), decimal_places=2) = Field(..., example=Decimal("19.49"))
    created_at: datetime
    updated_at: datetime

# --- Refund Schemas ---

class RefundBase(BaseSchema):
    amount: condecimal(ge=Decimal('0.01'), decimal_places=2) = Field(..., example=Decimal("5.00"))

class RefundCreate(RefundBase):
    transaction_id: uuid.UUID = Field(..., example=uuid.uuid4())

class RefundOut(RefundBase):
    id: uuid.UUID = Field(..., example=uuid.uuid4())
    transaction_id: uuid.UUID
    status: TransactionStatus = Field(..., example=TransactionStatus.PENDING)
    processor_refund_id: Optional[str] = Field(None, example="ref_456def")
    created_at: datetime
    updated_at: datetime

# --- List/Filter Schemas ---

class TransactionFilter(BaseSchema):
    merchant_id: Optional[uuid.UUID] = None
    status: Optional[TransactionStatus] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    
class ListResponse(BaseSchema):
    total: int
    page: int
    size: int
    items: List[TransactionOut] # Generic list response, but we'll use TransactionOut for now
