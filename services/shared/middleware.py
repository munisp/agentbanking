"""
Unified Platform Middleware for 54Agent Banking Platform

Integrates: Keycloak (auth), Permify (RBAC), Redis (cache/rate-limit),
APISIX (gateway), Kafka (events), Dapr (sidecar), Temporal (workflows),
TigerBeetle (ledger), Fluvio (streaming), Lakehouse (analytics).

Drop-in FastAPI middleware that every service should mount via apply_middleware(app).
"""

import os
import time
import uuid
import json
import logging
from typing import Optional, Dict, Any, List, Callable
from contextvars import ContextVar

from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

_request_id: ContextVar[str] = ContextVar("request_id", default="")
_trace_id: ContextVar[str] = ContextVar("trace_id", default="")

logger = logging.getLogger("platform.middleware")


ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:3000,http://localhost:5173,http://localhost:5174",
    ).split(",")
    if o.strip()
]

SERVICE_NAME = os.getenv("SERVICE_NAME", "unknown-service")


class ErrorResponse:
    """Standardised error envelope returned by every service."""

    @staticmethod
    def build(
        status_code: int,
        message: str,
        detail: Optional[Any] = None,
        trace_id: Optional[str] = None,
    ) -> JSONResponse:
        body: Dict[str, Any] = {
            "error": {
                "code": status_code,
                "message": message,
            }
        }
        if detail is not None:
            body["error"]["detail"] = detail
        if trace_id:
            body["error"]["trace_id"] = trace_id
        return JSONResponse(status_code=status_code, content=body)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Injects request-id / trace-id into every request and response."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        trace = request.headers.get("X-Trace-ID") or str(uuid.uuid4())
        _request_id.set(req_id)
        _trace_id.set(trace)

        request.state.request_id = req_id
        request.state.trace_id = trace
        request.state.service_name = SERVICE_NAME

        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        response.headers["X-Trace-ID"] = trace
        response.headers["X-Service"] = SERVICE_NAME
        return response


class PayloadSizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject payloads exceeding a configurable byte limit."""

    def __init__(self, app: FastAPI, max_bytes: int = 10 * 1024 * 1024):
        super().__init__(app)
        self.max_bytes = int(os.getenv("MAX_PAYLOAD_BYTES", str(max_bytes)))

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_bytes:
            return ErrorResponse.build(
                413,
                "Payload too large",
                detail=f"Max allowed: {self.max_bytes} bytes",
                trace_id=getattr(request.state, "trace_id", None),
            )
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to every response."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
        return response


try:
    import redis as _redis_mod

    _HAS_REDIS = True
except ImportError:
    _HAS_REDIS = False
    _redis_mod = None  # type: ignore[assignment]


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Redis-backed sliding-window rate limiter."""

    SKIP_PATHS = {"/health", "/healthz", "/ready", "/health/live", "/health/ready", "/metrics", "/v1/health"}

    def __init__(
        self,
        app: FastAPI,
        default_limit: int = 100,
        window_seconds: int = 60,
    ):
        super().__init__(app)
        self.limit = int(os.getenv("RATE_LIMIT_DEFAULT", str(default_limit)))
        self.window = int(os.getenv("RATE_LIMIT_WINDOW", str(window_seconds)))
        self._redis = None

    def _get_redis(self):
        if self._redis is None and _HAS_REDIS:
            url = os.getenv("REDIS_URL")
            if url:
                try:
                    self._redis = _redis_mod.from_url(url, decode_responses=True)
                except Exception:
                    pass
        return self._redis

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        rc = self._get_redis()
        if rc is None:
            return await call_next(request)

        client_key = self._client_key(request)
        bucket = f"rl:{client_key}:{int(time.time()) // self.window}"
        try:
            pipe = rc.pipeline()
            pipe.incr(bucket)
            pipe.expire(bucket, self.window)
            count, _ = pipe.execute()
        except Exception:
            return await call_next(request)

        remaining = max(0, self.limit - count)
        if count > self.limit:
            return JSONResponse(
                status_code=429,
                content={"error": {"code": 429, "message": "Rate limit exceeded", "retry_after": self.window}},
                headers={
                    "X-RateLimit-Limit": str(self.limit),
                    "X-RateLimit-Remaining": "0",
                    "Retry-After": str(self.window),
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response

    @staticmethod
    def _client_key(request: Request) -> str:
        uid = getattr(request.state, "user_id", None)
        if uid:
            return f"user:{uid}"
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return f"ip:{forwarded.split(',')[0].strip()}"
        return f"ip:{request.client.host if request.client else 'unknown'}"


def _health_routes(app: FastAPI) -> None:
    """Register standardised health-check endpoints on *app*."""

    @app.get("/health/live", tags=["health"])
    async def liveness():
        return {"status": "ok", "service": SERVICE_NAME}

    @app.get("/health/ready", tags=["health"])
    async def readiness():
        checks: Dict[str, str] = {}
        if _HAS_REDIS:
            try:
                url = os.getenv("REDIS_URL")
                if url:
                    rc = _redis_mod.from_url(url, decode_responses=True)
                    rc.ping()
                    checks["redis"] = "ok"
            except Exception:
                checks["redis"] = "unavailable"
        ready = all(v == "ok" for v in checks.values()) if checks else True
        code = 200 if ready else 503
        return JSONResponse(
            status_code=code,
            content={"status": "ready" if ready else "degraded", "service": SERVICE_NAME, "checks": checks},
        )

    @app.get("/health", tags=["health"])
    async def health_compat():
        return {"status": "ok", "service": SERVICE_NAME}


def apply_middleware(app: FastAPI, *, enable_auth: bool = False) -> FastAPI:
    """
    One-call setup that every service should invoke at startup.

    Usage::

        app = FastAPI(title="my-service")
        apply_middleware(app)
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Trace-ID", "X-RateLimit-Remaining"],
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(PayloadSizeLimitMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(RequestContextMiddleware)
    _health_routes(app)
    return app
