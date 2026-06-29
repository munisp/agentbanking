"""
Dapr event consumer — subscribes to TRANSACTION_INITIATED events from
payment-processing-service and auto-records VAT transactions for agents.
"""

import logging
import os
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Request
from sqlalchemy.orm import Session

from config import SessionLocal
from service import NigeriaVATService

logger = logging.getLogger(__name__)

DAPR_PUBSUB_NAME = os.getenv("DAPR_PUBSUB_NAME", "pubsub")
TRANSACTION_TOPIC = os.getenv("TRANSACTION_TOPIC", "TRANSACTION_INITIATED")

consumer_router = APIRouter()


def _get_db() -> Session:
    db = SessionLocal()
    try:
        return db
    except Exception:
        db.close()
        raise


@consumer_router.get("/dapr/subscribe")
def dapr_subscribe():
    """Tell Dapr which topics this service subscribes to."""
    return [
        {
            "pubsubname": DAPR_PUBSUB_NAME,
            "topic": TRANSACTION_TOPIC,
            "route": "/events/transaction",
        }
    ]


@consumer_router.post("/events/transaction")
async def handle_transaction_event(request: Request):
    """
    Receives TRANSACTION_INITIATED events from payment-processing-service.

    Event payload (TransactionEventSchema):
        transaction_id, payer, payee, amount, status, currency,
        completed_at, note, tag, tenant_id, ledger_id
    """
    try:
        body = await request.json()
        # Dapr wraps the event in a CloudEvent envelope
        event_data = body.get("data", body)

        status = event_data.get("status", "")
        # Only process successful transactions
        if status not in ("SUCCESS", "success", "COMPLETED", "completed"):
            return {"status": "skipped", "reason": "non-success status"}

        transaction_id = event_data.get("transaction_id", "")
        payer = str(event_data.get("payer", ""))
        payee = str(event_data.get("payee", ""))
        amount_raw = event_data.get("amount", "0")
        note = event_data.get("note", "") or ""
        completed_at = event_data.get("completed_at")
        tenant_id = event_data.get("tenant_id", "")

        try:
            amount = Decimal(str(amount_raw))
        except Exception:
            amount = Decimal("0")

        txn_date = datetime.utcnow()
        if completed_at:
            try:
                txn_date = datetime.fromisoformat(str(completed_at).replace("Z", "+00:00"))
            except Exception:
                pass

        db = SessionLocal()
        try:
            svc = NigeriaVATService(db)

            # Record for the payer (agent processing the transaction)
            # Use payer as entity_id — in agent banking the payer is the agent's account
            payer_ref = f"PAY-{transaction_id}-payer"
            svc.record_vat_from_payment_event(
                entity_id=payer,
                transaction_ref=payer_ref,
                amount=amount,
                note=note,
                transaction_date=txn_date,
            )
        finally:
            db.close()

        return {"status": "ok"}

    except Exception as exc:
        logger.error(f"Error processing transaction event: {exc}", exc_info=True)
        # Return 200 to prevent Dapr from retrying poison messages indefinitely
        return {"status": "error", "detail": str(exc)}
