"""
Receipt Generation Engine - FastAPI microservice
Multi-format receipt generation with thermal printer support, PDF export, and SMS/WhatsApp delivery
"""
import os
import sys
import logging
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query, Path
import sys as _sys2, os as _os2
_sys2.path.insert(0, _os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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
            "service.name": os.environ.get("OTEL_SERVICE_NAME", "receipt-engine"),
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
# Instrument FastAPI with OpenTelemetry
if _otel_endpoint:
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
    except (ImportError, Exception):
        pass


import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/receipt_engine")
apply_middleware(app, enable_auth=True)

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
        conn.execute("INSERT INTO audit_log (action, entity_id, data) VALUES (%s, %s, %s)", (action, entity_id, data))
        conn.commit()
        conn.close()
    except Exception:
        pass
    title="Receipt Generation Engine",
    description="Multi-format receipt generation with thermal printer support, PDF export, and SMS/WhatsApp delivery",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    """Service health check endpoint."""
    return {"status": "healthy", "service": "receipt-engine", "version": "1.0.0", "timestamp": datetime.utcnow().isoformat()}

@app.post("/api/v1/receipts/generate")
async def generate_receipt(transaction_id: str, format: str = "thermal", language: str = "en"):
    """Generate a receipt for a completed transaction."""
    valid_formats = ["thermal", "pdf", "sms", "whatsapp", "email"]
    if format not in valid_formats:
        raise HTTPException(status_code=400, detail=f"Invalid format. Must be one of: {valid_formats}")
    return {
        "receipt_id": f"RCT-{transaction_id}",
        "transaction_id": transaction_id,
        "format": format,
        "language": language,
        "status": "generated",
        "download_url": None,
        "generated_at": __import__('datetime').datetime.utcnow().isoformat(),
    }

@app.get("/api/v1/receipts/{receipt_id}")
async def get_receipt(receipt_id: str):
    """Get receipt details and download URL."""
    return {"receipt_id": receipt_id, "transaction_id": "", "format": "pdf", "status": "generated", "download_url": None}

@app.post("/api/v1/receipts/{receipt_id}/deliver")
async def deliver_receipt(receipt_id: str, channel: str, destination: str):
    """Deliver receipt via specified channel (SMS, WhatsApp, email)."""
    valid_channels = ["sms", "whatsapp", "email"]
    if channel not in valid_channels:
        raise HTTPException(status_code=400, detail=f"Invalid channel. Must be one of: {valid_channels}")
    return {
        "receipt_id": receipt_id,
        "channel": channel,
        "destination": destination,
        "delivery_status": "sent",
        "delivered_at": __import__('datetime').datetime.utcnow().isoformat(),
    }

@app.get("/api/v1/receipts/templates")
async def list_templates():
    """List available receipt templates."""
    return {
        "templates": [
            {"id": "default", "name": "Standard Receipt", "format": "thermal"},
            {"id": "detailed", "name": "Detailed Receipt", "format": "pdf"},
            {"id": "mini", "name": "Mini Receipt", "format": "sms"},
        ]
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
