"""
Unit tests for WeChat Pay v3 gateway migration.
Verifies that:
  1. No MD5 is used anywhere in the signing flow
  2. RSA-SHA256 is used for outbound request authorization
  3. HMAC-SHA256 is used for inbound callback verification
  4. AES-256-GCM is used for callback resource decryption
  5. Nonce uses secrets module (not uuid4)
  6. All v3 API endpoints are used (no v2 /pay/unifiedorder etc.)
"""

import base64
import hashlib
import hmac
import json
import secrets
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Import the module under test ──────────────────────────────────────────────
from services.wechat_pay_gateway import (
    WeChatPayGateway,
    _aes_gcm_decrypt,
    _hmac_sha256_hex,
    _rsa_sign,
    create_wechat_pay_gateway_from_env,
)

# ── Test fixtures ─────────────────────────────────────────────────────────────

# Generate a real RSA key pair for testing (using cryptography library)
try:
    from cryptography.hazmat.primitives.asymmetric import rsa, padding
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.backends import default_backend

    _TEST_PRIVATE_KEY = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )
    _TEST_PRIVATE_KEY_PEM = _TEST_PRIVATE_KEY.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    _CRYPTO_AVAILABLE = True
except ImportError:
    _CRYPTO_AVAILABLE = False
    _TEST_PRIVATE_KEY_PEM = b""

# 32-byte API v3 key for testing
_TEST_API_V3_KEY = "test_api_v3_key_32bytes_padding!!"  # exactly 32 bytes

GATEWAY = WeChatPayGateway(
    app_id="wx1234567890abcdef",
    mch_id="1234567890",
    api_v3_key=_TEST_API_V3_KEY,
    serial_no="TEST_SERIAL_NO_ABC123",
    private_key_pem=_TEST_PRIVATE_KEY_PEM,
    notify_url="https://54agent.io/api/payments/wechat/notify",
)


# ── Tests: Cryptographic primitives ──────────────────────────────────────────

class TestCryptoPrimitives:
    """Verify the correct crypto primitives are used."""

    def test_no_md5_in_module(self):
        """The wechat_pay_gateway module must not call hashlib.md5 anywhere."""
        import inspect
        import services.wechat_pay_gateway as mod
        source = inspect.getsource(mod)
        assert "hashlib.md5" not in source, "MD5 must not be used in WeChat Pay v3 gateway"
        assert "_generate_sign" not in source, "v2 _generate_sign method must not exist"
        assert "unifiedorder" not in source, "v2 /pay/unifiedorder endpoint must not be used"
        assert "orderquery" not in source, "v2 /pay/orderquery endpoint must not be used"

    def test_hmac_sha256_hex_correctness(self):
        """_hmac_sha256_hex must produce correct HMAC-SHA256."""
        key = "test_key"
        message = "test_message"
        expected = hmac.new(
            key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        result = _hmac_sha256_hex(key, message)
        assert result == expected
        assert len(result) == 64  # SHA-256 hex digest is 64 chars

    @pytest.mark.skipif(not _CRYPTO_AVAILABLE, reason="cryptography not installed")
    def test_rsa_sign_produces_valid_signature(self):
        """_rsa_sign must produce a valid RSA-SHA256 signature verifiable with the public key."""
        message = "test_message_for_signing"
        signature_b64 = _rsa_sign(_TEST_PRIVATE_KEY_PEM, message)
        signature_bytes = base64.b64decode(signature_b64)
        # Verify with the public key
        public_key = _TEST_PRIVATE_KEY.public_key()
        # Should not raise
        public_key.verify(
            signature_bytes,
            message.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )

    @pytest.mark.skipif(not _CRYPTO_AVAILABLE, reason="cryptography not installed")
    def test_aes_gcm_decrypt_roundtrip(self):
        """AES-256-GCM encrypt/decrypt roundtrip must work correctly."""
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        key = _TEST_API_V3_KEY.encode("utf-8")
        nonce = secrets.token_bytes(12)
        plaintext = json.dumps({"transaction_id": "TX123", "amount": 100})
        associated_data = "transaction"
        aesgcm = AESGCM(key)
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), associated_data.encode("utf-8"))
        ciphertext_b64 = base64.b64encode(ciphertext).decode("utf-8")
        # Decrypt using our function
        result = _aes_gcm_decrypt(
            _TEST_API_V3_KEY,
            nonce.decode("latin-1"),  # nonce as string
            ciphertext_b64,
            associated_data,
        )
        # The result should be the original plaintext
        assert json.loads(result)["transaction_id"] == "TX123"


