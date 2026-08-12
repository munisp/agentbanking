"""
Refund Service - FastAPI microservice
Automated refund processing with policy enforcement, approval workflows, and settlement adjustment

Fail-loud doctrine: refunds are persisted in PostgreSQL, unknown IDs return 404,
and approvals execute a REAL reversal rail call (payment gateway refund API or
TigerBeetle wallet credit). A refund is only marked completed when the rail
accepts it; rail failures mark the refund failed and surface a 502/503.
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

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://user:password@localhost:5432/refund_service")
PAYMENT_GATEWAY_URL = os.environ.get("PAYMENT_GATEWAY_URL", "")
TIGERBEETLE_SERVICE_URL = os.environ.get("TIGERBEETLE_SERVICE_URL", "")

app = FastAPI(title="Refund Service", description="Automated refund processing with policy enforcement, approval workflows, and settlement adjustment", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

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

def refund_row_to_dict(row: asyncpg.Record) -> Dict[str, Any]:
    """Serialize a refunds table row."""
    return {
        "refund_id": row["refund_id"],
        "transaction_id": row["transaction_id"],
        "amount": float(row["amount"]),
        "currency": row["currency"],
        "reason": row["reason"],
        "refund_method": row["refund_method"],
        "status": row["status"],
        "gateway_reference": row["gateway_reference"],
        "tigerbeetle_transfer_id": row["tigerbeetle_transfer_id"],
        "initiated_by": row["initiated_by"],
        "approved_by": row["approved_by"],
        "error_message": row["error_message"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "approved_at": row["approved_at"].isoformat() if row["approved_at"] else None,
        "processed_at": row["processed_at"].isoformat() if row["processed_at"] else None,
    }

@app.on_event("startup")
async def startup():
    """Connect to PostgreSQL and ensure the refunds table exists. Fails startup
    loudly when the database is unreachable — an in-memory refund ledger would
    silently lose money-movement records."""
    global db_pool, http_client
    db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS refunds (
                refund_id TEXT PRIMARY KEY,
                transaction_id TEXT NOT NULL,
                amount NUMERIC(20, 2) NOT NULL,
                currency TEXT NOT NULL DEFAULT 'NGN',
                reason TEXT NOT NULL,
                refund_method TEXT NOT NULL DEFAULT 'original_payment_method',
                status TEXT NOT NULL DEFAULT 'pending_approval',
                gateway_reference TEXT,
                tigerbeetle_transfer_id TEXT,
                initiated_by TEXT,
                approved_by TEXT,
                error_message TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                approved_at TIMESTAMPTZ,
                processed_at TIMESTAMPTZ
            )
        """)
    http_client = httpx.AsyncClient(timeout=20.0)
    logger.info("Refund Service started with PostgreSQL persistence")

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

