"""
User Management
Port: 8140
"""
from fastapi import FastAPI, HTTPException, Depends, Header
import sys as _sys2, os as _os2
_sys2.path.insert(0, _os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
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

async def verify_token(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    token = authorization[7:]
    if not token or len(token) < 10:
        raise HTTPException(status_code=401, detail="Invalid token")
    return token


# ── OpenTelemetry Tracing ────────────────────────────────────────────────────
_otel_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
if _otel_endpoint:
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        _resource = Resource.create({
            "service.name": os.environ.get("OTEL_SERVICE_NAME", "user-management"),
            "service.version": os.environ.get("OTEL_SERVICE_VERSION", "1.0.0"),
            "deployment.environment": os.environ.get("ENVIRONMENT", "production"),
        })
        _provider = TracerProvider(resource=_resource)
        _exporter = OTLPSpanExporter(endpoint=f"{_otel_endpoint}/v1/traces")
        _provider.add_span_processor(BatchSpanProcessor(_exporter))
        trace.set_tracer_provider(_provider)
        logging.getLogger(__name__).info(f"[OTel] Tracing enabled → {_otel_endpoint}")
    except ImportError:
        logging.getLogger(__name__).warning("[OTel] opentelemetry packages not installed — tracing disabled")

app = FastAPI(title="User Management", description="User Management for Remittance Platform", version="1.0.0")
apply_middleware(app, enable_auth=True)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
# Instrument FastAPI with OpenTelemetry
if _otel_endpoint:
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
    except (ImportError, Exception):
        pass


@app.on_event("startup")
async def startup():
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS managed_users (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                email VARCHAR(255) NOT NULL,
                phone VARCHAR(20),
                full_name VARCHAR(255),
                country VARCHAR(3) DEFAULT 'NGA',
                status VARCHAR(20) DEFAULT 'active',
                kyc_level INT DEFAULT 0,
                role VARCHAR(30) DEFAULT 'user',
                last_login_at TIMESTAMPTZ,
                metadata JSONB DEFAULT '{}',
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
        return {"status": "healthy", "service": "user-management", "database": "connected"}
    except Exception as e:
        return {"status": "degraded", "service": "user-management", "error": str(e)}

class ItemCreate(BaseModel):
    email: str
    phone: Optional[str] = None
    full_name: Optional[str] = None
    country: Optional[str] = None
    status: Optional[str] = None
    kyc_level: Optional[int] = None
    role: Optional[str] = None
    last_login_at: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class ItemUpdate(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None
    full_name: Optional[str] = None
    country: Optional[str] = None
    status: Optional[str] = None
    kyc_level: Optional[int] = None
    role: Optional[str] = None
    last_login_at: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

@app.post("/api/v1/user-management")
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
        query = f"INSERT INTO managed_users ({', '.join(cols)}) VALUES ({ph}) RETURNING *"
        row = await conn.fetchrow(query, *vals)
        return dict(row)

@app.get("/api/v1/user-management")
async def list_items(skip: int = 0, limit: int = 50, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM managed_users ORDER BY created_at DESC LIMIT $1 OFFSET $2",
            limit, skip
        )
        total = await conn.fetchval("SELECT COUNT(*) FROM managed_users")
        return {"total": total, "items": [dict(r) for r in rows], "skip": skip, "limit": limit}

@app.get("/api/v1/user-management/{item_id}")
async def get_item(item_id: str, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM managed_users WHERE id=$1", uuid.UUID(item_id))
        if not row:
            raise HTTPException(status_code=404, detail="Item not found")
        return dict(row)

@app.put("/api/v1/user-management/{item_id}")
async def update_item(item_id: str, item: ItemUpdate, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow("SELECT * FROM managed_users WHERE id=$1", uuid.UUID(item_id))
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
        query = f"UPDATE managed_users SET {', '.join(set_parts)}, updated_at=NOW() WHERE id=$1 RETURNING *"
        row = await conn.fetchrow(query, *params)
        return dict(row)

@app.delete("/api/v1/user-management/{item_id}")
async def delete_item(item_id: str, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM managed_users WHERE id=$1", uuid.UUID(item_id))
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Item not found")
        return {"deleted": True}

@app.get("/api/v1/user-management/stats")
async def get_stats(token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM managed_users")
        today = await conn.fetchval("SELECT COUNT(*) FROM managed_users WHERE created_at >= CURRENT_DATE")
        return {"total": total, "today": today, "service": "user-management"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8140)
