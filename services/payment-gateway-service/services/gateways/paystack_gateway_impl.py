"""
Paystack Payment Gateway - Production Implementation.
Replaces all NotImplementedError stubs with real Paystack API calls.
"""
import hashlib
import hmac
import json
import logging
import os
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

PAYSTACK_BASE_URL = "https://api.paystack.co"
PAYSTACK_SECRET_KEY = os.environ.get("PAYSTACK_SECRET_KEY", "")
PAYSTACK_WEBHOOK_SECRET = os.environ.get("PAYSTACK_WEBHOOK_SECRET", PAYSTACK_SECRET_KEY)


def _get_headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
    }


async def initialize_transaction(
    amount: int,
    currency: str,
    email: str,
    metadata: Optional[Dict[str, Any]] = None,
    callback_url: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Initialize a Paystack transaction."""
    payload: Dict[str, Any] = {
        "amount": amount,
        "currency": currency,
        "email": email,
    }
    if metadata:
        payload["metadata"] = metadata
    if callback_url:
        payload["callback_url"] = callback_url

    async with httpx.AsyncClient(base_url=PAYSTACK_BASE_URL, timeout=30.0) as client:
        resp = await client.post("/transaction/initialize", json=payload, headers=_get_headers())
        resp.raise_for_status()
        data = resp.json()
        if not data.get("status"):
            raise ValueError(f"Paystack error: {data.get('message')}")
        return {
            "reference": data["data"]["reference"],
            "authorization_url": data["data"]["authorization_url"],
            "access_code": data["data"]["access_code"],
        }


async def verify_transaction(reference: str) -> Dict[str, Any]:
    """Verify a Paystack transaction by reference."""
    async with httpx.AsyncClient(base_url=PAYSTACK_BASE_URL, timeout=30.0) as client:
        resp = await client.get(f"/transaction/verify/{reference}", headers=_get_headers())
        resp.raise_for_status()
        data = resp.json()
        if not data.get("status"):
            raise ValueError(f"Paystack verification error: {data.get('message')}")
        tx = data["data"]
        return {
            "reference": tx.get("reference"),
            "status": tx.get("status"),
            "amount": tx.get("amount"),
            "currency": tx.get("currency"),
            "paid_at": tx.get("paid_at"),
            "channel": tx.get("channel"),
            "customer": tx.get("customer", {}),
            "metadata": tx.get("metadata", {}),
        }


async def handle_webhook(payload: bytes, signature: str) -> Dict[str, Any]:
    """Process and verify a Paystack webhook."""
    expected = hmac.new(
        PAYSTACK_WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha512,
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise ValueError("Invalid Paystack webhook signature")

    event = json.loads(payload)
    return {
        "event": event.get("event"),
        "data": event.get("data", {}),
        "processed": True,
    }


async def refund_transaction(reference: str, amount: Optional[int] = None) -> Dict[str, Any]:
    """Initiate a Paystack refund."""
    payload: Dict[str, Any] = {"transaction": reference}
    if amount is not None:
        payload["amount"] = amount

    async with httpx.AsyncClient(base_url=PAYSTACK_BASE_URL, timeout=30.0) as client:
        resp = await client.post("/refund", json=payload, headers=_get_headers())
        resp.raise_for_status()
        data = resp.json()
        if not data.get("status"):
            raise ValueError(f"Paystack refund error: {data.get('message')}")
        return {
            "refund_id": data["data"].get("id"),
            "status": data["data"].get("status"),
            "amount": data["data"].get("amount"),
            "reference": reference,
        }


async def list_transactions(
    page: int = 1,
    per_page: int = 50,
    status: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> Dict[str, Any]:
    """List Paystack transactions with pagination."""
    params: Dict[str, Any] = {"page": page, "perPage": per_page}
    if status:
        params["status"] = status
    if from_date:
        params["from"] = from_date
    if to_date:
        params["to"] = to_date

    async with httpx.AsyncClient(base_url=PAYSTACK_BASE_URL, timeout=30.0) as client:
        resp = await client.get("/transaction", params=params, headers=_get_headers())
        resp.raise_for_status()
        data = resp.json()
        return {
            "transactions": data.get("data", []),
            "meta": data.get("meta", {}),
        }


async def get_transaction(transaction_id: int) -> Dict[str, Any]:
    """Get a specific Paystack transaction by ID."""
    async with httpx.AsyncClient(base_url=PAYSTACK_BASE_URL, timeout=30.0) as client:
        resp = await client.get(f"/transaction/{transaction_id}", headers=_get_headers())
        resp.raise_for_status()
        return resp.json().get("data", {})


async def charge_authorization(
    authorization_code: str,
    email: str,
    amount: int,
    currency: str = "NGN",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Charge a returning customer using their saved authorization code."""
    payload: Dict[str, Any] = {
        "authorization_code": authorization_code,
        "email": email,
        "amount": amount,
        "currency": currency,
    }
    if metadata:
        payload["metadata"] = metadata

    async with httpx.AsyncClient(base_url=PAYSTACK_BASE_URL, timeout=30.0) as client:
        resp = await client.post("/transaction/charge_authorization", json=payload, headers=_get_headers())
        resp.raise_for_status()
        data = resp.json()
        if not data.get("status"):
            raise ValueError(f"Paystack charge error: {data.get('message')}")
        return {
            "reference": data["data"].get("reference"),
            "status": data["data"].get("status"),
            "amount": data["data"].get("amount"),
        }
