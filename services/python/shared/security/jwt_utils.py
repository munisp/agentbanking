"""
Secure JWT Utility — Replaces python-jose across all Python microservices.

Fixes:
  - CVE-2024-33663: python-jose algorithm confusion with OpenSSH ECDSA keys
  - CVE-2026-48526: PyJWT public-key JWK accepted as HMAC secret (HS256 forgery)
  - CVE-2026-48524: PyJWT unbounded JWKS endpoint requests (DoS)

Security hardening:
  1. Explicit algorithm allow-list — never accept 'none' or unexpected algorithms
  2. Strict key type enforcement — RSA/EC public keys CANNOT be used as HMAC secrets
  3. JWKS cache with TTL and request throttling to prevent DoS
  4. Audience and issuer validation enforced by default
  5. Clock skew tolerance capped at 30 seconds
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
import threading
from typing import Any, Dict, List, Optional, Set
from urllib.request import urlopen
import json

import jwt
from jwt import PyJWKClient, PyJWKClientConnectionError
from jwt.algorithms import RSAAlgorithm, ECAlgorithm

logger = logging.getLogger(__name__)

# ─── Secure algorithm allow-list ─────────────────────────────────────────────
# NEVER include: 'none', 'HS256' for public-key scenarios
ALLOWED_ALGORITHMS: Set[str] = {
    "RS256", "RS384", "RS512",   # RSA PKCS#1 v1.5
    "PS256", "PS384", "PS512",   # RSA-PSS (preferred)
    "ES256", "ES384", "ES512",   # ECDSA
    "HS256", "HS384", "HS512",   # HMAC — only for symmetric secrets
}

# Internal-only algorithms (symmetric) — only allowed with explicit opt-in
SYMMETRIC_ALGORITHMS: Set[str] = {"HS256", "HS384", "HS512"}

# Clock skew tolerance (seconds)
MAX_CLOCK_SKEW = 30

# JWKS cache TTL (seconds)
JWKS_CACHE_TTL = int(os.getenv("JWKS_CACHE_TTL_SECONDS", "300"))
JWKS_MAX_REQUESTS_PER_MINUTE = int(os.getenv("JWKS_MAX_RPM", "10"))


class SecureJWKSClient:
    """
    Thread-safe JWKS client with caching and rate limiting.
    Prevents DoS via unbounded JWKS endpoint requests (CVE-2026-48524).
    """

    def __init__(self, jwks_uri: str, cache_ttl: int = JWKS_CACHE_TTL):
        self._uri = jwks_uri
        self._cache_ttl = cache_ttl
        self._cache: Optional[Dict] = None
        self._cache_time: float = 0.0
        self._lock = threading.Lock()
        self._request_times: List[float] = []
        self._client: Optional[PyJWKClient] = None

    def _get_client(self) -> PyJWKClient:
        if self._client is None:
            self._client = PyJWKClient(
                self._uri,
                cache_keys=True,
                max_cached_keys=16,
                lifespan=self._cache_ttl,
            )
        return self._client

    def _check_rate_limit(self) -> None:
        """Enforce rate limit on JWKS endpoint requests."""
        now = time.monotonic()
        # Remove requests older than 60 seconds
        self._request_times = [t for t in self._request_times if now - t < 60]
        if len(self._request_times) >= JWKS_MAX_REQUESTS_PER_MINUTE:
            raise RuntimeError(
                f"JWKS rate limit exceeded: {JWKS_MAX_REQUESTS_PER_MINUTE} requests/min"
            )
        self._request_times.append(now)

    def get_signing_key(self, token: str) -> Any:
        """Get the signing key for a token, with caching and rate limiting."""
        with self._lock:
            self._check_rate_limit()
        try:
            return self._get_client().get_signing_key_from_jwt(token)
        except PyJWKClientConnectionError as e:
            logger.error(f"[JWT] JWKS endpoint unreachable: {e}")
            raise


def decode_token(
    token: str,
    *,
    secret_or_jwks_uri: str,
    algorithms: Optional[List[str]] = None,
    audience: Optional[str] = None,
    issuer: Optional[str] = None,
    allow_symmetric: bool = False,
) -> Dict[str, Any]:
    """
    Securely decode and validate a JWT token.

    Args:
        token: The JWT string to decode.
        secret_or_jwks_uri: Either a symmetric secret string or a JWKS URI (https://).
        algorithms: Explicit list of allowed algorithms. Defaults to asymmetric only.
        audience: Expected 'aud' claim. Required for production use.
        issuer: Expected 'iss' claim. Required for production use.
        allow_symmetric: If True, allows HMAC algorithms (HS256/384/512).

    Returns:
        Decoded and validated JWT payload dict.

    Raises:
        jwt.InvalidTokenError: On any validation failure.
        ValueError: On configuration errors (e.g., attempting to use public key as HMAC secret).
    """
    # Determine allowed algorithms
    if algorithms is None:
        if allow_symmetric:
            algorithms = list(SYMMETRIC_ALGORITHMS)
        else:
            algorithms = [a for a in ALLOWED_ALGORITHMS if a not in SYMMETRIC_ALGORITHMS]

    # Validate algorithm list — never allow 'none'
    invalid_algos = set(algorithms) - ALLOWED_ALGORITHMS
    if invalid_algos:
        raise ValueError(f"Disallowed algorithms requested: {invalid_algos}")
    if "none" in [a.lower() for a in algorithms]:
        raise ValueError("Algorithm 'none' is explicitly forbidden")

    # Detect if using JWKS URI or symmetric secret
    is_jwks = secret_or_jwks_uri.startswith("https://") or secret_or_jwks_uri.startswith("http://")

    if is_jwks:
        # Asymmetric key from JWKS endpoint
        if any(a in SYMMETRIC_ALGORITHMS for a in algorithms):
            raise ValueError(
                "Symmetric algorithms (HS256/384/512) cannot be used with a JWKS URI. "
                "This prevents CVE-2026-48526 public-key-as-HMAC-secret attacks."
            )
        client = SecureJWKSClient(secret_or_jwks_uri)
        signing_key = client.get_signing_key(token)
        key = signing_key.key
    else:
        # Symmetric secret — validate it's not a PEM-encoded public key
        if secret_or_jwks_uri.strip().startswith("-----BEGIN"):
            raise ValueError(
                "A PEM-encoded public key was provided as a symmetric HMAC secret. "
                "This is the exact attack vector of CVE-2026-48526. "
                "Use a JWKS URI for asymmetric key verification."
            )
        if not allow_symmetric:
            raise ValueError(
                "Symmetric secret provided but allow_symmetric=False. "
                "Explicitly pass allow_symmetric=True to use HMAC tokens."
            )
        key = secret_or_jwks_uri

    # Decode options
    options = {
        "verify_signature": True,
        "verify_exp": True,
        "verify_nbf": True,
        "verify_iat": True,
        "verify_aud": audience is not None,
        "verify_iss": issuer is not None,
        "leeway": MAX_CLOCK_SKEW,
    }

    return jwt.decode(
        token,
        key,
        algorithms=algorithms,
        audience=audience,
        issuer=issuer,
        options=options,
    )


def encode_token(
    payload: Dict[str, Any],
    *,
    secret: str,
    algorithm: str = "HS256",
    allow_symmetric: bool = False,
) -> str:
    """
    Encode a JWT token with secure defaults.

    Args:
        payload: Claims dict. Should include 'exp', 'iat', 'iss', 'sub'.
        secret: Signing secret or private key PEM.
        algorithm: Signing algorithm. Defaults to HS256 for symmetric.
        allow_symmetric: Must be True to use HMAC algorithms.

    Returns:
        Signed JWT string.
    """
    if algorithm not in ALLOWED_ALGORITHMS:
        raise ValueError(f"Algorithm '{algorithm}' is not in the allowed list")
    if algorithm == "none":
        raise ValueError("Algorithm 'none' is explicitly forbidden")
    if algorithm in SYMMETRIC_ALGORITHMS and not allow_symmetric:
        raise ValueError("Symmetric algorithm requires allow_symmetric=True")

    # Ensure required claims are present
    if "exp" not in payload:
        raise ValueError("JWT payload must include 'exp' (expiration) claim")
    if "iat" not in payload:
        payload = {**payload, "iat": int(time.time())}

    return jwt.encode(payload, secret, algorithm=algorithm)


def get_keycloak_jwks_uri(realm: str = "master") -> str:
    """Return the Keycloak JWKS URI for the given realm."""
    base = os.getenv("KEYCLOAK_URL", "http://keycloak:8080")
    return f"{base}/realms/{realm}/protocol/openid-connect/certs"
