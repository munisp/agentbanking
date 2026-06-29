from fastapi import APIRouter, HTTPException, responses, Header
from utils import create_logger
from adapters import TigerBeetleBusinessError
from schemas import (
    InitiatePaymentSchema,
    InitiateDepositSchema,
    InitiateDepositWithAccountNumberSchema,
    InitiateLoanPaymentSchema,
    InitiateLPOPaymentSchema,
    Context,
    InitiateInsurancePremiumPaymentSchema,
    SupplyChainFinancingPaymentSchema,
)
from services import PaymentService
from schemas.payment import ExternalTransferSchema, ExternalDebitSchema
from utils import get_config
from dapr.clients import DaprClient
import json
import hashlib

config = get_config()
logger = create_logger(__name__)
_dapr = None

payment_router = APIRouter()

logger = create_logger(__name__)


def _get_dapr_client() -> DaprClient:
    global _dapr
    if _dapr is None:
        _dapr = DaprClient()
    return _dapr


def _is_state_store_unavailable(error: Exception) -> bool:
    """True when the Dapr state store is not yet reachable (transient or config issue)."""
    message = str(error).lower()
    return (
        ("state store" in message and "not configured" in message)
        or "dapr health check timed out" in message
        or "connection refused" in message
        or "connection reset" in message
    )


def _check_idempotency(key: str, label: str) -> responses.JSONResponse | None:
    """
    Read idempotency key from Dapr state store.
    Returns a cached JSONResponse if the key exists, None otherwise.
    Raises on unexpected errors (not transient store unavailability).
    """
    try:
        existing = _get_dapr_client().get_state(config.STATE_STORE_NAME, key)
        if existing and existing.data:
            body = (
                existing.data.decode("utf-8")
                if isinstance(existing.data, (bytes, bytearray))
                else existing.data
            )
            logger.info(
                "idempotency_hit key=%s label=%s", key, label,
                extra={"idempotency_key": key, "label": label},
            )
            return responses.JSONResponse(content=json.loads(body), status_code=202)
    except Exception as exc:
        if _is_state_store_unavailable(exc):
            logger.warning(
                "idempotency_store_unavailable key=%s label=%s error=%s",
                key, label, str(exc),
            )
            # Fail-open: allow the request through but log the gap.
            # The write path will also fail, meaning retries are NOT protected
            # until the store recovers.  Ops must be alerted on this metric.
        else:
            logger.error(
                "idempotency_read_error key=%s label=%s error=%s",
                key, label, str(exc),
            )
            raise HTTPException(
                status_code=503,
                detail="Payment gateway temporarily unavailable. Please retry.",
            )
    return None


def _save_idempotency(key: str, body: dict, label: str) -> None:
    """Persist idempotency result to Dapr state store with best-effort."""
    try:
        _get_dapr_client().save_state(config.STATE_STORE_NAME, key, json.dumps(body))
        logger.debug("idempotency_saved key=%s label=%s", key, label)
    except Exception as exc:
        if _is_state_store_unavailable(exc):
            logger.warning(
                "idempotency_save_skipped key=%s label=%s error=%s",
                key, label, str(exc),
            )
        else:
            logger.error(
                "idempotency_save_error key=%s label=%s error=%s",
                key, label, str(exc),
            )


def _idempotency_key_for_payload(prefix: str, *parts: str) -> str:
    """Deterministic key derived from logical payload fields."""
    combined = ":".join(str(p) for p in parts)
    digest = hashlib.sha256(combined.encode()).hexdigest()[:32]
    return f"idempotency:{prefix}:{digest}"


def _raise_known_business_error(error: Exception):
    if isinstance(error, TigerBeetleBusinessError):
        raise HTTPException(status_code=400, detail=str(error))


@payment_router.post("/deposit")
def deposit(
    payload: InitiateDepositSchema,
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
    ledger_id: str = Header(..., alias="x-ledger-id"),
    mint_account_id: str = Header(..., alias="x-mint-account-id"),
    idempotency_key: str = Header(None, alias="x-idempotency-key"),
):
    """Deposit handler. Idempotent when x-idempotency-key header is supplied."""

    context = Context(
        tenant_id=tenant_id,
        keycloak_id=keycloak_id,
        ledger_id=ledger_id,
        mint_account_id=mint_account_id,
    )

    idem_key = (
        f"idempotency:deposit:{idempotency_key}"
        if idempotency_key
        else _idempotency_key_for_payload(
            "deposit", tenant_id, keycloak_id,
            str(getattr(payload, "amount", "")),
            str(getattr(payload, "account_id", "")),
        )
    )

    cached = _check_idempotency(idem_key, "deposit")
    if cached is not None:
        return cached

    try:
        payment_service = PaymentService()
        reference = payment_service.initiate_deposit(payload, context)
        resp_body = {"message": "success", "reference": reference}
        _save_idempotency(idem_key, resp_body, "deposit")
        return responses.JSONResponse(content=resp_body, status_code=200)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(
            "deposit_failed tenant=%s keycloak=%s error=%s",
            tenant_id, keycloak_id, str(e),
        )
        raise HTTPException(status_code=500, detail="Deposit failed.")


