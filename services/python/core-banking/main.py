from typing import Any, Dict, List, Optional, Union, Tuple

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from config import settings
from database import init_db
from router import router
from service import ServiceException

# --- Production: Graceful Shutdown ---
import signal
import sys
import atexit
import logging

import psycopg2
import psycopg2.extras

def _init_persistence():
    """Initialize SQLite persistence for core-banking."""
    import os
    db_path = os.environ.get("CORE_BANKING_DB_PATH", "/tmp/core-banking.db")
    try:
        conn = psycopg2.connect(os.environ.get('DATABASE_URL', 'postgres://postgres:postgres@localhost:5432/core_banking'))
        
        
        return conn
    except Exception as e:
        import logging
        logging.warning(f"SQLite unavailable ({e}) — running in-memory only")
        return None

_persistence_db = _init_persistence()


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


# --- Configuration and Setup ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Application Lifespan ---
@asynccontextmanager
async def lifespan(app: FastAPI) -> None:
    """Handles startup and shutdown events."""
    logger.info(f"Starting up {settings.APP_NAME} v{settings.APP_VERSION}...")
    
    # Database initialization
    try:
        await init_db()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        # In a production environment, you might want to raise the exception
        # or implement a retry mechanism.

    yield
    
    # Shutdown logic (e.g., closing connections)
    logger.info(f"Shutting down {settings.APP_NAME}...")

# --- FastAPI Application Instance ---
app = FastAPI(

@app.get("/health")
async def health():
    return {"status": "ok", "service": "core-banking"}

    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="A production-ready Core Banking API built with FastAPI and SQLAlchemy.",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# --- Middleware ---

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Exception Handlers ---

@app.exception_handler(ServiceException)
async def service_exception_handler(request: Request, exc: ServiceException) -> None:
    """Handles custom business logic exceptions."""
    logger.warning(f"Service Exception: {exc.status_code} - {exc.message}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> None:
    """Handles Pydantic validation errors."""
    logger.error(f"Validation Error: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()},
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> None:
    """Handles all other unhandled exceptions."""
    logger.exception(f"Unhandled Exception: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected error occurred."},
    )

# --- Include Routers ---
app.include_router(router, prefix="/api/v1")

# --- Root Endpoint ---
@app.get("/", tags=["Health Check"])
async def root() -> Dict[str, Any]:
    return {"message": f"{settings.APP_NAME} is running", "version": settings.APP_VERSION}

# --- Example of running the app (for local development) ---
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)