"""
Refund Service - Rail helpers

Every helper talks to the real reversal rail (payment gateway) or ledger.
Nothing here fabricates a refund outcome: when the rail is not configured or
rejects the call, these functions raise instead of returning canned statuses.
"""
import os
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, Optional, Union
from enum import Enum

import httpx

logger = logging.getLogger(__name__)

PAYMENT_GATEWAY_URL = os.environ.get("PAYMENT_GATEWAY_URL", "")
TIGERBEETLE_SERVICE_URL = os.environ.get("TIGERBEETLE_SERVICE_URL", "")

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


def _require_gateway() -> str:
    if not PAYMENT_GATEWAY_URL:
        raise RuntimeError("PAYMENT_GATEWAY_URL not configured — reversal rail unavailable")
    return PAYMENT_GATEWAY_URL.rstrip("/")


def _refund_idempotency_key(transaction_id: str, amount: Decimal, reason: str, extra: Optional[Dict] = None) -> str:
    """Deterministic idempotency key for a refund: sha256 over the canonical
    refund identity (transaction + amount + reason + extra attributes), so a
    retried POST of the SAME refund reuses the SAME key and the gateway can
    dedupe it."""
    canonical = f"refund:{transaction_id}:{amount}:{reason}"
    if extra:
        canonical += ":" + ",".join(f"{k}={extra[k]}" for k in sorted(extra))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _enforce_refund_window(transaction_created_at: Union[datetime, str]) -> None:
    """Enforce REFUND_WINDOW_HOURS against the original transaction timestamp.
    Raises ValueError with a clear error when the refund window has expired."""
    if isinstance(transaction_created_at, str):
        parsed = transaction_created_at.replace("Z", "+00:00")
        transaction_created_at = datetime.fromisoformat(parsed)
    if transaction_created_at.tzinfo is None:
        transaction_created_at = transaction_created_at.replace(tzinfo=timezone.utc)
    age = datetime.now(timezone.utc) - transaction_created_at
    if age > timedelta(hours=REFUND_WINDOW_HOURS):
        raise ValueError(
            f"refund window expired: transaction is {age.total_seconds() / 3600:.1f}h old, "
            f"refunds are only accepted within {REFUND_WINDOW_HOURS}h of the original transaction"
        )


def _post_reversal(transaction_id: str, amount: Decimal, reason: str, extra: Optional[Dict] = None) -> Dict:
    """POST a real reversal to the payment gateway. Raises on any failure."""
    gateway = _require_gateway()
    payload = {
        "transaction_id": transaction_id,
        "amount": str(amount),
        "reason": reason,
    }
    if extra:
        payload.update(extra)
    idempotency_key = _refund_idempotency_key(transaction_id, amount, reason, extra)
    try:
        response = httpx.post(
            f"{gateway}/refund",
            json=payload,
            headers={"Idempotency-Key": idempotency_key},
            timeout=30.0,
        )
    except Exception as e:
        raise RuntimeError(f"payment gateway unreachable: {e}") from e
    if response.status_code >= 400:
        raise RuntimeError(f"payment gateway rejected reversal: HTTP {response.status_code}")
    return response.json() if response.content else {}


def process_refund(
    transaction_id: str,
    amount: Decimal,
    reason: str,
    initiated_by: str,
    transaction_created_at: Optional[Union[datetime, str]] = None,
) -> Dict:
    """Process a full refund for a transaction via the real reversal rail."""
    if amount <= Decimal("0"):
        return {"success": False, "error": "Refund amount must be positive"}

    if transaction_created_at is not None:
        try:
            _enforce_refund_window(transaction_created_at)
        except ValueError as e:
            logger.warning(f"Refund rejected for txn {transaction_id}: {e}")
            return {"success": False, "error": str(e)}

    gateway_result = _post_reversal(transaction_id, amount, reason, {"initiated_by": initiated_by})
    refund_id = gateway_result.get("refund_id") or f"REF-{transaction_id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

    result = {
        "refund_id": refund_id,
        "transaction_id": transaction_id,
        "amount": str(amount),
        "status": gateway_result.get("status", RefundStatus.PROCESSING.value),
        "reason": reason,
        "initiated_by": initiated_by,
        "initiated_at": datetime.utcnow().isoformat(),
        "gateway_reference": gateway_result.get("reversal_reference"),
    }
    logger.info(f"Refund initiated: {refund_id} for txn {transaction_id}")
    return {"success": True, "refund": result}