@payment_router.post("/deposit/account-number")
def deposit_with_account_number(
    payload: InitiateDepositWithAccountNumberSchema,
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
    ledger_id: str = Header(..., alias="x-ledger-id"),
    mint_account_id: str = Header(..., alias="x-mint-account-id"),
    idempotency_key: str = Header(None, alias="x-idempotency-key"),
):
    """Deposit handler using recipient account number. Idempotent via x-idempotency-key."""

    context = Context(
        tenant_id=tenant_id,
        keycloak_id=keycloak_id,
        ledger_id=ledger_id,
        mint_account_id=mint_account_id,
    )

    idem_key = (
        f"idempotency:deposit_acct:{idempotency_key}"
        if idempotency_key
        else _idempotency_key_for_payload(
            "deposit_acct", tenant_id,
            str(getattr(payload, "account_number", "")),
            str(getattr(payload, "amount", "")),
        )
    )

    cached = _check_idempotency(idem_key, "deposit_with_account_number")
    if cached is not None:
        return cached

    try:
        payment_service = PaymentService()
        reference = payment_service.initiate_deposit_with_account_number(payload, context)
        resp_body = {"message": "success", "reference": reference}
        _save_idempotency(idem_key, resp_body, "deposit_with_account_number")
        return responses.JSONResponse(content=resp_body, status_code=200)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(
            "deposit_account_number_failed tenant=%s error=%s", tenant_id, str(e),
        )
        raise HTTPException(status_code=500, detail="Deposit failed.")


@payment_router.post("/transfer")
def transfer(
    payload: InitiatePaymentSchema,
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
    ledger_id: str = Header(..., alias="x-ledger-id"),
    mint_account_id: str = Header(..., alias="x-mint-account-id"),
    idempotency_key: str = Header(None, alias="x-idempotency-key"),
):
    """Initiate transfer handler. Idempotent via x-idempotency-key header."""

    context = Context(
        tenant_id=tenant_id,
        keycloak_id=keycloak_id,
        ledger_id=ledger_id,
        mint_account_id=mint_account_id,
    )

    idem_key = (
        f"idempotency:transfer:{idempotency_key}"
        if idempotency_key
        else _idempotency_key_for_payload(
            "transfer", tenant_id, keycloak_id,
            str(getattr(payload, "payer", "")),
            str(getattr(payload, "payee", "")),
            str(getattr(payload, "amount", "")),
        )
    )

    cached = _check_idempotency(idem_key, "transfer")
    if cached is not None:
        return cached

    try:
        payment_service = PaymentService()
        reference = payment_service.initiate_transfer(payload, context)

        try:
            payment_service.notify_external_systems(reference, payload, context)
        except Exception as notify_error:
            logger.error(
                "notify_external_systems_failed reference=%s error=%s",
                reference, str(notify_error),
            )

        resp_body = {"message": "success", "reference": reference}
        _save_idempotency(idem_key, resp_body, "transfer")
        return responses.JSONResponse(content=resp_body, status_code=200)
    except HTTPException as e:
        raise e
    except Exception as e:
        _raise_known_business_error(e)
        logger.error(
            "transfer_failed tenant=%s keycloak=%s error=%s",
            tenant_id, keycloak_id, str(e),
        )
        raise HTTPException(status_code=500, detail=str(e) or "Transfer failed.")


@payment_router.post("/loan")
def loan_payment(
    payload: InitiateLoanPaymentSchema,
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
    ledger_id: str = Header(..., alias="x-ledger-id"),
    mint_account_id: str = Header(..., alias="x-mint-account-id"),
    idempotency_key: str = Header(None, alias="x-idempotency-key"),
):
    """Loan Payment handler. Idempotent via x-idempotency-key."""

    context = Context(
        tenant_id=tenant_id,
        keycloak_id=keycloak_id,
        ledger_id=ledger_id,
        mint_account_id=mint_account_id,
    )

    idem_key = (
        f"idempotency:loan:{idempotency_key}"
        if idempotency_key
        else _idempotency_key_for_payload(
            "loan", tenant_id, keycloak_id,
            str(getattr(payload, "loan_id", "")),
            str(getattr(payload, "amount", "")),
        )
    )

    cached = _check_idempotency(idem_key, "loan_payment")
    if cached is not None:
        return cached

    try:
        payment_service = PaymentService()
        reference = payment_service.initiate_loan_payment(payload, context)
        resp_body = {"message": "success", "reference": reference}
        _save_idempotency(idem_key, resp_body, "loan_payment")
        return responses.JSONResponse(content=resp_body, status_code=200)
    except HTTPException as e:
        raise e
    except Exception as e:
        _raise_known_business_error(e)
        logger.error(
            "loan_payment_failed tenant=%s keycloak=%s error=%s",
            tenant_id, keycloak_id, str(e),
        )
        raise HTTPException(status_code=500, detail=str(e) or "Payment failed.")


