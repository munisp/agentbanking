from typing import Any, Dict, List, Optional, Union, Tuple

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status, Depends
import sys as _sys2, os as _os2
_sys2.path.insert(0, _os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy import text as db_text # Renaming to avoid conflict with `text` from fastapi.responses

from . import database, router, service, schemas
from .config import settings
from .database import get_db

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

# --- Application Lifespan ---

@asynccontextmanager
async def lifespan(app: FastAPI) -> None:
    """
    Handles startup and shutdown events.
    On startup, it initializes the database tables.
    """
    logger.info("Application startup: Initializing database...")
    try:
        database.init_db()
        logger.info("Database initialization complete.")
    except Exception as e:
        logger.error(f"Error during database initialization: {e}")
        # In a production environment, you might want to exit or retry
        
    yield
    
    logger.info("Application shutdown.")

# --- FastAPI Application Instance ---


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
            "service.name": os.environ.get("OTEL_SERVICE_NAME", "monitoring"),
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

app = FastAPI(
    title="Monitoring Service API",
    description="API for monitoring the status and performance of various services and endpoints.",
    version="1.0.0",
    lifespan=lifespan
)
apply_middleware(app, enable_auth=True)
# Instrument FastAPI with OpenTelemetry
if _otel_endpoint:
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
    except (ImportError, Exception):
        pass


# --- CORS Middleware ---

# In a real application, you would restrict origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Custom Exception Handlers ---

@app.exception_handler(service.ServiceException)
async def service_exception_handler(request: Request, exc: service.ServiceException) -> None:
    """Handles custom service exceptions (e.g., Not Found, Conflict)."""
    logger.warning(f"Service Exception: {exc.detail} - Status: {exc.status_code}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

@app.exception_handler(OperationalError)
async def sqlalchemy_operational_error_handler(request: Request, exc: OperationalError) -> None:
    """Handles database operational errors (e.g., connection issues)."""
    logger.error(f"Database Operational Error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "Database service is unavailable."},
    )

# --- Root and Health Check Routes ---

@app.get("/", include_in_schema=False)
async def root() -> Dict[str, Any]:
    return {"message": "Welcome to the Monitoring Service API. See /docs for documentation."}

@app.get("/health", response_model=schemas.HealthCheck, tags=["System"])
def health_check(db: Session = Depends(get_db)) -> None:
    """Check the health of the application and its dependencies."""
    db_status = "ok"
    try:
        # Try to execute a simple query to check database connection
        db.execute(db_text("SELECT 1"))
    except Exception as e:
        logger.error(f"Health check failed: Database connection error: {e}")
        db_status = "error"
        
    return schemas.HealthCheck(
        status="ok" if db_status == "ok" else "degraded",
        database_connection=db_status,
        service_name="monitoring"
    )

# --- Include Router ---

app.include_router(router.router)