import httpx
"""
Interest Calculation Service - Production Implementation
"""

from fastapi import FastAPI
import sys as _sys2, os as _os2
_sys2.path.insert(0, _os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from decimal import Decimal
from datetime import datetime
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
            "service.name": os.environ.get("OTEL_SERVICE_NAME", "interest-calculation"),
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

app = FastAPI(title="Interest Calculation", version="2.0.0")
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

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/interest_calculation")

def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return conn

def init_db():
    conn = get_db()
    for stmt in """CREATE TABLE IF NOT EXISTS calculations (
            id SERIAL PRIMARY KEY,
            principal REAL, rate REAL, tenure_months INTEGER,
            model TEXT, loan_type TEXT, interest REAL, total REAL,
            monthly_payment REAL, created_at TEXT
        )""".split(";"):
        stmt = stmt.strip()
        if stmt:
            conn.execute(stmt)
    conn.commit()
    conn.close()

init_db()

# Interest calculation models
INTEREST_MODELS = {
    "simple": lambda p, r, t: p * r * t,
    "compound": lambda p, r, t: p * ((1 + r) ** t - 1),
    "reducing_balance": lambda p, r, t: sum(((p - (p / t * i)) * r) for i in range(int(t))),
    "flat_rate": lambda p, r, t: p * r * t,
}

CBN_MAX_RATES = {
    "personal_loan": 0.30,
    "mortgage": 0.18,
    "agricultural": 0.09,
    "sme": 0.15,
    "microfinance": 0.27,
}

@app.post("/api/v1/calculate")
async def calculate_interest(request: Request):
    body = await request.json()
    principal = float(body.get("principal", 0))
    rate = float(body.get("rate", 0))
    tenure_months = int(body.get("tenureMonths", 12))
    model = body.get("model", "simple")
    loan_type = body.get("loanType", "personal_loan")

    if principal <= 0 or rate <= 0:
        raise HTTPException(status_code=400, detail="Principal and rate must be positive")

    max_rate = CBN_MAX_RATES.get(loan_type, 0.30)
    if rate > max_rate:
        raise HTTPException(status_code=400, detail=f"Rate {rate} exceeds CBN max {max_rate} for {loan_type}")

    calc_fn = INTEREST_MODELS.get(model, INTEREST_MODELS["simple"])
    interest = calc_fn(principal, rate / 12, tenure_months)
    total = principal + interest
    monthly_payment = total / tenure_months if tenure_months > 0 else 0

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""INSERT INTO calculations (principal, rate, tenure_months, model, loan_type, interest, total, monthly_payment, created_at)
                      VALUES (%s, %s, %s, %s, %s, %s, ?, ?, NOW())""",
                   (principal, rate, tenure_months, model, loan_type, round(interest, 2), round(total, 2), round(monthly_payment, 2)))
    conn.commit()
    calc_id = cursor.fetchone()[0]
    conn.close()

    return {"id": calc_id, "principal": principal, "rate": rate, "tenure_months": tenure_months,
            "model": model, "loan_type": loan_type, "interest": round(interest, 2),
            "total": round(total, 2), "monthly_payment": round(monthly_payment, 2),
            "cbn_compliant": rate <= max_rate}

@app.get("/api/v1/amortization/{calc_id}")
async def get_amortization(calc_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM calculations WHERE id = %s", (calc_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Calculation not found")
    return {"id": row[0], "principal": row[1], "interest": row[6], "total": row[7]}

@app.get("/api/v1/cbn-rates")
async def get_cbn_rates():
    return {"rates": CBN_MAX_RATES, "effective_date": "2026-01-01", "regulator": "CBN"}
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class InterestCalculation(BaseModel):
    principal: Decimal
    rate: Decimal
    days: int
    interest: Decimal
    total: Decimal
    timestamp: datetime

class CalculateRequest(BaseModel):
    principal: Decimal
    rate: Decimal
    days: int

class InterestService:
    @staticmethod
    async def calculate(request: CalculateRequest) -> InterestCalculation:
        interest = (request.principal * request.rate * request.days) / (Decimal("365") * Decimal("100"))
        total = request.principal + interest
        
        result = InterestCalculation(
            principal=request.principal,
            rate=request.rate,
            days=request.days,
            interest=interest,
            total=total,
            timestamp=datetime.utcnow()
        )
        logger.info(f"Calculated interest: {interest}")
        return result

@app.post("/api/v1/calculate", response_model=InterestCalculation)
async def calculate(request: CalculateRequest):
    return await InterestService.calculate(request)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "interest-calculation", "version": "2.0.0"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8084)


@app.on_event("startup")
async def startup_event():
    """Register service with Kafka on startup."""
    await publish_kafka("interest.calculation.started", {
        "service": "interest-calculation",
        "timestamp": datetime.utcnow().isoformat() if "datetime" in dir() else "startup",
    })
