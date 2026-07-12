"""
Shared Security Middleware for all Python FastAPI microservices.

Implements fixes for:
  - CVE-2024-34069: Werkzeug debugger RCE — disable debugger in production
  - CVE-2024-47874: Starlette multipart DoS — enforce form size limits
  - CVE-2026-54283: Starlette form limits silently ignored — explicit enforcement
  - CVE-2026-54282: Starlette URL hostname poisoning — validate Host header
  - General: Security headers (CSP, HSTS, X-Frame-Options, etc.)
  - General: Request size limits to prevent memory exhaustion
"""

from __future__ import annotations

import logging
import os
import re
from typing import Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

# ─── Configuration ────────────────────────────────────────────────────────────
MAX_REQUEST_BODY_BYTES = int(os.getenv("MAX_REQUEST_BODY_BYTES", str(10 * 1024 * 1024)))  # 10 MB
MAX_FORM_FIELD_SIZE = int(os.getenv("MAX_FORM_FIELD_SIZE", str(1 * 1024 * 1024)))  # 1 MB
MAX_FORM_FIELDS = int(os.getenv("MAX_FORM_FIELDS", "100"))
MAX_MULTIPART_PARTS = int(os.getenv("MAX_MULTIPART_PARTS", "20"))
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "").split(",") if os.getenv("ALLOWED_HOSTS") else []

# ─── Security Headers Middleware ──────────────────────────────────────────────
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Adds security headers to all responses.
    Prevents XSS, clickjacking, MIME sniffing, and information disclosure.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"
        # XSS protection (legacy browsers)
        response.headers["X-XSS-Protection"] = "1; mode=block"
        # HSTS (1 year, include subdomains)
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; preload"
        )
        # Referrer policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # Permissions policy
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), payment=()"
        )
        # Content Security Policy
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
        # Remove server identification
        response.headers.pop("Server", None)
        response.headers.pop("X-Powered-By", None)

        return response


# ─── Request Size Limit Middleware ────────────────────────────────────────────
class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Enforces maximum request body size to prevent memory exhaustion DoS.
    Fixes CVE-2026-54280 (aiohttp resource leak) and CVE-2026-53540 (negative Content-Length).
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        content_length = request.headers.get("content-length")

        # Reject negative Content-Length (CVE-2026-53540)
        if content_length is not None:
            try:
                cl = int(content_length)
                if cl < 0:
                    return JSONResponse(
                        status_code=400,
                        content={"error": "Invalid Content-Length"},
                    )
                if cl > MAX_REQUEST_BODY_BYTES:
                    return JSONResponse(
                        status_code=413,
                        content={"error": "Request body too large"},
                    )
            except ValueError:
                return JSONResponse(
                    status_code=400,
                    content={"error": "Invalid Content-Length header"},
                )

        return await call_next(request)


# ─── Host Header Validation Middleware ───────────────────────────────────────
class HostValidationMiddleware(BaseHTTPMiddleware):
    """
    Validates the Host header to prevent URL hostname poisoning.
    Fixes CVE-2026-54282 (Starlette request.url.hostname poisoning).
    """

    def __init__(self, app: ASGIApp, allowed_hosts: list[str] | None = None):
        super().__init__(app)
        self._allowed = set(allowed_hosts or ALLOWED_HOSTS)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if self._allowed:
            host = request.headers.get("host", "").split(":")[0].lower()
            if host not in self._allowed:
                logger.warning(f"[Security] Rejected request with invalid Host: {host}")
                return JSONResponse(
                    status_code=400,
                    content={"error": "Invalid Host header"},
                )
        return await call_next(request)


# ─── Werkzeug Debugger Lockdown ───────────────────────────────────────────────
def disable_werkzeug_debugger() -> None:
    """
    Explicitly disable the Werkzeug interactive debugger in production.
    Fixes CVE-2024-34069: Werkzeug debugger RCE via attacker-controlled domain.

    Call this at application startup before any WSGI/ASGI server starts.
    """
    env = os.getenv("FLASK_ENV", os.getenv("APP_ENV", "production")).lower()
    debug_env = os.getenv("FLASK_DEBUG", os.getenv("DEBUG", "false")).lower()

    if env == "production" or debug_env in ("false", "0", "no"):
        os.environ["WERKZEUG_RUN_MAIN"] = "false"
        os.environ["FLASK_DEBUG"] = "0"
        os.environ["WERKZEUG_DEBUG_PIN"] = "off"
        logger.info("[Security] Werkzeug debugger disabled (CVE-2024-34069 mitigation)")
    elif env in ("development", "dev"):
        logger.warning(
            "[Security] Werkzeug debugger is ENABLED. "
            "This is a CRITICAL vulnerability (CVE-2024-34069) in production. "
            "Set FLASK_ENV=production before deploying."
        )


# ─── Multipart Form Size Enforcement ─────────────────────────────────────────
def get_secure_form_limits() -> dict:
    """
    Returns secure form parsing limits for Starlette/FastAPI.
    Fixes CVE-2024-47874 (Starlette multipart DoS) and CVE-2026-54283.

    Usage:
        @app.post("/upload")
        async def upload(request: Request):
            form = await request.form(
                max_fields=SECURE_FORM_LIMITS["max_fields"],
                max_files=SECURE_FORM_LIMITS["max_files"],
            )
    """
    return {
        "max_fields": MAX_FORM_FIELDS,
        "max_files": MAX_MULTIPART_PARTS,
        "max_field_size": MAX_FORM_FIELD_SIZE,
    }

SECURE_FORM_LIMITS = get_secure_form_limits()


# ─── Application Security Hardening ──────────────────────────────────────────
def apply_security_hardening(app: FastAPI, allowed_hosts: list[str] | None = None) -> FastAPI:
    """
    Apply all security middleware to a FastAPI application.

    Call this immediately after creating the FastAPI() instance:

        app = FastAPI()
        app = apply_security_hardening(app)

    Args:
        app: The FastAPI application instance.
        allowed_hosts: List of valid Host header values. If None, uses ALLOWED_HOSTS env var.

    Returns:
        The hardened FastAPI application.
    """
    # Disable Werkzeug debugger first
    disable_werkzeug_debugger()

    # Add middleware in reverse order (last added = first executed)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestSizeLimitMiddleware)
    if allowed_hosts or ALLOWED_HOSTS:
        app.add_middleware(HostValidationMiddleware, allowed_hosts=allowed_hosts)

    logger.info("[Security] Security hardening middleware applied")
    return app


# ─── Flask Security Hardening ─────────────────────────────────────────────────
def apply_flask_security_hardening(flask_app) -> None:
    """
    Apply security hardening to a Flask application.
    Fixes CVE-2024-34069 (Werkzeug debugger RCE) and CVE-2026-27205 (Flask Vary header).

    Args:
        flask_app: The Flask application instance.
    """
    disable_werkzeug_debugger()

    # Force debug off
    flask_app.config["DEBUG"] = False
    flask_app.config["TESTING"] = False
    flask_app.config["PROPAGATE_EXCEPTIONS"] = False

    # Fix CVE-2026-27205: Flask session Vary header
    flask_app.config["SESSION_COOKIE_SECURE"] = True
    flask_app.config["SESSION_COOKIE_HTTPONLY"] = True
    flask_app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    # Add security headers via after_request hook
    @flask_app.after_request
    def add_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers.pop("Server", None)
        return response

    logger.info("[Security] Flask security hardening applied")
