from fastapi import APIRouter, Depends, HTTPException, responses, Header
from utils import create_logger
from schemas import InitiateSystemPayoutSchema, Context
from services import PaymentService

system_router = APIRouter()

logger = create_logger(__name__)

@system_router.post("/payout")
def payout(
    payload: InitiateSystemPayoutSchema,
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
    ledger_id: str = Header(..., alias="x-ledger-id"),
    mint_account_id: str = Header(..., alias="x-mint-account-id"),
):
    """System payout handler."""

    context = Context(
        tenant_id=tenant_id,
        keycloak_id=keycloak_id,
        ledger_id=ledger_id,
        mint_account_id=mint_account_id,
    )

    try:
        payment_service = PaymentService()

        reference = payment_service.initiate_system_payout(payload, context)

        return responses.JSONResponse(content={
                "message": "success",
                "reference": reference
            }, status_code=200)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during system payout: {str(e)}")
        raise HTTPException(status_code=500, detail="System payout failed.")
