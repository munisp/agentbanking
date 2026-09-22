import datetime
import json
import os
import queue
import re
import threading
import time
import urllib.request

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

_AUDIT_URL = os.getenv("AUDIT_SVC_URL", "http://audit-service:8000")
_SKIP_METHODS = {"GET", "HEAD", "OPTIONS"}
_SKIP_PREFIXES = ("/health", "/metrics", "/dapr", "/docs", "/openapi")
_UUID_RE = re.compile(r"/[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}")
_INT_RE = re.compile(r"/\d+")

# Queue-based audit sender: a single background thread drains this queue and
# flushes in 100ms batching windows, instead of spawning a thread per request.
_AUDIT_QUEUE = queue.Queue(maxsize=int(os.getenv("AUDIT_QUEUE_MAXSIZE", "10000")))
_AUDIT_FLUSH_WINDOW_SECONDS = float(os.getenv("AUDIT_FLUSH_WINDOW_MS", "100")) / 1000.0
_AUDIT_BATCH_MAX = 100
_sender_thread = None
_sender_lock = threading.Lock()


def _path_to_event_type(method: str, path: str) -> str:
    clean = _UUID_RE.sub("/{id}", path)
    clean = _INT_RE.sub("/{id}", clean)
    return f"{method}:{clean}"


def _emit(actor_id: str, tenant_id: str, event_type: str, event_data: dict) -> None:
    if not _AUDIT_URL:
        return
    try:
        body = json.dumps({
            "actor_id": actor_id,
            "tenant_id": tenant_id,
            "event_type": event_type,
            "event_data": event_data,
            "timestamp": datetime.datetime.utcnow().isoformat(),
        }).encode()
        req = urllib.request.Request(
            f"{_AUDIT_URL}/audits",
            data=body,
            headers={
                "Content-Type": "application/json",
                "x-tenant-id": tenant_id,
                "x-keycloak-id": "system",
            },
            method="POST",
        )
        urllib.request.urlopen(req, timeout=3)
    except Exception:
        pass  # Audit failures must never affect core flow


def _sender_loop() -> None:
    """Drain the audit queue, flushing in ~100ms batching windows."""
    while True:
        batch = [_AUDIT_QUEUE.get()]  # blocks until first event
        deadline = time.monotonic() + _AUDIT_FLUSH_WINDOW_SECONDS
        while len(batch) < _AUDIT_BATCH_MAX:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                batch.append(_AUDIT_QUEUE.get(timeout=remaining))
            except queue.Empty:
                break
        for actor_id, tenant_id, event_type, event_data in batch:
            _emit(actor_id, tenant_id, event_type, event_data)


def _ensure_sender() -> None:
    global _sender_thread
    if _sender_thread is not None:
        return
    with _sender_lock:
        if _sender_thread is None:
            _sender_thread = threading.Thread(
                target=_sender_loop, name="audit-sender", daemon=True
            )
            _sender_thread.start()


def _enqueue(actor_id: str, tenant_id: str, event_type: str, event_data: dict) -> None:
    _ensure_sender()
    try:
        _AUDIT_QUEUE.put_nowait((actor_id, tenant_id, event_type, event_data))
    except queue.Full:
        pass  # Drop audit events under sustained overload; never block requests


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in _SKIP_METHODS:
            return await call_next(request)
        path = request.url.path
        if any(path.startswith(p) for p in _SKIP_PREFIXES):
            return await call_next(request)

        response = await call_next(request)

        tenant_id = request.headers.get("x-tenant-id", "unknown")
        actor_id = (
            request.headers.get("x-keycloak-id")
            or request.headers.get("x-keycloak-id", "unknown")
        )
        event_data: dict = {
            "method": request.method,
            "path": path,
            "status_code": response.status_code,
        }
        if str(request.query_params):
            event_data["query"] = str(request.query_params)

        _enqueue(actor_id, tenant_id, _path_to_event_type(request.method, path), event_data)

        return response

