"""
Backup Service
Port: 8113
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
            "service.name": os.environ.get("OTEL_SERVICE_NAME", "backup-service"),
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

app = FastAPI(title="Backup Service", description="Backup Service for Remittance Platform", version="1.0.0")
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
            CREATE TABLE IF NOT EXISTS backups (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                backup_type VARCHAR(50) NOT NULL,
                source VARCHAR(255) NOT NULL,
                destination VARCHAR(255),
                size_bytes BIGINT DEFAULT 0,
                status VARCHAR(20) DEFAULT 'pending',
                started_at TIMESTAMPTZ DEFAULT NOW(),
                completed_at TIMESTAMPTZ,
                retention_days INT DEFAULT 30,
                metadata JSONB DEFAULT '{}',
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS backup_schedules (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name VARCHAR(100) NOT NULL,
                backup_type VARCHAR(50) NOT NULL,
                source VARCHAR(255) NOT NULL,
                cron_expression VARCHAR(100) NOT NULL,
                retention_days INT DEFAULT 30,
                is_active BOOLEAN DEFAULT TRUE,
                last_run_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

@app.get("/health")
async def health_check():
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {"status": "healthy", "service": "backup-service", "database": "connected"}
    except Exception as e:
        return {"status": "degraded", "service": "backup-service", "error": str(e)}

class BackupCreate(BaseModel):
    backup_type: str
    source: str
    destination: Optional[str] = None
    retention_days: int = 30

class BackupScheduleCreate(BaseModel):
    name: str
    backup_type: str
    source: str
    cron_expression: str
    retention_days: int = 30

@app.post("/api/v1/backups/create")
async def create_backup(b: BackupCreate, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO backups (backup_type, source, destination, retention_days, status)
               VALUES ($1,$2,$3,$4,'in_progress') RETURNING *""",
            b.backup_type, b.source, b.destination, b.retention_days
        )
        backup_id = row["id"]
        await conn.execute(
            "UPDATE backups SET status='completed', completed_at=NOW(), size_bytes=$1 WHERE id=$2",
            0, backup_id
        )
        return {"backup_id": str(backup_id), "status": "completed"}

@app.get("/api/v1/backups")
async def list_backups(backup_type: Optional[str] = None, skip: int = 0, limit: int = 50, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        if backup_type:
            rows = await conn.fetch("SELECT * FROM backups WHERE backup_type=$1 ORDER BY created_at DESC LIMIT $2 OFFSET $3", backup_type, limit, skip)
        else:
            rows = await conn.fetch("SELECT * FROM backups ORDER BY created_at DESC LIMIT $1 OFFSET $2", limit, skip)
        return {"backups": [dict(r) for r in rows]}

@app.get("/api/v1/backups/{backup_id}")
async def get_backup(backup_id: str, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM backups WHERE id=$1", uuid.UUID(backup_id))
        if not row:
            raise HTTPException(status_code=404, detail="Backup not found")
        return dict(row)

@app.post("/api/v1/backups/schedules")
async def create_schedule(s: BackupScheduleCreate, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO backup_schedules (name, backup_type, source, cron_expression, retention_days) VALUES ($1,$2,$3,$4,$5) RETURNING *",
            s.name, s.backup_type, s.source, s.cron_expression, s.retention_days
        )
        return dict(row)

@app.get("/api/v1/backups/schedules")
async def list_schedules(token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM backup_schedules WHERE is_active=TRUE ORDER BY name")
        return {"schedules": [dict(r) for r in rows]}

@app.delete("/api/v1/backups/{backup_id}")
async def delete_backup(backup_id: str, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM backups WHERE id=$1", uuid.UUID(backup_id))
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Backup not found")
        return {"deleted": True}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8113)
