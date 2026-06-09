"""
Transaction History
Port: 8136
"""
from fastapi import FastAPI, HTTPException, Depends, Header
import sys as _sys2, os as _os2
_sys2.path.insert(0, _os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from enum import Enum
import uuid
import os
import json
import asyncpg
import uvicorn

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

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://remittance:remittance@localhost:5432/remittance")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

_db_pool = None

async def get_db_pool():
    global _db_pool
    if _db_pool is None:
        _db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    return _db_pool

async def verify_token(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    token = authorization[7:]
    if not token or len(token) < 10:
        raise HTTPException(status_code=401, detail="Invalid token")
    return token

app = FastAPI(title="Transaction History", description="Transaction History for Remittance Platform", version="1.0.0")
apply_middleware(app, enable_auth=True)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
async def startup():
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS transaction_history (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id VARCHAR(255) NOT NULL,
                transaction_type VARCHAR(30) NOT NULL,
                direction VARCHAR(10) NOT NULL DEFAULT 'outgoing',
                amount DECIMAL(18,2) NOT NULL,
                currency VARCHAR(3) NOT NULL DEFAULT 'NGN',
                fee DECIMAL(18,2) DEFAULT 0,
                exchange_rate DECIMAL(18,8),
                source_currency VARCHAR(3),
                destination_currency VARCHAR(3),
                counterparty_name VARCHAR(255),
                counterparty_account VARCHAR(100),
                reference VARCHAR(255),
                status VARCHAR(20) DEFAULT 'completed',
                description TEXT,
                metadata JSONB DEFAULT '{}',
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_txh_user ON transaction_history(user_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_txh_type ON transaction_history(transaction_type);
            CREATE INDEX IF NOT EXISTS idx_txh_ref ON transaction_history(reference)
        """)

@app.get("/health")
async def health_check():
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {"status": "healthy", "service": "transaction-history", "database": "connected"}
    except Exception as e:
        return {"status": "degraded", "service": "transaction-history", "error": str(e)}

class TransactionRecord(BaseModel):
    user_id: str
    transaction_type: str
    direction: str = "outgoing"
    amount: float
    currency: str = "NGN"
    fee: float = 0
    exchange_rate: Optional[float] = None
    source_currency: Optional[str] = None
    destination_currency: Optional[str] = None
    counterparty_name: Optional[str] = None
    counterparty_account: Optional[str] = None
    reference: Optional[str] = None
    status: str = "completed"
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

@app.post("/api/v1/transactions/record")
async def record_transaction(txn: TransactionRecord, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO transaction_history (user_id, transaction_type, direction, amount, currency, fee,
               exchange_rate, source_currency, destination_currency, counterparty_name, counterparty_account,
               reference, status, description, metadata)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15) RETURNING *""",
            txn.user_id, txn.transaction_type, txn.direction, txn.amount, txn.currency, txn.fee,
            txn.exchange_rate, txn.source_currency, txn.destination_currency, txn.counterparty_name,
            txn.counterparty_account, txn.reference, txn.status, txn.description, json.dumps(txn.metadata or {})
        )
        return dict(row)

@app.get("/api/v1/transactions")
async def list_transactions(user_id: Optional[str] = None, transaction_type: Optional[str] = None,
                            direction: Optional[str] = None, status: Optional[str] = None,
                            currency: Optional[str] = None, skip: int = 0, limit: int = 50,
                            token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        uid = user_id or token[:36]
        conditions = ["user_id=$1"]
        params = [uid]
        idx = 2
        if transaction_type:
            conditions.append(f"transaction_type=${idx}"); params.append(transaction_type); idx += 1
        if direction:
            conditions.append(f"direction=${idx}"); params.append(direction); idx += 1
        if status:
            conditions.append(f"status=${idx}"); params.append(status); idx += 1
        if currency:
            conditions.append(f"currency=${idx}"); params.append(currency); idx += 1
        where = "WHERE " + " AND ".join(conditions)
        params.extend([limit, skip])
        rows = await conn.fetch(f"SELECT * FROM transaction_history {where} ORDER BY created_at DESC LIMIT ${idx} OFFSET ${idx+1}", *params)
        total = await conn.fetchval(f"SELECT COUNT(*) FROM transaction_history {where}", *params[:-2])
        return {"total": total, "transactions": [dict(r) for r in rows]}

@app.get("/api/v1/transactions/{txn_id}")
async def get_transaction(txn_id: str, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM transaction_history WHERE id=$1", uuid.UUID(txn_id))
        if not row:
            raise HTTPException(status_code=404, detail="Transaction not found")
        return dict(row)

@app.get("/api/v1/transactions/stats/summary")
async def transaction_stats(token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        uid = token[:36]
        total_sent = await conn.fetchval("SELECT COALESCE(SUM(amount),0) FROM transaction_history WHERE user_id=$1 AND direction='outgoing'", uid)
        total_received = await conn.fetchval("SELECT COALESCE(SUM(amount),0) FROM transaction_history WHERE user_id=$1 AND direction='incoming'", uid)
        total_fees = await conn.fetchval("SELECT COALESCE(SUM(fee),0) FROM transaction_history WHERE user_id=$1", uid)
        count = await conn.fetchval("SELECT COUNT(*) FROM transaction_history WHERE user_id=$1", uid)
        by_type = await conn.fetch("SELECT transaction_type, COUNT(*) as cnt, SUM(amount) as total FROM transaction_history WHERE user_id=$1 GROUP BY transaction_type", uid)
        return {"total_sent": float(total_sent), "total_received": float(total_received), "total_fees": float(total_fees),
                "transaction_count": count, "by_type": [dict(r) for r in by_type]}

@app.get("/api/v1/transactions/export")
async def export_transactions(user_id: Optional[str] = None, format: str = "json", token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        uid = user_id or token[:36]
        rows = await conn.fetch("SELECT * FROM transaction_history WHERE user_id=$1 ORDER BY created_at DESC LIMIT 10000", uid)
        data = [dict(r) for r in rows]
        if format == "csv":
            if not data:
                return {"csv": ""}
            headers = list(data[0].keys())
            lines = [",".join(headers)]
            for row in data:
                lines.append(",".join(str(row.get(h, "")) for h in headers))
            return {"csv": "\n".join(lines), "count": len(data)}
        return {"transactions": data, "count": len(data)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8136)