@app.post("/api/v1/refunds", status_code=201)
async def create_refund(transaction_id: str, amount: float, reason: str,
                        refund_method: str = "original_payment_method",
                        initiated_by: str = None):
    """Create a refund request and persist it."""
    valid_reasons = ["customer_request", "duplicate_charge", "service_not_delivered", "overcharge", "fraud"]
    if reason not in valid_reasons:
        raise HTTPException(400, f"Must be one of: {valid_reasons}")
    if amount <= 0:
        raise HTTPException(400, "Refund amount must be positive")

    refund_id = f"RFD-{generate_reference('')}—{transaction_id}".replace("—", "-")
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO refunds (refund_id, transaction_id, amount, currency, reason,
                                 refund_method, status, initiated_by, created_at)
            VALUES ($1, $2, $3, 'NGN', $4, $5, 'pending_approval', $6, NOW())
        """, refund_id, transaction_id, amount, reason, refund_method, initiated_by)
        row = await conn.fetchrow("SELECT * FROM refunds WHERE refund_id = $1", refund_id)
    logger.info(f"Refund created: {refund_id} for txn {transaction_id}")
    return refund_row_to_dict(row)

@app.get("/api/v1/refunds/{refund_id}")
async def get_refund(refund_id: str):
    """Get refund status. Unknown IDs return 404 — never fabricated data."""
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM refunds WHERE refund_id = $1", refund_id)
    if not row:
        raise HTTPException(404, f"Refund '{refund_id}' not found")
    return refund_row_to_dict(row)

@app.post("/api/v1/refunds/{refund_id}/approve")
async def approve_refund(refund_id: str, approver_id: str, wallet_account_id: str = None):
    """Approve a pending refund and execute the real reversal rail call."""
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM refunds WHERE refund_id = $1", refund_id)
        if not row:
            raise HTTPException(404, f"Refund '{refund_id}' not found")
        if row["status"] != "pending_approval":
            raise HTTPException(400, f"Refund is not pending approval (status: {row['status']})")

        method = row["refund_method"]
        amount = float(row["amount"])
        transaction_id = row["transaction_id"]

        try:
            if method == "wallet":
                # Real wallet credit via the TigerBeetle ledger service
                if not TIGERBEETLE_SERVICE_URL:
                    raise HTTPException(503, "TIGERBEETLE_SERVICE_URL not configured — cannot credit wallet")
                if not wallet_account_id:
                    raise HTTPException(400, "wallet_account_id is required for wallet refunds")
                resp = await http_client.post(
                    f"{TIGERBEETLE_SERVICE_URL}/transfer",
                    json={
                        "from_user_id": "platform_refund_pool",
                        "to_user_id": wallet_account_id,
                        "amount": amount,
                        "transaction_type": "refund",
                        "description": f"Refund {refund_id} for txn {transaction_id}",
                    },
                )
                resp.raise_for_status()
                tb_result = resp.json()
                transfer_id = str(tb_result.get("transfer_id") or tb_result.get("id"))
                await conn.execute("""
                    UPDATE refunds
                    SET status = 'completed', approved_by = $2, approved_at = NOW(),
                        processed_at = NOW(), tigerbeetle_transfer_id = $3
                    WHERE refund_id = $1
                """, refund_id, approver_id, transfer_id)
            else:
                # Real reversal via the payment gateway refund API
                if not PAYMENT_GATEWAY_URL:
                    raise HTTPException(503, "PAYMENT_GATEWAY_URL not configured — cannot reverse payment")
                resp = await http_client.post(
                    f"{PAYMENT_GATEWAY_URL}/refund",
                    json={
                        "transaction_id": transaction_id,
                        "amount": amount,
                        "reason": row["reason"],
                        "refund_id": refund_id,
                    },
                )
                resp.raise_for_status()
                gw = resp.json() if resp.content else {}
                gw_status = gw.get("status", "processing")
                gw_ref = gw.get("reference") or gw.get("gateway_reference")
                new_status = "completed" if gw_status in ("completed", "success", "processed") else "processing"
                await conn.execute("""
                    UPDATE refunds
                    SET status = $2, approved_by = $3, approved_at = NOW(),
                        gateway_reference = $4,
                        processed_at = CASE WHEN $2 = 'completed' THEN NOW() ELSE NULL END
                    WHERE refund_id = $1
                """, refund_id, new_status, approver_id, gw_ref)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Reversal rail failed for refund {refund_id}: {e}")
            await conn.execute("""
                UPDATE refunds SET status = 'failed', error_message = $2 WHERE refund_id = $1
            """, refund_id, str(e))
            raise HTTPException(502, f"Reversal rail failed; refund {refund_id} marked failed: {e}")

        updated = await conn.fetchrow("SELECT * FROM refunds WHERE refund_id = $1", refund_id)
    logger.info(f"Refund {refund_id} approved by {approver_id}")
    return refund_row_to_dict(updated)

@app.get("/api/v1/refunds")
async def list_refunds(status: str = None, limit: int = 20):
    """List refunds from the database with optional status filtering."""
    async with db_pool.acquire() as conn:
        if status:
            rows = await conn.fetch(
                "SELECT * FROM refunds WHERE status = $1 ORDER BY created_at DESC LIMIT $2",
                status, limit)
        else:
            rows = await conn.fetch(
                "SELECT * FROM refunds ORDER BY created_at DESC LIMIT $1", limit)
    return {"refunds": [refund_row_to_dict(r) for r in rows], "total": len(rows), "status": status}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
