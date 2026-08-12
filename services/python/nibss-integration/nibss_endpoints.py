"""
NIBSS Integration API Endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from service import NIBSSService, ServiceException, BankNotFound
from schemas import NameEnquiryRequest

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
async def verify_account(data: AccountVerificationRequest, db: Session = Depends(get_db)):
    """
    Verify a Nigerian bank account via a real NIBSS Name Enquiry.

    - 404 when the bank code is unknown locally or NIBSS cannot resolve the account.
    - 503 when the NIBSS provider is not configured or unreachable.
    Never returns a fabricated account name.
    """
    service = NIBSSService(db)
    try:
        bank = service.get_bank_by_code(data.bank_code)
        result = service.perform_name_enquiry(
            NameEnquiryRequest(account_number=data.account_number, bank_code=data.bank_code)
        )
    except BankNotFound as e:
        raise HTTPException(status_code=404, detail=e.message)
    except ServiceException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    if result.response_code != "00":
        raise HTTPException(
            status_code=404,
            detail=f"Account verification failed: {result.response_message or result.response_code}",
        )

    return AccountVerificationResponse(
        success=True,
        account_name=result.account_name,
        account_number=data.account_number,
        bank_name=bank.bank_name,
        verified=True,
    )
