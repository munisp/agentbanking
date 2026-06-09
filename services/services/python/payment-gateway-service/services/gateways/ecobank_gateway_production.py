"""
Ecobank Payment Gateway - Production Implementation.
Supports pan-African payments across 33+ African countries.
"""
import os
import json
import logging
import uuid
import time
import hmac
import hashlib
from datetime import datetime
from decimal import Decimal
from typing import Dict, Optional, List

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

ECOBANK_API_BASE = os.environ.get("ECOBANK_API_BASE", "https://developer.ecobank.com/corporatepay/api")
ECOBANK_CLIENT_ID = os.environ.get("ECOBANK_CLIENT_ID", "")
ECOBANK_CLIENT_SECRET = os.environ.get("ECOBANK_CLIENT_SECRET", "")
ECOBANK_AFFILIATE_CODE = os.environ.get("ECOBANK_AFFILIATE_CODE", "")
ECOBANK_WEBHOOK_SECRET = os.environ.get("ECOBANK_WEBHOOK_SECRET", "")

# Ecobank supported currencies by country
ECOBANK_SUPPORTED_CURRENCIES = {
    "NGN": "NG", "GHS": "GH", "KES": "KE", "TZS": "TZ", "UGX": "UG",
    "ZAR": "ZA", "ETB": "ET", "XOF": "CI", "XAF": "CM", "ZMW": "ZM",
    "MWK": "MW", "RWF": "RW", "BIF": "BI", "MZN": "MZ", "AOA": "AO",
    "BWP": "BW", "NAD": "NA", "SZL": "SZ", "LSL": "LS", "MUR": "MU",
    "SCR": "SC", "GMD": "GM", "SLL": "SL", "LRD": "LR", "GNF": "GN",
    "CDF": "CD", "SSP": "SS", "SDG": "SD", "EGP": "EG", "MAD": "MA",
    "DZD": "DZ", "TND": "TN", "LYD": "LY",
}

_access_token: Optional[str] = None
_token_expiry: float = 0.0


def _get_access_token() -> str:
    """Obtain OAuth2 access token from Ecobank."""
    global _access_token, _token_expiry
    now = time.time()
    if _access_token and now < _token_expiry - 30:
        return _access_token

    if not ECOBANK_CLIENT_ID or not ECOBANK_CLIENT_SECRET:
        raise ValueError("Ecobank credentials not configured")

    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            f"{ECOBANK_API_BASE}/user/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": ECOBANK_CLIENT_ID,
                "client_secret": ECOBANK_CLIENT_SECRET,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        data = resp.json()
        _access_token = data.get("access_token") or data.get("token")
        _token_expiry = now + data.get("expires_in", 3600)
        logger.info("Ecobank access token refreshed")
        return _access_token


