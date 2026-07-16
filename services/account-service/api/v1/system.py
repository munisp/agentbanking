from fastapi import APIRouter, Depends, HTTPException, responses, Header
from sqlalchemy.orm import Session
from database import get_session
from schemas.v1 import Context
from services import AccountService
from utils import create_logger

system_router = APIRouter()

logger = create_logger(__name__)


# @system_router.post("/")
# def test_system(
#     db: Session = Depends(get_session),
#     tenant_id: str = Header(..., alias="x-tenant-id"),
#     keycloak_id: str = Header(..., alias="x-keycloak-id"),
#     ledger_id: str = Header(..., alias="x-ledger-id"),
# ):
#     """Test system route handler."""

#     context = Context(tenant_id=tenant_id, keycloak_id=keycloak_id, ledger_id=ledger_id)

#     try:
#         account_service = AccountService(db)
#         result = account_service.test_system(context)

#         return responses.JSONResponse(
#             content={"message": "success", "result": result}, status_code=200
#         )
#     except HTTPException as e:
#         raise e
#     except Exception as e:
#         logger.error(f"Unexpected error during test_system: {str(e)}")
#         raise HTTPException(status_code=500, detail="Test system failed.")


@system_router.post("")
@system_router.post("/create-mint-account")
def create_mint_account(
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
    ledger_id: str = Header(..., alias="x-ledger-id"),
):
    """Create mint account"""

    context = Context(
        tenant_id=tenant_id,
        keycloak_id=keycloak_id,
        ledger_id=ledger_id,
    )

    try:
        account_service = AccountService(db)

        accounts = account_service.create_mint_account(context)

        return responses.JSONResponse(
            content={
                "message": "success",
                "accounts": [account.to_dict() for account in accounts],
            },
            status_code=200,
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during create_account: {str(e)}")
        raise HTTPException(status_code=500, detail="Create account failed.")


@system_router.get("")
@system_router.get("/create-mint-account")
def get_mint_account(
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
    ledger_id: str = Header(..., alias="x-ledger-id"),
):
    """Get mint account"""

    context = Context(
        tenant_id=tenant_id,
        keycloak_id=keycloak_id,
        ledger_id=ledger_id,
    )

    try:
        account_service = AccountService(db)

        account = account_service.get_mint_account(context)

        return responses.JSONResponse(content={**account.to_dict()}, status_code=200)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during create_account: {str(e)}")
        raise HTTPException(status_code=500, detail="Create account failed.")
