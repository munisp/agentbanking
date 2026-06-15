import httpx
"""
Compliance Reporting Service
Automated regulatory compliance reporting for Remittance Platform

Features:
- CBN (Central Bank of Nigeria) reporting
- EFCC (Economic and Financial Crimes Commission) reporting
- NDIC (Nigeria Deposit Insurance Corporation) reporting
- FIRS (Federal Inland Revenue Service) reporting
- Automated report generation and submission
"""

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
import sys as _sys2, os as _os2
_sys2.path.insert(0, _os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from fastapi.security import HTTPBearer
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from enum import Enum
import asyncpg
import json
import os
import logging
from decimal import Decimal

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

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/compliance")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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
            "service.name": os.environ.get("OTEL_SERVICE_NAME", "compliance-reporting"),
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


# ── Middleware: Kafka via Dapr ─────────────────────────────────────────────────

DAPR_HTTP_PORT = os.environ.get("DAPR_HTTP_PORT", "3500")

async def publish_kafka(topic: str, data: dict):
    """Publish domain event to Kafka via Dapr sidecar."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            url = f"http://localhost:{DAPR_HTTP_PORT}/v1.0/publish/kafka-pubsub/{topic}"
            resp = await client.post(url, json=data)
            if resp.status_code < 300:
                logger.info(f"Published to {topic}")
            else:
                logger.warning(f"Dapr publish to {topic} returned {resp.status_code}")
    except Exception as e:
        logger.warning(f"Failed to publish to {topic}: {e}")

app = FastAPI(title="Compliance Reporting Service", version="1.0.0")
apply_middleware(app, enable_auth=True)
# Instrument FastAPI with OpenTelemetry
if _otel_endpoint:
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
    except (ImportError, Exception):
        pass


import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/compliance_reporting")

def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return conn

def init_db():
    conn = get_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS audit_log (
        id SERIAL PRIMARY KEY,
        action TEXT, entity_id TEXT, data TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS state_store (
        key TEXT PRIMARY KEY, value TEXT,
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )""")
    conn.commit()
    conn.close()

init_db()

def log_audit(action: str, entity_id: str, data: str = ""):
    try:
        conn = get_db()
        conn.execute("INSERT INTO audit_log (action, entity_id, data) VALUES (%s, %s, %s)", (action, entity_id, data))
        conn.commit()
        conn.close()
    except Exception:
        pass
security = HTTPBearer()
db_pool = None

class ReportType(str, Enum):
    CBN_DAILY = "cbn_daily"
    CBN_MONTHLY = "cbn_monthly"
    EFCC_SUSPICIOUS = "efcc_suspicious"
    NDIC_QUARTERLY = "ndic_quarterly"
    FIRS_TAX = "firs_tax"

class ReportStatus(str, Enum):
    PENDING = "pending"
    GENERATING = "generating"
    GENERATED = "generated"
    SUBMITTED = "submitted"
    FAILED = "failed"

class ComplianceReport(BaseModel):
    id: str
    report_type: ReportType
    period_start: datetime
    period_end: datetime
    status: ReportStatus
    created_at: datetime
    submitted_at: Optional[datetime]
    file_path: Optional[str]
    metadata: Dict[str, Any] = Field(default_factory=dict)

@app.on_event("startup")
async def startup():
    global db_pool
    db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=5, max_size=20)
    
    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS compliance_reports (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                report_type VARCHAR(50) NOT NULL,
                period_start TIMESTAMP NOT NULL,
                period_end TIMESTAMP NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                submitted_at TIMESTAMP,
                file_path TEXT,
                metadata JSONB DEFAULT '{}',
                error_message TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_compliance_type ON compliance_reports(report_type);
            CREATE INDEX IF NOT EXISTS idx_compliance_status ON compliance_reports(status);
        """)
    logger.info("Compliance Reporting Service started")

@app.on_event("shutdown")
async def shutdown():
    if db_pool:
        await db_pool.close()

async def generate_cbn_report(period_start: datetime, period_end: datetime) -> Dict[str, Any]:
    """Generate CBN compliance report"""
    async with db_pool.acquire() as conn:
        total_transactions = await conn.fetchval("""
            SELECT COUNT(*) FROM transactions 
            WHERE created_at BETWEEN $1 AND $2
        """, period_start, period_end) or 0
        
        total_volume = await conn.fetchval("""
            SELECT COALESCE(SUM(amount), 0) FROM transactions 
            WHERE created_at BETWEEN $1 AND $2
        """, period_start, period_end) or Decimal(0)
        
        return {
            "report_type": "CBN Daily Report",
            "period": f"{period_start.date()} to {period_end.date()}",
            "total_transactions": total_transactions,
            "total_volume": float(total_volume),
            "currency": "NGN"
        }

@app.post("/reports/generate", response_model=ComplianceReport)
async def generate_report(
    report_type: ReportType,
    period_start: datetime,
    period_end: datetime,
    background_tasks: BackgroundTasks
):
    """Generate a compliance report"""
    
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO compliance_reports (report_type, period_start, period_end, status)
            VALUES ($1, $2, $3, 'generating')
            RETURNING *
        """, report_type.value, period_start, period_end)
        
        report_id = str(row['id'])
        
        # Generate report in background
        if report_type in [ReportType.CBN_DAILY, ReportType.CBN_MONTHLY]:
            report_data = await generate_cbn_report(period_start, period_end)
            
            # Update report with generated data
            await conn.execute("""
                UPDATE compliance_reports 
                SET status = 'generated', metadata = $1
                WHERE id = $2
            """, json.dumps(report_data), report_id)
        
        return ComplianceReport(**dict(row))

@app.get("/reports", response_model=List[ComplianceReport])
async def list_reports(
    report_type: Optional[ReportType] = None,
    status: Optional[ReportStatus] = None,
    limit: int = 50
):
    """List compliance reports"""
    query = "SELECT * FROM compliance_reports WHERE 1=1"
    params = []
    
    if report_type:
        query += f" AND report_type = ${len(params) + 1}"
        params.append(report_type.value)
    
    if status:
        query += f" AND status = ${len(params) + 1}"
        params.append(status.value)
    
    query += f" ORDER BY created_at DESC LIMIT ${len(params) + 1}"
    params.append(limit)
    
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
        return [ComplianceReport(**dict(row)) for row in rows]

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "compliance-reporting"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8103)
