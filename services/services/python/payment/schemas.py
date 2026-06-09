from pydantic import BaseModel, Field, condecimal, validator
from typing import Optional, List
from datetime import datetime
from enum import Enum as PyEnum

# --- Enums from models.py ---

class PaymentStatus(str, PyEnum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    REFUNDED = "refunded"
    CANCELED = "canceled"

class PaymentMethodType(str, PyEnum):
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    BANK_TRANSFER = "bank_transfer"
    E_WALLET = "e_wallet"
    OTHER = "other"

# --- Base Schemas ---

class PaymentMethodBase(BaseModel):
    user_id: int = Field(..., description="ID of the user who owns this payment method.")
    method_type: PaymentMethodType = Field(..., description="Type of the payment method.")
    token: str = Field(..., description="Tokenized representation of the payment method.")
    last_four: Optional[str] = Field(None, max_length=4, description="Last four digits of the card/account.")
    expiry_month: Optional[int] = Field(None, ge=1, le=12, description="Expiration month for card.")
    expiry_year: Optional[int] = Field(None, description="Expiration year for card.")
    is_default: bool = Field(False, description="Whether this is the user's default payment method.")

class PaymentBase(BaseModel):
    external_id: str = Field(..., description="Unique identifier for the payment from an external system (e.g., Order ID).")
    amount: float = Field(..., gt=0, description="Amount of the payment.")
    currency: str = Field("USD", max_length=3, description="Currency code (ISO 4217).")
    user_id: int = Field(..., description="ID of the user making the payment.")
    description: Optional[str] = Field(None, description="Optional description for the payment.")
    payment_method_id: Optional[int] = Field(None, description="ID of the payment method to use.")

class TransactionBase(BaseModel):
    processor_transaction_id: str = Field(..., description="Unique ID from the payment processor.")
    transaction_type: str = Field(..., description="Type of transaction (e.g., 'charge', 'refund').")
    amount: float = Field(..., description="Amount of this specific transaction.")
    currency: str = Field("USD", max_length=3, description="Currency code (ISO 4217).")
    status: str = Field(..., description="Status of the transaction (e.g., 'success', 'failed').")
    error_code: Optional[str] = None
    error_message: Optional[str] = None

# --- Create Schemas ---

class PaymentMethodCreate(PaymentMethodBase):
    pass

class PaymentCreate(PaymentBase):
    pass

# --- Update Schemas ---

class PaymentMethodUpdate(BaseModel):
    last_four: Optional[str] = Field(None, max_length=4)
    expiry_month: Optional[int] = Field(None, ge=1, le=12)
    expiry_year: Optional[int] = None
    is_default: Optional[bool] = None

class PaymentUpdate(BaseModel):
    status: Optional[PaymentStatus] = None
    description: Optional[str] = None

# --- Read Schemas (Response Models) ---

class TransactionRead(TransactionBase):
    id: int
    payment_id: int
    created_at: datetime

    class Config:
        from_attributes = True

class PaymentMethodRead(PaymentMethodBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

class PaymentRead(PaymentBase):
    id: int
    status: PaymentStatus
    created_at: datetime
    updated_at: Optional[datetime]
    
    # Include nested transactions and payment method for a full view
    transactions: List[TransactionRead] = []
    payment_method: Optional[PaymentMethodRead] = None

    class Config:
        from_attributes = True