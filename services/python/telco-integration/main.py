"""
Telco Integration Service
Airtime and data purchase integration with real VTU provider APIs

Features:
- MTN, Airtel, Glo, 9mobile support
- Airtime VTU (Value Transfer Unit)
- Data bundle purchase
- Transaction verification and requery
- Commission allocation per transaction
- Retry with exponential backoff
"""

from fastapi import FastAPI, HTTPException, Query
import sys as _sys2, os as _os2
_sys2.path.insert(0, _os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum
import asyncpg
import httpx
import os
import logging
import uuid
import asyncio
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

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is required")

VTPASS_API_URL = os.getenv("VTPASS_API_URL", "https://vtpass.com/api")
VTPASS_API_KEY = os.getenv("VTPASS_API_KEY", "")
VTPASS_SECRET_KEY = os.getenv("VTPASS_SECRET_KEY", "")
COMMISSION_SERVICE_URL = os.getenv("COMMISSION_SERVICE_URL", "http://localhost:8010")

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")

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
            "service.name": os.environ.get("OTEL_SERVICE_NAME", "telco-integration"),
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

app = FastAPI(title="Telco Integration Service", version="2.0.0")
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

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/telco_integration")

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
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in ALLOWED_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db_pool = None

class TelcoProvider(str, Enum):
    MTN = "mtn"
    AIRTEL = "airtel"
    GLO = "glo"
    MOBILE_9 = "9mobile"

class ProductType(str, Enum):
    AIRTIME = "airtime"
    DATA = "data"

PROVIDER_SERVICE_IDS = {
    TelcoProvider.MTN: {"airtime": "mtn", "data": "mtn-data"},
    TelcoProvider.AIRTEL: {"airtime": "airtel", "data": "airtel-data"},
    TelcoProvider.GLO: {"airtime": "glo", "data": "glo-data"},
    TelcoProvider.MOBILE_9: {"airtime": "etisalat", "data": "etisalat-data"},
}

COMMISSION_RATES = {
    ProductType.AIRTIME: Decimal("0.03"),
    ProductType.DATA: Decimal("0.04"),
}

class TelcoPurchase(BaseModel):
    phone_number: str = Field(..., min_length=11, max_length=14)
    provider: TelcoProvider
    product_type: ProductType
    amount: Decimal = Field(..., gt=0)
    data_code: Optional[str] = None
    agent_id: Optional[str] = None
    request_id: Optional[str] = None

class TelcoResponse(BaseModel):
    transaction_id: str
    status: str
    provider: str
    product_type: str
    amount: str
    phone_number: str
    commission: Optional[str] = None
    provider_reference: Optional[str] = None
    created_at: datetime

class DataPlan(BaseModel):
    code: str
    name: str
    amount: Decimal
    validity: str

@app.on_event("startup")
async def startup():
    global db_pool
    db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=5, max_size=20)
    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS telco_transactions (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                request_id VARCHAR(50) UNIQUE,
                phone_number VARCHAR(15) NOT NULL,
                provider VARCHAR(20) NOT NULL,
                product_type VARCHAR(20) NOT NULL,
                amount DECIMAL(10,2) NOT NULL,
                commission DECIMAL(10,2) DEFAULT 0,
                agent_id VARCHAR(50),
                status VARCHAR(20) DEFAULT 'pending',
                provider_reference VARCHAR(100),
                error_message TEXT,
                retry_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
        """)
    logger.info("Telco Integration Service started")

@app.on_event("shutdown")
async def shutdown():
    if db_pool:
        await db_pool.close()

async def _call_vtpass_api(endpoint: str, payload: dict, max_retries: int = 3) -> dict:
    headers = {
        "api-key": VTPASS_API_KEY,
        "secret-key": VTPASS_SECRET_KEY,
        "Content-Type": "application/json",
    }
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{VTPASS_API_URL}/{endpoint}",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()
                if data.get("code") == "000" or data.get("response_description") == "TRANSACTION SUCCESSFUL":
                    return data
                if data.get("code") in ("016", "099"):
                    logger.warning(f"VTPass retryable error attempt {attempt + 1}: {data}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)
                        continue
                return data
        except httpx.HTTPStatusError as e:
            logger.error(f"VTPass HTTP error attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
                continue
            raise
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            logger.error(f"VTPass connection error attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
                continue
            raise
    raise HTTPException(status_code=502, detail="VTPass API unavailable after retries")

@app.post("/purchase", response_model=TelcoResponse)
async def purchase(purchase: TelcoPurchase):
    request_id = purchase.request_id or str(uuid.uuid4())

    async with db_pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT * FROM telco_transactions WHERE request_id = $1", request_id
        )
        if existing:
            return TelcoResponse(
                transaction_id=str(existing["id"]),
                status=existing["status"],
                provider=existing["provider"],
                product_type=existing["product_type"],
                amount=str(existing["amount"]),
                phone_number=existing["phone_number"],
                commission=str(existing["commission"]) if existing["commission"] else None,
                provider_reference=existing["provider_reference"],
                created_at=existing["created_at"],
            )

        row = await conn.fetchrow(
            """
            INSERT INTO telco_transactions
                (request_id, phone_number, provider, product_type, amount, agent_id, status)
            VALUES ($1, $2, $3, $4, $5, $6, 'processing') RETURNING *
            """,
            request_id, purchase.phone_number, purchase.provider.value,
            purchase.product_type.value, purchase.amount, purchase.agent_id,
        )
        tx_id = row["id"]

        service_id = PROVIDER_SERVICE_IDS[purchase.provider][purchase.product_type.value]
        payload = {
            "request_id": request_id,
            "serviceID": service_id,
            "phone": purchase.phone_number,
            "amount": int(purchase.amount),
        }
        if purchase.product_type == ProductType.DATA and purchase.data_code:
            payload["billersCode"] = purchase.phone_number
            payload["variation_code"] = purchase.data_code

        try:
            result = await _call_vtpass_api("pay", payload)

            provider_ref = None
            status = "failed"
            error_msg = None

            if result.get("code") == "000" or result.get("response_description") == "TRANSACTION SUCCESSFUL":
                status = "successful"
                content = result.get("content", {})
                txn = content.get("transactions", {})
                provider_ref = txn.get("transactionId") or result.get("requestId")
            else:
                error_msg = result.get("response_description", "Unknown error from provider")

            commission = Decimal("0")
            if status == "successful" and purchase.agent_id:
                rate = COMMISSION_RATES.get(purchase.product_type, Decimal("0.03"))
                commission = (purchase.amount * rate).quantize(Decimal("0.01"))

            await conn.execute(
                """
                UPDATE telco_transactions
                SET status = $1, provider_reference = $2, error_message = $3,
                    commission = $4, updated_at = NOW()
                WHERE id = $5
                """,
                status, provider_ref, error_msg, commission, tx_id,
            )

            if status == "successful" and purchase.agent_id and commission > 0:
                try:
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        await client.post(
                            f"{COMMISSION_SERVICE_URL}/api/v1/commissions",
                            json={
                                "agent_id": purchase.agent_id,
                                "transaction_id": str(tx_id),
                                "transaction_type": f"telco_{purchase.product_type.value}",
                                "amount": float(purchase.amount),
                                "commission_amount": float(commission),
                            },
                        )
                except Exception as ce:
                    logger.error(f"Failed to record commission: {ce}")

            return TelcoResponse(
                transaction_id=str(tx_id), status=status,
                provider=purchase.provider.value, product_type=purchase.product_type.value,
                amount=str(purchase.amount), phone_number=purchase.phone_number,
                commission=str(commission) if commission > 0 else None,
                provider_reference=provider_ref, created_at=row["created_at"],
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Purchase failed: {e}")
            await conn.execute(
                "UPDATE telco_transactions SET status = 'failed', error_message = $1, updated_at = NOW() WHERE id = $2",
                str(e), tx_id,
            )
            raise HTTPException(status_code=502, detail=f"Provider error: {str(e)}")

@app.get("/verify/{transaction_id}")
async def verify_transaction(transaction_id: str):
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM telco_transactions WHERE id::text = $1 OR request_id = $1", transaction_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Transaction not found")
        if row["provider_reference"]:
            try:
                result = await _call_vtpass_api("requery", {"request_id": row["request_id"]})
                provider_status = result.get("content", {}).get("transactions", {}).get("status")
                if provider_status and provider_status != row["status"]:
                    await conn.execute(
                        "UPDATE telco_transactions SET status = $1, updated_at = NOW() WHERE id = $2",
                        provider_status, row["id"],
                    )
                    row = await conn.fetchrow("SELECT * FROM telco_transactions WHERE id = $1", row["id"])
            except Exception as e:
                logger.warning(f"Requery failed: {e}")
        return TelcoResponse(
            transaction_id=str(row["id"]), status=row["status"],
            provider=row["provider"], product_type=row["product_type"],
            amount=str(row["amount"]), phone_number=row["phone_number"],
            commission=str(row["commission"]) if row["commission"] else None,
            provider_reference=row["provider_reference"], created_at=row["created_at"],
        )

@app.get("/data-plans/{provider}", response_model=List[DataPlan])
async def get_data_plans(provider: TelcoProvider):
    service_id = PROVIDER_SERVICE_IDS[provider]["data"]
    try:
        result = await _call_vtpass_api("service-variations", {"serviceID": service_id})
        variations = result.get("content", {}).get("varations", [])
        return [
            DataPlan(
                code=v.get("variation_code", ""),
                name=v.get("name", ""),
                amount=Decimal(str(v.get("variation_amount", 0))),
                validity=v.get("fixedPrice", "N/A"),
            )
            for v in variations
        ]
    except Exception as e:
        logger.error(f"Failed to fetch data plans: {e}")
        raise HTTPException(status_code=502, detail="Failed to fetch data plans from provider")

@app.get("/transactions")
async def list_transactions(
    agent_id: Optional[str] = None,
    status: Optional[str] = None,
    provider: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
):
    async with db_pool.acquire() as conn:
        query = "SELECT * FROM telco_transactions WHERE 1=1"
        params: list = []
        idx = 1
        if agent_id:
            query += f" AND agent_id = ${idx}"
            params.append(agent_id)
            idx += 1
        if status:
            query += f" AND status = ${idx}"
            params.append(status)
            idx += 1
        if provider:
            query += f" AND provider = ${idx}"
            params.append(provider)
            idx += 1
        query += f" ORDER BY created_at DESC LIMIT ${idx} OFFSET ${idx + 1}"
        params.extend([limit, offset])
        rows = await conn.fetch(query, *params)
        return [
            {
                "transaction_id": str(r["id"]),
                "request_id": r["request_id"],
                "phone_number": r["phone_number"],
                "provider": r["provider"],
                "product_type": r["product_type"],
                "amount": str(r["amount"]),
                "commission": str(r["commission"]) if r["commission"] else None,
                "status": r["status"],
                "provider_reference": r["provider_reference"],
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ]

@app.get("/health")
async def health_check():
    healthy = True
    details = {"service": "telco-integration", "database": "unknown", "vtpass": "unknown"}
    try:
        async with db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        details["database"] = "connected"
    except Exception:
        details["database"] = "disconnected"
        healthy = False
    details["vtpass"] = "configured" if VTPASS_API_KEY else "not_configured"
    details["status"] = "healthy" if healthy else "degraded"
    return details

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8105)
