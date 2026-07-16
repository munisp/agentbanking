from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field
from models import OnboardingStatus, DocumentType, VerificationStatus

# --- Enums Schemas ---

class OnboardingStatusSchema(BaseModel):
    status: OnboardingStatus

class DocumentTypeSchema(BaseModel):
    type: DocumentType

class VerificationStatusSchema(BaseModel):
    status: VerificationStatus

# --- Base Schemas ---

class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=1)
    phone_number: Optional[str] = None

class KYCProfileBase(BaseModel):
    date_of_birth: date
    address_line_1: str = Field(..., min_length=1)
    city: str = Field(..., min_length=1)
    country: str = Field(..., min_length=1)
    nationality: str = Field(..., min_length=1)

class DocumentBase(BaseModel):
    document_type: DocumentType
    file_path: str = Field(..., min_length=1) # URL or path to the document

# --- Request Schemas (Input) ---

# Step 1: Basic Info & Registration
class UserCreate(UserBase):
    password: str = Field(..., min_length=8)

# Step 2: Identity Info (KYC)
class KYCProfileCreate(KYCProfileBase):
    pass

# Step 3: Document Upload
class DocumentUpload(DocumentBase):
    pass

# Update Schemas
class UserUpdate(UserBase):
    full_name: Optional[str] = None
    phone_number: Optional[str] = None

class KYCProfileUpdate(KYCProfileBase):
    date_of_birth: Optional[date] = None
    address_line_1: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    nationality: Optional[str] = None

class DocumentUpdateStatus(BaseModel):
    verification_status: VerificationStatus
    rejection_reason: Optional[str] = None

# --- Response Schemas (Output) ---

class Document(DocumentBase):
    id: int
    user_id: int
    upload_date: datetime
    verification_status: VerificationStatus
    rejection_reason: Optional[str] = None

    class Config:
        orm_mode = True
        use_enum_values = True

class KYCProfile(KYCProfileBase):
    id: int
    user_id: int
    risk_score: float
    last_reviewed_at: Optional[datetime] = None

    class Config:
        orm_mode = True
        use_enum_values = True

class User(UserBase):
    id: int
    onboarding_status: OnboardingStatus
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    # Relationships will be loaded dynamically in the service layer, but we can include them in the response schema
    kyc_profile: Optional[KYCProfile] = None
    documents: List[Document] = []

    class Config:
        orm_mode = True
        use_enum_values = True

class UserList(BaseModel):
    users: List[User]

class StatusResponse(BaseModel):
    message: str
    status: OnboardingStatus