def process_partial_refund(
    transaction_id: str,
    partial_amount: Decimal,
    reason: str,
    initiated_by: str,
    transaction_created_at: Optional[Union[datetime, str]] = None,
) -> Dict:
    """Process a partial refund for a transaction via the real reversal rail."""
    if partial_amount <= Decimal("0"):
        return {"success": False, "error": "Partial refund amount must be positive"}

    if transaction_created_at is not None:
        try:
            _enforce_refund_window(transaction_created_at)
        except ValueError as e:
            logger.warning(f"Partial refund rejected for txn {transaction_id}: {e}")
            return {"success": False, "error": str(e)}

    gateway_result = _post_reversal(
        transaction_id, partial_amount, reason,
        {"initiated_by": initiated_by, "refund_type": "partial"},
    )
    refund_id = gateway_result.get("refund_id") or f"PREF-{transaction_id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

    result = {
        "refund_id": refund_id,
        "transaction_id": transaction_id,
        "partial_amount": str(partial_amount),
        "refund_type": "partial",
        "status": gateway_result.get("status", RefundStatus.PROCESSING.value),
        "reason": reason,
        "initiated_by": initiated_by,
        "initiated_at": datetime.utcnow().isoformat(),
        "gateway_reference": gateway_result.get("reversal_reference"),
    }
    logger.info(f"Partial refund initiated: {refund_id}")
    return {"success": True, "refund": result}


def refund_to_original_payment_method(
    transaction_id: str,
    amount: Decimal,
    gateway_reference: str,
) -> Dict:
    """Refund to the original payment method via the payment gateway."""
    gateway_result = _post_reversal(
        transaction_id, amount, "refund_to_original",
        {"gateway_reference": gateway_reference, "method": RefundMethod.ORIGINAL.value},
    )

    result = {
        "transaction_id": transaction_id,
        "amount": str(amount),
        "method": RefundMethod.ORIGINAL.value,
        "gateway_reference": gateway_reference,
        "status": gateway_result.get("status", RefundStatus.PROCESSING.value),
        "processed_at": datetime.utcnow().isoformat(),
    }
    logger.info(f"Refund to original method initiated for txn {transaction_id}")
    return {"success": True, "refund": result}


def refund_to_wallet(
    agent_id: str,
    transaction_id: str,
    amount: Decimal,
) -> Dict:
    """Refund to agent's wallet by posting a real reversal transfer on the ledger."""
    if not TIGERBEETLE_SERVICE_URL:
        raise RuntimeError("TIGERBEETLE_SERVICE_URL not configured — wallet credit rail unavailable")

    try:
        response = httpx.post(
            f"{TIGERBEETLE_SERVICE_URL.rstrip('/')}/transfer",
            json={
                "from_user_id": "platform_refund_pool",
                "to_user_id": agent_id,
                "amount": float(amount),
                "transaction_type": "refund_wallet_credit",
                "description": f"Wallet refund for transaction {transaction_id}",
            },
            timeout=30.0,
        )
    except Exception as e:
        raise RuntimeError(f"ledger service unreachable: {e}") from e
    if response.status_code >= 400:
        raise RuntimeError(f"ledger rejected wallet refund transfer: HTTP {response.status_code}")

    ledger_result = response.json() if response.content else {}

    result = {
        "agent_id": agent_id,
        "transaction_id": transaction_id,
        "amount": str(amount),
        "method": RefundMethod.WALLET.value,
        "status": RefundStatus.COMPLETED.value,  # Only reached after the ledger accepted the transfer
        "transfer_id": ledger_result.get("transfer_id"),
        "credited_at": datetime.utcnow().isoformat(),
    }
    logger.info(f"Wallet refund completed for agent {agent_id}, txn {transaction_id}")
    return {"success": True, "refund": result}


def get_refund_status(refund_id: str) -> Dict:
    """Get the current status of a refund from the refund-service API."""
    refund_service_url = os.environ.get("REFUND_SERVICE_URL", "")
    if not refund_service_url:
        raise RuntimeError("REFUND_SERVICE_URL not configured — cannot query refund status")
    try:
        response = httpx.get(
            f"{refund_service_url.rstrip('/')}/api/v1/refunds/{refund_id}", timeout=15.0)
    except Exception as e:
        raise RuntimeError(f"refund-service unreachable: {e}") from e
    if response.status_code == 404:
        raise LookupError(f"refund '{refund_id}' not found")
    if response.status_code >= 400:
        raise RuntimeError(f"refund-service returned HTTP {response.status_code}")
    logger.info(f"Fetched refund status for {refund_id}")
    return response.json()
