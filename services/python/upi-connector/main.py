from typing import Any, Dict, List, Optional, Union, Tuple

import logging
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database import init_db
from router import router
from service import UPIServiceException

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


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- FastAPI Application Initialization ---
app = FastAPI(

@app.get("/health")
async def health():
    return {"status": "ok", "service": "upi-connector"}

    title=settings.APP_NAME,
    description="A robust and production-ready FastAPI service for connecting to the UPI payment network.",
    version="1.0.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# --- Startup Event Handler ---
@app.on_event("startup")
def on_startup() -> None:
    """Initializes the database when the application starts."""
    logger.info("Application startup: Initializing database...")
    init_db()
    logger.info("Database initialized successfully.")

# --- Middleware ---

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In a real app, this should be restricted
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Custom Exception Handlers ---

@app.exception_handler(UPIServiceException)
async def upi_service_exception_handler(request: Request, exc: UPIServiceException) -> None:
    """Handles custom service exceptions and returns a structured JSON response."""
    logger.error(f"Service Exception: {exc.detail} (Status: {exc.status_code})")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

# --- Include Routers ---
app.include_router(router)

# --- Root Endpoint ---
@app.get("/", tags=["Health Check"])
def read_root() -> Dict[str, Any]:
    return {"message": f"{settings.APP_NAME} is running successfully!"}

# Example of how to run the app (for development/testing)
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)