# ── Tests: Nonce generation ───────────────────────────────────────────────────

class TestNonceGeneration:
    """Nonce must use secrets module, not uuid4."""

    def test_nonce_uses_secrets(self):
        """Gateway._nonce() must use secrets.token_hex, not uuid4."""
        import inspect
        import services.wechat_pay_gateway as mod
        source = inspect.getsource(mod)
        assert "secrets.token_hex" in source, "Nonce must use secrets.token_hex"
        assert "uuid4" not in source, "uuid4 must not be used for nonce generation"

    def test_nonce_length(self):
        """Nonce must be 32 characters."""
        nonce = GATEWAY._nonce()
        assert len(nonce) == 32

    def test_nonce_is_uppercase_hex(self):
        """Nonce must be uppercase hexadecimal."""
        nonce = GATEWAY._nonce()
        assert nonce == nonce.upper()
        int(nonce, 16)  # Must be valid hex

    def test_nonces_are_unique(self):
        """Each nonce call must produce a different value."""
        nonces = {GATEWAY._nonce() for _ in range(100)}
        assert len(nonces) == 100, "All 100 nonces must be unique"


# ── Tests: Authorization header ───────────────────────────────────────────────

class TestAuthorizationHeader:
    """Authorization header must use WECHATPAY2-SHA256-RSA2048 scheme."""

    @pytest.mark.skipif(not _CRYPTO_AVAILABLE, reason="cryptography not installed")
    def test_authorization_scheme(self):
        """Authorization header must start with WECHATPAY2-SHA256-RSA2048."""
        auth = GATEWAY._build_authorization("POST", "/v3/pay/transactions/native", "{}")
        assert auth.startswith("WECHATPAY2-SHA256-RSA2048 ")

    @pytest.mark.skipif(not _CRYPTO_AVAILABLE, reason="cryptography not installed")
    def test_authorization_contains_required_fields(self):
        """Authorization header must contain mchid, nonce_str, signature, timestamp, serial_no."""
        auth = GATEWAY._build_authorization("POST", "/v3/pay/transactions/native", "{}")
        assert 'mchid="1234567890"' in auth
        assert "nonce_str=" in auth
        assert "signature=" in auth
        assert "timestamp=" in auth
        assert f'serial_no="{GATEWAY.serial_no}"' in auth

    @pytest.mark.skipif(not _CRYPTO_AVAILABLE, reason="cryptography not installed")
    def test_authorization_timestamp_is_current(self):
        """Authorization timestamp must be within 5 seconds of now."""
        auth = GATEWAY._build_authorization("GET", "/v3/pay/transactions/id/TX123", "")
        import re
        ts_match = re.search(r'timestamp="(\d+)"', auth)
        assert ts_match, "timestamp must be present in auth header"
        ts = int(ts_match.group(1))
        assert abs(ts - int(time.time())) < 5, "Timestamp must be within 5 seconds of now"


# ── Tests: Callback verification ─────────────────────────────────────────────

