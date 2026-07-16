from typing import Any, Dict, List, Optional, Union, Tuple

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import settings, logger
from router import router
from database import init_db
from service import ConfigurationServiceError

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


# --- Application Initialization ---

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=settings.DESCRIPTION,
    debug=settings.DEBUG,
    openapi_url=f"{settings.API_PREFIX}/openapi.json"
)

# --- CORS Middleware ---

if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# --- Custom Exception Handlers ---

@app.exception_handler(ConfigurationServiceError)
async def configuration_service_exception_handler(request: Request, exc: ConfigurationServiceError) -> None:
    """Handles custom service exceptions and returns a clean JSON response."""
    logger.warning(f"Handled ConfigurationServiceError: {exc.detail} (Status: {exc.status_code})")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

# --- Event Handlers ---

@app.on_event("startup")
async def startup_event() -> None:
    """Application startup event handler."""
    logger.info("Application startup...")
    # NOTE: In a production environment, database migrations (e.g., Alembic) should be used.
    # init_db() # Uncomment this line for local development/testing to create tables automatically
    logger.info("Database initialization skipped (production-ready setup).")

@app.on_event("shutdown")
def shutdown_event() -> None:
    """Application shutdown event handler."""
    logger.info("Application shutdown...")

# --- Include Routers ---

app.include_router(router, prefix=settings.API_PREFIX)

# --- Root Endpoint ---

@app.get("/", tags=["status"], summary="Application Status")
def root() -> Dict[str, Any]:
    """Returns basic information about the application."""
    return {
        "project_name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "running",
        "api_docs": "/docs"
    }