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
import os

config = get_config()
logger = create_logger(__name__)
_dapr = None

payment_router = APIRouter()

logger = create_logger(__name__)

# NF-FF-21: ledger identity is deployment configuration, never caller input.
# Client-supplied x-ledger-id / x-mint-account-id headers are IGNORED; the
# service fails closed at startup when the configured values are missing.
_TB_LEDGER_ID = os.environ.get("TB_LEDGER_ID")
_TB_MINT_ACCOUNT_ID = os.environ.get("TB_MINT_ACCOUNT_ID")
if not _TB_LEDGER_ID or not _TB_MINT_ACCOUNT_ID:
    raise RuntimeError(
        "TB_LEDGER_ID and TB_MINT_ACCOUNT_ID environment variables must be set; "
        "refusing to start because caller-supplied ledger identity is not trusted."
    )


def _resolve_ledger_ids(ledger_id_header, mint_account_id_header) -> tuple:
    """Return the configured ledger identity, warning when client headers differ."""
    if ledger_id_header and ledger_id_header != _TB_LEDGER_ID:
        logger.warning(
            "Ignoring client-supplied x-ledger-id=%s (differs from configured ledger)",
            ledger_id_header,
        )
    if mint_account_id_header and mint_account_id_header != _TB_MINT_ACCOUNT_ID:
        logger.warning(
            "Ignoring client-supplied x-mint-account-id (differs from configured value)"
        )
    return _TB_LEDGER_ID, _TB_MINT_ACCOUNT_ID


def _get_dapr_client() -> DaprClient:
    global _dapr
    if _dapr is None:
        _dapr = DaprClient()
    return _dapr


# NF-FF-13/20: idempotency is enforced as an ATOMIC first-write-wins claim
# against the Dapr state store, bound to a hash of the request payload.
# Money-movement endpoints FAIL CLOSED: any state-store error aborts the
# request with 503 instead of letting an unprotected duplicate through.

try:  # Dapr python SDK state options (etag / first-write concurrency)
    from dapr.clients.grpc._state import Concurrency, Consistency, StateOptions

    _FIRST_WRITE_SUPPORTED = True
except Exception:  # pragma: no cover - older SDKs without state options
    _FIRST_WRITE_SUPPORTED = False


def _payload_fingerprint(payload, *extra) -> str:
    """Stable SHA-256 fingerprint binding an idempotency key to its payload."""
    try:
        raw = payload.model_dump_json()  # pydantic v2
    except AttributeError:
        raw = payload.json()  # pydantic v1
    combined = "|".join([raw, *[str(e) for e in extra]])
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def _read_idempotency_record(client, key: str, label: str) -> dict | None:
    """Read the idempotency record, failing closed (503) on any store error."""
    try:
        existing = client.get_state(config.STATE_STORE_NAME, key)
    except Exception as exc:
        logger.error(
            "idempotency_read_error key=%s label=%s error=%s", key, label, str(exc)
        )
        raise HTTPException(
            status_code=503,
            detail="Payment gateway temporarily unavailable. Please retry.",
        )
    if not existing or not existing.data:
        return None
    body = (
        existing.data.decode("utf-8")
        if isinstance(existing.data, (bytes, bytearray))
        else existing.data
    )
    try:
        return json.loads(body)
    except (TypeError, ValueError):
        logger.error("idempotency_record_corrupt key=%s label=%s", key, label)
        raise HTTPException(
            status_code=503,
            detail="Payment gateway temporarily unavailable. Please retry.",
        )


