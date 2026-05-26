"""
Float Management Service
Port: 8010
"""
from fastapi import FastAPI, HTTPException, Depends, Header
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

app = FastAPI(title="Float Management Service", description="Float Management Service for Remittance Platform", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
async def startup():
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS float_accounts (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                account_id VARCHAR(255) UNIQUE NOT NULL,
                currency VARCHAR(3) NOT NULL DEFAULT 'NGN',
                balance DECIMAL(18,2) NOT NULL DEFAULT 0,
                min_balance DECIMAL(18,2) DEFAULT 0,
                max_balance DECIMAL(18,2) DEFAULT 999999999,
                status VARCHAR(20) DEFAULT 'active',
                last_topup_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS float_transactions (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                account_id VARCHAR(255) NOT NULL,
                txn_type VARCHAR(20) NOT NULL,
                amount DECIMAL(18,2) NOT NULL,
                balance_before DECIMAL(18,2) NOT NULL,
                balance_after DECIMAL(18,2) NOT NULL,
                reference VARCHAR(255),
                description TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_float_acct ON float_transactions(account_id, created_at DESC)
        """)

@app.get("/health")
async def health_check():
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {"status": "healthy", "service": "float-service", "database": "connected"}
    except Exception as e:
        return {"status": "degraded", "service": "float-service", "error": str(e)}


class FloatTopupRequest(BaseModel):
    account_id: str
    amount: float
    reference: Optional[str] = None
    description: Optional[str] = None

class FloatDebitRequest(BaseModel):
    account_id: str
    amount: float
    reference: Optional[str] = None
    description: Optional[str] = None

@app.post("/api/v1/float/accounts")
async def create_float_account(account_id: str, currency: str = "NGN", token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        try:
            row = await conn.fetchrow(
                "INSERT INTO float_accounts (account_id, currency) VALUES ($1, $2) RETURNING *",
                account_id, currency
            )
            return dict(row)
        except asyncpg.UniqueViolationError:
            raise HTTPException(status_code=409, detail="Float account already exists")

@app.get("/api/v1/float/accounts/{account_id}")
async def get_float_account(account_id: str, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM float_accounts WHERE account_id=$1", account_id)
        if not row:
            raise HTTPException(status_code=404, detail="Float account not found")
        return dict(row)

@app.post("/api/v1/float/topup")
async def topup_float(req: FloatTopupRequest, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            acct = await conn.fetchrow("SELECT * FROM float_accounts WHERE account_id=$1 FOR UPDATE", req.account_id)
            if not acct:
                raise HTTPException(status_code=404, detail="Float account not found")
            balance_before = float(acct["balance"])
            balance_after = balance_before + req.amount
            if balance_after > float(acct["max_balance"]):
                raise HTTPException(status_code=400, detail="Topup would exceed max balance")
            await conn.execute(
                "UPDATE float_accounts SET balance=$1, last_topup_at=NOW(), updated_at=NOW() WHERE account_id=$2",
                balance_after, req.account_id
            )
            await conn.execute(
                """INSERT INTO float_transactions (account_id, txn_type, amount, balance_before, balance_after, reference, description)
                   VALUES ($1,'topup',$2,$3,$4,$5,$6)""",
                req.account_id, req.amount, balance_before, balance_after, req.reference, req.description
            )
        return {"account_id": req.account_id, "amount": req.amount, "balance_before": balance_before, "balance_after": balance_after}

@app.post("/api/v1/float/debit")
async def debit_float(req: FloatDebitRequest, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            acct = await conn.fetchrow("SELECT * FROM float_accounts WHERE account_id=$1 FOR UPDATE", req.account_id)
            if not acct:
                raise HTTPException(status_code=404, detail="Float account not found")
            balance_before = float(acct["balance"])
            balance_after = balance_before - req.amount
            if balance_after < float(acct["min_balance"]):
                raise HTTPException(status_code=400, detail="Insufficient float balance")
            await conn.execute("UPDATE float_accounts SET balance=$1, updated_at=NOW() WHERE account_id=$2", balance_after, req.account_id)
            await conn.execute(
                """INSERT INTO float_transactions (account_id, txn_type, amount, balance_before, balance_after, reference, description)
                   VALUES ($1,'debit',$2,$3,$4,$5,$6)""",
                req.account_id, req.amount, balance_before, balance_after, req.reference, req.description
            )
        return {"account_id": req.account_id, "amount": req.amount, "balance_before": balance_before, "balance_after": balance_after}

@app.get("/api/v1/float/transactions/{account_id}")
async def list_float_transactions(account_id: str, skip: int = 0, limit: int = 50, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM float_transactions WHERE account_id=$1 ORDER BY created_at DESC LIMIT $2 OFFSET $3",
            account_id, limit, skip
        )
        return {"transactions": [dict(r) for r in rows]}

@app.get("/api/v1/float/summary")
async def float_summary(token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        accounts = await conn.fetch("SELECT * FROM float_accounts WHERE status='active'")
        total_balance = sum(float(a["balance"]) for a in accounts)
        return {"total_accounts": len(accounts), "total_balance": total_balance, "accounts": [dict(a) for a in accounts]}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8010)
