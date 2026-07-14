from fastapi import APIRouter, Depends, HTTPException, responses, Header
from sqlalchemy.orm import Session
from database import get_session
from utils import create_logger
from services import BankService
from schemas.v1 import CreateBankSchema, Context

logger = create_logger(__name__)

bank_router = APIRouter()

@bank_router.post("")
def create_bank(
    payload: CreateBankSchema, 
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
    ledger_id: str = Header(..., alias="x-ledger-id"),
):
    """Create bank route handler."""

    context = Context(
        tenant_id=tenant_id,
        keycloak_id=keycloak_id,
        ledger_id=ledger_id
    )

    try:
        bank_service = BankService(db)
        
        bank = bank_service.create_bank(payload, context)

        return responses.JSONResponse(content={
            "message": "success",
            "bank": bank.to_dict()
        }, status_code=200)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during create_bank: {str(e)}")
        raise HTTPException(status_code=500, detail="Create bank failed.")

@bank_router.get("")
def get_banks(
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
    ledger_id: str = Header(..., alias="x-ledger-id"),
):
    """Get banks route handler."""

    context = Context(
        tenant_id=tenant_id,
        keycloak_id=keycloak_id,
        ledger_id=ledger_id
    )

    try:
        bank_service = BankService(db)
        
        banks = bank_service.get_banks(context)

        return responses.JSONResponse(content={
            "message": "success",
            "banks": [b.to_dict() for b in banks]
        }, status_code=200)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during get_banks: {str(e)}")
        raise HTTPException(status_code=500, detail="Get banks failed.")
