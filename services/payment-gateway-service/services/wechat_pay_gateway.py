"""
WeChat Pay Gateway Integration — v3 API (RSA-SHA256 / AES-256-GCM)
==================================================================
Migrated from v2 (MD5 + XML) to v3 (RSA-SHA256 + JSON + AES-GCM).

Key changes from v2:
  - No XML — all payloads are JSON
  - No MD5 — request signing uses RSA-SHA256 with merchant private key
  - Authorization: WECHATPAY2-SHA256-RSA2048 scheme
  - Callback verification: HMAC-SHA256 with API v3 key
  - Callback decryption: AES-256-GCM with API v3 key
  - Endpoints: https://api.mch.weixin.qq.com/v3/...

References:
  https://pay.weixin.qq.com/wiki/doc/apiv3/wechatpay/wechatpay3_0.shtml
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Any, Dict, Optional

import httpx

try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    _CRYPTO_AVAILABLE = True
except ImportError:
    _CRYPTO_AVAILABLE = False

WECHAT_PAY_V3_BASE = "https://api.mch.weixin.qq.com/v3"
AUTH_SCHEME = "WECHATPAY2-SHA256-RSA2048"


def _rsa_sign(private_key_pem: bytes, message: str) -> str:
    """Sign message with merchant RSA private key (PKCS1v15 + SHA-256)."""
    if not _CRYPTO_AVAILABLE:
        raise RuntimeError("cryptography package required for WeChat Pay v3. pip install cryptography")
    private_key = serialization.load_pem_private_key(
        private_key_pem, password=None, backend=default_backend()
    )
    signature = private_key.sign(message.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(signature).decode("utf-8")


def _hmac_sha256_hex(key: str, message: str) -> str:
    """HMAC-SHA256 for verifying inbound callback notifications."""
    return hmac.new(key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()


def _aes_gcm_decrypt(api_v3_key: str, nonce: str, ciphertext_b64: str, associated_data: str) -> str:
    """Decrypt WeChat Pay v3 callback resource using AES-256-GCM."""
    if not _CRYPTO_AVAILABLE:
        raise RuntimeError("cryptography package required for AES-GCM decryption")
    aesgcm = AESGCM(api_v3_key.encode("utf-8"))
    plaintext = aesgcm.decrypt(
        nonce.encode("utf-8"),
        base64.b64decode(ciphertext_b64),
        associated_data.encode("utf-8"),
    )
    return plaintext.decode("utf-8")


class WeChatPayGateway:
    """WeChat Pay v3 payment gateway — zero MD5, full RSA-SHA256 + AES-GCM.

    Args:
        app_id:           WeChat app ID (wx...)
        mch_id:           Merchant ID (10 digits)
        api_v3_key:       32-byte API v3 key from merchant portal
        serial_no:        Merchant certificate serial number
        private_key_pem:  PEM bytes of merchant RSA private key
        notify_url:       Default callback URL
    """

    def __init__(
        self,
        app_id: str,
        mch_id: str,
        api_v3_key: str,
        serial_no: str,
        private_key_pem: bytes,
        notify_url: str = "",
    ) -> None:
        self.app_id = app_id
        self.mch_id = mch_id
        self.api_v3_key = api_v3_key
        self.serial_no = serial_no
        self.private_key_pem = private_key_pem
        self.notify_url = notify_url

    def _nonce(self) -> str:
        """Cryptographically random 32-char nonce."""
        return secrets.token_hex(16).upper()

    def _timestamp(self) -> str:
        return str(int(time.time()))

    def _build_authorization(self, method: str, url_path: str, body: str) -> str:
        """Build WECHATPAY2-SHA256-RSA2048 Authorization header.

        Signature message: {METHOD}\n{URL_PATH}\n{TIMESTAMP}\n{NONCE}\n{BODY}\n
        """
        ts = self._timestamp()
        nonce = self._nonce()
        message = f"{method}\n{url_path}\n{ts}\n{nonce}\n{body}\n"
        sig = _rsa_sign(self.private_key_pem, message)
        return (
            f'{AUTH_SCHEME} mchid="{self.mch_id}",'
            f'nonce_str="{nonce}",'
            f'signature="{sig}",'
            f'timestamp="{ts}",'
            f'serial_no="{self.serial_no}"'
        )

    def _headers(self, method: str, url_path: str, body: str = "") -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": self._build_authorization(method, url_path, body),
            "User-Agent": "54agent-PaymentGateway/3.0 Python/3.11",
        }

    async def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        headers = self._headers("POST", path, body)
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{WECHAT_PAY_V3_BASE}{path}",
                content=body.encode("utf-8"),
                headers=headers,
            )
        response.raise_for_status()
        return response.json()

    async def _get(self, path: str) -> Dict[str, Any]:
        headers = self._headers("GET", path, "")
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{WECHAT_PAY_V3_BASE}{path}", headers=headers)
        response.raise_for_status()
        return response.json()

    async def create_native_payment(
        self,
        out_trade_no: str,
        total_fee: int,
        description: str,
        notify_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a native (QR code) payment order via WeChat Pay v3 JSON API."""
        path = "/pay/transactions/native"
        payload: Dict[str, Any] = {
            "appid": self.app_id,
            "mchid": self.mch_id,
            "description": description[:127],
            "out_trade_no": out_trade_no,
            "notify_url": notify_url or self.notify_url,
            "amount": {"total": total_fee, "currency": "CNY"},
        }
        result = await self._post(path, payload)
        return {"status": "success", "code_url": result.get("code_url"), "out_trade_no": out_trade_no}

    async def create_jsapi_payment(
        self,
        out_trade_no: str,
        total_fee: int,
        description: str,
        openid: str,
        notify_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create JSAPI (mini-program / H5) payment and return JS-SDK params."""
        path = "/pay/transactions/jsapi"
        payload: Dict[str, Any] = {
            "appid": self.app_id,
            "mchid": self.mch_id,
            "description": description[:127],
            "out_trade_no": out_trade_no,
            "notify_url": notify_url or self.notify_url,
            "amount": {"total": total_fee, "currency": "CNY"},
            "payer": {"openid": openid},
        }
        result = await self._post(path, payload)
        prepay_id = result.get("prepay_id", "")
        ts = self._timestamp()
        nonce = self._nonce()
        package = f"prepay_id={prepay_id}"
        sign_message = f"{self.app_id}\n{ts}\n{nonce}\n{package}\n"
        pay_sign = _rsa_sign(self.private_key_pem, sign_message)
        return {
            "status": "success",
            "prepay_id": prepay_id,
            "js_params": {
                "appId": self.app_id,
                "timeStamp": ts,
                "nonceStr": nonce,
                "package": package,
                "signType": "RSA",
                "paySign": pay_sign,
            },
        }

    async def query_order(
        self,
        out_trade_no: Optional[str] = None,
        transaction_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Query order status by merchant order number or WeChat transaction ID."""
        if transaction_id:
            path = f"/pay/transactions/id/{transaction_id}?mchid={self.mch_id}"
        elif out_trade_no:
            path = f"/pay/transactions/out-trade-no/{out_trade_no}?mchid={self.mch_id}"
        else:
            raise ValueError("Either out_trade_no or transaction_id must be provided")
        result = await self._get(path)
        trade_state = result.get("trade_state", "UNKNOWN")
        return {
            "status": "success" if trade_state == "SUCCESS" else "pending",
            "trade_state": trade_state,
            "trade_state_desc": result.get("trade_state_desc"),
            "transaction_id": result.get("transaction_id"),
            "out_trade_no": result.get("out_trade_no"),
            "total_fee": result.get("amount", {}).get("total", 0),
            "payer_total": result.get("amount", {}).get("payer_total", 0),
            "success_time": result.get("success_time"),
        }

    async def refund(
        self,
        out_trade_no: str,
        out_refund_no: str,
        total_fee: int,
        refund_fee: int,
        reason: Optional[str] = None,
        notify_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Submit a refund request via WeChat Pay v3."""
        path = "/refund/domestic/refunds"
        payload: Dict[str, Any] = {
            "out_trade_no": out_trade_no,
            "out_refund_no": out_refund_no,
            "amount": {"refund": refund_fee, "total": total_fee, "currency": "CNY"},
        }
        if reason:
            payload["reason"] = reason[:80]
        if notify_url:
            payload["notify_url"] = notify_url
        result = await self._post(path, payload)
        return {
            "status": "success",
            "refund_id": result.get("refund_id"),
            "out_refund_no": out_refund_no,
            "status_detail": result.get("status"),
            "refund_fee": refund_fee,
        }

    async def close_order(self, out_trade_no: str) -> Dict[str, Any]:
        """Close an unpaid order."""
        path = f"/pay/transactions/out-trade-no/{out_trade_no}/close"
        await self._post(path, {"mchid": self.mch_id})
        return {"status": "success", "message": "Order closed successfully"}

    def verify_notify(
        self,
        wechatpay_timestamp: str,
        wechatpay_nonce: str,
        wechatpay_signature: str,
        body: str,
    ) -> bool:
        """Verify HMAC-SHA256 signature on an inbound payment notification.

        Message: {timestamp}\n{nonce}\n{body}\n
        Constant-time comparison to prevent timing attacks.
        """
        message = f"{wechatpay_timestamp}\n{wechatpay_nonce}\n{body}\n"
        expected = _hmac_sha256_hex(self.api_v3_key, message)
        try:
            received = base64.b64decode(wechatpay_signature).hex()
        except Exception:
            return False
        return hmac.compare_digest(expected, received)

    def decrypt_notify_resource(
        self,
        algorithm: str,
        nonce: str,
        ciphertext: str,
        associated_data: str,
    ) -> Dict[str, Any]:
        """Decrypt AES-256-GCM encrypted payment notification resource."""
        if algorithm != "AEAD_AES_256_GCM":
            raise ValueError(f"Unsupported encryption algorithm: {algorithm}")
        plaintext = _aes_gcm_decrypt(self.api_v3_key, nonce, ciphertext, associated_data)
        return json.loads(plaintext)


def create_wechat_pay_gateway_from_env() -> WeChatPayGateway:
    """Build WeChatPayGateway from environment variables.

    Required: WECHAT_APP_ID, WECHAT_MCH_ID, WECHAT_API_V3_KEY,
              WECHAT_SERIAL_NO, WECHAT_PRIVATE_KEY_PATH, WECHAT_NOTIFY_URL
    """
    required = [
        "WECHAT_APP_ID", "WECHAT_MCH_ID", "WECHAT_API_V3_KEY",
        "WECHAT_SERIAL_NO", "WECHAT_PRIVATE_KEY_PATH", "WECHAT_NOTIFY_URL",
    ]
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        raise EnvironmentError(f"WeChat Pay v3 requires env vars: {', '.join(missing)}")
    with open(os.environ["WECHAT_PRIVATE_KEY_PATH"], "rb") as f:
        private_key_pem = f.read()
    return WeChatPayGateway(
        app_id=os.environ["WECHAT_APP_ID"],
        mch_id=os.environ["WECHAT_MCH_ID"],
        api_v3_key=os.environ["WECHAT_API_V3_KEY"],
        serial_no=os.environ["WECHAT_SERIAL_NO"],
        private_key_pem=private_key_pem,
        notify_url=os.environ["WECHAT_NOTIFY_URL"],
    )
