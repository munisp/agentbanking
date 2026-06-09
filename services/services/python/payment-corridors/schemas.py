from pydantic import BaseModel, Field, conlist, validator
from typing import List, Optional
from datetime import datetime
import enum

# --- Enums (Mirroring models.py) ---

class CorridorStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    MAINTENANCE = "MAINTENANCE"

class FeeType(str, enum.Enum):
    FIXED = "FIXED"
    PERCENTAGE = "PERCENTAGE"
    TIERED = "TIERED"

class LimitType(str, enum.Enum):
    TRANSACTION = "TRANSACTION"
    DAILY = "DAILY"
    MONTHLY = "MONTHLY"

# --- Nested Schemas: CorridorFee ---

class CorridorFeeBase(BaseModel):
    fee_type: FeeType = Field(..., description="Type of fee: FIXED, PERCENTAGE, or TIERED.")
    value: float = Field(..., gt=0, description="The fee value. Absolute amount for FIXED, percentage for PERCENTAGE.")
    min_amount: float = Field(0.0, ge=0, description="Minimum transaction amount for this fee to apply.")
    max_amount: float = Field(999999999.99, ge=0, description="Maximum transaction amount for this fee to apply.")

    class Config:
        use_enum_values = True

class CorridorFeeCreate(CorridorFeeBase):
    pass

class CorridorFeeUpdate(CorridorFeeBase):
    pass

class CorridorFee(CorridorFeeBase):
    id: int
    corridor_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# --- Nested Schemas: CorridorLimit ---

class CorridorLimitBase(BaseModel):
    limit_type: LimitType = Field(..., description="Type of limit: TRANSACTION, DAILY, or MONTHLY.")
    max_value: float = Field(..., gt=0, description="The maximum allowed value for the limit type.")

    class Config:
        use_enum_values = True

class CorridorLimitCreate(CorridorLimitBase):
    pass

class CorridorLimitUpdate(CorridorLimitBase):
    pass

class CorridorLimit(CorridorLimitBase):
    id: int
    corridor_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# --- Main Schema: PaymentCorridor ---

class PaymentCorridorBase(BaseModel):
    source_country_iso: str = Field(..., min_length=3, max_length=3, pattern=r"^[A-Z]{3}$", description="Source country ISO 3166-1 alpha-3 code.")
    source_currency_iso: str = Field(..., min_length=3, max_length=3, pattern=r"^[A-Z]{3}$", description="Source currency ISO 4217 code.")
    destination_country_iso: str = Field(..., min_length=3, max_length=3, pattern=r"^[A-Z]{3}$", description="Destination country ISO 3166-1 alpha-3 code.")
    destination_currency_iso: str = Field(..., min_length=3, max_length=3, pattern=r"^[A-Z]{3}$", description="Destination currency ISO 4217 code.")
    
    status: CorridorStatus = Field(CorridorStatus.INACTIVE, description="Current status of the corridor.")
    exchange_rate: float = Field(..., gt=0, description="The exchange rate from source to destination currency.")
    processing_time_hours: int = Field(24, ge=1, description="Estimated processing time in hours.")
    is_enabled: bool = Field(True, description="Whether the corridor is currently enabled for use.")

    class Config:
        use_enum_values = True

class PaymentCorridorCreate(PaymentCorridorBase):
    fees: conlist(CorridorFeeCreate, min_length=1) = Field(..., description="List of fees associated with this corridor.")
    limits: conlist(CorridorLimitCreate, min_length=1) = Field(..., description="List of limits associated with this corridor.")

class PaymentCorridorUpdate(BaseModel):
    # All fields are optional for update
    source_country_iso: Optional[str] = Field(None, min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    source_currency_iso: Optional[str] = Field(None, min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    destination_country_iso: Optional[str] = Field(None, min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    destination_currency_iso: Optional[str] = Field(None, min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    
    status: Optional[CorridorStatus] = None
    exchange_rate: Optional[float] = Field(None, gt=0)
    processing_time_hours: Optional[int] = Field(None, ge=1)
    is_enabled: Optional[bool] = None

    # For nested updates, we'll use the service layer to handle the complexity
    # We can add fields for fees and limits if a full replacement is desired, but for simplicity, we'll handle nested updates via separate endpoints or a more complex service method.
    # For this implementation, we'll focus on top-level updates and assume nested entities are managed separately or via full replacement on update.
    # To keep it simple for the CRUD service, we'll allow full replacement of fees/limits on update.
    fees: Optional[conlist(CorridorFeeCreate, min_length=1)] = None
    limits: Optional[conlist(CorridorLimitCreate, min_length=1)] = None

    class Config:
        use_enum_values = True

class PaymentCorridor(PaymentCorridorBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    fees: List[CorridorFee]
    limits: List[CorridorLimit]

    class Config:
        from_attributes = True
