"""
Payment Gateway Service - Main Application

FastAPI application for payment gateway integration with support for 13 payment gateways,
60+ currencies, and comprehensive transaction management.
"""

from fastapi import FastAPI, Request, status
import sys as _sys2, os as _os2
_sys2.path.insert(0, _os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
import logging
import time
from typing import Dict, Any

from .routers import payment_router, webhook_router
from .services.base_gateway import PaymentGatewayError

# --- Production: Graceful Shutdown ---
import signal
import sys
import atexit
import logging

import psycopg2
import psycopg2.extras

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


def _init_persistence():
    """Initialize PostgreSQL persistence for payment-gateway-service."""
    import os
    try:
        conn = psycopg2.connect(os.environ.get('DATABASE_URL', 'postgres://postgres:postgres@localhost:5432/payment_gateway_service'))
        
        
        return conn
    except Exception as e:
        import logging
        logging.warning(f"Database unavailable ({e}) — running in-memory only")
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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI) -> None:
    """Application lifespan manager."""
    logger.info("Payment Gateway Service starting up...")
    # Production: Initialize gateway connections, load configurations
    yield
    logger.info("Payment Gateway Service shutting down...")
    # Production: Cleanup gateway connections

# Create FastAPI application
app = FastAPI(
    title="Nigerian Remittance Platform - Payment Gateway Service",
    description="""
    Payment Gateway Service for the Nigerian Remittance Platform.
    
    ## Features
    
    * **13 Payment Gateway Integrations**: Paystack, Flutterwave, Interswitch, Stripe, PayPal, 
      Remita, Paga, Opay, Kuda, Chipper Cash, NIBSS, GTPay, Ecobank
    * **60+ Currency Support**: Comprehensive coverage across African and international currencies
    * **Transaction Management**: Initiate, verify, refund, and track payments
    * **Webhook Handling**: Real-time payment status updates from gateways
    * **Exchange Rates**: Real-time currency conversion rates
    * **Fee Calculation**: Transparent fee calculation for all transactions
    * **Account Validation**: Validate bank accounts before transactions
    
    ## Security
    
    * JWT authentication for all endpoints
    * Webhook signature verification
    * Rate limiting and request throttling
    * Comprehensive audit logging
    
    ## Supported Transaction Types
    
    * Domestic transfers (within Nigeria)

@app.on_event("startup")
async def _init_pg_pool():
    await get_pg_pool()

apply_middleware(app, enable_auth=True)
    * International remittances (54 African countries)
    * Deposits and withdrawals
    * Refunds and reversals
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Production: Configure specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# GZip compression middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next) -> None:
    """Add processing time header to responses."""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next) -> None:
    """Log all incoming requests."""
    logger.info(f"Request: {request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"Response: {response.status_code}")
    return response

# Exception handlers
@app.exception_handler(PaymentGatewayError)
async def payment_gateway_error_handler(request: Request, exc: PaymentGatewayError) -> None:
    """Handle payment gateway errors."""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "success": False,
            "error_code": exc.error_code,
            "message": str(exc),
            "details": exc.details
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> None:
    """Handle request validation errors."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error_code": "VALIDATION_ERROR",
            "message": "Request validation failed",
            "details": exc.errors()
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> None:
    """Handle general exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error_code": "INTERNAL_ERROR",
            "message": "An unexpected error occurred"
        }
    )

# Include routers
app.include_router(payment_router.router)
app.include_router(webhook_router.router)

# Health check endpoint
@app.get("/health", tags=["health"])
async def health_check() -> Dict[str, Any]:
    """
    Health check endpoint.
    
    Returns service health status and basic information.
    """
    return {
        "status": "healthy",
        "service": "payment-gateway-service",
        "version": "1.0.0",
        "timestamp": time.time()
    }

# Root endpoint
@app.get("/", tags=["root"])
async def root() -> Dict[str, str]:
    """
    Root endpoint.
    
    Returns basic service information.
    """
    return {
        "service": "Nigerian Remittance Platform - Payment Gateway Service",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