def _get_headers(body: str = "") -> Dict[str, str]:
    """Build authenticated headers for Ecobank API."""
    token = _get_access_token()
    timestamp = str(int(time.time()))
    nonce = str(uuid.uuid4()).replace("-", "")
    body_hash = hashlib.sha256(body.encode()).hexdigest()
    string_to_sign = f"{timestamp}\n{nonce}\n{body_hash}"
    signature = hmac.new(
        ECOBANK_CLIENT_SECRET.encode(),
        string_to_sign.encode(),
        hashlib.sha256
    ).hexdigest()

    return {
        "Authorization": f"Bearer {token}",
        "X-Ecobank-Affiliate": ECOBANK_AFFILIATE_CODE,
        "X-Timestamp": timestamp,
        "X-Nonce": nonce,
        "X-Signature": signature,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _api_call(method: str, endpoint: str, data: Optional[Dict] = None) -> Dict:
    """Make authenticated Ecobank API call."""
    body_str = json.dumps(data) if data else ""
    headers = _get_headers(body_str)
    url = f"{ECOBANK_API_BASE}{endpoint}"

    with httpx.Client(timeout=30.0) as client:
        if method == "GET":
            resp = client.get(url, headers=headers)
        elif method == "POST":
            resp = client.post(url, content=body_str, headers=headers)
        else:
            raise ValueError(f"Unsupported method: {method}")

        if resp.status_code == 401:
            global _access_token
            _access_token = None
            raise Exception("Ecobank token expired")
        resp.raise_for_status()
        return resp.json()


def validate_account(
    account_number: str,
    bank_code: str,
    country_code: str,
    currency: str,
) -> Dict:
    """Validate a bank account via Ecobank account verification API."""
    payload = {
        "accountNumber": account_number,
        "bankCode": bank_code,
        "countryCode": country_code,
        "currency": currency,
    }
    try:
        response = _api_call("POST", "/account/validate", payload)
        return {
            "valid": response.get("valid", False),
            "account_name": response.get("accountName", ""),
            "bank_name": response.get("bankName", ""),
            "account_number": account_number,
            "bank_code": bank_code,
            "country_code": country_code,
        }
    except Exception as e:
        logger.error(f"Ecobank account validation failed: {e}")
        return {"valid": False, "error": str(e)}


def initiate_transfer(
    amount: Decimal,
    source_currency: str,
    target_currency: str,
    source_country: str,
    target_country: str,
    sender_account: str,
    sender_name: str,
    beneficiary_account: str,
    beneficiary_bank_code: str,
    beneficiary_name: str,
    reference: str,
    narration: str = "",
) -> Dict:
    """Initiate a cross-border transfer via Ecobank."""
    if source_currency not in ECOBANK_SUPPORTED_CURRENCIES:
        return {"success": False, "error": f"Unsupported source currency: {source_currency}"}
    if target_currency not in ECOBANK_SUPPORTED_CURRENCIES:
        return {"success": False, "error": f"Unsupported target currency: {target_currency}"}

    transaction_id = str(uuid.uuid4())
    payload = {
        "transactionId": transaction_id,
        "amount": str(amount),
        "sourceCurrency": source_currency,
        "targetCurrency": target_currency,
        "sourceCountry": source_country,
        "targetCountry": target_country,
        "sender": {
            "accountNumber": sender_account,
            "name": sender_name,
        },
        "beneficiary": {
            "accountNumber": beneficiary_account,
            "bankCode": beneficiary_bank_code,
            "name": beneficiary_name,
        },
        "reference": reference,
        "narration": narration or f"Transfer {transaction_id}",
        "submissionDateTime": datetime.utcnow().isoformat() + "Z",
    }

    try:
        response = _api_call("POST", "/transfer/initiate", payload)
        return {
            "success": True,
            "transaction_id": transaction_id,
            "ecobank_reference": response.get("reference"),
            "status": response.get("status", "PENDING"),
            "amount": str(amount),
            "source_currency": source_currency,
            "target_currency": target_currency,
            "exchange_rate": response.get("exchangeRate"),
            "charges": response.get("charges", {}),
            "initiated_at": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Ecobank transfer failed: {e}")
        return {"success": False, "error": str(e), "transaction_id": transaction_id}


def get_transaction_status(transaction_id: str) -> Dict:
    """Query Ecobank transaction status."""
    response = _api_call("GET", f"/transfer/status/{transaction_id}")
    return {
        "transaction_id": transaction_id,
        "status": response.get("status"),
        "settled_at": response.get("settlementDateTime"),
        "amount": response.get("amount"),
        "currency": response.get("currency"),
    }


def get_exchange_rate(source_currency: str, target_currency: str, amount: Decimal) -> Dict:
    """Get Ecobank exchange rate for a currency pair."""
    response = _api_call("GET", f"/rates/{source_currency}/{target_currency}?amount={amount}")
    return {
        "source_currency": source_currency,
        "target_currency": target_currency,
        "rate": response.get("rate"),
        "source_amount": str(amount),
        "target_amount": response.get("targetAmount"),
        "charges": response.get("charges"),
        "valid_until": response.get("validUntil"),
    }


def verify_webhook_signature(payload: bytes, headers: Dict[str, str]) -> bool:
    """Verify Ecobank webhook HMAC-SHA256 signature."""
    if not ECOBANK_WEBHOOK_SECRET:
        return False
    received = headers.get("X-Ecobank-Signature", "")
    expected = hmac.new(ECOBANK_WEBHOOK_SECRET.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(received, expected)
