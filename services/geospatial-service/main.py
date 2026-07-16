"""
Geospatial Service
Port: 8011
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

async def verify_token_optional(authorization: str = Header(None)):
    """Optional token verification - allows requests without token or with invalid token (for public dashboards)"""
    if authorization is None:
        return None  # Allow unauthenticated access
    if authorization.startswith("Bearer "):
        token = authorization[7:]
        if token and len(token) >= 10:
            return token
    return None  # Silently accept invalid token format for backwards compatibility

app = FastAPI(title="Geospatial Service", description="Geospatial Service for Remittance Platform", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
async def startup():
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        try:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS locations (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    entity_id VARCHAR(255) NOT NULL,
                    entity_type VARCHAR(50) NOT NULL,
                    latitude DECIMAL(10,8),
                    longitude DECIMAL(11,8),
                    address TEXT,
                    city VARCHAR(100),
                    country VARCHAR(3),
                    metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
        except asyncpg.exceptions.UniqueViolationError:
            pass  # Another worker already created the table concurrently

@app.get("/health")
async def health_check():
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {"status": "healthy", "service": "geospatial-service", "database": "connected"}
    except Exception as e:
        return {"status": "degraded", "service": "geospatial-service", "error": str(e)}


class ItemCreate(BaseModel):
    entity_id: str
    entity_type: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class ItemUpdate(BaseModel):
    entity_id: Optional[str] = None
    entity_type: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@app.post("/api/v1/geospatial-service")
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
        query = f"INSERT INTO locations ({', '.join(cols)}) VALUES ({ph}) RETURNING *"
        row = await conn.fetchrow(query, *vals)
        return dict(row)


@app.get("/api/v1/geospatial-service")
async def list_items(skip: int = 0, limit: int = 50, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM locations ORDER BY created_at DESC LIMIT $1 OFFSET $2",
            limit, skip
        )
        total = await conn.fetchval("SELECT COUNT(*) FROM locations")
        return {"total": total, "items": [dict(r) for r in rows], "skip": skip, "limit": limit}


@app.get("/api/v1/geospatial-service/{item_id}")
async def get_item(item_id: str, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM locations WHERE id=$1", uuid.UUID(item_id))
        if not row:
            raise HTTPException(status_code=404, detail="Item not found")
        return dict(row)


@app.put("/api/v1/geospatial-service/{item_id}")
async def update_item(item_id: str, item: ItemUpdate, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow("SELECT * FROM locations WHERE id=$1", uuid.UUID(item_id))
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
        query = f"UPDATE locations SET {', '.join(set_parts)}, updated_at=NOW() WHERE id=$1 RETURNING *"
        row = await conn.fetchrow(query, *params)
        return dict(row)


@app.delete("/api/v1/geospatial-service/{item_id}")
async def delete_item(item_id: str, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM locations WHERE id=$1", uuid.UUID(item_id))
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Item not found")
        return {"deleted": True}


@app.get("/api/v1/geospatial-service/stats")
async def get_stats(token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM locations")
        today = await conn.fetchval("SELECT COUNT(*) FROM locations WHERE created_at >= CURRENT_DATE")
        return {"total": total, "today": today, "service": "geospatial-service"}


@app.get("/api/v1/territories/analytics")
async def get_territories_analytics(token: str = Depends(verify_token_optional)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM locations")
        by_country = await conn.fetch(
            "SELECT country, COUNT(*) as count FROM locations WHERE country IS NOT NULL GROUP BY country ORDER BY count DESC LIMIT 20"
        )
        by_city = await conn.fetch(
            "SELECT city, country, COUNT(*) as count FROM locations WHERE city IS NOT NULL GROUP BY city, country ORDER BY count DESC LIMIT 20"
        )
        return {
            "total_locations": total,
            "by_country": [dict(r) for r in by_country],
            "by_city": [dict(r) for r in by_city],
        }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8011)
