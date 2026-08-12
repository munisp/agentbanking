"""
Telegram Integration
Port: 8159
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

_db_pool = None

async def get_db_pool():
    global _db_pool
    if _db_pool is None:
        _db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    return _db_pool

KEYCLOAK_SERVER_URL = os.getenv("KEYCLOAK_SERVER_URL", "http://keycloak:8080")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "remittance")
KEYCLOAK_CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "remittance-api")
_JWKS_URL = f"{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs"
_jwks_client = None


def _get_jwks_client():
    global _jwks_client
    if _jwks_client is None:
        from jwt import PyJWKClient
        _jwks_client = PyJWKClient(_JWKS_URL, cache_keys=True)
    return _jwks_client


async def verify_token(authorization: str = Header(...)):
    """Validate the Bearer JWT against the Keycloak realm JWKS.

    Previously this only checked the header shape, so any non-empty string
    was accepted as a token (authentication bypass). Authentication is now
    always enforced: tokens must be signed, unexpired realm JWTs.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    token = authorization[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    import jwt
    try:
        signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
        return claims.get("sub", "")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Token validation unavailable: {e}")


app = FastAPI(title="Telegram Integration", description="Telegram Integration for Remittance Platform", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
async def startup():
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS telegram_messages (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                chat_id VARCHAR(100),
                user_id VARCHAR(255),
                message_type VARCHAR(30) DEFAULT 'notification',
                content TEXT NOT NULL,
                status VARCHAR(20) DEFAULT 'pending',
                sent_at TIMESTAMPTZ,
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
        return {"status": "healthy", "service": "telegram-service", "database": "connected"}
    except Exception as e:
        return {"status": "degraded", "service": "telegram-service", "error": str(e)}


class ItemCreate(BaseModel):
    chat_id: Optional[str] = None
    user_id: Optional[str] = None
    message_type: Optional[str] = None
    content: str
    status: Optional[str] = None
    sent_at: Optional[str] = None

class ItemUpdate(BaseModel):
    chat_id: Optional[str] = None
    user_id: Optional[str] = None
    message_type: Optional[str] = None
    content: Optional[str] = None
    status: Optional[str] = None
    sent_at: Optional[str] = None


@app.post("/api/v1/telegram-service")
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
        query = f"INSERT INTO telegram_messages ({', '.join(cols)}) VALUES ({ph}) RETURNING *"
        row = await conn.fetchrow(query, *vals)
        return dict(row)


@app.get("/api/v1/telegram-service")
async def list_items(skip: int = 0, limit: int = 50, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM telegram_messages ORDER BY created_at DESC LIMIT $1 OFFSET $2",
            limit, skip
        )
        total = await conn.fetchval("SELECT COUNT(*) FROM telegram_messages")
        return {"total": total, "items": [dict(r) for r in rows], "skip": skip, "limit": limit}


@app.get("/api/v1/telegram-service/{item_id}")
async def get_item(item_id: str, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM telegram_messages WHERE id=$1", uuid.UUID(item_id))
        if not row:
            raise HTTPException(status_code=404, detail="Item not found")
        return dict(row)


@app.put("/api/v1/telegram-service/{item_id}")
async def update_item(item_id: str, item: ItemUpdate, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow("SELECT * FROM telegram_messages WHERE id=$1", uuid.UUID(item_id))
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
        query = f"UPDATE telegram_messages SET {', '.join(set_parts)}, updated_at=NOW() WHERE id=$1 RETURNING *"
        row = await conn.fetchrow(query, *params)
        return dict(row)


@app.delete("/api/v1/telegram-service/{item_id}")
async def delete_item(item_id: str, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM telegram_messages WHERE id=$1", uuid.UUID(item_id))
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Item not found")
        return {"deleted": True}


@app.get("/api/v1/telegram-service/stats")
async def get_stats(token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM telegram_messages")
        today = await conn.fetchval("SELECT COUNT(*) FROM telegram_messages WHERE created_at >= CURRENT_DATE")
        return {"total": total, "today": today, "service": "telegram-service"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8159)
