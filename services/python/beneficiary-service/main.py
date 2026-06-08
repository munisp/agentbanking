"""
Beneficiary Service
Port: 8055
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

app = FastAPI(title="Beneficiary Service", description="Beneficiary Service for Remittance Platform", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
async def startup():
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS beneficiaries (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id VARCHAR(255) NOT NULL,
                name VARCHAR(255) NOT NULL,
                nickname VARCHAR(100),
                bank_code VARCHAR(20),
                bank_name VARCHAR(100),
                account_number VARCHAR(50),
                account_type VARCHAR(20) DEFAULT 'savings',
                phone VARCHAR(20),
                email VARCHAR(255),
                country VARCHAR(3) DEFAULT 'NGA',
                currency VARCHAR(3) DEFAULT 'NGN',
                transfer_type VARCHAR(20) DEFAULT 'bank',
                is_favorite BOOLEAN DEFAULT FALSE,
                last_transfer_at TIMESTAMPTZ,
                metadata JSONB DEFAULT '{}',
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_benef_user ON beneficiaries(user_id);
            CREATE INDEX IF NOT EXISTS idx_benef_favorite ON beneficiaries(user_id, is_favorite)
        """)

@app.get("/health")
async def health_check():
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {"status": "healthy", "service": "beneficiary-service", "database": "connected"}
    except Exception as e:
        return {"status": "degraded", "service": "beneficiary-service", "error": str(e)}

class BeneficiaryCreate(BaseModel):
    name: str
    nickname: Optional[str] = None
    bank_code: Optional[str] = None
    bank_name: Optional[str] = None
    account_number: Optional[str] = None
    account_type: str = "savings"
    phone: Optional[str] = None
    email: Optional[str] = None
    country: str = "NGA"
    currency: str = "NGN"
    transfer_type: str = "bank"

class BeneficiaryUpdate(BaseModel):
    nickname: Optional[str] = None
    bank_code: Optional[str] = None
    bank_name: Optional[str] = None
    account_number: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    is_favorite: Optional[bool] = None

@app.post("/api/v1/beneficiaries")
async def create_beneficiary(b: BeneficiaryCreate, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT id FROM beneficiaries WHERE user_id=$1 AND account_number=$2 AND bank_code=$3",
            token[:36], b.account_number, b.bank_code
        )
        if existing:
            raise HTTPException(status_code=409, detail="Beneficiary already exists")
        row = await conn.fetchrow(
            """INSERT INTO beneficiaries (user_id, name, nickname, bank_code, bank_name, account_number,
               account_type, phone, email, country, currency, transfer_type)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12) RETURNING *""",
            token[:36], b.name, b.nickname, b.bank_code, b.bank_name, b.account_number,
            b.account_type, b.phone, b.email, b.country, b.currency, b.transfer_type
        )
        return dict(row)

@app.get("/api/v1/beneficiaries")
async def list_beneficiaries(favorites_only: bool = False, skip: int = 0, limit: int = 50, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        fav_filter = "AND is_favorite = TRUE" if favorites_only else ""
        rows = await conn.fetch(
            f"SELECT * FROM beneficiaries WHERE user_id=$1 {fav_filter} ORDER BY is_favorite DESC, last_transfer_at DESC NULLS LAST LIMIT $2 OFFSET $3",
            token[:36], limit, skip
        )
        total = await conn.fetchval(f"SELECT COUNT(*) FROM beneficiaries WHERE user_id=$1 {fav_filter}", token[:36])
        return {"total": total, "beneficiaries": [dict(r) for r in rows]}

@app.get("/api/v1/beneficiaries/{benef_id}")
async def get_beneficiary(benef_id: str, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM beneficiaries WHERE id=$1 AND user_id=$2", uuid.UUID(benef_id), token[:36])
        if not row:
            raise HTTPException(status_code=404, detail="Beneficiary not found")
        return dict(row)

@app.put("/api/v1/beneficiaries/{benef_id}")
async def update_beneficiary(benef_id: str, b: BeneficiaryUpdate, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow("SELECT * FROM beneficiaries WHERE id=$1 AND user_id=$2", uuid.UUID(benef_id), token[:36])
        if not existing:
            raise HTTPException(status_code=404, detail="Beneficiary not found")
        updates = {k: v for k, v in b.dict().items() if v is not None}
        if not updates:
            return dict(existing)
        set_clause = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(updates.keys()))
        row = await conn.fetchrow(
            f"UPDATE beneficiaries SET {set_clause}, updated_at=NOW() WHERE id=$1 RETURNING *",
            uuid.UUID(benef_id), *updates.values()
        )
        return dict(row)

@app.delete("/api/v1/beneficiaries/{benef_id}")
async def delete_beneficiary(benef_id: str, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM beneficiaries WHERE id=$1 AND user_id=$2", uuid.UUID(benef_id), token[:36])
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Beneficiary not found")
        return {"deleted": True}

@app.put("/api/v1/beneficiaries/{benef_id}/favorite")
async def toggle_favorite(benef_id: str, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "UPDATE beneficiaries SET is_favorite = NOT is_favorite, updated_at=NOW() WHERE id=$1 AND user_id=$2 RETURNING *",
            uuid.UUID(benef_id), token[:36]
        )
        if not row:
            raise HTTPException(status_code=404, detail="Beneficiary not found")
        return dict(row)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8055)
