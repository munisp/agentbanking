"""
Stripe Payment Gateway - Production Implementation.
Replaces all NotImplementedError stubs with real Stripe API calls.
"""
import hashlib
import hmac
import json
import logging
import os
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

STRIPE_BASE_URL = "https://api.stripe.com/v1"
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")


def _get_headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {STRIPE_SECRET_KEY}",
        "Content-Type": "application/x-www-form-urlencoded",
    }


async def initialize_transaction(
    amount: int,
    currency: str,
    email: str,
    metadata: Optional[Dict[str, Any]] = None,
    success_url: Optional[str] = None,
    cancel_url: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Create a Stripe Checkout Session."""
    params = {
        "payment_method_types[]": "card",
        "mode": "payment",
        "success_url": success_url or os.environ.get("STRIPE_SUCCESS_URL", "https://example.com/success"),
        "cancel_url": cancel_url or os.environ.get("STRIPE_CANCEL_URL", "https://example.com/cancel"),
        "customer_email": email,
        "line_items[0][price_data][currency]": currency.lower(),
        "line_items[0][price_data][unit_amount]": str(amount),
        "line_items[0][price_data][product_data][name]": "Payment",
        "line_items[0][quantity]": "1",
    }
    if metadata:
        for k, v in metadata.items():
            params[f"metadata[{k}]"] = str(v)

    async with httpx.AsyncClient(base_url=STRIPE_BASE_URL, timeout=30.0) as client:
        resp = await client.post("/checkout/sessions", data=params, headers=_get_headers())
        resp.raise_for_status()
        session = resp.json()
        return {
            "reference": session["id"],
            "authorization_url": session["url"],
            "payment_intent": session.get("payment_intent"),
        }


async def verify_transaction(reference: str) -> Dict[str, Any]:
    """Verify a Stripe Checkout Session or PaymentIntent."""
    async with httpx.AsyncClient(base_url=STRIPE_BASE_URL, timeout=30.0) as client:
        # Try as checkout session first
        resp = await client.get(f"/checkout/sessions/{reference}", headers=_get_headers())
        if resp.status_code == 200:
            session = resp.json()
            return {
                "reference": session["id"],
                "status": session.get("payment_status"),
                "amount": session.get("amount_total"),
                "currency": session.get("currency"),
                "customer_email": session.get("customer_email"),
                "payment_intent": session.get("payment_intent"),
            }
        # Try as payment intent
        resp2 = await client.get(f"/payment_intents/{reference}", headers=_get_headers())
        resp2.raise_for_status()
        pi = resp2.json()
        return {
            "reference": pi["id"],
            "status": pi.get("status"),
            "amount": pi.get("amount"),
            "currency": pi.get("currency"),
        }


async def handle_webhook(payload: bytes, signature: str) -> Dict[str, Any]:
    """Process and verify a Stripe webhook using Stripe-Signature header."""
    if not STRIPE_WEBHOOK_SECRET:
        raise ValueError("Stripe webhook secret not configured")

    # Stripe signature format: t=timestamp,v1=signature
    parts = {k: v for k, v in (p.split("=", 1) for p in signature.split(","))}
    timestamp = parts.get("t", "")
    v1_sig = parts.get("v1", "")

    signed_payload = f"{timestamp}.{payload.decode()}"
    expected = hmac.new(
        STRIPE_WEBHOOK_SECRET.encode(),
        signed_payload.encode(),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected, v1_sig):
        raise ValueError("Invalid Stripe webhook signature")

    event = json.loads(payload)
    return {
        "event_id": event.get("id"),
        "event_type": event.get("type"),
        "data": event.get("data", {}).get("object", {}),
        "processed": True,
    }


async def refund_transaction(reference: str, amount: Optional[int] = None) -> Dict[str, Any]:
    """Initiate a Stripe refund."""
    params: Dict[str, str] = {"payment_intent": reference}
    if amount is not None:
        params["amount"] = str(amount)

    async with httpx.AsyncClient(base_url=STRIPE_BASE_URL, timeout=30.0) as client:
        resp = await client.post("/refunds", data=params, headers=_get_headers())
        resp.raise_for_status()
        refund = resp.json()
        return {
            "refund_id": refund.get("id"),
            "status": refund.get("status"),
            "amount": refund.get("amount"),
            "reference": reference,
        }


async def create_payment_intent(
    amount: int,
    currency: str,
    customer_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create a Stripe PaymentIntent for direct API integration."""
    params: Dict[str, str] = {
        "amount": str(amount),
        "currency": currency.lower(),
        "automatic_payment_methods[enabled]": "true",
    }
    if customer_id:
        params["customer"] = customer_id
    if metadata:
        for k, v in metadata.items():
            params[f"metadata[{k}]"] = str(v)

    async with httpx.AsyncClient(base_url=STRIPE_BASE_URL, timeout=30.0) as client:
        resp = await client.post("/payment_intents", data=params, headers=_get_headers())
        resp.raise_for_status()
        pi = resp.json()
        return {
            "payment_intent_id": pi["id"],
            "client_secret": pi["client_secret"],
            "status": pi["status"],
            "amount": pi["amount"],
            "currency": pi["currency"],
        }


async def list_transactions(
    limit: int = 50,
    starting_after: Optional[str] = None,
) -> Dict[str, Any]:
    """List Stripe payment intents."""
    params: Dict[str, str] = {"limit": str(limit)}
    if starting_after:
        params["starting_after"] = starting_after

    async with httpx.AsyncClient(base_url=STRIPE_BASE_URL, timeout=30.0) as client:
        resp = await client.get("/payment_intents", params=params, headers=_get_headers())
        resp.raise_for_status()
        data = resp.json()
        return {
            "transactions": data.get("data", []),
            "has_more": data.get("has_more", False),
        }
