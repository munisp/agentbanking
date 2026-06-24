import os
from typing import Any, Dict, List, Optional, Union, Tuple

import logging
from fastapi import FastAPI, Request, status
import sys as _sys2, os as _os2
_sys2.path.insert(0, _os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .database import init_db
from .router import router
from .service import ServiceException
from .schemas import APIExceptionSchema

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

# --- Logging Setup ---
logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

# --- FastAPI App Initialization ---
app = FastAPI(

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/white_label_api")
apply_middleware(app, enable_auth=True)

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

@app.get("/health")
async def health():
    return {"status": "ok", "service": "white-label-api"}

    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    description="A production-ready white-label API for identity verification (KYC/KYB).",
    docs_url="/docs",
    redoc_url="/redoc"
)

# --- Event Handlers ---
@app.on_event("startup")
async def _init_pg_pool():
    await get_pg_pool()

@app.on_event("startup")
async def startup_event() -> None:
    """Initializes the database on application startup."""
    logger.info("Application startup: Initializing database.")
    # NOTE: In a production environment, this should be replaced with a proper migration tool (e.g., Alembic)
    # and only run if the database is empty or needs initial setup.
    init_db()
    logger.info("Database initialization complete.")

# --- Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Custom Exception Handlers ---
@app.exception_handler(ServiceException)
async def service_exception_handler(request: Request, exc: ServiceException) -> None:
    """Handles custom service exceptions and returns a standardized JSON response."""
    logger.error(f"Service Exception caught: {exc.code} - {exc.detail}", exc_info=True)
    return JSONResponse(
        status_code=exc.status_code,
        content=APIExceptionSchema(detail=exc.detail, code=exc.code).model_dump(),
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> None:
    """Handles all unhandled exceptions."""
    logger.critical(f"Unhandled Exception caught: {type(exc).__name__} - {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=APIExceptionSchema(
            detail="An unexpected error occurred on the server.",
            code="INTERNAL_SERVER_ERROR"
        ).model_dump(),
    )

# --- Include Router ---
app.include_router(router)

# --- Root Endpoint ---
@app.get("/", tags=["health"])
async def root() -> Dict[str, Any]:
    # Load persisted state from PostgreSQL
    _pg_cached = await pg_get("root", "white-label-api")
    if _pg_cached is not None:
        import json as _json
        try:
            return _json.loads(_pg_cached) if isinstance(_pg_cached, str) else _pg_cached
        except Exception:
            pass

    return {"message": f"{settings.PROJECT_NAME} is running", "version": settings.PROJECT_VERSION}