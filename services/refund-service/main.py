"""
Refund Service - FastAPI microservice
Automated refund processing with policy enforcement, approval workflows, and settlement adjustment
"""
import os
import logging
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

import asyncpg
import httpx

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


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Refund Service", description="Automated refund processing with policy enforcement, approval workflows, and settlement adjustment", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# --- Configuration ---
DATABASE_URL = os.environ.get("DATABASE_URL", "")
PAYMENT_GATEWAY_URL = os.environ.get("PAYMENT_GATEWAY_URL", "")

db_pool: Optional[asyncpg.Pool] = None
http_client: Optional[httpx.AsyncClient] = None

# --- Domain Helpers ---

def validate_request(data: dict, required_fields: list) -> list:
    """Validate that all required fields are present in request data."""
    missing = [f for f in required_fields if f not in data or data[f] is None]
    return missing

def sanitize_input(value: str) -> str:
    """Sanitize user input to prevent injection attacks."""
    if not isinstance(value, str):
        return str(value)
    return value.strip().replace("<", "&lt;").replace(">", "&gt;")

def format_currency(amount: float, currency: str = "NGN") -> str:
    """Format amount with currency symbol."""
    symbols = {"NGN": "₦", "USD": "$", "GBP": "£", "EUR": "€", "KES": "KSh"}
    symbol = symbols.get(currency, currency + " ")
    return f"{symbol}{amount:,.2f}"

def generate_reference(prefix: str = "REF") -> str:
    """Generate a unique reference ID."""
    import time
    import hashlib
    ts = str(time.time()).encode()
    h = hashlib.md5(ts).hexdigest()[:8].upper()
    return f"{prefix}-{h}"

def paginate(items: list, page: int = 1, per_page: int = 20) -> dict:
    """Paginate a list of items."""
    start = (page - 1) * per_page
    end = start + per_page
    return {
        "items": items[start:end],
        "total": len(items),
        "page": page,
        "per_page": per_page,
        "total_pages": (len(items) + per_page - 1) // per_page
    }

async def _refund_row_to_dict(row) -> dict:
    return {
        "refund_id": row["refund_id"],
        "transaction_id": row["transaction_id"],
        "amount": float(row["amount"]),
        "reason": row["reason"],
        "status": row["status"],
        "gateway_reference": row["gateway_reference"],
        "approved_by": row["approved_by"],
        "approved_at": row["approved_at"].isoformat() if row["approved_at"] else None,
        "processed_at": row["processed_at"].isoformat() if row["processed_at"] else None,
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }

async def _call_reversal_rail(refund_id: str, transaction_id: str, amount: float, reason: str) -> str:
    """Initiate a real reversal via the payment gateway rail.

    Returns the gateway reversal reference. Raises RuntimeError when the rail
    is not configured or rejects the reversal — never fabricates a completion.
    """
    if not PAYMENT_GATEWAY_URL:
        raise RuntimeError("PAYMENT_GATEWAY_URL not configured — reversal rail unavailable")
    response = await http_client.post(
        f"{PAYMENT_GATEWAY_URL.rstrip('/')}/refund",
        json={
            "refund_id": refund_id,
            "transaction_id": transaction_id,
            "amount": amount,
            "reason": reason,
        },
    )
    if response.status_code >= 400:
        raise RuntimeError(f"payment gateway rejected reversal: HTTP {response.status_code}")
    data = response.json() if response.content else {}
    return data.get("reversal_reference") or data.get("reference") or refund_id

@app.on_event("startup")
async def startup():
    global db_pool, http_client
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL not set — refund-service refuses to start without persistence")
    db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS refunds (
                refund_id TEXT PRIMARY KEY,
                transaction_id TEXT NOT NULL,
                amount NUMERIC(18,2) NOT NULL,
                reason TEXT NOT NULL,
                status TEXT NOT NULL,
                gateway_reference TEXT,
                approved_by TEXT,
                approved_at TIMESTAMPTZ,
                processed_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
    http_client = httpx.AsyncClient(timeout=30.0)
    logger.info("Refund Service started")

@app.on_event("shutdown")
async def shutdown():
    global db_pool, http_client
    if db_pool:
        await db_pool.close()
    if http_client:
        await http_client.aclose()

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "refund-service", "version": "1.0.0", "timestamp": datetime.utcnow().isoformat()}

