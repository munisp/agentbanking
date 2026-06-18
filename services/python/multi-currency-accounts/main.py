import os
from typing import Any, Dict, List, Optional, Union, Tuple

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import logging

import database
from config import settings
from router import router
from service import ServiceError, AccountNotFound, CurrencyBalanceNotFound, CurrencyBalanceAlreadyExists

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

# Create database tables on startup
database.create_db_and_tables()

app = FastAPI(

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/multi_currency_accounts")

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
    return {"status": "ok", "service": "multi-currency-accounts"}

    title=settings.APP_NAME,
    version=settings.VERSION,
    description="API for managing multi-currency accounts and balances.",
    docs_url="/docs",
    redoc_url="/redoc"
)

# --- Middleware ---

# CORS Middleware
origins = [
    "http://localhost",
    "http://localhost:8080",
    "http://localhost:3000",
    "*" # Allow all for development, restrict in production
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Exception Handlers ---

@app.exception_handler(AccountNotFound)
async def account_not_found_exception_handler(request: Request, exc: AccountNotFound) -> None:
    logger.warning(f"Account not found: {exc}")
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": str(exc)},
    )

@app.exception_handler(CurrencyBalanceNotFound)
async def currency_balance_not_found_exception_handler(request: Request, exc: CurrencyBalanceNotFound) -> None:
    logger.warning(f"Currency balance not found: {exc}")
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": str(exc)},
    )

@app.exception_handler(CurrencyBalanceAlreadyExists)
async def currency_balance_already_exists_exception_handler(request: Request, exc: CurrencyBalanceAlreadyExists) -> None:
    logger.warning(f"Currency balance already exists: {exc}")
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )

@app.exception_handler(ServiceError)
async def service_error_exception_handler(request: Request, exc: ServiceError) -> None:
    logger.error(f"Service error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": str(exc)},
    )

# --- Router Inclusion ---

app.include_router(router, prefix="/api/v1")

# --- Root Endpoint ---

@app.get("/", tags=["Health Check"])
def read_root() -> Dict[str, Any]:
    return {"message": f"{settings.APP_NAME} v{settings.VERSION} is running."}

# Example of how to run the app (for local development)
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)