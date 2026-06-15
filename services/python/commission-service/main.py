import httpx
"""
Commission Service
Port: 8114
"""
from fastapi import FastAPI, HTTPException, Depends, Header
import sys as _sys2, os as _os2
_sys2.path.insert(0, _os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from enum import Enum
import uuid
import os
import json
import asyncpg
import uvicorn

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

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://remittance:remittance@localhost:5432/remittance")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

_db_pool = None

async def get_db_pool():
    global _db_pool
    if _db_pool is None:
        _db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    return _db_pool

async def verify_token(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    token = authorization[7:]
    if not token or len(token) < 10:
        raise HTTPException(status_code=401, detail="Invalid token")
    return token


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
            "service.name": os.environ.get("OTEL_SERVICE_NAME", "commission-service"),
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

app = FastAPI(title="Commission Service", description="Commission Service for Remittance Platform", version="1.0.0")
apply_middleware(app, enable_auth=True)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
# Instrument FastAPI with OpenTelemetry
if _otel_endpoint:
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
    except (ImportError, Exception):
        pass


@app.on_event("startup")
async def startup():
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS commission_rules (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                corridor VARCHAR(20) NOT NULL,
                currency_from VARCHAR(3) NOT NULL,
                currency_to VARCHAR(3) NOT NULL,
                min_amount DECIMAL(18,2) DEFAULT 0,
                max_amount DECIMAL(18,2) DEFAULT 999999999,
                fee_type VARCHAR(10) DEFAULT 'percentage',
                fee_value DECIMAL(10,4) NOT NULL,
                flat_fee DECIMAL(18,2) DEFAULT 0,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS commission_transactions (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                transaction_id VARCHAR(255) NOT NULL,
                rule_id UUID REFERENCES commission_rules(id),
                amount DECIMAL(18,2) NOT NULL,
                fee_amount DECIMAL(18,2) NOT NULL,
                currency VARCHAR(3) NOT NULL,
                calculated_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_comm_corridor ON commission_rules(corridor, is_active)
        """)

@app.get("/health")
async def health_check():
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {"status": "healthy", "service": "commission-service", "database": "connected"}
    except Exception as e:
        return {"status": "degraded", "service": "commission-service", "error": str(e)}

class CommissionRuleCreate(BaseModel):
    corridor: str
    currency_from: str
    currency_to: str
    min_amount: float = 0
    max_amount: float = 999999999
    fee_type: str = "percentage"
    fee_value: float
    flat_fee: float = 0

class FeeCalculationRequest(BaseModel):
    amount: float
    corridor: str
    currency_from: str
    currency_to: str
    transaction_id: Optional[str] = None

@app.post("/api/v1/commissions/rules")
async def create_rule(rule: CommissionRuleCreate, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO commission_rules (corridor, currency_from, currency_to, min_amount, max_amount, fee_type, fee_value, flat_fee)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING *""",
            rule.corridor, rule.currency_from, rule.currency_to, rule.min_amount,
            rule.max_amount, rule.fee_type, rule.fee_value, rule.flat_fee
        )
        return dict(row)

@app.get("/api/v1/commissions/rules")
async def list_rules(corridor: Optional[str] = None, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        if corridor:
            rows = await conn.fetch("SELECT * FROM commission_rules WHERE corridor=$1 AND is_active=TRUE ORDER BY min_amount", corridor)
        else:
            rows = await conn.fetch("SELECT * FROM commission_rules WHERE is_active=TRUE ORDER BY corridor, min_amount")
        return {"rules": [dict(r) for r in rows]}

@app.post("/api/v1/commissions/calculate")
async def calculate_fee(req: FeeCalculationRequest, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rule = await conn.fetchrow(
            """SELECT * FROM commission_rules WHERE corridor=$1 AND currency_from=$2 AND currency_to=$3
               AND min_amount <= $4 AND max_amount >= $4 AND is_active=TRUE ORDER BY fee_value ASC LIMIT 1""",
            req.corridor, req.currency_from, req.currency_to, req.amount
        )
        if not rule:
            raise HTTPException(status_code=404, detail="No commission rule found for this corridor and amount")
        if rule["fee_type"] == "percentage":
            fee = round(req.amount * float(rule["fee_value"]) / 100, 2)
        else:
            fee = float(rule["fee_value"])
        fee += float(rule["flat_fee"])
        total = req.amount + fee
        if req.transaction_id:
            await conn.execute(
                "INSERT INTO commission_transactions (transaction_id, rule_id, amount, fee_amount, currency) VALUES ($1,$2,$3,$4,$5)",
                req.transaction_id, rule["id"], req.amount, fee, req.currency_from
            )
        return {"amount": req.amount, "fee": fee, "total": total, "fee_type": rule["fee_type"],
                "fee_rate": float(rule["fee_value"]), "flat_fee": float(rule["flat_fee"]), "corridor": req.corridor}

@app.get("/api/v1/commissions/stats")
async def commission_stats(token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        total = await conn.fetchval("SELECT COALESCE(SUM(fee_amount), 0) FROM commission_transactions")
        count = await conn.fetchval("SELECT COUNT(*) FROM commission_transactions")
        by_corridor = await conn.fetch(
            """SELECT r.corridor, COUNT(*) as txn_count, SUM(ct.fee_amount) as total_fees
               FROM commission_transactions ct JOIN commission_rules r ON ct.rule_id=r.id
               GROUP BY r.corridor ORDER BY total_fees DESC"""
        )
        return {"total_fees_collected": float(total), "total_transactions": count, "by_corridor": [dict(r) for r in by_corridor]}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8114)
