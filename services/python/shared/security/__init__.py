"""
Shared Security Module for agentbanking Python microservices.

Provides hardened implementations of:
- JWT token encoding/decoding (replaces python-jose)
- FastAPI/Flask security middleware
- Security headers
- Request size limits
- Form parsing limits

Usage:
    from shared.security.jwt_utils import decode_token, encode_token
    from shared.security.middleware import apply_security_hardening

CVEs addressed:
    CVE-2024-33663  python-jose algorithm confusion
    CVE-2026-48526  PyJWT public-key as HMAC secret
    CVE-2026-48524  PyJWT unbounded JWKS requests (DoS)
    CVE-2024-34069  Werkzeug debugger RCE
    CVE-2024-47874  Starlette multipart DoS
    CVE-2026-54283  Starlette form limits ignored
    CVE-2026-54282  Starlette URL hostname poisoning
    CVE-2026-27205  Flask session Vary header
"""

from .jwt_utils import decode_token, encode_token, SecureJWKSClient, get_keycloak_jwks_uri
from .middleware import (
    apply_security_hardening,
    apply_flask_security_hardening,
    SecurityHeadersMiddleware,
    RequestSizeLimitMiddleware,
    HostValidationMiddleware,
    disable_werkzeug_debugger,
    SECURE_FORM_LIMITS,
)

__all__ = [
    "decode_token",
    "encode_token",
    "SecureJWKSClient",
    "get_keycloak_jwks_uri",
    "apply_security_hardening",
    "apply_flask_security_hardening",
    "SecurityHeadersMiddleware",
    "RequestSizeLimitMiddleware",
    "HostValidationMiddleware",
    "disable_werkzeug_debugger",
    "SECURE_FORM_LIMITS",
]