def _claim_idempotency(
    key: str, payload_hash: str, label: str
) -> responses.JSONResponse | None:
    """Atomically claim an idempotency key (first-write-wins).

    Returns None when THIS request won the claim and must execute the payment.
    Returns a JSONResponse when an identical request already completed (cached
    response, 202) or is still in progress (202). Raises 409 when the same key
    was used with a different payload, and 503 on any state-store error.
    """
    client = _get_dapr_client()

    def _replay_or_conflict(record: dict) -> responses.JSONResponse:
        if record.get("payload_hash") != payload_hash:
            logger.warning("idempotency_payload_mismatch key=%s label=%s", key, label)
            raise HTTPException(
                status_code=409,
                detail="Idempotency key was already used with a different payload.",
            )
        if record.get("status") == "completed" and record.get("response") is not None:
            logger.info("idempotency_hit key=%s label=%s", key, label)
            return responses.JSONResponse(content=record["response"], status_code=202)
        logger.info("idempotency_in_progress key=%s label=%s", key, label)
        return responses.JSONResponse(
            content={"message": "duplicate request already in progress"},
            status_code=202,
        )

    record = _read_idempotency_record(client, key, label)
    if record is not None:
        return _replay_or_conflict(record)

    claim = {"payload_hash": payload_hash, "status": "in_progress", "response": None}
    try:
        if _FIRST_WRITE_SUPPORTED:
            # etag="" + first-write concurrency == create-only-if-absent,
            # which makes the claim atomic (no check-then-act race).
            client.save_state(
                config.STATE_STORE_NAME,
                key,
                json.dumps(claim),
                etag="",
                state_options=StateOptions(
                    consistency=Consistency.strong,
                    concurrency=Concurrency.first_write,
                ),
            )
        else:
            client.save_state(config.STATE_STORE_NAME, key, json.dumps(claim))
    except Exception as exc:
        # Lost the race OR the store failed. Re-read to disambiguate; when no
        # existing claim can be confirmed, fail closed.
        logger.warning(
            "idempotency_claim_failed key=%s label=%s error=%s", key, label, str(exc)
        )
        record = _read_idempotency_record(client, key, label)
        if record is None:
            raise HTTPException(
                status_code=503,
                detail="Payment gateway temporarily unavailable. Please retry.",
            )
        return _replay_or_conflict(record)
    return None


