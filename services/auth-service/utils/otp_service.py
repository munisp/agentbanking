"""
OTP (One-Time Password) Service
Redis-backed, distributed, replay-safe OTP management.

All OTP codes are stored exclusively in Redis with TTL expiry.
OTP codes are NEVER written to log output.
"""

import hashlib
import hmac
import os
import random
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

import redis as redis_lib

from utils.helpers import create_logger

logger = create_logger(__name__)

_REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
_redis_client: Optional[redis_lib.Redis] = None


def _get_redis() -> redis_lib.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis_lib.from_url(_REDIS_URL, decode_responses=True)
    return _redis_client


class OTPService:
    """Manages OTP generation, storage, and validation — backed by Redis.

    Security properties:
    - OTP codes are stored as keyed hashes (HMAC-SHA-256), never plaintext.
    - Tokens are single-use (replay of a verified token invalidates it).
    - Tokens expire via Redis TTL.
    - Resend is throttled by a per-user cooldown window.
    - Verification attempts are capped (MAX_ATTEMPTS).
    """

    OTP_LENGTH = 6
    OTP_EXPIRY_SECONDS = 600   # 10 minutes
    MAX_ATTEMPTS = 3
    RESEND_COOLDOWN_SECONDS = 60  # min interval between OTP sends per user

    _OTP_KEY = "54b:otp:{tenant_id}:{keycloak_id}"
    _ATTEMPT_KEY = "54b:otp_atm:{tenant_id}:{keycloak_id}"

    @staticmethod
    def _hash_code(otp_code: str, tenant_id: str, keycloak_id: str) -> str:
        """Keyed hash of the OTP. The tenant/user pair acts as the HMAC key so
        a Redis snapshot leak does not expose usable codes and hashes are not
        portable across users."""
        key = f"{tenant_id}:{keycloak_id}".encode("utf-8")
        return hmac.new(key, otp_code.encode("utf-8"), hashlib.sha256).hexdigest()

    def generate_otp(
        self, keycloak_id: str, tenant_id: str, email: str
    ) -> Dict[str, str]:
        """
        Generate a new OTP and store it in Redis with TTL.
        Returns expires_at timestamp. OTP code is NOT returned in any log.
        Enforces a resend cooldown — a fresh OTP cannot be requested while a
        recently-issued one is still within the cooldown window.
        """
        r = _get_redis()

        otp_key = self._OTP_KEY.format(tenant_id=tenant_id, keycloak_id=keycloak_id)
        attempt_key = self._ATTEMPT_KEY.format(tenant_id=tenant_id, keycloak_id=keycloak_id)

        # Resend cooldown: a token issued < RESEND_COOLDOWN_SECONDS ago still
        # has a TTL greater than (expiry - cooldown).
        ttl = r.ttl(otp_key)
        if ttl is not None and ttl > self.OTP_EXPIRY_SECONDS - self.RESEND_COOLDOWN_SECONDS:
            retry_after = int(ttl - (self.OTP_EXPIRY_SECONDS - self.RESEND_COOLDOWN_SECONDS))
            logger.info(
                "OTP resend throttled keycloak_id=%s tenant=%s retry_after=%ss",
                keycloak_id, tenant_id, retry_after,
            )
            return {
                "error": "resend_cooldown",
                "message": f"Please wait {retry_after} seconds before requesting a new OTP.",
                "retry_after_seconds": str(max(retry_after, 1)),
            }

        otp_code = "".join(secrets.choice(string.digits) for _ in range(self.OTP_LENGTH))

        pipe = r.pipeline(transaction=True)
        pipe.hset(otp_key, mapping={
            "code_hash": self._hash_code(otp_code, tenant_id, keycloak_id),
            "email": email,
            "verified": "0",
        })
        pipe.expire(otp_key, self.OTP_EXPIRY_SECONDS)
        pipe.delete(attempt_key)
        pipe.execute()

        expires_at = (
            datetime.now(timezone.utc) + timedelta(seconds=self.OTP_EXPIRY_SECONDS)
        ).isoformat()

        logger.info(
            "OTP generated keycloak_id=%s tenant=%s expires_at=%s",
            keycloak_id, tenant_id, expires_at,
        )

        return {"expires_at": expires_at}

    def verify_otp(
        self, keycloak_id: str, tenant_id: str, otp_code: str
    ) -> Dict:
        """
        Verify the OTP code against Redis state.
        Enforces: TTL expiry, attempt throttle, single-use replay prevention.
        """
        r = _get_redis()
        otp_key = self._OTP_KEY.format(tenant_id=tenant_id, keycloak_id=keycloak_id)
        attempt_key = self._ATTEMPT_KEY.format(tenant_id=tenant_id, keycloak_id=keycloak_id)

        otp_data = r.hgetall(otp_key)
        if not otp_data:
            logger.warning(
                "OTP verification failed — no OTP found keycloak_id=%s tenant=%s",
                keycloak_id, tenant_id,
            )
            return {"valid": False, "message": "No OTP found. Please request a new one."}

        if otp_data.get("verified") == "1":
            logger.warning(
                "OTP replay attempt — already verified keycloak_id=%s tenant=%s",
                keycloak_id, tenant_id,
            )
            r.delete(otp_key, attempt_key)
            return {"valid": False, "message": "OTP already used. Please request a new one."}

        attempts = r.incr(attempt_key)
        if int(attempts) == 1:
            r.expire(attempt_key, self.OTP_EXPIRY_SECONDS)

        if int(attempts) > self.MAX_ATTEMPTS:
            logger.warning(
                "OTP max attempts exceeded keycloak_id=%s tenant=%s attempts=%s",
                keycloak_id, tenant_id, attempts,
            )
            r.delete(otp_key, attempt_key)
            return {
                "valid": False,
                "message": "Maximum verification attempts exceeded. Please request a new OTP.",
            }

        # Constant-time comparison of the keyed hash (plaintext codes are
        # never stored; legacy plaintext rows are treated as invalid).
        expected_hash = otp_data.get("code_hash", "")
        if not expected_hash:
            logger.warning(
                "OTP row missing hash (legacy plaintext) — refusing verification keycloak_id=%s tenant=%s",
                keycloak_id, tenant_id,
            )
            r.delete(otp_key, attempt_key)
            return {"valid": False, "message": "OTP invalid. Please request a new one."}
        presented_hash = self._hash_code(otp_code, tenant_id, keycloak_id)
        if not secrets.compare_digest(presented_hash, expected_hash):
            remaining = self.MAX_ATTEMPTS - int(attempts)
            logger.warning(
                "OTP verification failed — invalid code keycloak_id=%s tenant=%s attempts=%s",
                keycloak_id, tenant_id, attempts,
            )
            return {
                "valid": False,
                "message": "Invalid OTP code.",
                "attempts_remaining": max(remaining, 0),
            }

        # Mark as used and let Redis expire naturally after 60s grace window
        r.hset(otp_key, "verified", "1")
        r.expire(otp_key, 60)
        r.delete(attempt_key)

        logger.info(
            "OTP verified keycloak_id=%s tenant=%s email=%s",
            keycloak_id, tenant_id, otp_data.get("email", ""),
        )
        return {"valid": True, "message": "OTP verified successfully."}

    def invalidate_otp(self, keycloak_id: str, tenant_id: str) -> None:
        """Explicitly invalidate an OTP (e.g., on password change)."""
        r = _get_redis()
        otp_key = self._OTP_KEY.format(tenant_id=tenant_id, keycloak_id=keycloak_id)
        attempt_key = self._ATTEMPT_KEY.format(tenant_id=tenant_id, keycloak_id=keycloak_id)
        r.delete(otp_key, attempt_key)
        logger.info("OTP invalidated keycloak_id=%s tenant=%s", keycloak_id, tenant_id)

    def get_otp_status(self, keycloak_id: str, tenant_id: str) -> Optional[Dict]:
        """Return OTP metadata for monitoring — code is never included."""
        r = _get_redis()
        otp_key = self._OTP_KEY.format(tenant_id=tenant_id, keycloak_id=keycloak_id)
        attempt_key = self._ATTEMPT_KEY.format(tenant_id=tenant_id, keycloak_id=keycloak_id)
        ttl = r.ttl(otp_key)
        if ttl < 0:
            return None
        attempts = r.get(attempt_key) or "0"
        verified = r.hget(otp_key, "verified") == "1"
        return {
            "exists": True,
            "ttl_seconds": ttl,
            "attempts_used": int(attempts),
            "verified": verified,
        }


_otp_service_instance: Optional[OTPService] = None


def get_otp_service() -> OTPService:
    global _otp_service_instance
    if _otp_service_instance is None:
        _otp_service_instance = OTPService()
    return _otp_service_instance
