from pydantic import BaseModel, Field, EmailStr, condecimal
from datetime import datetime
from typing import Optional, List
from decimal import Decimal
import enum

# --- Enums from models.py (re-defined for Pydantic) ---
class TransactionType(str, enum.Enum):
    MINT = "MINT"
    BURN = "BURN"
    TRANSFER = "TRANSFER"
    COLLATERAL_DEPOSIT = "COLLATERAL_DEPOSIT"
    COLLATERAL_WITHDRAWAL = "COLLATERAL_WITHDRAWAL"

class VaultStatus(str, enum.Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    LIQUIDATED = "LIQUIDATED"

class CollateralAsset(str, enum.Enum):
    ETH = "ETH"
    BTC = "BTC"
    USDC = "USDC"
    T_BILLS = "T_BILLS"

# --- Base Schemas ---
class BaseSchema(BaseModel):
    """Base schema for common fields."""
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        # Pydantic V1 compatibility for FastAPI
        orm_mode = True
        # Pydantic V2 compatibility
        from_attributes = True

# --- User Schemas ---
class UserBase(BaseModel):
    public_address: str = Field(..., description="The user's public blockchain address.")
    email: Optional[EmailStr] = Field(None, description="Optional email address for communication.")

class UserCreate(UserBase):
    pass

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = Field(None, description="Optional email address for communication.")
    is_active: Optional[bool] = None

class UserResponse(BaseSchema, UserBase):
    is_active: bool
    # Relationships will be added later if needed, but for now, keep it simple.

# --- Transaction Schemas (Forward declaration for Vault) ---
class TransactionBase(BaseModel):
    transaction_type: TransactionType
    stablecoin_amount: condecimal(max_digits=30, decimal_places=18) = Field(..., description="Amount of stablecoin involved in the transaction.")
    collateral_change: Optional[condecimal(max_digits=30, decimal_places=18)] = Field(None, description="Change in collateral amount for vault transactions.")
    tx_hash: Optional[str] = Field(None, description="Blockchain transaction hash.")

class TransactionCreate(TransactionBase):
    user_id: int
    vault_id: Optional[int] = None

class TransactionResponse(BaseSchema, TransactionBase):
    user_id: int
    vault_id: Optional[int] = None

# --- Vault Schemas ---
class VaultBase(BaseModel):
    collateral_asset: CollateralAsset
    collateral_amount: condecimal(max_digits=30, decimal_places=18) = Field(..., description="Current amount of collateral in the vault.")
    stablecoin_debt: condecimal(max_digits=30, decimal_places=18) = Field(..., description="Current stablecoin debt owed by the vault.")
    collateralization_ratio: float = Field(..., description="Current collateralization ratio (e.g., 1.5 for 150%).")
    status: VaultStatus = VaultStatus.OPEN

class VaultCreate(VaultBase):
    owner_id: int
    # For creation, we only need the initial collateral and debt, ratio is calculated.
    collateral_amount: condecimal(max_digits=30, decimal_places=18) = Field(..., gt=Decimal(0), description="Initial collateral amount.")
    stablecoin_debt: condecimal(max_digits=30, decimal_places=18) = Field(..., ge=Decimal(0), description="Initial stablecoin debt.")
    collateralization_ratio: Optional[float] = None # Will be calculated by service

class VaultUpdate(BaseModel):
    collateral_amount: Optional[condecimal(max_digits=30, decimal_places=18)] = Field(None, description="New collateral amount.")
    stablecoin_debt: Optional[condecimal(max_digits=30, decimal_places=18)] = Field(None, description="New stablecoin debt.")
    status: Optional[VaultStatus] = None

class VaultResponse(BaseSchema, VaultBase):
    owner_id: int
    # Include a list of transactions for a full response, but this can be heavy.
    # For simplicity in the main response, we'll omit the full list, but keep the relationship.
    # transactions: List[TransactionResponse] = []

# --- Global State Schemas ---
class GlobalStateResponse(BaseModel):
    total_stablecoin_supply: condecimal(max_digits=30, decimal_places=18)
    total_collateral_value: condecimal(max_digits=30, decimal_places=18)
    last_updated: datetime

    class Config:
        orm_mode = True
        from_attributes = True