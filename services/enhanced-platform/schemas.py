from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field

# --- Utility Schemas ---

class Message(BaseModel):
    """Generic message schema for error or success responses."""
    message: str

class Token(BaseModel):
    """Schema for JWT token response."""
    access_token: str
    token_type: str

class TokenData(BaseModel):
    """Schema for data contained in the JWT token."""
    email: Optional[str] = None

# --- User Schemas ---

class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    is_active: Optional[bool] = True
    is_superuser: Optional[bool] = False

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None

class UserInDB(UserBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# --- Party Schemas ---

class PartyBase(BaseModel):
    party_type: str = Field(..., pattern="^(Individual|Organization)$", description="Type of party: Individual or Organization")
    name: str
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = None
    address: Optional[str] = None
    is_active: Optional[bool] = True

class PartyCreate(PartyBase):
    pass

class PartyUpdate(PartyBase):
    party_type: Optional[str] = Field(None, pattern="^(Individual|Organization)$")
    name: Optional[str] = None

class Party(PartyBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# --- LandAsset Schemas ---

class LandAssetBase(BaseModel):
    parcel_id: str = Field(..., description="Unique cadastral or parcel identifier")
    name: str
    description: Optional[str] = None
    area_sqm: float = Field(..., gt=0, description="Area in square meters")
    owner_id: int = Field(..., description="ID of the owning Party")
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    zoning_code: Optional[str] = None
    is_active: Optional[bool] = True

class LandAssetCreate(LandAssetBase):
    pass

class LandAssetUpdate(LandAssetBase):
    parcel_id: Optional[str] = None
    name: Optional[str] = None
    area_sqm: Optional[float] = Field(None, gt=0)
    owner_id: Optional[int] = None

class LandAsset(LandAssetBase):
    id: int
    created_at: datetime
    updated_at: datetime
    # Nested relationship to be populated by the service layer
    owner: Optional[Party] = None

    class Config:
        from_attributes = True

# --- Agreement Schemas ---

class AgreementBase(BaseModel):
    agreement_type: str = Field(..., pattern="^(Lease|Permit|ROW)$", description="Type of agreement: Lease, Permit, or ROW")
    name: str
    land_asset_id: int = Field(..., description="ID of the associated LandAsset")
    party_id: int = Field(..., description="ID of the Party (Lessee/Permittee) in the agreement")
    start_date: datetime
    end_date: Optional[datetime] = None
    term_months: Optional[int] = Field(None, gt=0)
    status: str = Field(..., pattern="^(Active|Expired|Pending)$", description="Status of the agreement: Active, Expired, or Pending")
    payment_amount: Optional[float] = Field(None, ge=0)
    payment_frequency: Optional[str] = Field(None, pattern="^(Monthly|Annually|Quarterly|One-time)$")

class AgreementCreate(AgreementBase):
    pass

class AgreementUpdate(AgreementBase):
    agreement_type: Optional[str] = Field(None, pattern="^(Lease|Permit|ROW)$")
    name: Optional[str] = None
    land_asset_id: Optional[int] = None
    party_id: Optional[int] = None
    status: Optional[str] = Field(None, pattern="^(Active|Expired|Pending)$")

class Agreement(AgreementBase):
    id: int
    created_at: datetime
    updated_at: datetime
    # Nested relationships
    land_asset: Optional[LandAsset] = None
    party: Optional[Party] = None

    class Config:
        from_attributes = True
