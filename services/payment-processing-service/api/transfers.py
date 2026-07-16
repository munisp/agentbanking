from fastapi import APIRouter, HTTPException, responses, Header, Body
from utils import create_logger
from utils.config import get_config
from utils.enums import CurrencyLedgerId
from schemas.context import Context
from schemas.payment import ExternalDebitSchema, ExternalTransferSchema, ExternalParty, ExternalAmount
from services.payment import PaymentService
import json
import uuid

transfers_router = APIRouter()

logger = create_logger(__name__)

config = get_config()

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


@transfers_router.post("/withdraw")
def withdraw(
    body: dict = Body(...),
    tenant_id: str = Header("system", alias="x-tenant-id"),
):
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

        reference = PaymentService().process_external_debit(payload, context)

        logger.info(f"Withdrawal processed for tenant {effective_tenant}, reference: {reference}")

        return responses.JSONResponse(
            content={
                "success": True,
                "message": "Withdrawal processed successfully",
                "transactionId": body.get("transferId"),
                "reference": reference,
            },
            status_code=200,
        )

    except Exception as e:
        logger.error(f"Unexpected error during withdraw: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e) or "Withdrawal failed.")


@transfers_router.post("/deposit")
def deposit(
    body: dict = Body(...),
    tenant_id: str = Header("system", alias="x-tenant-id"),
):
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

        return responses.JSONResponse(
            content={
                "success": True,
                "message": "Deposit processed successfully",
                "transactionId": body.get("transaction_id"),
                "reference": reference,
            },
            status_code=200,
        )

    except Exception as e:
        logger.error(f"Unexpected error during deposit: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e) or "Deposit failed.")


@transfers_router.post("/settlement-payout")
def settlement_payout(
    body: dict = Body(...),
    tenant_id: str = Header("default", alias="x-tenant-id"),
    service_auth: str = Header("", alias="x-service-auth"),
):
    """Service-to-service endpoint: pays out commission settlement funds to an agent account.

    Called by the commission-settlement service. Requires X-Service-Auth header.
    No PIN needed — the commission-settlement service is trusted.
    """
    if service_auth != "commission-settlement-service":
        raise HTTPException(status_code=403, detail="Forbidden: invalid service auth")

    try:
        agent_id = body.get("agent_id", "")
        amount = float(body.get("amount", 0))
        currency = str(body.get("currency", "NGN")).upper()
        settlement_ref = body.get("settlement_ref", str(uuid.uuid4()))
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

        return responses.JSONResponse(
            content={
                "success": True,
                "message": "Settlement payout processed",
                "settlement_ref": settlement_ref,
                "reference": reference,
            },
            status_code=200,
        )

    except Exception as e:
        logger.error(f"Settlement payout failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e) or "Settlement payout failed.")
