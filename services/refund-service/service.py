"""
Refund Service - Full Implementation

Refunds are persisted via SQLAlchemy and executed against real reversal rails
(payment gateway refund API or TigerBeetle wallet credit). Functions never
report COMPLETED unless the rail actually accepted the reversal; rail failures
mark the refund FAILED and raise/return an explicit error.
"""
import logging
import os
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional
from enum import Enum

import httpx
from sqlalchemy.orm import Session

from .models import RefundService as RefundModel

logger = logging.getLogger(__name__)

PAYMENT_GATEWAY_URL = os.getenv("PAYMENT_GATEWAY_URL", "")
TIGERBEETLE_SERVICE_URL = os.getenv("TIGERBEETLE_SERVICE_URL", "")

class RefundStatus(str, Enum):
    INITIATED = "initiated"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"

class RefundMethod(str, Enum):
    ORIGINAL = "original_payment_method"
    WALLET = "wallet"
    BANK_TRANSFER = "bank_transfer"

REFUND_WINDOW_HOURS = 72  # 72-hour refund window


def _post_json(url: str, payload: dict) -> dict:
    """POST JSON to a reversal rail. Raises on transport or non-2xx errors."""
    with httpx.Client(timeout=20.0) as client:
        resp = client.post(url, json=payload)
        resp.raise_for_status()
        return resp.json() if resp.content else {}


# ---------------------------------------------------------------------------
# CRUD used by router.py (real persistence, no fabricated rows)
# ---------------------------------------------------------------------------

async def create(db: Session, data) -> RefundModel:
    """Persist a new refund record."""
    refund = RefundModel(
        amount=data.amount,
        currency=getattr(data, "currency", "NGN"),
        reason=data.reason,
        transaction_id=data.transaction_id,
        status="pending",
    )
    db.add(refund)
    db.commit()
    db.refresh(refund)
    logger.info(f"Refund persisted: {refund.id} for txn {refund.transaction_id}")
    return refund


async def get_by_id(db: Session, id: str) -> Optional[RefundModel]:
    """Fetch a refund by ID (None when unknown)."""
    return db.query(RefundModel).filter(RefundModel.id == id).first()


async def get_all(db: Session, skip: int = 0, limit: int = 100) -> List[RefundModel]:
    """List refunds."""
    return db.query(RefundModel).order_by(RefundModel.created_at.desc()).offset(skip).limit(limit).all()


async def update(db: Session, id: str, data) -> Optional[RefundModel]:
    """Update a refund record."""
    refund = await get_by_id(db, id)
    if not refund:
        return None
    if getattr(data, "status", None):
        refund.status = data.status
    db.commit()
    db.refresh(refund)
    return refund


async def delete(db: Session, id: str) -> bool:
    """Delete a refund record."""
    refund = await get_by_id(db, id)
    if not refund:
        return False
    db.delete(refund)
    db.commit()
    return True


# ---------------------------------------------------------------------------
# Domain logic (real reversal rails)
# ---------------------------------------------------------------------------

def process_refund(
    transaction_id: str,
    amount: Decimal,
    reason: str,
    initiated_by: str,
    db: Optional[Session] = None,
) -> Dict:
    """Process a full refund for a transaction via the payment gateway."""
    if amount <= Decimal("0"):
        return {"success": False, "error": "Refund amount must be positive"}
    if not PAYMENT_GATEWAY_URL:
        return {"success": False, "error": "PAYMENT_GATEWAY_URL not configured — cannot process refund"}

    refund_id = f"REF-{transaction_id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

    # Persist the refund attempt before touching the rail
    record = None
    if db is not None:
        record = RefundModel(
            id=refund_id,
            amount=float(amount),
            reason=reason,
            transaction_id=transaction_id,
            status=RefundStatus.PROCESSING.value,
        )
        db.add(record)
        db.commit()

    try:
        gw = _post_json(f"{PAYMENT_GATEWAY_URL}/refund", {
            "transaction_id": transaction_id,
            "amount": str(amount),
            "reason": reason,
            "refund_id": refund_id,
        })
    except Exception as e:
        logger.error(f"Gateway refund failed for {refund_id}: {e}")
        if record is not None:
            record.status = RefundStatus.FAILED.value
            db.commit()
        return {"success": False, "error": f"Payment gateway refund failed: {e}", "refund_id": refund_id}

    gw_status = gw.get("status", RefundStatus.PROCESSING.value)
    final_status = RefundStatus.COMPLETED.value if gw_status in ("completed", "success", "processed") else RefundStatus.PROCESSING.value
    if record is not None:
        record.status = final_status
        db.commit()

    result = {
        "refund_id": refund_id,
        "transaction_id": transaction_id,
        "amount": str(amount),
        "status": final_status,
        "gateway_reference": gw.get("reference") or gw.get("gateway_reference"),
        "reason": reason,
        "initiated_by": initiated_by,
        "initiated_at": datetime.utcnow().isoformat(),
    }
    logger.info(f"Refund initiated: {refund_id} for txn {transaction_id} (status={final_status})")
    return {"success": True, "refund": result}