@app.post("/api/v1/refunds")
async def create_refund(transaction_id: str, amount: float, reason: str):
    """Create a refund request."""
    valid_reasons = ["customer_request", "duplicate_charge", "service_not_delivered", "overcharge", "fraud"]
    if reason not in valid_reasons:
        raise HTTPException(400, f"Must be one of: {valid_reasons}")
    if amount <= 0:
        raise HTTPException(400, "Refund amount must be positive")

    refund_id = generate_reference("RFD")
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO refunds (refund_id, transaction_id, amount, reason, status)
            VALUES ($1, $2, $3, $4, 'pending_approval')
        """, refund_id, transaction_id, amount, reason)
    logger.info(f"Refund created: {refund_id} for txn {transaction_id}")
    return {"refund_id": refund_id, "transaction_id": transaction_id, "amount": amount, "reason": reason, "status": "pending_approval"}

@app.get("/api/v1/refunds/{refund_id}")
async def get_refund(refund_id: str):
    """Get refund status."""
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM refunds WHERE refund_id = $1", refund_id)
    if not row:
        raise HTTPException(404, f"Refund '{refund_id}' not found")
    return await _refund_row_to_dict(row)

@app.post("/api/v1/refunds/{refund_id}/approve")
async def approve_refund(refund_id: str, approver_id: str):
    """Approve a pending refund and initiate the real reversal rail call."""
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow("SELECT * FROM refunds WHERE refund_id = $1 FOR UPDATE", refund_id)
            if not row:
                raise HTTPException(404, f"Refund '{refund_id}' not found")
            if row["status"] != "pending_approval":
                raise HTTPException(409, f"Refund is not pending approval (status: {row['status']})")

            await conn.execute("""
                UPDATE refunds SET status = 'approved', approved_by = $2, approved_at = NOW()
                WHERE refund_id = $1
            """, refund_id, approver_id)

    # Initiate the real reversal. Failure is recorded — never reported as success.
    try:
        gateway_ref = await _call_reversal_rail(refund_id, row["transaction_id"], float(row["amount"]), row["reason"])
    except Exception as e:
        logger.error(f"Reversal rail failed for refund {refund_id}: {e}")
        async with db_pool.acquire() as conn:
            await conn.execute("UPDATE refunds SET status = 'failed' WHERE refund_id = $1", refund_id)
        raise HTTPException(502, f"reversal rail failed for refund {refund_id}: {e}")

    async with db_pool.acquire() as conn:
        await conn.execute("""
            UPDATE refunds SET status = 'processing', gateway_reference = $2, processed_at = NOW()
            WHERE refund_id = $1
        """, refund_id, gateway_ref)

    return {
        "refund_id": refund_id,
        "status": "processing",
        "approved_by": approver_id,
        "approved_at": datetime.utcnow().isoformat(),
        "gateway_reference": gateway_ref,
    }

@app.get("/api/v1/refunds")
async def list_refunds(status: str = None, limit: int = 20):
    """List refunds with filtering."""
    async with db_pool.acquire() as conn:
        if status:
            rows = await conn.fetch(
                "SELECT * FROM refunds WHERE status = $1 ORDER BY created_at DESC LIMIT $2", status, limit)
        else:
            rows = await conn.fetch(
                "SELECT * FROM refunds ORDER BY created_at DESC LIMIT $1", limit)
    refunds = [await _refund_row_to_dict(r) for r in rows]
    return {"refunds": refunds, "total": len(refunds), "status": status}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
