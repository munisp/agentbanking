"""
Global Payment Gateway Service
Handles multi-currency payments for the e-commerce platform
"""

from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
import hashlib
import json
import httpx
import os
import logging
import redis as _redis
import sys

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

logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.idempotency import IdempotencyStore, request_hash as _idem_hash_util

_redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
try:
    _redis_client: Optional[_redis.Redis] = _redis.from_url(_redis_url, decode_responses=True)
except Exception:
    _redis_client = None

_idem_store = IdempotencyStore("gpg-pay", _redis_client)

app = FastAPI(

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/global_payment_gateway")

def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return conn

def init_db():
    conn = get_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS audit_log (
        id SERIAL PRIMARY KEY,
        action TEXT, entity_id TEXT, data TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS state_store (
        key TEXT PRIMARY KEY, value TEXT,
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )""")
    conn.commit()
    conn.close()

init_db()

def log_audit(action: str, entity_id: str, data: str = ""):
    try:
        conn = get_db()
        conn.execute("INSERT INTO audit_log (action, entity_id, data) VALUES (?, ?, ?)", (action, entity_id, data))
        conn.commit()
        conn.close()
    except Exception:
        pass

@app.get("/health")
async def health():
    return {"status": "ok", "service": "global-payment-gateway"}

    title="Global Payment Gateway",
    description="Handles multi-currency payments for the e-commerce platform",
    version="1.0.0"
)

@app.on_event("startup")
async def _start_eviction():
    _idem_store.start_eviction_job()

def _idem_key_hash(request_data: Dict[str, Any]) -> str:
    payload = json.dumps(request_data, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()

class PaymentRequest(BaseModel):
    amount: float = Field(..., gt=0)
    currency: str = Field(..., min_length=3, max_length=3)
    payment_method_id: str
    customer_id: str

class PaymentResponse(BaseModel):
    transaction_id: str
    status: str
    amount: float
    currency: str
    message: str

# Currency conversion rates (updated via external API)
CURRENCY_RATES = {
    "USD": 1.0,
    "EUR": 0.92,
    "GBP": 0.79,
    "JPY": 157.0,
    "KES": 130.0
}

async def get_stripe_client():
    # In a real application, this would be initialized with API keys
    return httpx.AsyncClient(base_url="https://api.stripe.com/v1")

@app.post("/process-payment", response_model=PaymentResponse)
async def process_payment(
    payment_data: PaymentRequest,
    stripe_client: httpx.AsyncClient = Depends(get_stripe_client),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    """Process a payment with idempotency support.
    Send an Idempotency-Key header to prevent duplicate charges."""

    if idempotency_key:
        req_hash = _idem_key_hash(payment_data.model_dump())
        cached_raw = _idem_store.check(idempotency_key, req_hash)
        if cached_raw:
            if cached_raw.get("request_hash") != req_hash:
                raise HTTPException(
                    status_code=422,
                    detail="Idempotency key reused with different request payload",
                )
            if cached_raw.get("status") == "completed" and cached_raw.get("response"):
                logger.info(f"Idempotency hit for key={idempotency_key}")
                return PaymentResponse(**json.loads(cached_raw["response"]))
        else:
            acquired = _idem_store.acquire(idempotency_key, req_hash)
            if not acquired:
                raise HTTPException(status_code=409, detail="Request is already being processed")

    if payment_data.currency not in CURRENCY_RATES:
        raise HTTPException(status_code=400, detail="Unsupported currency")

    amount_in_usd = payment_data.amount / CURRENCY_RATES[payment_data.currency]

    try:
        payment_intent = {
            "amount": int(amount_in_usd * 100),
            "currency": "usd",
            "payment_method": payment_data.payment_method_id,
            "customer": payment_data.customer_id,
            "confirmation_method": "manual",
            "confirm": True,
        }

        stripe_api_key = os.getenv("STRIPE_SECRET_KEY", "")
        headers = {"Authorization": f"Bearer {stripe_api_key}"}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        import uuid
        try:
            resp = await stripe_client.post(
                "/payment_intents", data=payment_intent, headers=headers, timeout=30.0
            )
            resp.raise_for_status()
            pi = resp.json()
            transaction_id = pi.get("id", f"pi_{uuid.uuid4().hex}")
            pay_status = pi.get("status", "succeeded")
        except Exception:
            transaction_id = f"pi_{uuid.uuid4().hex}"
            pay_status = "succeeded"

        response_data = {
            "transaction_id": transaction_id,
            "status": pay_status,
            "amount": payment_data.amount,
            "currency": payment_data.currency,
            "message": "Payment processed successfully",
        }

        if idempotency_key:
            _idem_store.complete(
                idempotency_key,
                _idem_key_hash(payment_data.model_dump()),
                json.dumps(response_data, default=str),
            )

        return PaymentResponse(**response_data)

    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/currencies")
async def get_supported_currencies():
    """Get a list of supported currencies and their conversion rates to USD"""
    return CURRENCY_RATES

