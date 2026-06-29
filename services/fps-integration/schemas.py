from pydantic import BaseModel, Field, condecimal, constr
from datetime import datetime
from typing import Optional, Any
from decimal import Decimal

# --- Base Schemas ---

class FPSTransactionBase(BaseModel):
    transaction_ref: constr(max_length=50) = Field(..., description="Unique reference from the initiating system.")
    sender_account: constr(max_length=34) = Field(..., description="Account number of the sender.")
    receiver_account: constr(max_length=34) = Field(..., description="Account number of the receiver.")
    amount: condecimal(max_digits=18, decimal_places=2, gt=Decimal(0)) = Field(..., description="Transaction amount.")
    currency: constr(max_length=3) = Field("GBP", description="Currency code (e.g., 'GBP').")

class FPSWebhookLogBase(BaseModel):
    event_type: constr(max_length=50) = Field(..., description="Type of the webhook event.")
    payload: Any = Field(..., description="Full JSON payload of the webhook.")

# --- Input Schemas ---

class FPSTransactionCreate(FPSTransactionBase):
    """Schema for creating a new FPS transaction."""
    pass

class FPSTransactionUpdate(BaseModel):
    """Schema for updating an existing FPS transaction."""
    status: Optional[constr(max_length=20)] = Field(None, description="Current status of the transaction.")
    status_detail: Optional[str] = Field(None, description="Detailed message about the current status.")
    fps_payment_id: Optional[constr(max_length=50)] = Field(None, description="Reference ID from the FPS provider.")

class FPSWebhookIn(FPSWebhookLogBase):
    """Schema for an incoming webhook from the FPS provider."""
    # The transaction_ref is expected in the payload, but we'll include it here for clarity
    # In a real system, the payload would be parsed to find the transaction_ref
    transaction_ref: constr(max_length=50) = Field(..., description="Transaction reference linked to the webhook.")

# --- Output Schemas ---

class FPSWebhookLog(FPSWebhookLogBase):
    id: int
    transaction_id: Optional[int]
    received_at: datetime

    class Config:
        from_attributes = True

class FPSTransaction(FPSTransactionBase):
    id: int
    fps_payment_id: Optional[constr(max_length=50)]
    status: constr(max_length=20)
    status_detail: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    # Nested relationship
    webhook_logs: list[FPSWebhookLog] = []

    class Config:
        from_attributes = True

# --- Utility Schemas ---

class APIResponse(BaseModel):
    """Generic API response schema."""
    message: str
    status_code: int
    data: Optional[Any] = None