@payment_router.post("/lpo")
def lpo_payment(
    payload: InitiateLPOPaymentSchema,
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
    ledger_id: str = Header(..., alias="x-ledger-id"),
    mint_account_id: str = Header(..., alias="x-mint-account-id"),
):
    """LPO payment handler."""

    context = Context(
        tenant_id=tenant_id,
        keycloak_id=keycloak_id,
        ledger_id=ledger_id,
        mint_account_id=mint_account_id,
    )

    try:
        payment_service = PaymentService()

        reference = payment_service.initiate_lpo_payment(payload, context)

        return responses.JSONResponse(
            content={"message": "success", "reference": reference}, status_code=200
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        _raise_known_business_error(e)
        logger.error(f"Unexpected error during payment: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e) or "Payment failed.")


@payment_router.post("/insurance-premium")
def insurance_premium_payment(
    payload: InitiateInsurancePremiumPaymentSchema,
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
    ledger_id: str = Header(..., alias="x-ledger-id"),
    mint_account_id: str = Header(..., alias="x-mint-account-id"),
):
    """Insurance payment handler."""

    context = Context(
        tenant_id=tenant_id,
        keycloak_id=keycloak_id,
        ledger_id=ledger_id,
        mint_account_id=mint_account_id,
    )

    try:
        payment_service = PaymentService()

        reference = payment_service.initiate_insurance_premium_payment(payload, context)

        return responses.JSONResponse(
            content={"message": "success", "reference": reference}, status_code=200
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        _raise_known_business_error(e)
        logger.error(f"Unexpected error during payment: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e) or "Payment failed.")


@payment_router.post("/supply-chain-financing")
def supply_chain_financing_payment(
    payload: SupplyChainFinancingPaymentSchema,
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
    ledger_id: str = Header(..., alias="x-ledger-id"),
    mint_account_id: str = Header(..., alias="x-mint-account-id"),
):
    """Supply chain financing payment handler."""

    context = Context(
        tenant_id=tenant_id,
        keycloak_id=keycloak_id,
        ledger_id=ledger_id,
        mint_account_id=mint_account_id,
    )

    try:
        payment_service = PaymentService()

        reference = payment_service.supply_chain_financing_payment(payload, context)

        return responses.JSONResponse(
            content={"message": "success", "reference": reference}, status_code=200
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        _raise_known_business_error(e)
        logger.error(f"Unexpected error during payment: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e) or "Payment failed.")


@payment_router.post("/transfer/credit")
def transfer_credit(
    payload: ExternalTransferSchema,
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
    ledger_id: str = Header(..., alias="x-ledger-id"),
    mint_account_id: str = Header(..., alias="x-mint-account-id"),
):
    """External credit (deposit) handler."""

    context = Context(
        tenant_id=tenant_id,
        keycloak_id=keycloak_id,
        ledger_id=ledger_id,
        mint_account_id=mint_account_id,
    )

    idem_key = f"idempotency:transfer:credit:{payload.transactionId}"

    cached = _check_idempotency(idem_key, "external_credit")
    if cached is not None:
        return cached

    try:
        logger.info(
            "external_credit_received transaction_id=%s tenant=%s amount=%s",
            payload.transactionId, context.tenant_id,
            getattr(payload, "amount", "unknown"),
        )
        payment_service = PaymentService()
        reference = payment_service.process_external_credit(payload, context)
        resp_body = {"message": "success", "reference": reference}
        _save_idempotency(idem_key, resp_body, "external_credit")
        return responses.JSONResponse(content=resp_body, status_code=202)
    except HTTPException as e:
        raise e
    except Exception as e:
        _raise_known_business_error(e)
        logger.error(
            "external_credit_failed transaction_id=%s error=%s",
            payload.transactionId, str(e),
        )
        raise HTTPException(status_code=500, detail=str(e) or "External credit failed.")


@payment_router.post("/transfer/debit")
def transfer_debit(
    payload: ExternalDebitSchema,
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
    ledger_id: str = Header(..., alias="x-ledger-id"),
    mint_account_id: str = Header(..., alias="x-mint-account-id"),
):
    """External debit (withdraw) handler."""

    context = Context(
        tenant_id=tenant_id,
        keycloak_id=keycloak_id,
        ledger_id=ledger_id,
        mint_account_id=mint_account_id,
    )

    idem_key = f"idempotency:transfer:debit:{payload.transactionId}"

    cached = _check_idempotency(idem_key, "external_debit")
    if cached is not None:
        return cached

    try:
        logger.info(
            "external_debit_received transaction_id=%s tenant=%s amount=%s",
            payload.transactionId, context.tenant_id,
            getattr(getattr(payload, "amount", None), "amount", "unknown"),
        )
        payment_service = PaymentService()
        reference = payment_service.process_external_debit(payload, context)
        resp_body = {"message": "success", "reference": reference}
        _save_idempotency(idem_key, resp_body, "external_debit")
        return responses.JSONResponse(content=resp_body, status_code=202)
    except HTTPException as e:
        raise e
    except Exception as e:
        _raise_known_business_error(e)
        logger.error(
            "external_debit_failed transaction_id=%s error=%s",
            payload.transactionId, str(e),
        )
        raise HTTPException(status_code=500, detail=str(e) or "External debit failed.")
