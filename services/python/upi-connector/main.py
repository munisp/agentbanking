import httpx
from typing import Any, Dict, List, Optional, Union, Tuple

import logging
from fastapi import FastAPI, Request, status
import sys as _sys2, os as _os2
_sys2.path.insert(0, _os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
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
            "service.name": os.environ.get("OTEL_SERVICE_NAME", "upi-connector"),
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


import psycopg2
import psycopg2.extras
import os

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/upi_connector")
apply_middleware(app, enable_auth=True)

def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return conn

def init_db():
    conn = get_db()
    for stmt in """CREATE TABLE IF NOT EXISTS items (
            id SERIAL PRIMARY KEY,
            name TEXT, status TEXT, data TEXT, created_at TEXT
        )""".split(";"):
        stmt = stmt.strip()
        if stmt:
            conn.execute(stmt)
    conn.commit()
    conn.close()

init_db()

@app.get("/api/v1/items")
async def list_items():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, status, data, created_at FROM items ORDER BY created_at DESC LIMIT 100")
    rows = cursor.fetchall()
    conn.close()
    return {"items": [{"id": r[0], "name": r[1], "status": r[2], "data": r[3], "created_at": r[4]} for r in rows]}

@app.post("/api/v1/items")
async def create_item(request: Request):
    body = await request.json()
    name = body.get("name", "")
    if not name:
        raise HTTPException(status_code=400, detail="Name required")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO items (name, status, data, created_at) VALUES (%s, 'active', %s, NOW())",
                   (name, str(body)))
    conn.commit()
    item_id = cursor.fetchone()[0]
    conn.close()
    return {"id": item_id, "name": name, "status": "active"}

@app.get("/api/v1/items/{item_id}")
async def get_item(item_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM items WHERE id = %s", (item_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"id": row[0], "name": row[1], "status": row[2]}

@app.put("/api/v1/items/{item_id}")
async def update_item(item_id: int, request: Request):
    body = await request.json()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE items SET name = %s, status = %s, data = %s WHERE id = %s",
                   (body.get("name", ""), body.get("status", "active"), str(body), item_id))
    conn.commit()
    conn.close()
    return {"id": item_id, "status": "updated"}

@app.delete("/api/v1/items/{item_id}")
async def delete_item(item_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM items WHERE id = %s", (item_id,))
    conn.commit()
    conn.close()
    return {"id": item_id, "status": "deleted"}

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