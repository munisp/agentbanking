"""
main.py — CBN Automated Reporting Engine FastAPI application
Wires together the FastAPI app, database, and APScheduler cron jobs.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
import sys as _sys2, os as _os2
_sys2.path.insert(0, _os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from fastapi.middleware.cors import CORSMiddleware

from .router import router
from models import Base
from config import engine
import scheduler as cbn_scheduler

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

logger = logging.getLogger(__name__)

# Ensure all tables exist at startup
Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan: start scheduler on startup, stop on shutdown."""
    logger.info("[CBN] Starting CBN Reporting Engine...")
    sched = cbn_scheduler.start(async_mode=False)
    logger.info("[CBN] APScheduler started with %d jobs", len(sched.get_jobs()))
    yield
    logger.info("[CBN] Shutting down CBN Reporting Engine...")
    cbn_scheduler.stop()
    logger.info("[CBN] APScheduler stopped.")


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
            "service.name": os.environ.get("OTEL_SERVICE_NAME", "cbn-reporting-engine"),
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

app = FastAPI(
# Instrument FastAPI with OpenTelemetry
if _otel_endpoint:
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
    except (ImportError, Exception):
        pass


import psycopg2
import psycopg2.extras
import os

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/cbn_reporting_engine")
apply_middleware(app, enable_auth=True)

def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return conn

def init_db():
    conn = get_db()
    for stmt in """CREATE TABLE IF NOT EXISTS reports (
            id SERIAL PRIMARY KEY,
            report_type TEXT, period TEXT, status TEXT, generated_at TEXT
        )""".split(";"):
        stmt = stmt.strip()
        if stmt:
            conn.execute(stmt)
    conn.commit()
    conn.close()

init_db()

REPORT_TYPES = ["daily_returns", "weekly_summary", "monthly_prudential", "quarterly_cbn", "annual_compliance"]

@app.post("/api/v1/reports/generate")
async def generate_report(request: Request):
    body = await request.json()
    report_type = body.get("type", "daily_returns")
    if report_type not in REPORT_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid report type. Valid: {REPORT_TYPES}")
    period = body.get("period", "2026-06")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""INSERT INTO reports (report_type, period, status, generated_at)
                      VALUES (%s, %s, 'generated', NOW())""", (report_type, period))
    conn.commit()
    report_id = cursor.fetchone()[0]
    conn.close()
    return {"id": report_id, "type": report_type, "period": period, "status": "generated"}

@app.get("/api/v1/reports")
async def list_reports():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, report_type, period, status, generated_at FROM reports ORDER BY generated_at DESC LIMIT 50")
    rows = cursor.fetchall()
    conn.close()
    return {"reports": [{"id": r[0], "type": r[1], "period": r[2], "status": r[3], "generated_at": r[4]} for r in rows]}

@app.get("/api/v1/reports/{report_id}")
async def get_report(report_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM reports WHERE id = %s", (report_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Report not found")
    return {"id": row[0], "type": row[1], "period": row[2], "status": row[3]}
    title="CBN Automated Reporting Engine",
    version="2.0.0",
    description=(
        "Generates and submits all mandatory CBN reports: "
        "Monthly Activity, Quarterly Fraud, Annual KYC, SAR, Network Expansion."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

@app.get("/health")
def health_check():
    """Liveness probe."""
    sched = cbn_scheduler._scheduler
    return {
        "status": "ok",
        "service": "cbn-reporting-engine",
        "scheduler": {
            "running": sched.running if sched else False,
            "jobs": [
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                }
                for job in (sched.get_jobs() if sched else [])
            ],
        },
    }
