from typing import Any, Dict, List, Optional, Union, Tuple

import logging
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError

from config import settings
from database import Base, engine
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


# --- Configuration ---

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Database Initialization ---

def create_db_tables() -> None:
    """Creates all database tables defined in models.py."""
    Base.metadata.create_all(bind=engine)

# --- Application Setup ---

app = FastAPI(
    title=settings.APP_NAME,
    description="API for CIPS (Cross-border Interbank Payment System) Integration.",
    version="1.0.0",
    debug=settings.DEBUG,
)

# --- Middleware ---

# CORS Middleware
origins = ["*"] # In a real application, this should be restricted
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Exception Handlers ---

@app.exception_handler(ServiceException)
async def service_exception_handler(request: Request, exc: ServiceException) -> None:
    """Handles custom service exceptions."""
    logger.error(f"Service Exception: {exc.message} (Status: {exc.status_code})")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
    )

@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError) -> None:
    """Handles general SQLAlchemy errors."""
    logger.error(f"SQLAlchemy Error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "A database error occurred."},
    )

# --- Startup Event ---

@app.on_event("startup")
async def startup_event() -> None:
    """Run on application startup."""
    logger.info(f"Starting up {settings.APP_NAME}...")
    create_db_tables()
    logger.info("Database tables created/checked.")

# --- Root Endpoint ---

@app.get("/", tags=["Health Check"])
def read_root() -> Dict[str, Any]:
    return {"message": f"Welcome to the {settings.APP_NAME} API"}

# --- Include Routers ---

app.include_router(router)

# --- Security (Placeholder) ---
# In a production environment, you would add security dependencies here,
# e.g., for token authentication in the router or as a global dependency.
# For simplicity, this implementation omits full authentication/authorization.
