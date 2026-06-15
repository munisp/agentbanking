"""
Audit Logging Service
Port: 8112
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
            "service.name": os.environ.get("OTEL_SERVICE_NAME", "audit-service"),
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

app = FastAPI(title="Audit Logging Service", description="Audit Logging Service for Remittance Platform", version="1.0.0")
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
            CREATE TABLE IF NOT EXISTS audit_logs (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id VARCHAR(255),
                action VARCHAR(100) NOT NULL,
                resource_type VARCHAR(100),
                resource_id VARCHAR(255),
                details JSONB DEFAULT '{}',
                ip_address VARCHAR(45),
                user_agent TEXT,
                status VARCHAR(20) DEFAULT 'success',
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_logs(user_id);
            CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_logs(action);
            CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_logs(created_at)
        """)

@app.get("/health")
async def health_check():
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {"status": "healthy", "service": "audit-service", "database": "connected"}
    except Exception as e:
        return {"status": "degraded", "service": "audit-service", "error": str(e)}

class AuditLogCreate(BaseModel):
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

class AuditLogResponse(BaseModel):
    id: str
    user_id: Optional[str]
    action: str
    resource_type: Optional[str]
    resource_id: Optional[str]
    details: Optional[Dict[str, Any]]
    ip_address: Optional[str]
    status: str
    created_at: datetime

@app.post("/api/v1/audit/logs", response_model=Dict)
async def create_audit_log(log: AuditLogCreate, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO audit_logs (user_id, action, resource_type, resource_id, details, ip_address, user_agent)
               VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING id, created_at""",
            token[:36], log.action, log.resource_type, log.resource_id,
            json.dumps(log.details or {}), log.ip_address, log.user_agent
        )
        return {"id": str(row["id"]), "created_at": row["created_at"].isoformat()}

@app.get("/api/v1/audit/logs")
async def list_audit_logs(
    user_id: Optional[str] = None, action: Optional[str] = None,
    resource_type: Optional[str] = None, skip: int = 0, limit: int = 50,
    token: str = Depends(verify_token)
):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        conditions = []
        params = []
        idx = 1
        if user_id:
            conditions.append(f"user_id = ${idx}")
            params.append(user_id)
            idx += 1
        if action:
            conditions.append(f"action = ${idx}")
            params.append(action)
            idx += 1
        if resource_type:
            conditions.append(f"resource_type = ${idx}")
            params.append(resource_type)
            idx += 1
        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        params.extend([limit, skip])
        rows = await conn.fetch(
            f"SELECT * FROM audit_logs {where} ORDER BY created_at DESC LIMIT ${idx} OFFSET ${idx+1}",
            *params
        )
        total = await conn.fetchval(f"SELECT COUNT(*) FROM audit_logs {where}", *params[:-2]) if params[:-2] else await conn.fetchval("SELECT COUNT(*) FROM audit_logs")
        return {"total": total, "logs": [dict(r) for r in rows], "skip": skip, "limit": limit}

@app.get("/api/v1/audit/logs/{log_id}")
async def get_audit_log(log_id: str, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM audit_logs WHERE id = $1", uuid.UUID(log_id))
        if not row:
            raise HTTPException(status_code=404, detail="Audit log not found")
        return dict(row)

@app.get("/api/v1/audit/stats")
async def get_audit_stats(token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM audit_logs")
        today = await conn.fetchval("SELECT COUNT(*) FROM audit_logs WHERE created_at >= CURRENT_DATE")
        by_action = await conn.fetch("SELECT action, COUNT(*) as cnt FROM audit_logs GROUP BY action ORDER BY cnt DESC LIMIT 10")
        return {"total_logs": total, "today": today, "by_action": [dict(r) for r in by_action]}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8112)
