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

# --- PostgreSQL Persistence ---
import asyncpg
from typing import Optional

_pg_pool: Optional[asyncpg.Pool] = None

async def get_pg_pool() -> Optional[asyncpg.Pool]:
    global _pg_pool
    if _pg_pool is None:
        try:
            _pg_pool = await asyncpg.create_pool(
                dsn=os.environ.get("DATABASE_URL", "postgresql://localhost:5432/agentbanking"),
                min_size=2, max_size=10, command_timeout=10
            )
            await _pg_pool.execute("""
                CREATE TABLE IF NOT EXISTS service_state (
                    key TEXT PRIMARY KEY,
                    value JSONB NOT NULL DEFAULT '{}',
                    service TEXT NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
        except Exception:
            _pg_pool = None
    return _pg_pool

async def pg_get(key: str, service: str):
    pool = await get_pg_pool()
    if pool:
        row = await pool.fetchrow(
            "SELECT value FROM service_state WHERE key = $1 AND service = $2", key, service
        )
        return row["value"] if row else None
    return None

async def pg_set(key: str, value, service: str):
    pool = await get_pg_pool()
    if pool:
        import json
        await pool.execute(
            "INSERT INTO service_state (key, value, service, updated_at) VALUES ($1, $2::jsonb, $3, NOW()) "
            "ON CONFLICT (key) DO UPDATE SET value = $2::jsonb, updated_at = NOW()",
            key, json.dumps(value) if not isinstance(value, str) else value, service
        )
# --- End PostgreSQL Persistence ---


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

app = FastAPI(

import psycopg2
import psycopg2.extras
import os

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/cbn_reporting_engine")

@app.on_event("startup")
async def _init_pg_pool():
    await get_pg_pool()

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
