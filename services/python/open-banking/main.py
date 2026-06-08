import os
from typing import Any, Dict, List, Optional, Union, Tuple

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import logging

from config import settings
from router import router
from service import NotFoundException, ConflictException, UnauthorizedException, ForbiddenException

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

log = logging.getLogger(__name__)

# --- Application Setup ---
app = FastAPI(

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/open_banking")

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
        conn.execute("INSERT INTO audit_log (action, entity_id, data) VALUES (?, ?, ?)", (action, entity_id, data))
        conn.commit()
        conn.close()
    except Exception:
        pass

@app.get("/health")
async def health():
    return {"status": "ok", "service": "open-banking"}

    title=settings.SERVICE_NAME,
    version=settings.VERSION,
    description="A production-ready Open Banking API built with FastAPI and SQLAlchemy.",
    docs_url="/docs",
    redoc_url="/redoc",
)

# --- CORS Middleware ---
# Allows all origins for development. Restrict this in production.
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Custom Exception Handlers ---

@app.exception_handler(NotFoundException)
async def not_found_exception_handler(request: Request, exc: NotFoundException) -> None:
    log.warning(f"NotFoundException: {exc.detail} for URL: {request.url}")
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"message": exc.detail},
    )

@app.exception_handler(ConflictException)
async def conflict_exception_handler(request: Request, exc: ConflictException) -> None:
    log.warning(f"ConflictException: {exc.detail} for URL: {request.url}")
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"message": exc.detail},
    )

@app.exception_handler(UnauthorizedException)
async def unauthorized_exception_handler(request: Request, exc: UnauthorizedException) -> None:
    log.warning(f"UnauthorizedException: {exc.detail} for URL: {request.url}")
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"message": exc.detail},
        headers={"WWW-Authenticate": "Bearer"},
    )

@app.exception_handler(ForbiddenException)
async def forbidden_exception_handler(request: Request, exc: ForbiddenException) -> None:
    log.warning(f"ForbiddenException: {exc.detail} for URL: {request.url}")
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"message": exc.detail},
    )

# --- Root Endpoint ---

@app.get("/", tags=["Health Check"])
async def root() -> Dict[str, Any]:
    return {"message": f"{settings.SERVICE_NAME} API is running", "version": settings.VERSION}

# --- Include Router ---
app.include_router(router)

# --- Database Initialization (Optional, for quick setup) ---
# In a real production environment, migrations (e.g., Alembic) would be used.
# This is included for a complete, runnable example.
@app.on_event("startup")
async def startup_event() -> None:
    log.info("Application startup...")
    try:
        from database import engine, Base
        async with engine.begin() as conn:
            # Create all tables if they don't exist
            # This is a development-only feature. Use Alembic for production migrations.
            await conn.run_sync(Base.metadata.create_all)
        log.info("Database tables checked/created successfully.")
    except Exception as e:
        log.error(f"Failed to connect to or initialize database: {e}")
        # In a real app, you might want to raise an exception to prevent startup

# --- Main Execution Block (for local development) ---
if __name__ == "__main__":
    import uvicorn
    log.info("Starting Uvicorn server...")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level=settings.LOG_LEVEL.lower()
    )