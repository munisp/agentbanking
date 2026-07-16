from pydantic import BaseModel, Field, condecimal
from datetime import datetime
from typing import Optional
from models import TransactionStatus

# Base Schema for common fields
class CipsTransactionBase(BaseModel):
    sender_bank_id: str = Field(..., description="ID of the sending bank.")
    receiver_bank_id: str = Field(..., description="ID of the receiving bank.")
    amount: condecimal(max_digits=12, decimal_places=2) = Field(..., gt=0, description="Transaction amount.")
    currency: str = Field(..., min_length=3, max_length=3, description="Currency code (e.g., CNY, USD).")

# Schema for creating a new transaction
class CipsTransactionCreate(CipsTransactionBase):
    cips_transaction_id: str = Field(..., description="Unique ID assigned by the CIPS system.")
    pass

# Schema for updating an existing transaction (e.g., status update)
class CipsTransactionUpdate(BaseModel):
    status: TransactionStatus = Field(..., description="New status of the transaction.")
    
# Schema for the response model
class CipsTransaction(CipsTransactionBase):
    id: int = Field(..., description="Internal database ID.")
    cips_transaction_id: str = Field(..., description="Unique ID assigned by the CIPS system.")
    status: TransactionStatus = Field(..., description="Current status of the transaction.")
    created_at: datetime = Field(..., description="Timestamp of creation.")
    updated_at: Optional[datetime] = Field(None, description="Timestamp of last update.")

    class Config:
        from_attributes = True
        json_encoders = {
            TransactionStatus: lambda v: v.value
        }

# Schema for a successful response with a message
class MessageResponse(BaseModel):
    message: str = Field(..., description="A descriptive message about the operation.")
    
# Schema for error response
class ErrorResponse(BaseModel):
    detail: str = Field(..., description="Detailed error message.")
