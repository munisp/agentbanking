from fastapi import APIRouter, Depends, HTTPException, responses, Header, Body
from utils import create_logger
from utils.config import get_config
from utils.enums import CurrencyLedgerId
from schemas.context import Context
from schemas.payment import ExternalDebitSchema, ExternalTransferSchema, ExternalParty, ExternalAmount
from adapters import AccountServiceAdapter
from services.payment import PaymentService
import hmac
import json
import os
import uuid

# Canonical funds-flow business metric (services/shared/observability.py).
# Guarded: metrics must never break money-movement endpoints.
try:
    from shared.observability import record_funds_flow_operation
except ImportError:
    try:
        import os as _obs_os
        import sys as _obs_sys

        _obs_sys.path.insert(
            0,
            _obs_os.path.join(
                _obs_os.path.dirname(_obs_os.path.abspath(__file__)), "..", ".."
            ),
        )
        from shared.observability import record_funds_flow_operation
    except ImportError:
        def record_funds_flow_operation(operation, tenant, status, service=None):
            return None

transfers_router = APIRouter()

logger = create_logger(__name__)

config = get_config()

# NF-FF-2/3/4: these endpoints move money; they must never be reachable without
# service-to-service authentication. The shared secret is REQUIRED — fail closed
# at startup if it is not configured.
_EXPECTED_SERVICE_AUTH = os.environ.get("SETTLEMENT_SERVICE_AUTH")
if not _EXPECTED_SERVICE_AUTH:
    raise RuntimeError(
        "SETTLEMENT_SERVICE_AUTH environment variable is not set; "
        "refusing to start because /transfers money-movement endpoints "
        "would be unauthenticated."
    )


def require_service_auth(
    service_auth: str = Header("", alias="x-service-auth"),
) -> None:
    """FastAPI dependency: constant-time check of the service-auth shared secret."""
    if not service_auth or not hmac.compare_digest(
        service_auth.encode("utf-8"), _EXPECTED_SERVICE_AUTH.encode("utf-8")
    ):
        logger.warning("Rejected unauthenticated /transfers request")
        raise HTTPException(status_code=403, detail="Forbidden: invalid service auth")


_SYSTEM_AGENT_NS = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # uuid.NAMESPACE_URL


def _system_agent_id(tenant: str) -> str:
    """Deterministic non-nil UUID for the Mojaloop system agent scoped to a tenant."""
    return str(uuid.uuid5(_SYSTEM_AGENT_NS, f"mojaloop-system-agent:{tenant}"))


def _resolve_agent_id(body: dict, tenant: str) -> str:
    """Return the real agent UUID from the request body, falling back to the system agent."""
    candidate = str(body.get("agent_id") or "").strip()
    try:
        uuid.UUID(candidate)
        return candidate
    except (ValueError, AttributeError):
        return _system_agent_id(tenant)


