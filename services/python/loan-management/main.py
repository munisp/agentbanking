import httpx
"""
Loan Management Service
End-to-end loan lifecycle management

Features:
- Loan application processing
- Credit scoring integration
- Loan disbursement
- Repayment tracking
- Collections management
"""

from fastapi import FastAPI, HTTPException
import sys as _sys2, os as _os2
_sys2.path.insert(0, _os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta
from enum import Enum
import asyncpg
import os
import logging
from decimal import Decimal

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

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/loans")

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
            "service.name": os.environ.get("OTEL_SERVICE_NAME", "loan-management"),
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

app = FastAPI(title="Loan Management Service", version="1.0.0")
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

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/loan_management")

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
db_pool = None

class LoanStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DISBURSED = "disbursed"
    REPAYING = "repaying"
    COMPLETED = "completed"
    DEFAULTED = "defaulted"

class LoanApplication(BaseModel):
    user_id: str
    amount: Decimal
    tenure_months: int
    purpose: str
    monthly_income: Decimal

class LoanResponse(BaseModel):
    id: str
    user_id: str
    amount: Decimal
    interest_rate: Decimal
    tenure_months: int
    monthly_payment: Decimal
    status: LoanStatus
    created_at: datetime

@app.on_event("startup")
async def startup():
    global db_pool
    db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=5, max_size=20)
    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS loans (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id VARCHAR(100) NOT NULL,
                amount DECIMAL(15,2) NOT NULL,
                interest_rate DECIMAL(5,2) NOT NULL,
                tenure_months INT NOT NULL,
                monthly_payment DECIMAL(15,2) NOT NULL,
                status VARCHAR(20) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT NOW(),
                disbursed_at TIMESTAMP,
                purpose TEXT
            );
        """)
    logger.info("Loan Management Service started")

@app.on_event("shutdown")
async def shutdown():
    if db_pool:
        await db_pool.close()

def calculate_monthly_payment(principal: Decimal, rate: Decimal, months: int) -> Decimal:
    """Calculate monthly loan payment"""
    monthly_rate = rate / Decimal(12) / Decimal(100)
    payment = principal * (monthly_rate * (1 + monthly_rate) ** months) / ((1 + monthly_rate) ** months - 1)
    return payment.quantize(Decimal('0.01'))

@app.post("/applications", response_model=LoanResponse)
async def apply_for_loan(application: LoanApplication):
    """Submit loan application"""
    
    # Simple credit scoring
    if application.monthly_income < application.amount / Decimal(6):
        raise HTTPException(status_code=400, detail="Insufficient income for loan amount")
    
    # Calculate interest rate based on tenure
    interest_rate = Decimal(15) if application.tenure_months <= 6 else Decimal(18)
    monthly_payment = calculate_monthly_payment(application.amount, interest_rate, application.tenure_months)
    
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO loans (user_id, amount, interest_rate, tenure_months, monthly_payment, purpose, status)
            VALUES ($1, $2, $3, $4, $5, $6, 'approved') RETURNING *
        """, application.user_id, application.amount, interest_rate, application.tenure_months,
            monthly_payment, application.purpose)
        
        return LoanResponse(**dict(row))

@app.get("/loans/{loan_id}", response_model=LoanResponse)
async def get_loan(loan_id: str):
    """Get loan details"""
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM loans WHERE id = $1", loan_id)
        if not row:
            raise HTTPException(status_code=404, detail="Loan not found")
        return LoanResponse(**dict(row))

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "loan-management"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8106)