def _finalize_idempotency(key: str, payload_hash: str, body: dict, label: str) -> None:
    """Record the successful response under a previously claimed key.

    A failure here is logged CRITICAL but never swallowed silently: the claim
    marker remains in place, so retries stay replay-safe even without the
    cached response.
    """
    record = {"payload_hash": payload_hash, "status": "completed", "response": body}
    try:
        _get_dapr_client().save_state(
            config.STATE_STORE_NAME, key, json.dumps(record)
        )
        logger.debug("idempotency_finalized key=%s label=%s", key, label)
    except Exception as exc:
        logger.critical(
            "idempotency_finalize_failed key=%s label=%s error=%s",
            key,
            label,
            str(exc),
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
    ledger_id: str = Header(None, alias="x-ledger-id"),  # ignored: derived from env (NF-FF-21)
    mint_account_id: str = Header(None, alias="x-mint-account-id"),  # ignored: derived from env (NF-FF-21)
    idempotency_key: str = Header(None, alias="x-idempotency-key"),
):
    """Deposit handler. Idempotent when x-idempotency-key header is supplied."""

    resolved_ledger_id, resolved_mint_account_id = _resolve_ledger_ids(
        ledger_id, mint_account_id
    )
    context = Context(
        tenant_id=tenant_id,
        keycloak_id=keycloak_id,
        ledger_id=resolved_ledger_id,
        mint_account_id=resolved_mint_account_id,
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

    payload_hash = _payload_fingerprint(payload, tenant_id, keycloak_id)
    cached = _claim_idempotency(idem_key, payload_hash, "deposit")
    if cached is not None:
        return cached

    try:
        payment_service = PaymentService()
        reference = payment_service.initiate_deposit(payload, context)
        resp_body = {"message": "success", "reference": reference}
        _finalize_idempotency(idem_key, payload_hash, resp_body, "deposit")
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
    ledger_id: str = Header(None, alias="x-ledger-id"),  # ignored: derived from env (NF-FF-21)
    mint_account_id: str = Header(None, alias="x-mint-account-id"),  # ignored: derived from env (NF-FF-21)
    idempotency_key: str = Header(None, alias="x-idempotency-key"),
):
    """Deposit handler using recipient account number. Idempotent via x-idempotency-key."""

    resolved_ledger_id, resolved_mint_account_id = _resolve_ledger_ids(
        ledger_id, mint_account_id
    )
    context = Context(
        tenant_id=tenant_id,
        keycloak_id=keycloak_id,
        ledger_id=resolved_ledger_id,
        mint_account_id=resolved_mint_account_id,
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

    payload_hash = _payload_fingerprint(payload, tenant_id, keycloak_id)
    cached = _claim_idempotency(idem_key, payload_hash, "deposit_with_account_number")
    if cached is not None:
        return cached

    try:
        payment_service = PaymentService()
        reference = payment_service.initiate_deposit_with_account_number(payload, context)
        resp_body = {"message": "success", "reference": reference}
        _finalize_idempotency(idem_key, payload_hash, resp_body, "deposit_with_account_number")
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
    ledger_id: str = Header(None, alias="x-ledger-id"),  # ignored: derived from env (NF-FF-21)
    mint_account_id: str = Header(None, alias="x-mint-account-id"),  # ignored: derived from env (NF-FF-21)
    idempotency_key: str = Header(None, alias="x-idempotency-key"),
):
    """Initiate transfer handler. Idempotent via x-idempotency-key header."""

    resolved_ledger_id, resolved_mint_account_id = _resolve_ledger_ids(
        ledger_id, mint_account_id
    )
    context = Context(
        tenant_id=tenant_id,
        keycloak_id=keycloak_id,
        ledger_id=resolved_ledger_id,
        mint_account_id=resolved_mint_account_id,
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

    payload_hash = _payload_fingerprint(payload, tenant_id, keycloak_id)
    cached = _claim_idempotency(idem_key, payload_hash, "transfer")
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
        _finalize_idempotency(idem_key, payload_hash, resp_body, "transfer")
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
    ledger_id: str = Header(None, alias="x-ledger-id"),  # ignored: derived from env (NF-FF-21)
    mint_account_id: str = Header(None, alias="x-mint-account-id"),  # ignored: derived from env (NF-FF-21)
    idempotency_key: str = Header(None, alias="x-idempotency-key"),
):
    """Loan Payment handler. Idempotent via x-idempotency-key."""

    resolved_ledger_id, resolved_mint_account_id = _resolve_ledger_ids(
        ledger_id, mint_account_id
    )
    context = Context(
        tenant_id=tenant_id,
        keycloak_id=keycloak_id,
        ledger_id=resolved_ledger_id,
        mint_account_id=resolved_mint_account_id,
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

    payload_hash = _payload_fingerprint(payload, tenant_id, keycloak_id)
    cached = _claim_idempotency(idem_key, payload_hash, "loan_payment")
    if cached is not None:
        return cached

    try:
        payment_service = PaymentService()
        reference = payment_service.initiate_loan_payment(payload, context)
        resp_body = {"message": "success", "reference": reference}
        _finalize_idempotency(idem_key, payload_hash, resp_body, "loan_payment")
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
    ledger_id: str = Header(None, alias="x-ledger-id"),  # ignored: derived from env (NF-FF-21)
    mint_account_id: str = Header(None, alias="x-mint-account-id"),  # ignored: derived from env (NF-FF-21)
    idempotency_key: str = Header(None, alias="x-idempotency-key"),
):
    """LPO payment handler. Idempotent via x-idempotency-key."""

    resolved_ledger_id, resolved_mint_account_id = _resolve_ledger_ids(
        ledger_id, mint_account_id
    )
    context = Context(
        tenant_id=tenant_id,
        keycloak_id=keycloak_id,
        ledger_id=resolved_ledger_id,
        mint_account_id=resolved_mint_account_id,
    )

    payload_hash = _payload_fingerprint(payload, tenant_id, keycloak_id)
    idem_key = (
        f"idempotency:lpo:{idempotency_key}"
        if idempotency_key
        else f"idempotency:lpo:derived:{payload_hash[:32]}"
    )
    cached = _claim_idempotency(idem_key, payload_hash, "lpo_payment")
    if cached is not None:
        return cached

    try:
        payment_service = PaymentService()

        reference = payment_service.initiate_lpo_payment(payload, context)

        resp_body = {"message": "success", "reference": reference}
        _finalize_idempotency(idem_key, payload_hash, resp_body, "lpo_payment")
        return responses.JSONResponse(content=resp_body, status_code=200)
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
    ledger_id: str = Header(None, alias="x-ledger-id"),  # ignored: derived from env (NF-FF-21)
    mint_account_id: str = Header(None, alias="x-mint-account-id"),  # ignored: derived from env (NF-FF-21)
    idempotency_key: str = Header(None, alias="x-idempotency-key"),
):
    """Insurance payment handler. Idempotent via x-idempotency-key."""

    resolved_ledger_id, resolved_mint_account_id = _resolve_ledger_ids(
        ledger_id, mint_account_id
    )
    context = Context(
        tenant_id=tenant_id,
        keycloak_id=keycloak_id,
        ledger_id=resolved_ledger_id,
        mint_account_id=resolved_mint_account_id,
    )

    payload_hash = _payload_fingerprint(payload, tenant_id, keycloak_id)
    idem_key = (
        f"idempotency:insurance:{idempotency_key}"
        if idempotency_key
        else f"idempotency:insurance:derived:{payload_hash[:32]}"
    )
    cached = _claim_idempotency(idem_key, payload_hash, "insurance_premium_payment")
    if cached is not None:
        return cached

    try:
        payment_service = PaymentService()

        reference = payment_service.initiate_insurance_premium_payment(payload, context)

        resp_body = {"message": "success", "reference": reference}
        _finalize_idempotency(idem_key, payload_hash, resp_body, "insurance_premium_payment")
        return responses.JSONResponse(content=resp_body, status_code=200)
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
    ledger_id: str = Header(None, alias="x-ledger-id"),  # ignored: derived from env (NF-FF-21)
    mint_account_id: str = Header(None, alias="x-mint-account-id"),  # ignored: derived from env (NF-FF-21)
    idempotency_key: str = Header(None, alias="x-idempotency-key"),
):
    """Supply chain financing payment handler. Idempotent via x-idempotency-key."""

    resolved_ledger_id, resolved_mint_account_id = _resolve_ledger_ids(
        ledger_id, mint_account_id
    )
    context = Context(
        tenant_id=tenant_id,
        keycloak_id=keycloak_id,
        ledger_id=resolved_ledger_id,
        mint_account_id=resolved_mint_account_id,
    )

    payload_hash = _payload_fingerprint(payload, tenant_id, keycloak_id)
    idem_key = (
        f"idempotency:scf:{idempotency_key}"
        if idempotency_key
        else f"idempotency:scf:derived:{payload_hash[:32]}"
    )
    cached = _claim_idempotency(idem_key, payload_hash, "supply_chain_financing_payment")
    if cached is not None:
        return cached

    try:
        payment_service = PaymentService()

        reference = payment_service.supply_chain_financing_payment(payload, context)

        resp_body = {"message": "success", "reference": reference}
        _finalize_idempotency(idem_key, payload_hash, resp_body, "supply_chain_financing_payment")
        return responses.JSONResponse(content=resp_body, status_code=200)
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
    ledger_id: str = Header(None, alias="x-ledger-id"),  # ignored: derived from env (NF-FF-21)
    mint_account_id: str = Header(None, alias="x-mint-account-id"),  # ignored: derived from env (NF-FF-21)
):
    """External credit (deposit) handler."""

    resolved_ledger_id, resolved_mint_account_id = _resolve_ledger_ids(
        ledger_id, mint_account_id
    )
    context = Context(
        tenant_id=tenant_id,
        keycloak_id=keycloak_id,
        ledger_id=resolved_ledger_id,
        mint_account_id=resolved_mint_account_id,
    )

    idem_key = f"idempotency:transfer:credit:{payload.transactionId}"

    payload_hash = _payload_fingerprint(payload, tenant_id, keycloak_id)
    cached = _claim_idempotency(idem_key, payload_hash, "external_credit")
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
        _finalize_idempotency(idem_key, payload_hash, resp_body, "external_credit")
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
    ledger_id: str = Header(None, alias="x-ledger-id"),  # ignored: derived from env (NF-FF-21)
    mint_account_id: str = Header(None, alias="x-mint-account-id"),  # ignored: derived from env (NF-FF-21)
):
    """External debit (withdraw) handler."""

    resolved_ledger_id, resolved_mint_account_id = _resolve_ledger_ids(
        ledger_id, mint_account_id
    )
    context = Context(
        tenant_id=tenant_id,
        keycloak_id=keycloak_id,
        ledger_id=resolved_ledger_id,
        mint_account_id=resolved_mint_account_id,
    )

    idem_key = f"idempotency:transfer:debit:{payload.transactionId}"

    payload_hash = _payload_fingerprint(payload, tenant_id, keycloak_id)
    cached = _claim_idempotency(idem_key, payload_hash, "external_debit")
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
        _finalize_idempotency(idem_key, payload_hash, resp_body, "external_debit")
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
