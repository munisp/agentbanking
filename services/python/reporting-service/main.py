"""
Reporting Service
Port: 8000
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
            "service.name": os.environ.get("OTEL_SERVICE_NAME", "reporting-service"),
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

app = FastAPI(title="Reporting Service", description="Reporting Service for Remittance Platform", version="1.0.0")
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
            CREATE TABLE IF NOT EXISTS reports (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                report_type VARCHAR(50) NOT NULL,
                title VARCHAR(255) NOT NULL,
                parameters JSONB DEFAULT '{}',
                status VARCHAR(20) DEFAULT 'pending',
                result JSONB,
                generated_by VARCHAR(255),
                file_url TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                completed_at TIMESTAMPTZ
            );
            CREATE INDEX IF NOT EXISTS idx_report_type ON reports(report_type);
            CREATE INDEX IF NOT EXISTS idx_report_status ON reports(status)
        """)

@app.get("/health")
async def health_check():
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {"status": "healthy", "service": "reporting-service", "database": "connected"}
    except Exception as e:
        return {"status": "degraded", "service": "reporting-service", "error": str(e)}

class ReportRequest(BaseModel):
    report_type: str
    title: str
    parameters: Optional[Dict[str, Any]] = None

@app.post("/api/v1/reports/generate")
async def generate_report(req: ReportRequest, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO reports (report_type, title, parameters, generated_by, status)
               VALUES ($1, $2, $3, $4, 'processing') RETURNING *""",
            req.report_type, req.title, json.dumps(req.parameters or {}), token[:36]
        )
        report_id = row["id"]
        result = {"summary": f"Report {req.report_type} generated", "parameters": req.parameters, "generated_at": datetime.utcnow().isoformat()}
        await conn.execute(
            "UPDATE reports SET status='completed', result=$1, completed_at=NOW() WHERE id=$2",
            json.dumps(result), report_id
        )
        return {"report_id": str(report_id), "status": "completed", "result": result}

@app.get("/api/v1/reports")
async def list_reports(report_type: Optional[str] = None, skip: int = 0, limit: int = 50, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        if report_type:
            rows = await conn.fetch("SELECT * FROM reports WHERE report_type=$1 ORDER BY created_at DESC LIMIT $2 OFFSET $3", report_type, limit, skip)
        else:
            rows = await conn.fetch("SELECT * FROM reports ORDER BY created_at DESC LIMIT $1 OFFSET $2", limit, skip)
        return {"reports": [dict(r) for r in rows]}

@app.get("/api/v1/reports/{report_id}")
async def get_report(report_id: str, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM reports WHERE id=$1", uuid.UUID(report_id))
        if not row:
            raise HTTPException(status_code=404, detail="Report not found")
        return dict(row)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
