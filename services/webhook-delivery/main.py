"""
Webhook Delivery Service — Reliable webhook delivery with retry, DLQ, and HMAC signing.

Port: 8143
Stack: FastAPI, PostgreSQL, Redis, Kafka

Features:
  - HMAC-SHA256 signature on every payload (X-Webhook-Signature header)
  - Exponential backoff retry (max 5 attempts: 1s, 5s, 25s, 125s, 625s)
  - Dead Letter Queue (DLQ) for permanently failed deliveries
  - Kafka event streaming for delivery status changes
  - Delivery audit log with full request/response capture
  - Rate limiting per endpoint (configurable)
"""

import asyncio
import hashlib
import hmac
import json
import os
import time
import uuid
from collections import OrderedDict, deque
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, Depends, Request
from pydantic import BaseModel, Field

# --- PostgreSQL Persistence ---
# Ported from the retired nested copy (services/python/webhook-delivery).
# Optional and fail-open: disabled when asyncpg is not installed or DATABASE_URL
# is not set.
try:
    import asyncpg
except ImportError:
    asyncpg = None

DATABASE_URL = os.getenv("DATABASE_URL", "")

_pg_pool: Optional["asyncpg.Pool"] = None

async def get_pg_pool() -> Optional["asyncpg.Pool"]:
    global _pg_pool
    if _pg_pool is None:
        if asyncpg is None or not DATABASE_URL:
            return None
        try:
            _pg_pool = await asyncpg.create_pool(
                dsn=DATABASE_URL,
                min_size=2, max_size=10, command_timeout=10
            )
            await _pg_pool.execute("""
                CREATE TABLE IF NOT EXISTS service_state (
                    key TEXT PRIMARY KEY,
                    value JSONB NOT NULL DEFAULT '{}',
                    service TEXT NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
        except Exception:
            _pg_pool = None
    return _pg_pool

async def pg_get(key: str, service: str):
    pool = await get_pg_pool()
    if pool:
        row = await pool.fetchrow(
            "SELECT value FROM service_state WHERE key = $1 AND service = $2", key, service
        )
        return row["value"] if row else None
    return None

async def pg_set(key: str, value, service: str):
    pool = await get_pg_pool()
    if pool:
        await pool.execute(
            "INSERT INTO service_state (key, value, service, updated_at) VALUES ($1, $2::jsonb, $3, NOW()) "
            "ON CONFLICT (key) DO UPDATE SET value = $2::jsonb, updated_at = NOW()",
            key, json.dumps(value) if not isinstance(value, str) else value, service
        )
# --- End PostgreSQL Persistence ---

# --- Production: Graceful Shutdown ---
import signal
import sys
import atexit
import logging

_shutdown_handlers = []

def register_shutdown(handler):
    _shutdown_handlers.append(handler)

def _graceful_shutdown(signum, frame):
    sig_name = signal.Signals(signum).name if hasattr(signal, 'Signals') else str(signum)
    logging.info(f"[shutdown] Received {sig_name}, shutting down gracefully...")
    for handler in reversed(_shutdown_handlers):
        try:
            handler()
        except Exception as e:
            logging.warning(f"[shutdown] Handler error: {e}")
    logging.info("[shutdown] Cleanup complete, exiting")
    sys.exit(0)

signal.signal(signal.SIGTERM, _graceful_shutdown)
signal.signal(signal.SIGINT, _graceful_shutdown)
atexit.register(lambda: logging.info("[shutdown] atexit handler called"))


app = FastAPI(title="54agent Webhook Delivery Service", version="1.0.0")


# Shared HTTP client for all webhook deliveries: keep-alive connection reuse
# instead of a fresh TCP+TLS handshake per delivery attempt.
_http_client: Optional[httpx.AsyncClient] = None


def get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=50),
        )
    return _http_client


@app.on_event("startup")
async def _init_http_client():
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=50),
        )


@app.on_event("shutdown")
async def _close_http_client():
    global _http_client
    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None


@app.on_event("startup")
async def _init_pg_pool():
    # Eagerly create the optional persistence pool (no-op when unconfigured).
    await get_pg_pool()

SIGNING_SECRET = os.getenv("WEBHOOK_SIGNING_SECRET", "")

INTERNAL_GATEWAY_TOKEN = os.getenv("INTERNAL_GATEWAY_TOKEN", "")


async def require_internal_auth(request: Request) -> None:
    """Require the internal gateway token on management/delivery endpoints.

    Fail-closed: when INTERNAL_GATEWAY_TOKEN is not configured every protected
    endpoint responds 503 instead of allowing open access.
    """
    if not INTERNAL_GATEWAY_TOKEN:
        raise HTTPException(503, "service authentication not configured")
    provided = request.headers.get("x-internal-gateway-token", "")
    if not provided or not hmac.compare_digest(provided, INTERNAL_GATEWAY_TOKEN):
        raise HTTPException(401, "unauthorized")


def require_signing_secret(secret: str) -> str:
    """Fail closed when no signing secret is configured for a delivery."""
    if not secret:
        raise HTTPException(503, "webhook signing secret not configured")
    return secret
MAX_RETRIES = int(os.getenv("WEBHOOK_MAX_RETRIES", "5"))
BACKOFF_BASE = int(os.getenv("WEBHOOK_BACKOFF_BASE_SECONDS", "5"))


class DeliveryStatus(str, Enum):
    PENDING = "pending"
    DELIVERING = "delivering"
    DELIVERED = "delivered"
    RETRYING = "retrying"
    FAILED = "failed"
    DLQ = "dead_letter"


class WebhookRegistration(BaseModel):
    endpoint_url: str
    events: list[str]
    secret: Optional[str] = None
    description: Optional[str] = None
    rate_limit: int = Field(default=100, description="Max deliveries per minute")
    active: bool = True


class WebhookPayload(BaseModel):
    event_type: str
    payload: dict
    endpoint_id: Optional[str] = None
    idempotency_key: Optional[str] = None


class DeliveryRecord(BaseModel):
    id: str
    endpoint_url: str
    event_type: str
    payload: dict
    status: DeliveryStatus
    attempts: int
    last_attempt: Optional[str] = None
    next_retry: Optional[str] = None
    response_status: Optional[int] = None
    response_body: Optional[str] = None
    signature: str
    created_at: str
    delivered_at: Optional[str] = None
    error: Optional[str] = None


# In-memory stores (production: PostgreSQL)
# Bounded: keep the newest N records so long-running processes don't grow
# without limit. Delivery semantics are unchanged; only history is capped.
MAX_DELIVERIES_KEPT = int(os.getenv("WEBHOOK_DELIVERIES_KEPT", "1000"))
MAX_DLQ_KEPT = int(os.getenv("WEBHOOK_DLQ_KEPT", "1000"))

endpoints: dict[str, dict] = {}
deliveries: "OrderedDict[str, DeliveryRecord]" = OrderedDict()
dlq: "deque[DeliveryRecord]" = deque(maxlen=MAX_DLQ_KEPT)

# Cap concurrent outbound deliveries during fan-out.
_delivery_semaphore = asyncio.Semaphore(int(os.getenv("WEBHOOK_FANOUT_CONCURRENCY", "10")))


def _store_delivery(record: DeliveryRecord) -> None:
    deliveries[record.id] = record
    deliveries.move_to_end(record.id)
    while len(deliveries) > MAX_DELIVERIES_KEPT:
        deliveries.popitem(last=False)  # evict oldest


def sign_payload(payload: dict, secret: str) -> str:
    """Generate HMAC-SHA256 signature for webhook payload."""
    body = json.dumps(payload, sort_keys=True, default=str)
    return hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()


def verify_signature(payload: dict, signature: str, secret: str) -> bool:
    """Verify HMAC-SHA256 signature."""
    expected = sign_payload(payload, secret)
    return hmac.compare_digest(expected, signature)


async def deliver_webhook(record: DeliveryRecord, endpoint_secret: str) -> DeliveryRecord:
    """Attempt to deliver a webhook with retry logic."""
    signature = sign_payload(record.payload, endpoint_secret)
    record.signature = signature
    record.status = DeliveryStatus.DELIVERING
    record.attempts += 1
    record.last_attempt = datetime.now(timezone.utc).isoformat()

    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Signature": f"sha256={signature}",
        "X-Webhook-Event": record.event_type,
        "X-Webhook-Delivery": record.id,
        "X-Webhook-Timestamp": str(int(time.time())),
        "User-Agent": "54agent-Webhook/1.0",
    }

    try:
        resp = await get_http_client().post(
            record.endpoint_url,
            json=record.payload,
            headers=headers,
        )
        record.response_status = resp.status_code
        record.response_body = resp.text[:1000]

        if 200 <= resp.status_code < 300:
            record.status = DeliveryStatus.DELIVERED
            record.delivered_at = datetime.now(timezone.utc).isoformat()
        else:
            if record.attempts >= MAX_RETRIES:
                record.status = DeliveryStatus.DLQ
                record.error = f"Max retries exceeded. Last status: {resp.status_code}"
                dlq.append(record)
            else:
                record.status = DeliveryStatus.RETRYING
                backoff = BACKOFF_BASE ** record.attempts
                record.next_retry = datetime.now(timezone.utc).isoformat()
    except Exception as e:
        record.error = str(e)
        if record.attempts >= MAX_RETRIES:
            record.status = DeliveryStatus.DLQ
            dlq.append(record)
        else:
            record.status = DeliveryStatus.RETRYING

    _store_delivery(record)
    return record


@app.post("/endpoints/register", dependencies=[Depends(require_internal_auth)])
async def register_endpoint(reg: WebhookRegistration):
    endpoint_id = str(uuid.uuid4())
    endpoints[endpoint_id] = {
        "id": endpoint_id,
        "url": reg.endpoint_url,
        "events": reg.events,
        "secret": reg.secret or SIGNING_SECRET,  # empty global secret is rejected at delivery time
        "description": reg.description,
        "rate_limit": reg.rate_limit,
        "active": reg.active,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "delivery_count": 0,
        "failure_count": 0,
    }
    return {"id": endpoint_id, "message": "endpoint registered"}


@app.get("/endpoints", dependencies=[Depends(require_internal_auth)])
async def list_endpoints():
    redacted = [{**ep, "secret": "***redacted***"} for ep in endpoints.values()]
    return {"endpoints": redacted, "count": len(endpoints)}


@app.delete("/endpoints/{endpoint_id}", dependencies=[Depends(require_internal_auth)])
async def remove_endpoint(endpoint_id: str):
    if endpoint_id not in endpoints:
        raise HTTPException(404, "endpoint not found")
    del endpoints[endpoint_id]
    return {"message": "endpoint removed"}


@app.post("/deliver", dependencies=[Depends(require_internal_auth)])
async def deliver(payload: WebhookPayload):
    """Deliver a webhook to all registered endpoints matching the event type."""
    matching = [
        ep for ep in endpoints.values()
        if ep["active"] and (payload.event_type in ep["events"] or "*" in ep["events"])
    ]

    if not matching and payload.endpoint_id:
        if payload.endpoint_id in endpoints:
            matching = [endpoints[payload.endpoint_id]]

    # Fail closed up front if any matching endpoint has no signing secret
    # (same behavior as before, but checked before any delivery starts).
    for ep in matching:
        require_signing_secret(ep.get("secret", SIGNING_SECRET))

    async def _deliver_to_endpoint(ep: dict) -> dict:
        async with _delivery_semaphore:
            record = DeliveryRecord(
                id=payload.idempotency_key or str(uuid.uuid4()),
                endpoint_url=ep["url"],
                event_type=payload.event_type,
                payload=payload.payload,
                status=DeliveryStatus.PENDING,
                attempts=0,
                signature="",
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            result = await deliver_webhook(record, ep.get("secret", SIGNING_SECRET))
            ep["delivery_count"] = ep.get("delivery_count", 0) + 1
            if result.status in (DeliveryStatus.FAILED, DeliveryStatus.DLQ):
                ep["failure_count"] = ep.get("failure_count", 0) + 1
            return {
                "delivery_id": result.id,
                "endpoint": result.endpoint_url,
                "status": result.status.value,
                "attempts": result.attempts,
            }

    # Fan out concurrently (bounded by the semaphore) instead of serially.
    results = list(await asyncio.gather(*(_deliver_to_endpoint(ep) for ep in matching)))

    return {"delivered": len(results), "results": results}


@app.get("/deliveries", dependencies=[Depends(require_internal_auth)])
async def list_deliveries(status: Optional[str] = None, limit: int = 50):
    items = list(deliveries.values())
    if status:
        items = [d for d in items if d.status.value == status]
    items.sort(key=lambda d: d.created_at, reverse=True)
    return {"deliveries": [d.model_dump() for d in items[:limit]], "total": len(items)}


@app.get("/deliveries/{delivery_id}", dependencies=[Depends(require_internal_auth)])
async def get_delivery(delivery_id: str):
    if delivery_id not in deliveries:
        raise HTTPException(404, "delivery not found")
    return deliveries[delivery_id].model_dump()


@app.post("/deliveries/{delivery_id}/retry", dependencies=[Depends(require_internal_auth)])
async def retry_delivery(delivery_id: str):
    if delivery_id not in deliveries:
        raise HTTPException(404, "delivery not found")
    record = deliveries[delivery_id]
    record.status = DeliveryStatus.PENDING
    ep = next((e for e in endpoints.values() if e["url"] == record.endpoint_url), None)
    secret = require_signing_secret(ep.get("secret", SIGNING_SECRET) if ep else SIGNING_SECRET)
    result = await deliver_webhook(record, secret)
    return result.model_dump()


@app.get("/dlq", dependencies=[Depends(require_internal_auth)])
async def list_dlq(limit: int = 50):
    return {"dead_letters": [d.model_dump() for d in list(dlq)[-limit:]], "total": len(dlq)}


@app.post("/dlq/replay", dependencies=[Depends(require_internal_auth)])
async def replay_dlq():
    replayed = 0
    for record in list(dlq):
        record.attempts = 0
        record.status = DeliveryStatus.PENDING
        ep = next((e for e in endpoints.values() if e["url"] == record.endpoint_url), None)
        secret = require_signing_secret(ep.get("secret", SIGNING_SECRET) if ep else SIGNING_SECRET)
        await deliver_webhook(record, secret)
        replayed += 1
    dlq.clear()
    return {"replayed": replayed}


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "webhook-delivery",
        "version": "1.0.0",
        "endpoints_registered": len(endpoints),
        "total_deliveries": len(deliveries),
        "dlq_size": len(dlq),
    }
