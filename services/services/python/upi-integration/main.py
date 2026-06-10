import os
from typing import Any, Dict, List, Optional, Union, Tuple

import logging
from datetime import datetime

from fastapi import FastAPI, Request, status
import sys as _sys2, os as _os2
_sys2.path.insert(0, _os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database import init_db
from router import router
from schemas import HealthCheck
from service import NotFoundException, ConflictException, PaymentGatewayException

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

# --- Logging Setup ---
logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

# --- Application Initialization ---
app = FastAPI(

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/upi_integration")
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
    title=f"{settings.SERVICE_NAME.upper()} API",
    description="API service for managing UPI transaction integration and webhooks.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# --- Event Handlers ---

@app.on_event("startup")
async def startup_event() -> None:
    """Initializes the database on application startup."""
    logger.info(f"Starting up {settings.SERVICE_NAME} service...")
    init_db()
    logger.info("Database initialized.")

@app.on_event("shutdown")
def shutdown_event() -> None:
    """Logs shutdown event."""
    logger.info(f"Shutting down {settings.SERVICE_NAME} service...")

# --- Middleware ---

# CORS Middleware
origins = [
    "http://localhost",
    "http://localhost:8000",
    # Add other allowed origins in production
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all for simplicity, restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request Logging Middleware
@app.middleware("http")
async def log_requests(request: Request, call_next) -> None:
    """Logs incoming requests."""
    start_time = datetime.now()
    response = await call_next(request)
    process_time = (datetime.now() - start_time).total_seconds()
    logger.info(f"Request: {request.method} {request.url.path} | Status: {response.status_code} | Time: {process_time:.4f}s")
    return response

# --- Exception Handlers ---

@app.exception_handler(NotFoundException)
async def not_found_exception_handler(request: Request, exc: NotFoundException) -> None:
    """Handles custom NotFoundException."""
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"message": exc.detail},
    )

@app.exception_handler(ConflictException)
async def conflict_exception_handler(request: Request, exc: ConflictException) -> None:
    """Handles custom ConflictException."""
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"message": exc.detail},
    )

@app.exception_handler(PaymentGatewayException)
async def pg_exception_handler(request: Request, exc: PaymentGatewayException) -> None:
    """Handles custom PaymentGatewayException."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"message": exc.detail},
    )

# --- Root and Health Check Endpoints ---

@app.get("/", response_model=HealthCheck, summary="Health Check")
def health_check() -> None:
    """Returns the health status of the service."""
    return HealthCheck(timestamp=datetime.utcnow())

# --- Include Router ---
app.include_router(router)

# Example of how to run the application (for documentation purposes)
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)