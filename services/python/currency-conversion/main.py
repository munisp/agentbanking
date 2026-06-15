import httpx
"""
Currency Conversion Service - Production Implementation
"""

from fastapi import FastAPI, HTTPException
import sys as _sys2, os as _os2
_sys2.path.insert(0, _os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict
from datetime import datetime
from decimal import Decimal
import uvicorn
import logging

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
            "service.name": os.environ.get("OTEL_SERVICE_NAME", "currency-conversion"),
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

app = FastAPI(title="Currency Conversion", version="2.0.0")
apply_middleware(app, enable_auth=True)
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

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/currency_conversion")

def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return conn

def init_db():
    conn = get_db()
    for stmt in """CREATE TABLE IF NOT EXISTS conversions (
            id SERIAL PRIMARY KEY,
            from_currency TEXT, to_currency TEXT, amount REAL,
            rate REAL, converted REAL, created_at TEXT
        )""".split(";"):
        stmt = stmt.strip()
        if stmt:
            conn.execute(stmt)
    conn.commit()
    conn.close()

init_db()

CBN_OFFICIAL_RATES = {
    "NGN_USD": 1550.0, "NGN_GBP": 1950.0, "NGN_EUR": 1680.0,
    "NGN_GHS": 120.0, "NGN_KES": 11.5, "NGN_ZAR": 83.0,
    "NGN_XOF": 2.5, "NGN_EGP": 32.0,
}

@app.post("/api/v1/convert")
async def convert_currency(request: Request):
    body = await request.json()
    from_currency = body.get("from", "NGN").upper()
    to_currency = body.get("to", "USD").upper()
    amount = float(body.get("amount", 0))
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")
    pair = f"{from_currency}_{to_currency}"
    reverse_pair = f"{to_currency}_{from_currency}"
    if pair in CBN_OFFICIAL_RATES:
        rate = CBN_OFFICIAL_RATES[pair]
        converted = amount / rate
    elif reverse_pair in CBN_OFFICIAL_RATES:
        rate = 1 / CBN_OFFICIAL_RATES[reverse_pair]
        converted = amount / rate
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported currency pair: {pair}")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""INSERT INTO conversions (from_currency, to_currency, amount, rate, converted, created_at)
                      VALUES (%s, %s, %s, ?, ?, NOW())""",
                   (from_currency, to_currency, amount, rate, round(converted, 4)))
    conn.commit()
    conn.close()
    return {"from": from_currency, "to": to_currency, "amount": amount,
            "rate": rate, "converted": round(converted, 4), "source": "CBN"}

@app.get("/api/v1/rates")
async def get_rates():
    return {"rates": CBN_OFFICIAL_RATES, "source": "CBN", "updated": "2026-06-01T00:00:00Z"}

@app.get("/api/v1/corridors")
async def get_corridors():
    return {"corridors": [{"pair": k, "rate": v} for k, v in CBN_OFFICIAL_RATES.items()]}
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class ConversionResult(BaseModel):
    from_currency: str
    to_currency: str
    amount: Decimal
    converted_amount: Decimal
    rate: Decimal
    timestamp: datetime

class ConversionRequest(BaseModel):
    from_currency: str
    to_currency: str
    amount: Decimal

rates = {
    ("USD", "NGN"): Decimal("1550.00"),
    ("GBP", "NGN"): Decimal("1970.00"),
    ("EUR", "NGN"): Decimal("1680.00"),
    ("NGN", "USD"): Decimal("0.00065"),
}

class CurrencyService:
    @staticmethod
    async def convert(request: ConversionRequest) -> ConversionResult:
        key = (request.from_currency, request.to_currency)
        if key not in rates:
            raise HTTPException(status_code=400, detail="Currency pair not supported")
        
        rate = rates[key]
        converted = request.amount * rate
        
        return ConversionResult(
            from_currency=request.from_currency,
            to_currency=request.to_currency,
            amount=request.amount,
            converted_amount=converted,
            rate=rate,
            timestamp=datetime.utcnow()
        )

@app.post("/api/v1/convert", response_model=ConversionResult)
async def convert(request: ConversionRequest):
    return await CurrencyService.convert(request)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "currency-conversion", "version": "2.0.0"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8079)


@app.on_event("startup")
async def startup_event():
    """Register service with Kafka on startup."""
    await publish_kafka("currency.conversion.started", {
        "service": "currency-conversion",
        "timestamp": datetime.utcnow().isoformat() if "datetime" in dir() else "startup",
    })
