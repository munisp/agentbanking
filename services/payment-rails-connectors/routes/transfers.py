from typing import Any

import httpx
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from utils import (
    create_logger,
    get_config,
    PaymentProcessingClient,
    MojaloopConnectorClient,
)

transfers_router = APIRouter()
logger = create_logger(__name__)
config = get_config()
payment_processing_client = PaymentProcessingClient()
mojaloop_client = MojaloopConnectorClient()


class Party(BaseModel):
    idType: str = "MSISDN"
    idValue: str


class Amount(BaseModel):
    amount: float
    currency: str | None = None


class OutboundTransferRequest(BaseModel):
    transactionId: str
    payer: Party
    payee: Party
    amount: Amount
    destination: str
    note: str | None = None
    pin: str | None = None
    initiator_type: str | None = "CONSUMER"
    debit_in_payment_processing: bool = False
    metadata: dict[str, Any] | None = None


class OutboundTransferResponse(BaseModel):
    success: bool
    transaction_id: str
    status: str
    payment_processing: dict[str, Any] | None = None
    mojaloop: dict[str, Any] | None = None


@transfers_router.post("/transfers", response_model=OutboundTransferResponse)
async def initiate_outbound_transfer(
    payload: OutboundTransferRequest,
    tenant_id: str = Header("system", alias="x-tenant-id"),
    keycloak_id: str = Header("system", alias="x-keycloak-id"),
    ledger_id: str = Header("system", alias="x-ledger-id"),
    mint_account_id: str = Header("system", alias="x-mint-account-id"),
):
    headers = {
        "x-tenant-id": tenant_id,
        "x-keycloak-id": keycloak_id,
        "x-ledger-id": ledger_id,
        "x-mint-account-id": mint_account_id,
    }

    payment_processing_response: dict[str, Any] | None = None

    try:
        if payload.debit_in_payment_processing:
            debit_payload = {
                "transactionId": payload.transactionId,
                "party": {
                    "idType": payload.payer.idType,
                    "idValue": payload.payer.idValue,
                },
                "amount": {
                    "currency": payload.amount.currency or config.DEFAULT_CURRENCY,
                    "amount": payload.amount.amount,
                },
                "metadata": payload.metadata or {},
            }

            payment_processing_response = (
                await payment_processing_client.external_debit(
                    debit_payload,
                    headers,
                )
            )

        mojaloop_payload = {
            "from": {
                "idType": payload.payer.idType,
                "idValue": payload.payer.idValue,
            },
            "to": {
                "idType": payload.payee.idType,
                "idValue": payload.payee.idValue,
            },
            "currency": payload.amount.currency or config.DEFAULT_CURRENCY,
            "amount": str(payload.amount.amount),
            "destination": payload.destination,
            "note": payload.note or "Outbound transfer",
            "reference": payload.transactionId,
            "pin": payload.pin,
            "initiator_type": payload.initiator_type,
        }

        mojaloop_data = await mojaloop_client.initiate_transfer(
            mojaloop_payload, headers
        )

        return OutboundTransferResponse(
            success=True,
            transaction_id=payload.transactionId,
            status="submitted",
            payment_processing=payment_processing_response,
            mojaloop=mojaloop_data,
        )
    except httpx.HTTPStatusError as e:
        logger.error(f"Outbound transfer HTTP error: {e.response.text}")
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        logger.error(f"Outbound transfer failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Outbound transfer failed")
