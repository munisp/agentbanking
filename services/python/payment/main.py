import os
import httpx
from typing import Any, Dict, List, Optional, Union, Tuple

import uvicorn
import logging
from fastapi import FastAPI, Request, status
import sys as _sys2, os as _os2
_sys2.path.insert(0, _os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError

from . import router, database, service, models
from .config import settings

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

# --- Application Initialization ---


# ── OpenTelemetry Tracing ────────────────────────────────────────────────────
_otel_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
if _otel_endpoint:
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        _resource = Resource.create({
            "service.name": os.environ.get("OTEL_SERVICE_NAME", "payment"),
            "service.version": os.environ.get("OTEL_SERVICE_VERSION", "1.0.0"),
            "deployment.environment": os.environ.get("ENVIRONMENT", "production"),
        })
        _provider = TracerProvider(resource=_resource)
        _exporter = OTLPSpanExporter(endpoint=f"{_otel_endpoint}/v1/traces")
        _provider.add_span_processor(BatchSpanProcessor(_exporter))
        trace.set_tracer_provider(_provider)
        logging.getLogger(__name__).info(f"[OTel] Tracing enabled → {_otel_endpoint}")
    except ImportError:
        logging.getLogger(__name__).warning("[OTel] opentelemetry packages not installed — tracing disabled")


# ── Middleware: Kafka via Dapr ─────────────────────────────────────────────────

DAPR_HTTP_PORT = os.environ.get("DAPR_HTTP_PORT", "3500")

async def publish_kafka(topic: str, data: dict):
    """Publish domain event to Kafka via Dapr sidecar."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            url = f"http://localhost:{DAPR_HTTP_PORT}/v1.0/publish/kafka-pubsub/{topic}"
            resp = await client.post(url, json=data)
            if resp.status_code < 300:
                logger.info(f"Published to {topic}")
            else:
                logger.warning(f"Dapr publish to {topic} returned {resp.status_code}")
    except Exception as e:
        logger.warning(f"Failed to publish to {topic}: {e}")

app = FastAPI(
# Instrument FastAPI with OpenTelemetry
if _otel_endpoint:
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
    except (ImportError, Exception):
        pass


@app.get("/health")
apply_middleware(app, enable_auth=True)
async def health():
    return {"status": "ok", "service": "payment"}

    title=settings.SERVICE_NAME,
    version=settings.VERSION,
    debug=settings.DEBUG,
    description="A production-ready FastAPI service for payment processing.",
)

# --- Startup/Shutdown Events ---

@app.on_event("startup")
def on_startup() -> None:
    """Initializes the database and logs startup information."""
    logger.info(f"Starting up {settings.SERVICE_NAME} v{settings.VERSION}...")
    # Create database tables if they don't exist
    models.Base.metadata.create_all(bind=database.engine)
    logger.info("Database initialization complete.")

@app.on_event("shutdown")
def on_shutdown() -> None:
    """Logs shutdown information."""
    logger.info(f"Shutting down {settings.SERVICE_NAME}...")

# --- Middleware ---

# CORS Middleware
origins = ["*"] # In production, this should be restricted
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Exception Handlers ---

@app.exception_handler(service.PaymentServiceError)
async def payment_service_exception_handler(request: Request, exc: service.PaymentServiceError) -> None:
    """Handles custom PaymentServiceError exceptions."""
    logger.warning(f"PaymentServiceError: {exc.detail} for request {request.url}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"message": exc.detail},
    )

@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError) -> None:
    """Handles general SQLAlchemy errors (e.g., integrity errors)."""
    logger.error(f"SQLAlchemy Error: {exc} for request {request.url}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"message": "A database error occurred."},
    )

# --- Routers ---

app.include_router(router.router)

# --- Root Endpoint ---

@app.get("/", tags=["Health Check"])
def read_root() -> Dict[str, Any]:
    """Health check endpoint."""
    return {"service": settings.SERVICE_NAME, "version": settings.VERSION, "status": "running"}

# --- Main Execution ---

if __name__ == "__main__":
    # This is for local development and testing
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=settings.DEBUG
    )