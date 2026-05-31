from typing import Any, Dict, List, Optional, Union, Tuple

import logging
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from .config import settings
from .database import init_db
from .router import router
from .service import TransactionNotFoundError, TransactionAlreadyExistsError, InvalidTransactionStateError

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
logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

# Initialize the database (create tables)
init_db()

# Initialize FastAPI application
app = FastAPI(

@app.get("/health")
async def health():
    return {"status": "ok", "service": "papss-integration"}

    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    version="1.0.0",
    description="API service for integrating and tracking PAPSS (Pan-African Payment and Settlement System) transactions."
)

# --- Middleware ---

# CORS Middleware
# In a production environment, you should restrict origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# --- Custom Exception Handlers ---

@app.exception_handler(TransactionNotFoundError)
async def transaction_not_found_exception_handler(request: Request, exc: TransactionNotFoundError) -> None:
    logger.warning(f"Transaction Not Found: {exc.detail}")
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": exc.detail},
    )

@app.exception_handler(TransactionAlreadyExistsError)
async def transaction_already_exists_exception_handler(request: Request, exc: TransactionAlreadyExistsError) -> None:
    logger.warning(f"Transaction Conflict: {exc.detail}")
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": exc.detail},
    )

@app.exception_handler(InvalidTransactionStateError)
async def invalid_transaction_state_exception_handler(request: Request, exc: InvalidTransactionStateError) -> None:
    logger.warning(f"Invalid State Transition: {exc.detail}")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": exc.detail},
    )

# --- Root Endpoint ---

@app.get("/", tags=["Health Check"])
async def root() -> Dict[str, Any]:
    return {"message": f"{settings.PROJECT_NAME} is running", "version": app.version}

# --- Include Router ---

app.include_router(router, prefix=settings.API_V1_STR)

# Example command to run the application:
# uvicorn papss_integration.main:app --reload
