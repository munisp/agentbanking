"""
Interswitch Payment Gateway - Production Implementation.
Replaces all NotImplementedError stubs with real Interswitch API calls.
"""
import base64
import hashlib
import hmac
import json
import logging
import os
import time
import uuid
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

INTERSWITCH_BASE_URL = os.environ.get("INTERSWITCH_BASE_URL", "https://api.interswitchgroup.com")
INTERSWITCH_CLIENT_ID = os.environ.get("INTERSWITCH_CLIENT_ID", "")
INTERSWITCH_CLIENT_SECRET = os.environ.get("INTERSWITCH_CLIENT_SECRET", "")
INTERSWITCH_TERMINAL_ID = os.environ.get("INTERSWITCH_TERMINAL_ID", "")

_access_token: Optional[str] = None
_token_expiry: float = 0.0


def _get_access_token() -> str:
    """Obtain OAuth2 access token from Interswitch."""
    global _access_token, _token_expiry
    now = time.time()
    if _access_token and now < _token_expiry - 30:
        return _access_token

    credentials = base64.b64encode(
        f"{INTERSWITCH_CLIENT_ID}:{INTERSWITCH_CLIENT_SECRET}".encode()
    ).decode()

    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            f"{INTERSWITCH_BASE_URL}/passport/oauth/token",
            data={"grant_type": "client_credentials"},
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        _access_token = data["access_token"]
        _token_expiry = now + data.get("expires_in", 3600)
        return _access_token


def _get_headers() -> Dict[str, str]:
    """Build authenticated headers for Interswitch API."""
    token = _get_access_token()
    timestamp = str(int(time.time()))
    nonce = uuid.uuid4().hex
    return {
        "Authorization": f"InterswitchAuth {token}",
        "Timestamp": timestamp,
        "Nonce": nonce,
        "Content-Type": "application/json",
        "Accept": "application/json",
        "TerminalID": INTERSWITCH_TERMINAL_ID,
    }


async def initialize_transaction(
    amount: int,
    currency: str,
    email: str,
    metadata: Optional[Dict[str, Any]] = None,
    redirect_url: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Initialize an Interswitch Quickteller payment."""
    reference = f"ISW-{uuid.uuid4().hex[:16].upper()}"
    payload = {
        "merchantCode": INTERSWITCH_CLIENT_ID,
        "payableCode": os.environ.get("INTERSWITCH_PAYABLE_CODE", ""),
        "amount": str(amount),
        "transactionReference": reference,
        "redirectUrl": redirect_url or os.environ.get("INTERSWITCH_REDIRECT_URL", ""),
        "currency": currency,
        "customerEmail": email,
    }
    if metadata:
        payload["customData"] = json.dumps(metadata)

    async with httpx.AsyncClient(base_url=INTERSWITCH_BASE_URL, timeout=30.0) as client:
        resp = await client.post(
            "/collections/api/v1/initiate",
            json=payload,
            headers=_get_headers(),
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "reference": reference,
            "authorization_url": data.get("redirectUrl", ""),
            "payment_id": data.get("paymentId", ""),
        }


async def verify_transaction(reference: str) -> Dict[str, Any]:
    """Verify an Interswitch transaction."""
    async with httpx.AsyncClient(base_url=INTERSWITCH_BASE_URL, timeout=30.0) as client:
        resp = await client.get(
            f"/collections/api/v1/gettransaction/v2/reference/{reference}",
            headers=_get_headers(),
        )
        resp.raise_for_status()
        tx = resp.json()
        return {
            "reference": reference,
            "status": "success" if tx.get("responseCode") == "00" else "failed",
            "response_code": tx.get("responseCode"),
            "amount": tx.get("amount"),
            "currency": tx.get("currencyCode"),
            "payment_date": tx.get("paymentDate"),
        }


async def handle_webhook(payload: bytes, signature: str) -> Dict[str, Any]:
    """Process an Interswitch webhook notification."""
    # Interswitch uses HMAC-SHA512 for webhook verification
    webhook_secret = os.environ.get("INTERSWITCH_WEBHOOK_SECRET", INTERSWITCH_CLIENT_SECRET)
    expected = hmac.new(webhook_secret.encode(), payload, hashlib.sha512).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise ValueError("Invalid Interswitch webhook signature")

    event = json.loads(payload)
    return {
        "event_type": event.get("eventType"),
        "reference": event.get("transactionReference"),
        "status": event.get("status"),
        "processed": True,
    }


async def refund_transaction(reference: str, amount: Optional[int] = None) -> Dict[str, Any]:
    """Initiate an Interswitch refund."""
    payload: Dict[str, Any] = {
        "transactionReference": reference,
        "merchantCode": INTERSWITCH_CLIENT_ID,
    }
    if amount is not None:
        payload["amount"] = str(amount)

    async with httpx.AsyncClient(base_url=INTERSWITCH_BASE_URL, timeout=30.0) as client:
        resp = await client.post(
            "/collections/api/v1/refund",
            json=payload,
            headers=_get_headers(),
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "refund_reference": data.get("refundReference"),
            "status": "success" if data.get("responseCode") == "00" else "failed",
            "amount": amount,
            "original_reference": reference,
        }