def process_partial_refund(
    transaction_id: str,
    partial_amount: Decimal,
    reason: str,
    initiated_by: str,
    db: Optional[Session] = None,
) -> Dict:
    """Process a partial refund for a transaction via the payment gateway."""
    if partial_amount <= Decimal("0"):
        return {"success": False, "error": "Partial refund amount must be positive"}

    result = process_refund(transaction_id, partial_amount, reason, initiated_by, db=db)
    if result.get("success") and "refund" in result:
        result["refund"]["refund_type"] = "partial"
        result["refund"]["partial_amount"] = str(partial_amount)
    return result


def refund_to_original_payment_method(
    transaction_id: str,
    amount: Decimal,
    gateway_reference: str,
) -> Dict:
    """Refund to the original payment method via the payment gateway."""
    if not PAYMENT_GATEWAY_URL:
        return {"success": False, "error": "PAYMENT_GATEWAY_URL not configured — cannot refund"}

    try:
        gw = _post_json(f"{PAYMENT_GATEWAY_URL}/refund", {
            "transaction_id": transaction_id,
            "amount": str(amount),
            "gateway_reference": gateway_reference,
        })
    except Exception as e:
        logger.error(f"Gateway refund failed for txn {transaction_id}: {e}")
        return {"success": False, "error": f"Payment gateway refund failed: {e}"}

    result = {
        "transaction_id": transaction_id,
        "amount": str(amount),
        "method": RefundMethod.ORIGINAL.value,
        "gateway_reference": gw.get("reference") or gateway_reference,
        "status": gw.get("status", RefundStatus.PROCESSING.value),
        "processed_at": datetime.utcnow().isoformat(),
    }
    logger.info(f"Refund to original method initiated for txn {transaction_id}")
    return {"success": True, "refund": result}


def refund_to_wallet(
    agent_id: str,
    transaction_id: str,
    amount: Decimal,
) -> Dict:
    """Refund to agent's wallet via a real TigerBeetle ledger transfer.

    Only reports COMPLETED when the ledger service accepted the transfer.
    """
    if not TIGERBEETLE_SERVICE_URL:
        return {"success": False, "error": "TIGERBEETLE_SERVICE_URL not configured — cannot credit wallet"}

    try:
        tb = _post_json(f"{TIGERBEETLE_SERVICE_URL}/transfer", {
            "from_user_id": "platform_refund_pool",
            "to_user_id": agent_id,
            "amount": float(amount),
            "transaction_type": "refund",
            "description": f"Wallet refund for txn {transaction_id}",
        })
    except Exception as e:
        logger.error(f"Wallet credit failed for agent {agent_id}, txn {transaction_id}: {e}")
        return {"success": False, "error": f"Wallet credit via ledger failed: {e}"}

    result = {
        "agent_id": agent_id,
        "transaction_id": transaction_id,
        "amount": str(amount),
        "method": RefundMethod.WALLET.value,
        "status": RefundStatus.COMPLETED.value,
        "tigerbeetle_transfer_id": str(tb.get("transfer_id") or tb.get("id")),
        "credited_at": datetime.utcnow().isoformat(),
    }
    logger.info(f"Wallet refund completed for agent {agent_id}, txn {transaction_id}")
    return {"success": True, "refund": result}


def get_refund_status(refund_id: str, db: Optional[Session] = None) -> Optional[Dict]:
    """Get the current status of a refund from the database (None when unknown)."""
    if db is None:
        raise RuntimeError("get_refund_status requires a database session")
    record = db.query(RefundModel).filter(RefundModel.id == refund_id).first()
    if not record:
        return None
    return {
        "refund_id": record.id,
        "status": record.status,
        "amount": record.amount,
        "transaction_id": record.transaction_id,
        "last_updated": record.updated_at.isoformat() if record.updated_at else None,
    }
