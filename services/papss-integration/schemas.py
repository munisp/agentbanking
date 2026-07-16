from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum as PyEnum

# --- Enums ---

class PaymentStatus(str, PyEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SETTLED = "SETTLED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

# --- Base Schemas ---

class PaymentTransactionBase(BaseModel):
    """Base schema for a PAPSS Payment Transaction."""
    
    papss_ref_id: str = Field(..., description="Unique PAPSS transaction reference ID.")
    originator_bank_bic: str = Field(..., description="Originator Bank BIC/SWIFT code.")
    beneficiary_bank_bic: str = Field(..., description="Beneficiary Bank BIC/SWIFT code.")
    
    amount: float = Field(..., gt=0, description="Transaction amount.")
    currency_code: str = Field(..., min_length=3, max_length=3, description="ISO 4217 currency code (e.g., 'NGN', 'ZAR').")
    
    originator_account_number: str = Field(..., description="Originator's account number.")
    originator_name: str = Field(..., description="Originator's name.")
    
    beneficiary_account_number: str = Field(..., description="Beneficiary's account number.")
    beneficiary_name: str = Field(..., description="Beneficiary's name.")

    class Config:
        from_attributes = True

# --- Request Schemas ---

class PaymentTransactionCreate(PaymentTransactionBase):
    """Schema for creating a new PAPSS Payment Transaction."""
    pass

class PaymentTransactionUpdate(BaseModel):
    """Schema for updating an existing PAPSS Payment Transaction."""
    
    status: Optional[PaymentStatus] = Field(None, description="New status of the transaction.")
    error_code: Optional[str] = Field(None, description="Error code if the transaction failed.")
    error_message: Optional[str] = Field(None, description="Detailed error message.")

    class Config:
        from_attributes = True

# --- Response Schemas ---

class PaymentTransactionResponse(PaymentTransactionBase):
    """Schema for a full PAPSS Payment Transaction response."""
    
    id: int = Field(..., description="Database ID of the transaction.")
    status: PaymentStatus = Field(PaymentStatus.PENDING, description="Current status of the transaction.")
    created_at: datetime = Field(..., description="Timestamp of creation.")
    updated_at: Optional[datetime] = Field(None, description="Timestamp of last update.")
    
    error_code: Optional[str] = Field(None, description="Error code if the transaction failed.")
    error_message: Optional[str] = Field(None, description="Detailed error message.")

# --- Error Schema ---

class HTTPError(BaseModel):
    """Standard error response schema."""
    detail: str = Field(..., description="A detailed error message.")
