from typing import Any, Dict, List, Optional, Union, Tuple

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import engine, Base
from router import router
from service import ServiceException

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

# --- Setup Logging ---
logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

# --- Application Lifespan ---

@asynccontextmanager
async def lifespan(app: FastAPI) -> None:
    """
    Handles startup and shutdown events for the application.
    Creates database tables on startup.
    """
    logger.info("Application startup: Initializing database...")
    # Create database tables
    async with engine.begin() as conn:
        # Import models here to ensure they are registered with Base.metadata
        from models import Merchant, PaymentMethod, Transaction, Refund
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialization complete.")
    
    yield
    
    logger.info("Application shutdown: Cleanup complete.")

# --- FastAPI Application Initialization ---

app = FastAPI(

@app.get("/health")
async def health():
    return {"status": "ok", "service": "payment-processing"}

    title=f"{settings.SERVICE_NAME.title()} API",
    description="A production-ready FastAPI service for payment processing, handling transactions, refunds, merchants, and payment methods.",
    version="1.0.0",
    lifespan=lifespan
)

# --- Middleware ---

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=settings.CORS_METHODS,
    allow_headers=settings.CORS_HEADERS,
)

# --- Custom Exception Handlers ---

@app.exception_handler(ServiceException)
async def service_exception_handler(request: Request, exc: ServiceException) -> None:
    """Handles custom ServiceException raised from the business logic layer."""
    logger.error(f"Service Exception: {exc.message} (Status: {exc.status_code}) for request: {request.url}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> None:
    """Handles all unhandled exceptions."""
    logger.critical(f"Unhandled Exception: {exc} for request: {request.url}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected error occurred. Please try again later."},
    )

# --- Include Routers ---

app.include_router(router)

# --- Root Endpoint for Health Check ---

@app.get("/", tags=["Health Check"])
async def root() -> Dict[str, Any]:
    return {"message": f"{settings.SERVICE_NAME.title()} API is running."}

# Note: To run this application, you would typically use:
# uvicorn main:app --reload --host 0.0.0.0 --port 8000
