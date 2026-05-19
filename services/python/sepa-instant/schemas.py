from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field, root_validator, validator

# Import Enums from models to ensure consistency
from models import TransactionStatus, RecallReason, RecallStatus

# --- Base Schemas ---

class SCTInstBase(BaseModel):
    """Base schema for SEPA Instant Credit Transfer transaction data."""
    end_to_end_id: str = Field(..., max_length=35, description="Unique end-to-end transaction reference.")
    amount: Decimal = Field(..., gt=Decimal(0), max_digits=18, decimal_places=2, description="The amount of the transfer in Euro.")
    currency: str = Field("EUR", const=True, max_length=3, description="The currency of the transfer (must be EUR).")
    remittance_information: Optional[str] = Field(None, max_length=140, description="Customer remittance data.")

    # Originator (Payer) Information
    originator_name: str = Field(..., max_length=100, description="Name of the Originator (Payer).")
    originator_iban: str = Field(..., max_length=34, description="IBAN of the Originator's account.")
    originator_bic: str = Field(..., max_length=11, description="BIC of the Originator's Bank.")

    # Beneficiary (Payee) Information
    beneficiary_name: str = Field(..., max_length=100, description="Name of the Beneficiary (Payee).")
    beneficiary_iban: str = Field(..., max_length=34, description="IBAN of the Beneficiary's account.")
    beneficiary_bic: str = Field(..., max_length=11, description="BIC of the Beneficiary's Bank.")

    class Config:
        use_enum_values = True
        from_attributes = True
        json_encoders = {
            UUID: str,
            Decimal: lambda v: str(v)
        }

# --- Recall Schemas ---

class TransactionRecallBase(BaseModel):
    """Base schema for a Transaction Recall request."""
    recall_reason: RecallReason = Field(..., description="Reason for the recall (e.g., DUPLICATE, FRAUDULENT).")

class TransactionRecallCreate(TransactionRecallBase):
    """Schema for creating a new Transaction Recall request."""
    pass

class TransactionRecallResponse(TransactionRecallBase):
    """Schema for returning a Transaction Recall record."""
    id: UUID
    transaction_id: UUID
    recall_request_date: datetime
    recall_status: RecallStatus
    response_date: Optional[datetime] = None
    return_amount: Optional[Decimal] = None
    return_fee: Optional[Decimal] = None

    class Config(SCTInstBase.Config):
        pass

# --- Transaction Schemas ---

class SCTInstTransactionCreate(SCTInstBase):
    """Schema for creating a new SCT Inst Transaction."""
    # requested_execution_date is typically set by the system upon receipt,
    # but we can allow it in the request for simulation/future-dated payments.
    requested_execution_date: datetime = Field(..., description="Timestamp when the payment is requested.")

    @validator('originator_iban', 'beneficiary_iban')
    def validate_iban(cls, v) -> None:
        # Simple length check for IBAN as a placeholder for full validation
        if not (15 <= len(v) <= 34):
            raise ValueError("IBAN must be between 15 and 34 characters long.")
        return v

    @validator('originator_bic', 'beneficiary_bic')
    def validate_bic(cls, v) -> None:
        # Simple length check for BIC
        if not (8 <= len(v) <= 11):
            raise ValueError("BIC must be 8 or 11 characters long.")
        return v


class SCTInstTransactionUpdate(BaseModel):
    """Schema for updating an existing SCT Inst Transaction (e.g., status update)."""
    transaction_status: Optional[TransactionStatus] = Field(None, description="New status of the transaction.")
    execution_timestamp: Optional[datetime] = Field(None, description="Timestamp of successful execution.")
    rejection_reason_code: Optional[str] = Field(None, max_length=4, description="ISO 20022 reason code for rejection.")
    rejection_reason_text: Optional[str] = Field(None, description="Detailed rejection reason.")

    class Config(SCTInstBase.Config):
        pass


class SCTInstTransactionResponse(SCTInstBase):
    """Schema for returning a full SCT Inst Transaction record."""
    id: UUID
    instruction_id: str = Field(..., max_length=35, description="Unique message ID from the Originator Bank.")
    transaction_status: TransactionStatus
    requested_execution_date: datetime
    execution_timestamp: Optional[datetime] = None
    rejection_reason_code: Optional[str] = None
    rejection_reason_text: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    # Nested relationship
    recalls: List[TransactionRecallResponse] = Field([], description="List of recall requests for this transaction.")

    class Config(SCTInstBase.Config):
        pass

# --- Utility Schemas ---

class StatusMessage(BaseModel):
    """Generic status message for API responses."""
    message: str
    id: Optional[UUID] = None
    status_code: int = 200
