"""
PIX (Brazilian Instant Payment System) Gateway - Production Implementation.
Integrates with Banco Central do Brasil PIX API using mTLS and OAuth2.
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
from typing import Dict, Optional
from enum import Enum

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)


class PIXKeyType(str, Enum):
    CPF = "CPF"
    CNPJ = "CNPJ"
    PHONE = "PHONE"
    EMAIL = "EMAIL"
    EVP = "EVP"  # Random key


class PIXAPIError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


# Configuration from environment
PIX_API_BASE = os.environ.get("PIX_API_BASE", "https://pix.bcb.gov.br")
PIX_CLIENT_ID = os.environ.get("PIX_CLIENT_ID", "")
PIX_CLIENT_SECRET = os.environ.get("PIX_CLIENT_SECRET", "")
PIX_CERT_PATH = os.environ.get("PIX_CERT_PATH", "/etc/pix/tls/client.crt")
PIX_KEY_PATH = os.environ.get("PIX_KEY_PATH", "/etc/pix/tls/client.key")
PIX_CA_PATH = os.environ.get("PIX_CA_PATH", "/etc/pix/tls/ca.crt")
PIX_WEBHOOK_SECRET = os.environ.get("PIX_WEBHOOK_SECRET", "")

# Token cache
_access_token: Optional[str] = None
_token_expiry: float = 0.0


def _build_client() -> httpx.Client:
    """Build mTLS-enabled httpx client for PIX API."""
    cert = None
    verify: object = True
    if os.path.exists(PIX_CERT_PATH) and os.path.exists(PIX_KEY_PATH):
        cert = (PIX_CERT_PATH, PIX_KEY_PATH)
    if os.path.exists(PIX_CA_PATH):
        verify = PIX_CA_PATH
    return httpx.Client(cert=cert, verify=verify, timeout=30.0)


def _get_access_token() -> str:
    """Obtain OAuth2 access token for PIX API using client credentials."""
    global _access_token, _token_expiry
    now = time.time()
    if _access_token and now < _token_expiry - 30:
        return _access_token

    if not PIX_CLIENT_ID or not PIX_CLIENT_SECRET:
        raise PIXAPIError("PIX credentials not configured - set PIX_CLIENT_ID and PIX_CLIENT_SECRET")

    with _build_client() as client:
        resp = client.post(
            f"{PIX_API_BASE}/oauth/token",
            data={
                "grant_type": "client_credentials",
                "client_id": PIX_CLIENT_ID,
                "client_secret": PIX_CLIENT_SECRET,
                "scope": "cob.write cob.read cobv.write cobv.read pix.write pix.read",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        data = resp.json()
        _access_token = data["access_token"]
        _token_expiry = now + data.get("expires_in", 3600)
        logger.info("PIX OAuth2 token refreshed")
        return _access_token


def _get_headers() -> Dict[str, str]:
    """Build authenticated headers for PIX API."""
    return {
        "Authorization": f"Bearer {_get_access_token()}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(PIXAPIError),
    reraise=True,
)
def _api_call(method: str, endpoint: str, data: Optional[Dict] = None) -> Dict:
    """Make authenticated PIX API call."""
    with _build_client() as client:
        url = f"{PIX_API_BASE}{endpoint}"
        headers = _get_headers()
        try:
            if method == "GET":
                resp = client.get(url, headers=headers)
            elif method == "POST":
                resp = client.post(url, json=data, headers=headers)
            elif method == "PUT":
                resp = client.put(url, json=data, headers=headers)
            elif method == "PATCH":
                resp = client.patch(url, json=data, headers=headers)
            elif method == "DELETE":
                resp = client.delete(url, headers=headers)
            else:
                raise ValueError(f"Unsupported method: {method}")

            if resp.status_code == 401:
                global _access_token
                _access_token = None
                raise PIXAPIError("Unauthorized - refreshing token", 401)
            if resp.status_code == 429:
                time.sleep(int(resp.headers.get("Retry-After", "5")))
                raise PIXAPIError("Rate limited", 429)
            if resp.status_code >= 500:
                raise PIXAPIError(f"PIX server error: {resp.status_code}", resp.status_code)
            if resp.status_code >= 400:
                error = resp.json() if resp.content else {}
                raise PIXAPIError(f"PIX error: {error.get('mensagem', resp.status_code)}", resp.status_code)

            return resp.json() if resp.content else {}
        except httpx.TimeoutException:
            raise PIXAPIError("PIX API timeout")
        except httpx.ConnectError as e:
            raise PIXAPIError(f"PIX connection error: {e}")


def create_immediate_charge(
    amount: Decimal,
    pix_key: str,
    pix_key_type: PIXKeyType,
    debtor_name: str,
    debtor_cpf_cnpj: str,
    description: str = "",
    expiration_seconds: int = 3600,
) -> Dict:
    """
    Create a PIX immediate charge (cob) via Banco Central API.
    Returns QR code and payment details.
    """
    txid = uuid.uuid4().hex[:26].upper()
    payload = {
        "calendario": {"expiracao": expiration_seconds},
        "devedor": {
            "cpf" if len(debtor_cpf_cnpj.replace(".", "").replace("-", "")) == 11 else "cnpj": debtor_cpf_cnpj,
            "nome": debtor_name,
        },
        "valor": {"original": f"{amount:.2f}"},
        "chave": pix_key,
        "solicitacaoPagador": description or f"PIX charge {txid}",
    }

    try:
        response = _api_call("PUT", f"/v2/cob/{txid}", payload)
        return {
            "success": True,
            "txid": txid,
            "status": response.get("status", "ATIVA"),
            "pix_copy_paste": response.get("pixCopiaECola", ""),
            "qr_code_url": response.get("imagemQrcode", ""),
            "amount": str(amount),
            "expiration": expiration_seconds,
            "created_at": datetime.utcnow().isoformat(),
        }
    except PIXAPIError as e:
        logger.error(f"PIX charge creation failed: {e}")
        return {"success": False, "error": str(e), "txid": txid}


def initiate_pix_payment(
    amount: Decimal,
    pix_key: str,
    pix_key_type: PIXKeyType,
    beneficiary_name: str,
    beneficiary_cpf_cnpj: str,
    description: str = "",
) -> Dict:
    """
    Initiate an outbound PIX payment (pix/send).
    """
    end_to_end_id = f"E{uuid.uuid4().hex[:29].upper()}"
    payload = {
        "valor": str(amount),
        "chave": pix_key,
        "infoPagador": description or f"PIX payment {end_to_end_id}",
        "endToEndId": end_to_end_id,
    }

    try:
        response = _api_call("POST", "/v2/pix", payload)
        return {
            "success": True,
            "end_to_end_id": end_to_end_id,
            "status": response.get("status", "REALIZADO"),
            "amount": str(amount),
            "pix_key": pix_key,
            "beneficiary_name": beneficiary_name,
            "initiated_at": datetime.utcnow().isoformat(),
        }
    except PIXAPIError as e:
        logger.error(f"PIX payment failed: {e}")
        return {"success": False, "error": str(e), "end_to_end_id": end_to_end_id}


def get_charge_status(txid: str) -> Dict:
    """Get PIX charge status."""
    response = _api_call("GET", f"/v2/cob/{txid}")
    return {
        "txid": txid,
        "status": response.get("status"),
        "amount": response.get("valor", {}).get("original"),
        "pago_em": response.get("pix", [{}])[0].get("horario") if response.get("pix") else None,
    }


def get_payment_status(end_to_end_id: str) -> Dict:
    """Get PIX outbound payment status."""
    response = _api_call("GET", f"/v2/pix/{end_to_end_id}")
    return {
        "end_to_end_id": end_to_end_id,
        "status": response.get("status"),
        "amount": response.get("valor"),
        "processed_at": response.get("horario"),
    }


def handle_webhook_notification(headers: Dict[str, str], body: Dict) -> Dict:
    """
    Process incoming PIX webhook notification.
    Validates HMAC signature and returns processed event.
    """
    if PIX_WEBHOOK_SECRET:
        body_str = json.dumps(body, separators=(",", ":"), sort_keys=True)
        received_sig = headers.get("X-Webhook-Secret", "")
        expected_sig = hmac.new(
            PIX_WEBHOOK_SECRET.encode(),
            body_str.encode(),
            hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(received_sig, expected_sig):
            raise ValueError("Invalid PIX webhook signature")

    pix_events = body.get("pix", [])
    processed = []
    for event in pix_events:
        processed.append({
            "end_to_end_id": event.get("endToEndId"),
            "txid": event.get("txid"),
            "amount": event.get("valor"),
            "payer_name": event.get("pagador", {}).get("nome"),
            "received_at": event.get("horario"),
            "info": event.get("infoPagador"),
        })

    return {
        "processed": True,
        "events": processed,
        "processed_at": datetime.utcnow().isoformat(),
    }
