"""
Beneficiary API Endpoints
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

router = APIRouter(prefix="/api/beneficiaries", tags=["beneficiaries"])

class BeneficiaryCreate(BaseModel):
    name: str
    account_number: str
    bank_code: str
    nickname: Optional[str] = None

class BeneficiaryResponse(BaseModel):
    id: int
    name: str
    account_number: str
    bank_code: str
    bank_name: str
    verified: bool
    created_at: datetime

class BeneficiaryListResponse(BaseModel):
    beneficiaries: List[BeneficiaryResponse]
    total: int
    page: int
    limit: int

@router.get("/", response_model=BeneficiaryListResponse)
async def list_beneficiaries(skip: int = 0, limit: int = 20):
    """List all beneficiaries."""
    # Mock data
    beneficiaries = [
        {
            "id": 1,
            "name": "John Doe",
            "account_number": "0123456789",
            "bank_code": "058",
            "bank_name": "GTBank",
            "verified": True,
            "created_at": datetime.utcnow()
        }
    ]
    
    return {
        "beneficiaries": beneficiaries,
        "total": len(beneficiaries),
        "page": skip // limit + 1,
        "limit": limit
    }

@router.post("/", response_model=BeneficiaryResponse, status_code=201)
async def create_beneficiary(data: BeneficiaryCreate):
    """Create new beneficiary."""
    # Verify account (mock)
    
    return {
        "id": 1,
        "name": data.name,
        "account_number": data.account_number,
        "bank_code": data.bank_code,
        "bank_name": "GTBank",
        "verified": True,
        "created_at": datetime.utcnow()
    }
