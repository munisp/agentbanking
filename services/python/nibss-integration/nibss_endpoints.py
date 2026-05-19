"""
NIBSS Integration API Endpoints
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/nibss", tags=["nibss"])

class AccountVerificationRequest(BaseModel):
    account_number: str
    bank_code: str

class AccountVerificationResponse(BaseModel):
    success: bool
    account_name: str
    account_number: str
    bank_name: str
    verified: bool

@router.post("/verify-account", response_model=AccountVerificationResponse)
async def verify_account(data: AccountVerificationRequest):
    """Verify Nigerian bank account via NIBSS."""
    # Mock NIBSS Name Enquiry API call
    # In production, integrate with actual NIBSS API
    
    bank_names = {
        "058": "Guaranty Trust Bank",
        "044": "Access Bank",
        "033": "United Bank for Africa"
    }
    
    return {
        "success": True,
        "account_name": "JOHN DOE",
        "account_number": data.account_number,
        "bank_name": bank_names.get(data.bank_code, "Unknown Bank"),
        "verified": True
    }
