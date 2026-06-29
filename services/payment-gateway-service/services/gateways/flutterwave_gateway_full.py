"""
Flutterwave Payment Gateway - Full Production Implementation
Replaces all NotImplementedError stubs with real API calls.
"""
import hmac
import hashlib
import json
import logging
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger(__name__)

FLUTTERWAVE_BASE_URL = "https://api.flutterwave.com/v3"


class FlutterwaveGateway:
    """Full production Flutterwave gateway implementation."""

    def __init__(self, secret_key: str, public_key: str, encryption_key: str):
        self.secret_key = secret_key
        self.public_key = public_key
        self.encryption_key = encryption_key
        self.base_url = FLUTTERWAVE_BASE_URL
        self.headers = {
            "Authorization": f"Bearer {secret_key}",
            "Content-Type": "application/json",
        }

    async def initialize_payment(
        self,
        amount: float,
        currency: str,
        customer_info: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        redirect_url: str = "",
    ) -> Dict[str, Any]:
        """Initialize a Flutterwave payment and return checkout URL."""
        tx_ref = f"54agent-{customer_info.get('agent_id', 'unknown')}-{int(__import__('time').time())}"
        payload = {
            "tx_ref": tx_ref,
            "amount": amount,
            "currency": currency,
            "redirect_url": redirect_url,
            "customer": {
                "email": customer_info.get("email", ""),
                "phonenumber": customer_info.get("phone", ""),
                "name": customer_info.get("name", ""),
            },
            "customizations": {
                "title": "54agent Agency Banking",
                "description": metadata.get("description", "Payment") if metadata else "Payment",
            },
            "meta": metadata or {},
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.base_url}/payments",
                headers=self.headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
        return {
            "gateway": "flutterwave",
            "tx_ref": tx_ref,
            "payment_link": data.get("data", {}).get("link", ""),
            "status": data.get("status", ""),
            "message": data.get("message", ""),
        }

    async def verify_transaction(self, transaction_id: str) -> Dict[str, Any]:
        """Verify a Flutterwave transaction by ID."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{self.base_url}/transactions/{transaction_id}/verify",
                headers=self.headers,
            )
            resp.raise_for_status()
            data = resp.json()
        txn = data.get("data", {})
        return {
            "gateway": "flutterwave",
            "transaction_id": transaction_id,
            "status": txn.get("status", ""),
            "amount": txn.get("amount", 0),
            "currency": txn.get("currency", ""),
            "customer_email": txn.get("customer", {}).get("email", ""),
            "tx_ref": txn.get("tx_ref", ""),
            "flw_ref": txn.get("flw_ref", ""),
            "narration": txn.get("narration", ""),
            "created_at": txn.get("created_at", ""),
        }

    async def initiate_transfer(
        self,
        amount: float,
        currency: str,
        account_number: str,
        bank_code: str,
        narration: str,
        reference: str,
    ) -> Dict[str, Any]:
        """Initiate a bank transfer via Flutterwave."""
        payload = {
            "account_bank": bank_code,
            "account_number": account_number,
            "amount": amount,
            "narration": narration,
            "currency": currency,
            "reference": reference,
            "callback_url": "",
            "debit_currency": currency,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.base_url}/transfers",
                headers=self.headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
        return {
            "gateway": "flutterwave",
            "transfer_id": data.get("data", {}).get("id", ""),
            "reference": reference,
            "status": data.get("data", {}).get("status", ""),
            "amount": amount,
            "currency": currency,
        }

    async def get_banks(self, country: str = "NG") -> List[Dict[str, Any]]:
        """Get list of banks for a country."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{self.base_url}/banks/{country}",
                headers=self.headers,
            )
            resp.raise_for_status()
            data = resp.json()
        return data.get("data", [])

    async def validate_account(self, account_number: str, bank_code: str) -> Dict[str, Any]:
        """Validate a bank account number."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{self.base_url}/accounts/resolve",
                headers=self.headers,
                params={"account_number": account_number, "account_bank": bank_code},
            )
            resp.raise_for_status()
            data = resp.json()
        return {
            "account_number": account_number,
            "account_name": data.get("data", {}).get("account_name", ""),
            "bank_code": bank_code,
            "valid": data.get("status") == "success",
        }

    def verify_webhook(self, payload: bytes, signature: str) -> bool:
        """Verify Flutterwave webhook signature."""
        expected = hmac.new(
            self.secret_key.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    async def refund_transaction(
        self, transaction_id: str, amount: Optional[float] = None
    ) -> Dict[str, Any]:
        """Refund a Flutterwave transaction (full or partial)."""
        payload = {"id": transaction_id}
        if amount:
            payload["amount"] = amount
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.base_url}/transactions/{transaction_id}/refund",
                headers=self.headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
        return {
            "gateway": "flutterwave",
            "transaction_id": transaction_id,
            "refund_status": data.get("data", {}).get("status", ""),
            "amount_refunded": data.get("data", {}).get("amount_refunded", 0),
        }