class TestCallbackVerification:
    """Callback verification must use HMAC-SHA256, not MD5."""

    def test_verify_notify_valid_signature(self):
        """verify_notify must return True for a valid HMAC-SHA256 signature."""
        ts = str(int(time.time()))
        nonce = "TESTNONCE123"
        body = json.dumps({"id": "EV-001", "event_type": "TRANSACTION.SUCCESS"})
        message = f"{ts}\n{nonce}\n{body}\n"
        expected_hex = hmac.new(
            _TEST_API_V3_KEY.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        # Encode as base64 (as WeChat Pay sends it)
        signature_b64 = base64.b64encode(bytes.fromhex(expected_hex)).decode("utf-8")
        result = GATEWAY.verify_notify(ts, nonce, signature_b64, body)
        assert result is True

    def test_verify_notify_invalid_signature(self):
        """verify_notify must return False for a tampered signature."""
        result = GATEWAY.verify_notify(
            str(int(time.time())),
            "TESTNONCE",
            base64.b64encode(b"invalid_signature_bytes").decode("utf-8"),
            "{}",
        )
        assert result is False

    def test_verify_notify_malformed_base64(self):
        """verify_notify must return False (not raise) for malformed base64."""
        result = GATEWAY.verify_notify(
            str(int(time.time())),
            "TESTNONCE",
            "!!!not_valid_base64!!!",
            "{}",
        )
        assert result is False


# ── Tests: V3 API endpoints ───────────────────────────────────────────────────

class TestV3ApiEndpoints:
    """All API calls must use v3 endpoints."""

    @pytest.mark.asyncio
    @pytest.mark.skipif(not _CRYPTO_AVAILABLE, reason="cryptography not installed")
    async def test_create_native_payment_uses_v3_endpoint(self):
        """create_native_payment must POST to /v3/pay/transactions/native."""
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__.return_value = mock_client
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json.return_value = {"code_url": "weixin://wxpay/s?a=b"}
            mock_client.post.return_value = mock_response
            result = await GATEWAY.create_native_payment(
                out_trade_no="ORDER_001",
                total_fee=100,
                description="Test payment",
            )
            call_url = mock_client.post.call_args[0][0]
            assert "/v3/pay/transactions/native" in call_url
            assert result["status"] == "success"
            assert result["code_url"] == "weixin://wxpay/s?a=b"

    @pytest.mark.asyncio
    @pytest.mark.skipif(not _CRYPTO_AVAILABLE, reason="cryptography not installed")
    async def test_refund_uses_v3_endpoint(self):
        """refund must POST to /v3/refund/domestic/refunds."""
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__.return_value = mock_client
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json.return_value = {"refund_id": "RF001", "status": "PROCESSING"}
            mock_client.post.return_value = mock_response
            result = await GATEWAY.refund(
                out_trade_no="ORDER_001",
                out_refund_no="REFUND_001",
                total_fee=100,
                refund_fee=50,
                reason="Customer request",
            )
            call_url = mock_client.post.call_args[0][0]
            assert "/v3/refund/domestic/refunds" in call_url
            assert result["status"] == "success"
            assert result["refund_id"] == "RF001"

    @pytest.mark.asyncio
    @pytest.mark.skipif(not _CRYPTO_AVAILABLE, reason="cryptography not installed")
    async def test_query_order_uses_v3_endpoint(self):
        """query_order must GET from /v3/pay/transactions/out-trade-no/..."""
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__.return_value = mock_client
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json.return_value = {
                "trade_state": "SUCCESS",
                "transaction_id": "TX_WECHAT_001",
                "out_trade_no": "ORDER_001",
                "amount": {"total": 100, "payer_total": 100},
            }
            mock_client.get.return_value = mock_response
            result = await GATEWAY.query_order(out_trade_no="ORDER_001")
            call_url = mock_client.get.call_args[0][0]
            assert "/v3/pay/transactions/out-trade-no/ORDER_001" in call_url
            assert result["status"] == "success"
            assert result["trade_state"] == "SUCCESS"


# ── Tests: Factory function ───────────────────────────────────────────────────

class TestFactoryFunction:
    """create_wechat_pay_gateway_from_env must validate all required env vars."""

    def test_raises_on_missing_env_vars(self):
        """Factory must raise EnvironmentError when required env vars are missing."""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(EnvironmentError) as exc_info:
                create_wechat_pay_gateway_from_env()
            assert "WECHAT_APP_ID" in str(exc_info.value)

    def test_raises_on_partial_env_vars(self):
        """Factory must raise EnvironmentError when only some env vars are set."""
        with patch.dict("os.environ", {"WECHAT_APP_ID": "wx123"}, clear=True):
            with pytest.raises(EnvironmentError) as exc_info:
                create_wechat_pay_gateway_from_env()
            assert "WECHAT_MCH_ID" in str(exc_info.value)
