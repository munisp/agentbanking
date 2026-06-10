"""
PAPSS (Pan-African Payment and Settlement System) Gateway - Production Implementation.
Replaces all mock implementations with real API calls, mTLS, and proper authentication.
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
from dataclasses import dataclass

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)


class PAPSSAPIError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


@dataclass
class PAPSSConfig:
    base_url: str = os.environ.get("PAPSS_API_URL", "https://api.papss.africa/v1")
    client_id: str = os.environ.get("PAPSS_CLIENT_ID", "")
    client_secret: str = os.environ.get("PAPSS_CLIENT_SECRET", "")
    participant_id: str = os.environ.get("PAPSS_PARTICIPANT_ID", "")
    cert_path: str = os.environ.get("PAPSS_CERT_PATH", "/etc/papss/tls/client.crt")
    key_path: str = os.environ.get("PAPSS_KEY_PATH", "/etc/papss/tls/client.key")
    ca_path: str = os.environ.get("PAPSS_CA_PATH", "/etc/papss/tls/ca.crt")
    webhook_secret: str = os.environ.get("PAPSS_WEBHOOK_SECRET", "")
    timeout: float = 30.0


class PAPSSGateway:
    """
    Production PAPSS gateway implementation.
    Supports real-time cross-border African payments via PAPSS infrastructure.
    """

    # PAPSS supported African currencies
    SUPPORTED_CURRENCIES = {
        "NGN", "GHS", "KES", "ZAR", "EGP", "MAD", "TZS", "UGX",
        "ETB", "XOF", "XAF", "ZMW", "RWF", "MZN", "AOA", "BWP",
    }

    def __init__(self, config: Optional[PAPSSConfig] = None):
        self.config = config or PAPSSConfig()
        self._access_token: Optional[str] = None
        self._token_expiry: float = 0.0

        if not self.config.client_id:
            logger.warning("PAPSS credentials not configured - set PAPSS_CLIENT_ID, PAPSS_CLIENT_SECRET")

    def _build_client(self) -> httpx.Client:
        """Build httpx client with mTLS support."""
        cert = None
        verify: object = True

        if os.path.exists(self.config.cert_path) and os.path.exists(self.config.key_path):
            cert = (self.config.cert_path, self.config.key_path)

        if os.path.exists(self.config.ca_path):
            verify = self.config.ca_path

        return httpx.Client(
            cert=cert,
            verify=verify,
            timeout=self.config.timeout,
        )

    def _get_access_token(self) -> str:
        """Obtain OAuth2 access token using client credentials grant."""
        now = time.time()
        if self._access_token and now < self._token_expiry - 30:
            return self._access_token

        with self._build_client() as client:
            response = client.post(
                f"{self.config.base_url}/oauth/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.config.client_id,
                    "client_secret": self.config.client_secret,
                    "scope": "payments:write payments:read",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            data = response.json()
            self._access_token = data["access_token"]
            self._token_expiry = now + data.get("expires_in", 3600)
            logger.info("PAPSS access token refreshed")
            return self._access_token

    def _get_headers(self, body: str = "") -> Dict[str, str]:
        """Build authenticated request headers with HMAC signature."""
        token = self._get_access_token()
        timestamp = str(int(time.time()))
        nonce = str(uuid.uuid4()).replace("-", "")
        body_hash = hashlib.sha256(body.encode()).hexdigest()
        string_to_sign = f"{timestamp}\n{nonce}\n{body_hash}"
        signature = hmac.new(
            self.config.client_secret.encode(),
            string_to_sign.encode(),
            hashlib.sha256
        ).hexdigest()

        return {
            "Authorization": f"Bearer {token}",
            "X-PAPSS-Participant-ID": self.config.participant_id,
            "X-PAPSS-Timestamp": timestamp,
            "X-PAPSS-Nonce": nonce,
            "X-PAPSS-Signature": signature,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(PAPSSAPIError),
        reraise=True,
    )
    def _api_call(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict:
        """Make authenticated PAPSS API call with retry logic."""
        body_str = json.dumps(data) if data else ""
        headers = self._get_headers(body_str)

        with self._build_client() as client:
            url = f"{self.config.base_url}{endpoint}"
            try:
                if method == "GET":
                    resp = client.get(url, headers=headers)
                elif method == "POST":
                    resp = client.post(url, content=body_str, headers=headers)
                else:
                    raise ValueError(f"Unsupported method: {method}")

                if resp.status_code == 401:
                    self._access_token = None  # Force token refresh
                    raise PAPSSAPIError("Unauthorized - token refreshed", 401)
                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", "5"))
                    time.sleep(retry_after)
                    raise PAPSSAPIError("Rate limited", 429)
                if resp.status_code >= 500:
                    raise PAPSSAPIError(f"PAPSS server error: {resp.status_code}", resp.status_code)
                if resp.status_code >= 400:
                    error = resp.json() if resp.content else {}
                    raise PAPSSAPIError(
                        f"PAPSS error: {error.get('message', resp.status_code)}",
                        resp.status_code
                    )
                return resp.json()
            except httpx.TimeoutException:
                raise PAPSSAPIError("PAPSS API timeout")
            except httpx.ConnectError as e:
                raise PAPSSAPIError(f"PAPSS connection error: {e}")

    def initiate_payment(
        self,
        amount: Decimal,
        source_currency: str,
        target_currency: str,
        sender_account: str,
        sender_bank_code: str,
        sender_country: str,
        beneficiary_account: str,
        beneficiary_bank_code: str,
        beneficiary_country: str,
        beneficiary_name: str,
        reference: str,
        purpose: str = "REMITTANCE",
    ) -> Dict:
        """Initiate a cross-border payment via PAPSS."""
        if source_currency not in self.SUPPORTED_CURRENCIES:
            return {"success": False, "error": f"Unsupported source currency: {source_currency}"}
        if target_currency not in self.SUPPORTED_CURRENCIES:
            return {"success": False, "error": f"Unsupported target currency: {target_currency}"}

        payment_id = str(uuid.uuid4())
        payload = {
            "paymentId": payment_id,
            "amount": str(amount),
            "sourceCurrency": source_currency,
            "targetCurrency": target_currency,
            "sender": {
                "accountNumber": sender_account,
                "bankCode": sender_bank_code,
                "country": sender_country,
            },
            "beneficiary": {
                "accountNumber": beneficiary_account,
                "bankCode": beneficiary_bank_code,
                "country": beneficiary_country,
                "name": beneficiary_name,
            },
            "reference": reference,
            "purpose": purpose,
            "submissionDateTime": datetime.utcnow().isoformat() + "Z",
        }

        try:
            response = self._api_call("POST", "/payments", payload)
            return {
                "success": True,
                "payment_id": payment_id,
                "papss_transaction_id": response.get("transactionId"),
                "status": response.get("status", "ACCEPTED"),
                "amount": str(amount),
                "source_currency": source_currency,
                "target_currency": target_currency,
                "exchange_rate": response.get("exchangeRate"),
                "target_amount": response.get("targetAmount"),
                "fees": response.get("fees", {}),
                "submitted_at": datetime.utcnow().isoformat(),
            }
        except PAPSSAPIError as e:
            logger.error(f"PAPSS payment failed: {e}")
            return {"success": False, "error": str(e), "payment_id": payment_id}

    def get_payment_status(self, transaction_id: str) -> Dict:
        """Query payment status from PAPSS."""
        response = self._api_call("GET", f"/payments/{transaction_id}")
        return {
            "transaction_id": transaction_id,
            "status": response.get("status"),
            "settled_at": response.get("settlementDateTime"),
            "amount": response.get("amount"),
            "source_currency": response.get("sourceCurrency"),
            "target_currency": response.get("targetCurrency"),
        }

    def get_exchange_rate(self, source_currency: str, target_currency: str) -> Dict:
        """Get real-time exchange rate from PAPSS."""
        response = self._api_call("GET", f"/rates/{source_currency}/{target_currency}")
        return {
            "source_currency": source_currency,
            "target_currency": target_currency,
            "rate": response.get("rate"),
            "timestamp": response.get("timestamp", datetime.utcnow().isoformat()),
            "valid_until": response.get("validUntil"),
        }

    def verify_webhook_signature(self, payload: bytes, headers: Dict[str, str]) -> bool:
        """Verify PAPSS webhook signature using HMAC-SHA256."""
        if not self.config.webhook_secret:
            logger.warning("PAPSS webhook secret not configured")
            return False

        received_signature = headers.get("X-PAPSS-Signature", "")
        if not received_signature:
            return False

        expected = hmac.new(
            self.config.webhook_secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(received_signature, expected)

    def handle_webhook(self, payload_str: str, signature: str) -> Dict:
        """Process incoming PAPSS webhook notification."""
        payload_bytes = payload_str.encode()
        if not self.verify_webhook_signature(payload_bytes, {"X-PAPSS-Signature": signature}):
            raise ValueError("Invalid PAPSS webhook signature")

        event = json.loads(payload_str)
        event_type = event.get("eventType")
        transaction_id = event.get("transactionId")
        status = event.get("status")

        logger.info(f"PAPSS webhook: {event_type} for transaction {transaction_id}, status: {status}")

        return {
            "processed": True,
            "event_type": event_type,
            "transaction_id": transaction_id,
            "status": status,
            "processed_at": datetime.utcnow().isoformat(),
        }
