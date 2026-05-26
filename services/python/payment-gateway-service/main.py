"""
Payment Gateway Service - Main Application

FastAPI application for payment gateway integration with support for 13 payment gateways,
60+ currencies, and comprehensive transaction management.
"""

from fastapi import FastAPI, Request, status
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
