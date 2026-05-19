"""
Payout Service
Port: 8125
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

app = FastAPI(title="Payout Service", description="Payout Service for Remittance Platform", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
async def startup():
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS payouts (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id VARCHAR(255) NOT NULL,
                beneficiary_id VARCHAR(255),
                amount DECIMAL(18,2) NOT NULL,
                currency VARCHAR(3) NOT NULL DEFAULT 'NGN',
                destination_type VARCHAR(20) NOT NULL,
                destination_account VARCHAR(100) NOT NULL,
                destination_bank VARCHAR(50),
                status VARCHAR(20) DEFAULT 'pending',
                provider VARCHAR(50),
                provider_reference VARCHAR(255),
                fee DECIMAL(18,2) DEFAULT 0,
                failure_reason TEXT,
                idempotency_key VARCHAR(255) UNIQUE,
                initiated_at TIMESTAMPTZ DEFAULT NOW(),
                completed_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_payout_user ON payouts(user_id);
            CREATE INDEX IF NOT EXISTS idx_payout_status ON payouts(status);
            CREATE INDEX IF NOT EXISTS idx_payout_idemp ON payouts(idempotency_key)
        """)

@app.get("/health")
async def health_check():
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {"status": "healthy", "service": "payout-service", "database": "connected"}
    except Exception as e:
        return {"status": "degraded", "service": "payout-service", "error": str(e)}


class PayoutCreate(BaseModel):
    beneficiary_id: Optional[str] = None
    amount: float
    currency: str = "NGN"
    destination_type: str
    destination_account: str
    destination_bank: Optional[str] = None
    provider: Optional[str] = None
    idempotency_key: Optional[str] = None

@app.post("/api/v1/payouts")
async def create_payout(p: PayoutCreate, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        if p.idempotency_key:
            existing = await conn.fetchrow("SELECT * FROM payouts WHERE idempotency_key=$1", p.idempotency_key)
            if existing:
                return dict(existing)
        row = await conn.fetchrow(
            """INSERT INTO payouts (user_id, beneficiary_id, amount, currency, destination_type, destination_account,
               destination_bank, provider, idempotency_key, status)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,'processing') RETURNING *""",
            token[:36], p.beneficiary_id, p.amount, p.currency, p.destination_type,
            p.destination_account, p.destination_bank, p.provider or "auto", p.idempotency_key
        )
        return dict(row)

@app.get("/api/v1/payouts")
async def list_payouts(status: Optional[str] = None, skip: int = 0, limit: int = 50, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        extra = "AND status=$3" if status else ""
        params = [token[:36], limit, skip] if not status else [token[:36], limit, skip, status]
        if status:
            rows = await conn.fetch(f"SELECT * FROM payouts WHERE user_id=$1 AND status=$4 ORDER BY created_at DESC LIMIT $2 OFFSET $3", *params)
        else:
            rows = await conn.fetch("SELECT * FROM payouts WHERE user_id=$1 ORDER BY created_at DESC LIMIT $2 OFFSET $3", *params[:3])
        return {"payouts": [dict(r) for r in rows]}

@app.get("/api/v1/payouts/{payout_id}")
async def get_payout(payout_id: str, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM payouts WHERE id=$1 AND user_id=$2", uuid.UUID(payout_id), token[:36])
        if not row:
            raise HTTPException(status_code=404, detail="Payout not found")
        return dict(row)

@app.put("/api/v1/payouts/{payout_id}/status")
async def update_payout_status(payout_id: str, status: str, provider_reference: Optional[str] = None,
                               failure_reason: Optional[str] = None, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        completed = "completed_at=NOW()," if status in ("completed", "failed") else ""
        row = await conn.fetchrow(
            f"UPDATE payouts SET status=$1, provider_reference=$2, failure_reason=$3, {completed} updated_at=NOW() WHERE id=$4 RETURNING *",
            status, provider_reference, failure_reason, uuid.UUID(payout_id)
        ) if completed else await conn.fetchrow(
            "UPDATE payouts SET status=$1, provider_reference=$2, failure_reason=$3 WHERE id=$4 RETURNING *",
            status, provider_reference, failure_reason, uuid.UUID(payout_id)
        )
        if not row:
            raise HTTPException(status_code=404, detail="Payout not found")
        return dict(row)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8125)
