from pydantic import BaseModel, Field, EmailStr, validator
from typing import List, Optional
from datetime import datetime
from models import KYCStatus, DocumentType, CheckType, CheckStatus

# --- Base Schemas for Enums ---
class KYCStatusSchema(BaseModel):
    status: KYCStatus

class DocumentTypeSchema(BaseModel):
    type: DocumentType

class CheckTypeSchema(BaseModel):
    type: CheckType

class CheckStatusSchema(BaseModel):
    status: CheckStatus

# --- Document Schemas ---
class KYCDocumentBase(BaseModel):
    document_type: DocumentType = Field(..., description="Type of the document being uploaded.")
    file_url: str = Field(..., description="URL to the stored document file.")

class KYCDocumentCreate(KYCDocumentBase):
    pass

class KYCDocumentUpdate(BaseModel):
    verification_status: CheckStatus = Field(..., description="Manual update of the document verification status.")

class KYCDocumentInDB(KYCDocumentBase):
    id: int
    kyc_record_id: int
    verification_status: CheckStatus
    uploaded_at: datetime

    class Config:
        from_attributes = True

# --- Check Schemas ---
class KYCCheckBase(BaseModel):
    check_type: CheckType = Field(..., description="Type of the compliance check performed.")
    provider_response: Optional[str] = Field(None, description="Raw response from the external check provider.")

class KYCCheckCreate(KYCCheckBase):
    check_status: CheckStatus = Field(CheckStatus.PENDING, description="Initial status of the check.")

class KYCCheckUpdate(BaseModel):
    check_status: CheckStatus = Field(..., description="The final status of the check.")
    provider_response: Optional[str] = Field(None, description="Updated raw response from the external check provider.")
    is_manual_override: Optional[bool] = Field(False, description="Flag if the status was manually overridden.")

class KYCCheckInDB(KYCCheckBase):
    id: int
    kyc_record_id: int
    check_status: CheckStatus
    is_manual_override: bool
    performed_at: datetime

    class Config:
        from_attributes = True

# --- KYC Record Schemas ---
class KYCRecordBase(BaseModel):
    customer_id: str = Field(..., min_length=1, description="External ID of the customer.")

class KYCRecordCreate(KYCRecordBase):
    pass

class KYCRecordUpdate(BaseModel):
    status: Optional[KYCStatus] = Field(None, description="The overall status of the KYC record.")
    risk_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="The calculated risk score (0.0 to 1.0).")
    reviewer_id: Optional[str] = Field(None, description="ID of the internal reviewer.")
    rejection_reason: Optional[str] = Field(None, description="Reason for rejection, if applicable.")

class KYCRecordInDB(KYCRecordBase):
    id: int
    status: KYCStatus
    risk_score: float
    reviewer_id: Optional[str]
    rejection_reason: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    
    # Nested relationships for full detail response
    documents: List[KYCDocumentInDB] = []
    checks: List[KYCCheckInDB] = []

    class Config:
        from_attributes = True

# --- List Response Schema ---
class KYCRecordList(BaseModel):
    total: int
    records: List[KYCRecordInDB]

# --- Utility Schemas ---
class Message(BaseModel):
    message: str