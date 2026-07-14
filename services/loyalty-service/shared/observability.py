"""
Observability utilities for 54Agent Banking Platform

Structured JSON logging, OpenTelemetry-compatible tracing context,
and Prometheus-compatible metrics endpoints.

Usage::

    from shared.observability import setup_logging, get_logger, metrics_router

    setup_logging("my-service")
    log = get_logger("my-service.payments")
    log.info("payment processed", extra={"amount": 5000, "agent": "A1"})

    app.include_router(metrics_router)
"""

import os
import json
import time
import logging
import threading
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from contextvars import ContextVar

from fastapi import APIRouter, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

_service_name: str = os.getenv("SERVICE_NAME", "unknown")

_req_id_var: ContextVar[str] = ContextVar("obs_request_id", default="-")
_trace_var: ContextVar[str] = ContextVar("obs_trace_id", default="-")


class _JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": _service_name,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": _req_id_var.get("-"),
            "trace_id": _trace_var.get("-"),
        }
        if record.exc_info and record.exc_info[1]:
            payload["exception"] = self.formatException(record.exc_info)
        for key in ("amount", "agent", "user_id", "txn_id", "duration_ms", "status_code", "method", "path"):
            val = getattr(record, key, None)
            if val is not None:
                payload[key] = val
        return json.dumps(payload, default=str)


def setup_logging(service: str = "", level: str = "") -> None:
    global _service_name
    _service_name = service or os.getenv("SERVICE_NAME", "unknown")
    lvl = getattr(logging, (level or os.getenv("LOG_LEVEL", "INFO")).upper(), logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(_JSONFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(lvl)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


class _Metrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.request_count: Dict[str, int] = {}
        self.request_errors: Dict[str, int] = {}
        self.request_latency_sum: Dict[str, float] = {}
        self.request_latency_count: Dict[str, int] = {}

    def record(self, method: str, path: str, status: int, duration: float) -> None:
        key = f'{method} {path}'
        with self._lock:
            self.request_count[key] = self.request_count.get(key, 0) + 1
            if status >= 400:
                self.request_errors[key] = self.request_errors.get(key, 0) + 1
            self.request_latency_sum[key] = self.request_latency_sum.get(key, 0.0) + duration
            self.request_latency_count[key] = self.request_latency_count.get(key, 0) + 1

    def prometheus_text(self) -> str:
        lines = [
            "# HELP http_requests_total Total HTTP requests",
            "# TYPE http_requests_total counter",
        ]
        with self._lock:
            for key, cnt in self.request_count.items():
                method, path = key.split(" ", 1)
                lines.append(f'http_requests_total{{service="{_service_name}",method="{method}",path="{path}"}} {cnt}')

            lines.append("# HELP http_request_errors_total Total HTTP errors")
            lines.append("# TYPE http_request_errors_total counter")
            for key, cnt in self.request_errors.items():
                method, path = key.split(" ", 1)
                lines.append(f'http_request_errors_total{{service="{_service_name}",method="{method}",path="{path}"}} {cnt}')

            lines.append("# HELP http_request_duration_seconds HTTP request latency")
            lines.append("# TYPE http_request_duration_seconds summary")
            for key in self.request_latency_sum:
                method, path = key.split(" ", 1)
                total = self.request_latency_sum[key]
                count = self.request_latency_count[key]
                lines.append(f'http_request_duration_seconds_sum{{service="{_service_name}",method="{method}",path="{path}"}} {total:.6f}')
                lines.append(f'http_request_duration_seconds_count{{service="{_service_name}",method="{method}",path="{path}"}} {count}')
        return "\n".join(lines) + "\n"


_metrics = _Metrics()

metrics_router = APIRouter(tags=["observability"])


@metrics_router.get("/metrics")
async def prometheus_metrics():
    return Response(content=_metrics.prometheus_text(), media_type="text/plain; charset=utf-8")


class MetricsMiddleware(BaseHTTPMiddleware):
    SKIP = {"/health", "/healthz", "/ready", "/health/live", "/health/ready", "/metrics"}

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in self.SKIP:
            return await call_next(request)
        start = time.monotonic()
        response = await call_next(request)
        duration = time.monotonic() - start
        _metrics.record(request.method, request.url.path, response.status_code, duration)
        _req_id_var.set(getattr(request.state, "request_id", "-"))
        _trace_var.set(getattr(request.state, "trace_id", "-"))
        return response