@transfers_router.post("/withdraw", dependencies=[Depends(require_service_auth)])
def withdraw(
    body: dict = Body(...),
    tenant_id: str = Header("system", alias="x-tenant-id"),
):
    effective_tenant = tenant_id  # fallback tenant label for failure metrics
    try:
        logger.info(f"Process withdrawal tenant_id={tenant_id} body={json.dumps(body)}")

        payer_info = body.get("payer", {})
        amount_info = body.get("amount", {})
        currency = amount_info.get("currency", "NGN")
        logger.info(f"Parsed withdrawal details: payer_info={payer_info}, amount_info={amount_info}, currency={currency}")

        payload = ExternalDebitSchema(
            transactionId=body["transferId"],
            payer=payer_info.get("partyIdentifier", ""),
            amount=ExternalAmount(
                currency=currency,
                amount=float(amount_info.get("amount", 0)),
            ),
        )

        effective_tenant = body.get("bank", tenant_id)
        logger.info(f"Effective tenant for withdrawal: {effective_tenant}")
        context = Context(
            tenant_id=effective_tenant,
            keycloak_id=_resolve_agent_id(body, effective_tenant),
            ledger_id=str(int(CurrencyLedgerId.from_currency(currency))),
            mint_account_id="0",
        )

        # NF-FF-3: withdrawals are debits out of a customer account and must be
        # authorised by the account holder's PIN (same check_account pattern used
        # by the other debit flows in services/payment.py).
        pin = str(body.get("pin") or "").strip()
        if not pin:
            raise HTTPException(
                status_code=403, detail="PIN is required for withdrawals."
            )

        account_adapter = AccountServiceAdapter()
        payer_account_id = payload.payer
        try:
            payer_account = account_adapter.get_account_by_account_number(
                payload.payer, context
            )
            payer_account_data = (
                payer_account.get("account") if isinstance(payer_account, dict) else {}
            )
            payer_account_id = str(payer_account_data.get("id") or payload.payer)
        except Exception as resolve_error:
            logger.info(
                "Payer account-number lookup failed for withdrawal, using raw identifier: %s",
                str(resolve_error),
            )

        try:
            account_adapter.check_account(str(payer_account_id), pin, context)
        except HTTPException:
            raise
        except Exception as pin_error:
            logger.warning(
                "Withdrawal PIN verification failed for tenant %s: %s",
                effective_tenant, str(pin_error),
            )
            raise HTTPException(status_code=403, detail="PIN verification failed.")

        reference = PaymentService().process_external_debit(payload, context)

        logger.info(f"Withdrawal processed for tenant {effective_tenant}, reference: {reference}")

        record_funds_flow_operation("withdraw", effective_tenant, "success")
        return responses.JSONResponse(
            content={
                "success": True,
                "message": "Withdrawal processed successfully",
                "transactionId": body.get("transferId"),
                "reference": reference,
            },
            status_code=200,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during withdraw: {str(e)}")
        record_funds_flow_operation("withdraw", effective_tenant, "failed")
        raise HTTPException(status_code=500, detail=str(e) or "Withdrawal failed.")


@transfers_router.post("/deposit", dependencies=[Depends(require_service_auth)])
def deposit(
    body: dict = Body(...),
    tenant_id: str = Header("system", alias="x-tenant-id"),
):
    effective_tenant = tenant_id  # fallback tenant label for failure metrics
    try:
        logger.info(f"Process deposit tenant_id={tenant_id} body={json.dumps(body)}")

        payee_info = body.get("payee", {})
        amount_info = body.get("amount", {})
        currency = amount_info.get("currency", "NGN")

        payee_id_value = payee_info.get("partyIdentifier", "").lstrip("+")

        payload = ExternalTransferSchema(
            transactionId=body["transaction_id"],
            party=ExternalParty(
                idType=payee_info.get("partyIdType", "ACCOUNT_ID"),
                idValue=payee_id_value,
            ),
            amount=ExternalAmount(
                currency=currency,
                amount=float(amount_info.get("amount", 0)),
            ),
        )

        effective_tenant = body.get("source", tenant_id)
        context = Context(
            tenant_id=effective_tenant,
            keycloak_id=_resolve_agent_id(body, effective_tenant),
            ledger_id=str(int(CurrencyLedgerId.from_currency(currency))),
            mint_account_id="0",
        )

        reference = PaymentService().process_external_credit(payload, context)

        record_funds_flow_operation("deposit", effective_tenant, "success")
        return responses.JSONResponse(
            content={
                "success": True,
                "message": "Deposit processed successfully",
                "transactionId": body.get("transaction_id"),
                "reference": reference,
            },
            status_code=200,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during deposit: {str(e)}")
        record_funds_flow_operation("deposit", effective_tenant, "failed")
        raise HTTPException(status_code=500, detail=str(e) or "Deposit failed.")


@transfers_router.post("/settlement-payout", dependencies=[Depends(require_service_auth)])
def settlement_payout(
    body: dict = Body(...),
    tenant_id: str = Header("default", alias="x-tenant-id"),
):
    """Service-to-service endpoint: pays out commission settlement funds to an agent account.

    Called by the commission-settlement service. Requires the X-Service-Auth
    shared secret (SETTLEMENT_SERVICE_AUTH), verified with a constant-time
    comparison by the require_service_auth dependency.
    No PIN needed — the commission-settlement service is trusted.
    """
    try:
        agent_id = body.get("agent_id", "")
        amount = float(body.get("amount", 0))
        currency = str(body.get("currency", "NGN")).upper()
        # NF-FF-4: never trust a caller-chosen settlement reference for replay
        # protection — generate it server-side when absent.
        settlement_ref = str(body.get("settlement_ref") or "").strip() or str(uuid.uuid4())
        note = body.get("note", f"Commission settlement {settlement_ref}")

        payment_details = body.get("payment_details") or {}
        account_number = payment_details.get("account_number") or payment_details.get("destination_account") or agent_id

        logger.info(
            "Settlement payout: agent=%s amount=%.2f currency=%s ref=%s",
            agent_id, amount, currency, settlement_ref,
        )

        if amount <= 0:
            raise ValueError("Settlement amount must be greater than zero")

        payload = ExternalTransferSchema(
            transactionId=settlement_ref,
            party=ExternalParty(
                idType="ACCOUNT_ID",
                idValue=str(account_number),
            ),
            amount=ExternalAmount(
                currency=currency,
                amount=amount,
            ),
        )

        context = Context(
            tenant_id=tenant_id,
            keycloak_id=_resolve_agent_id(body, tenant_id),
            ledger_id=str(int(CurrencyLedgerId.from_currency(currency))),
            mint_account_id="0",
        )

        reference = PaymentService().process_external_credit(payload, context)

        record_funds_flow_operation("settlement_payout", tenant_id, "success")
        return responses.JSONResponse(
            content={
                "success": True,
                "message": "Settlement payout processed",
                "settlement_ref": settlement_ref,
                "reference": reference,
            },
            status_code=200,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Settlement payout failed: {str(e)}")
        record_funds_flow_operation("settlement_payout", tenant_id, "failed")
        raise HTTPException(status_code=500, detail=str(e) or "Settlement payout failed.")
