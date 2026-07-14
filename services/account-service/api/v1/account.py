from fastapi import APIRouter, Depends, HTTPException, responses, Header
from sqlalchemy.orm import Session
from database import get_session
from utils import create_logger
from services import AccountService
from schemas.v1 import (
    CreateAccountSchema,
    SetupPinSchema,
    VerifyPinSchema,
    CheckAccountSchema,
    Context,
)

logger = create_logger(__name__)

account_router = APIRouter()


# def _enum_value_or_self(value):
#     return getattr(value, "value", value)


@account_router.post("")
def create_account(
    payload: CreateAccountSchema,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
    ledger_id: str = Header(..., alias="x-ledger-id"),
):
    """Create account route handler."""

    context = Context(tenant_id=tenant_id, keycloak_id=keycloak_id, ledger_id=ledger_id)

    try:
        account_service = AccountService(db)
        account = account_service.create_account(payload, context)

        # Publish Kafka event for account creation
        # KafkaClientInstance.publish_account_event(
        #     event_type=AccountEventTypes.ACCOUNT_CREATED,
        #     account_id=account.id,
        #     tenant_id=tenant_id,
        #     status=_enum_value_or_self(getattr(account, "status", None)),
        #     metadata={
        #         "name": account.name,
        #         "account_number": account.account_number,
        #         "account_type": _enum_value_or_self(
        #             getattr(account, "account_type", None)
        #         ),
        #         "keycloak_id": account.keycloak_id,
        #     },
        # )

        return responses.JSONResponse(
            content={"message": "success", "account": account.to_dict()},
            status_code=200,
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during create_account: {str(e)}")
        raise HTTPException(status_code=500, detail="Create account failed.")


@account_router.get("/all")
def get_accounts(
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
    ledger_id: str = Header(..., alias="x-ledger-id"),
):
    """Get account route handler."""

    context = Context(tenant_id=tenant_id, keycloak_id=keycloak_id, ledger_id=ledger_id)

    try:
        account_service = AccountService(db)

        accounts = account_service.get_accounts(context)

        return responses.JSONResponse(
            content={
                "message": "success",
                "account": accounts,  # Already converted to dict in service layer
            },
            status_code=200,
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during get_accounts: {str(e)}")
        raise HTTPException(status_code=500, detail="Get accounts failed.")


@account_router.get("/user/all")
def get_accounts_by_user(
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
    ledger_id: str = Header(..., alias="x-ledger-id"),
):
    """Get account route handler."""

    context = Context(tenant_id=tenant_id, keycloak_id=keycloak_id, ledger_id=ledger_id)

    try:
        account_service = AccountService(db)

        accounts = account_service.get_accounts_by_user(context)

        return responses.JSONResponse(
            content={
                "message": "success",
                "account": accounts,  # Already converted to dict in service layer
            },
            status_code=200,
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during get_accounts_by_user: {str(e)}")
        raise HTTPException(status_code=500, detail="Get accounts failed.")


@account_router.get("/{account_id}")
def get_account_by_id(
    account_id: int,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
    ledger_id: str = Header(..., alias="x-ledger-id"),
):
    """Get account route handler."""

    context = Context(tenant_id=tenant_id, keycloak_id=keycloak_id, ledger_id=ledger_id)

    try:
        print(context)
        logger.info(f"get account by if {context}")
        account_service = AccountService(db)

        account = account_service.get_account_by_id(account_id, context)

        if not account:
            raise HTTPException(status_code=404, detail="Account not found.")

        return responses.JSONResponse(
            content={"message": "success", "account": account}, status_code=200
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during get_account: {str(e)}")
        raise HTTPException(status_code=500, detail="Get account failed.")


@account_router.get("/account-number/{account_number}")
def get_account_by_account_number(
    account_number: str,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
    ledger_id: str = Header(..., alias="x-ledger-id"),
):
    """Get account by account number route handler."""

    context = Context(tenant_id=tenant_id, keycloak_id=keycloak_id, ledger_id=ledger_id)

    try:
        # logger.info(
        #     f"Fetching account with account number: {account_number} for tenant: {tenant_id}, context: {context}"
        # )
        account_service = AccountService(db)

        account = account_service.get_account_by_account_number(account_number, context)

        if not account:
            raise HTTPException(status_code=404, detail="Account not found.")

        return responses.JSONResponse(
            content={"message": "success", "account": account}, status_code=200
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during get_account: {str(e)}")
        raise HTTPException(status_code=500, detail="Get account failed.")


@account_router.get("/keycloak/{id}")
def get_account_by_keycloak_id(
    id: str,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
    ledger_id: str = Header(..., alias="x-ledger-id"),
):
    """Get account route handler."""

    context = Context(tenant_id=tenant_id, keycloak_id=keycloak_id, ledger_id=ledger_id)

    try:
        account_service = AccountService(db)

        account = account_service.get_account_by_keycloak_id(id, context)

        if not account:
            raise HTTPException(status_code=404, detail="Account not found.")

        return responses.JSONResponse(
            content={"message": "success", "account": account}, status_code=200
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during get_account: {str(e)}")
        raise HTTPException(status_code=500, detail="Get account failed.")


@account_router.post("/check-account")
def check_account(
    payload: CheckAccountSchema,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
    ledger_id: str = Header(..., alias="x-ledger-id"),
):
    """Check an account's eligibility for a transaction"""

    context = Context(tenant_id=tenant_id, keycloak_id=keycloak_id, ledger_id=ledger_id)

    try:
        account_service = AccountService(db)

        account_service.check_account(payload.account_id, payload.pin, context)

        return responses.JSONResponse(content={"message": "success"}, status_code=200)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during check_account: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@account_router.post("/setup-pin")
def setup_pin(
    payload: SetupPinSchema,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
    ledger_id: str = Header(..., alias="x-ledger-id"),
):
    """Create account route handler."""

    context = Context(tenant_id=tenant_id, keycloak_id=keycloak_id, ledger_id=ledger_id)

    try:
        account_service = AccountService(db)

        account_service.setup_pin(payload.pin, context)

        return responses.JSONResponse(content={"message": "success"}, status_code=200)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during pin setup: {str(e)}")
        raise HTTPException(status_code=500, detail="Pin setup failed.")


@account_router.post("/verify-pin")
def verify_pin(
    payload: VerifyPinSchema,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
    ledger_id: str = Header(..., alias="x-ledger-id"),
):
    """Create account route handler."""

    context = Context(tenant_id=tenant_id, keycloak_id=keycloak_id, ledger_id=ledger_id)

    try:
        account_service = AccountService(db)

        is_valid = account_service.verify_pin(payload.pin, context)

        if not is_valid:
            raise Exception("Invalid PIN")

        return responses.JSONResponse(content={"message": "success"}, status_code=200)
    except HTTPException as e:
        raise e
    except Exception:
        logger.error("Invalid PIN")
        raise HTTPException(status_code=400, detail="Invalid PIN")
