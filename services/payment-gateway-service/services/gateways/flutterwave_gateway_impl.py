"""
Flutterwave Payment Gateway - Production Implementation.
Replaces all NotImplementedError stubs with real Flutterwave API calls.
"""
import hashlib
import hmac
import json
import logging
import os
import uuid
from decimal import Decimal
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

FLW_BASE_URL = "https://api.flutterwave.com/v3"
FLW_SECRET_KEY = os.environ.get("FLUTTERWAVE_SECRET_KEY", "")
FLW_WEBHOOK_SECRET = os.environ.get("FLUTTERWAVE_WEBHOOK_SECRET", "")
FLW_ENCRYPTION_KEY = os.environ.get("FLUTTERWAVE_ENCRYPTION_KEY", "")


def _get_headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {FLW_SECRET_KEY}",
        "Content-Type": "application/json",
    }


async def initialize_transaction(
    amount: int,
    currency: str,
    email: str,
    metadata: Optional[Dict[str, Any]] = None,
    redirect_url: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Initialize a Flutterwave payment."""
    tx_ref = f"FLW-{uuid.uuid4().hex[:16].upper()}"
    payload: Dict[str, Any] = {
        "tx_ref": tx_ref,
        "amount": amount / 100,  # Flutterwave uses full currency units
        "currency": currency,
        "redirect_url": redirect_url or os.environ.get("FLW_REDIRECT_URL", "https://example.com/callback"),
        "customer": {"email": email},
    }
    if metadata:
        payload["meta"] = metadata

    async with httpx.AsyncClient(base_url=FLW_BASE_URL, timeout=30.0) as client:
        resp = await client.post("/payments", json=payload, headers=_get_headers())
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "success":
            raise ValueError(f"Flutterwave error: {data.get('message')}")
        return {
            "reference": tx_ref,
            "authorization_url": data["data"]["link"],
            "flw_ref": data["data"].get("flw_ref", tx_ref),
        }


async def verify_transaction(reference: str) -> Dict[str, Any]:
    """Verify a Flutterwave transaction by reference."""
    async with httpx.AsyncClient(base_url=FLW_BASE_URL, timeout=30.0) as client:
        resp = await client.get(
            f"/transactions/verify_by_reference",
            params={"tx_ref": reference},
            headers=_get_headers(),
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "success":
            raise ValueError(f"Flutterwave verification error: {data.get('message')}")
        tx = data["data"]
        return {
            "reference": tx.get("tx_ref"),
            "flw_ref": tx.get("flw_ref"),
            "status": tx.get("status"),
            "amount": int(float(tx.get("amount", 0)) * 100),
            "currency": tx.get("currency"),
            "paid_at": tx.get("created_at"),
            "customer": tx.get("customer", {}),
        }


async def handle_webhook(payload: bytes, signature: str) -> Dict[str, Any]:
    """Process and verify a Flutterwave webhook."""
    if FLW_WEBHOOK_SECRET:
        expected = hmac.new(FLW_WEBHOOK_SECRET.encode(), payload, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise ValueError("Invalid Flutterwave webhook signature")

    event = json.loads(payload)
    return {
        "event": event.get("event"),
        "data": event.get("data", {}),
        "processed": True,
    }


async def refund_transaction(reference: str, amount: Optional[int] = None) -> Dict[str, Any]:
    """Initiate a Flutterwave refund by transaction ID."""
    # First, get the transaction ID from the reference
    async with httpx.AsyncClient(base_url=FLW_BASE_URL, timeout=30.0) as client:
        # Get transaction by reference
        verify_resp = await client.get(
            "/transactions/verify_by_reference",
            params={"tx_ref": reference},
            headers=_get_headers(),
        )
        verify_resp.raise_for_status()
        tx_data = verify_resp.json().get("data", {})
        transaction_id = tx_data.get("id")

        if not transaction_id:
            raise ValueError(f"Transaction not found for reference: {reference}")

        # Initiate refund
        payload: Dict[str, Any] = {}
        if amount is not None:
            payload["amount"] = amount / 100  # Convert to full currency units

        refund_resp = await client.post(
            f"/transactions/{transaction_id}/refund",
            json=payload,
            headers=_get_headers(),
        )
        refund_resp.raise_for_status()
        refund_data = refund_resp.json()
        return {
            "refund_id": refund_data.get("data", {}).get("id"),
            "status": refund_data.get("data", {}).get("status"),
            "amount": amount,
            "reference": reference,
        }


async def initiate_transfer(
    amount: Decimal,
    currency: str,
    account_number: str,
    bank_code: str,
    account_name: str,
    narration: str = "",
) -> Dict[str, Any]:
    """Initiate a Flutterwave bank transfer."""
    payload = {
        "account_bank": bank_code,
        "account_number": account_number,
        "amount": float(amount),
        "currency": currency,
        "narration": narration or f"Transfer to {account_name}",
        "reference": f"FLW-TRF-{uuid.uuid4().hex[:12].upper()}",
        "beneficiary_name": account_name,
    }

    async with httpx.AsyncClient(base_url=FLW_BASE_URL, timeout=30.0) as client:
        resp = await client.post("/transfers", json=payload, headers=_get_headers())
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "success":
            raise ValueError(f"Flutterwave transfer error: {data.get('message')}")
        return {
            "transfer_id": data["data"].get("id"),
            "reference": data["data"].get("reference"),
            "status": data["data"].get("status"),
            "amount": float(amount),
            "currency": currency,
        }
