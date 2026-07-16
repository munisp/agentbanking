from fastapi import APIRouter , HTTPException, responses, Header
from utils import create_logger
from schemas import GenerateQRSchema, ValidateQRSchema, Context
from services import QRService

qr_router = APIRouter()

logger = create_logger(__name__)

@qr_router.post("/generate")
def generate_qr_code(
    payload: GenerateQRSchema,
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
    ledger_id: str = Header(..., alias="x-ledger-id"),
    mint_account_id: str = Header(..., alias="x-mint-account-id"),
):
    """Generate QR code handler."""

    context = Context(
        tenant_id=tenant_id,
        keycloak_id=keycloak_id,
        ledger_id=ledger_id,
        mint_account_id=mint_account_id,
    )

    try:
        qr_service = QRService()

        qr_code_data = qr_service.generate_qr_code(payload, context)

        return responses.JSONResponse(content={
                "message": "success",
                "qr_code_data": qr_code_data
            }, status_code=200)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during QR code generation: {str(e)}")
        raise HTTPException(status_code=500, detail="QR code generation failed.")

@qr_router.post("/validate")
def validate_qr_code(
    payload: ValidateQRSchema,
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
    ledger_id: str = Header(..., alias="x-ledger-id"),
    mint_account_id: str = Header(..., alias="x-mint-account-id"),
):
    """Validate QR code handler."""

    context = Context(
        tenant_id=tenant_id,
        keycloak_id=keycloak_id,
        ledger_id=ledger_id,
        mint_account_id=mint_account_id,
    )

    try:
        qr_service = QRService()

        is_valid = qr_service.validate_qr_code(payload, context)

        return responses.JSONResponse(content={
                "message": "success",
                "is_valid": is_valid
            }, status_code=200)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during QR code validation: {str(e)}")
        raise HTTPException(status_code=500, detail="QR code validation failed.")
