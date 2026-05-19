"""
Bank Verification Service
Port: 8075
"""
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid
import os
import json
import asyncpg
import uvicorn

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://remittance:remittance@localhost:5432/remittance")

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

app = FastAPI(title="Bank Verification Service", description="Bank Verification Service for Remittance Platform", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
async def startup():
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS bank_verifications (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                account_number VARCHAR(50) NOT NULL,
                bank_code VARCHAR(20) NOT NULL,
                account_name VARCHAR(255),
                bank_name VARCHAR(100),
                status VARCHAR(20) DEFAULT 'pending',
                verification_method VARCHAR(30) DEFAULT 'nibss',
                verified_at TIMESTAMPTZ,
                user_id VARCHAR(255),
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

@app.get("/health")
async def health_check():
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {"status": "healthy", "service": "bank-verification", "database": "connected"}
    except Exception as e:
        return {"status": "degraded", "service": "bank-verification", "error": str(e)}


class ItemCreate(BaseModel):
    account_number: str
    bank_code: str
    account_name: Optional[str] = None
    bank_name: Optional[str] = None
    status: Optional[str] = None
    verification_method: Optional[str] = None
    verified_at: Optional[str] = None
    user_id: Optional[str] = None

class ItemUpdate(BaseModel):
    account_number: Optional[str] = None
    bank_code: Optional[str] = None
    account_name: Optional[str] = None
    bank_name: Optional[str] = None
    status: Optional[str] = None
    verification_method: Optional[str] = None
    verified_at: Optional[str] = None
    user_id: Optional[str] = None


@app.post("/api/v1/bank-verification")
async def create_item(item: ItemCreate, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        data = {k: v for k, v in item.dict().items() if v is not None}
        if not data:
            raise HTTPException(status_code=400, detail="No fields provided")
        cols = list(data.keys())
        vals = list(data.values())
        for i in range(len(vals)):
            if isinstance(vals[i], dict):
                vals[i] = json.dumps(vals[i])
        ph = ", ".join(["$" + str(i+1) for i in range(len(cols))])
        query = f"INSERT INTO bank_verifications ({', '.join(cols)}) VALUES ({ph}) RETURNING *"
        row = await conn.fetchrow(query, *vals)
        return dict(row)


@app.get("/api/v1/bank-verification")
async def list_items(skip: int = 0, limit: int = 50, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM bank_verifications ORDER BY created_at DESC LIMIT $1 OFFSET $2",
            limit, skip
        )
        total = await conn.fetchval("SELECT COUNT(*) FROM bank_verifications")
        return {"total": total, "items": [dict(r) for r in rows], "skip": skip, "limit": limit}


@app.get("/api/v1/bank-verification/{item_id}")
async def get_item(item_id: str, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM bank_verifications WHERE id=$1", uuid.UUID(item_id))
        if not row:
            raise HTTPException(status_code=404, detail="Item not found")
        return dict(row)


@app.put("/api/v1/bank-verification/{item_id}")
async def update_item(item_id: str, item: ItemUpdate, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow("SELECT * FROM bank_verifications WHERE id=$1", uuid.UUID(item_id))
        if not existing:
            raise HTTPException(status_code=404, detail="Item not found")
        updates = {k: v for k, v in item.dict().items() if v is not None}
        if not updates:
            return dict(existing)
        set_parts = []
        params = [uuid.UUID(item_id)]
        idx = 2
        for k, v in updates.items():
            set_parts.append(f"{k}=${idx}")
            params.append(json.dumps(v) if isinstance(v, dict) else v)
            idx += 1
        query = f"UPDATE bank_verifications SET {', '.join(set_parts)}, updated_at=NOW() WHERE id=$1 RETURNING *"
        row = await conn.fetchrow(query, *params)
        return dict(row)


@app.delete("/api/v1/bank-verification/{item_id}")
async def delete_item(item_id: str, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM bank_verifications WHERE id=$1", uuid.UUID(item_id))
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Item not found")
        return {"deleted": True}


@app.get("/api/v1/bank-verification/stats")
async def get_stats(token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM bank_verifications")
        today = await conn.fetchval("SELECT COUNT(*) FROM bank_verifications WHERE created_at >= CURRENT_DATE")
        return {"total": total, "today": today, "service": "bank-verification"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8075)
