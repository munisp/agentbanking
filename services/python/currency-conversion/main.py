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

# --- PostgreSQL Persistence ---
import asyncpg
from typing import Optional

_pg_pool: Optional[asyncpg.Pool] = None

async def get_pg_pool() -> Optional[asyncpg.Pool]:
    global _pg_pool
    if _pg_pool is None:
        try:
            _pg_pool = await asyncpg.create_pool(
                dsn=os.environ.get("DATABASE_URL", "postgresql://localhost:5432/agentbanking"),
                min_size=2, max_size=10, command_timeout=10
            )
            await _pg_pool.execute("""
                CREATE TABLE IF NOT EXISTS service_state (
                    key TEXT PRIMARY KEY,
                    value JSONB NOT NULL DEFAULT '{}',
                    service TEXT NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
        except Exception:
            _pg_pool = None
    return _pg_pool

async def pg_get(key: str, service: str):
    pool = await get_pg_pool()
    if pool:
        row = await pool.fetchrow(
            "SELECT value FROM service_state WHERE key = $1 AND service = $2", key, service
        )
        return row["value"] if row else None
    return None

async def pg_set(key: str, value, service: str):
    pool = await get_pg_pool()
    if pool:
        import json
        await pool.execute(
            "INSERT INTO service_state (key, value, service, updated_at) VALUES ($1, $2::jsonb, $3, NOW()) "
            "ON CONFLICT (key) DO UPDATE SET value = $2::jsonb, updated_at = NOW()",
            key, json.dumps(value) if not isinstance(value, str) else value, service
        )
# --- End PostgreSQL Persistence ---


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

app = FastAPI(title="Currency Conversion", version="2.0.0")

@app.on_event("startup")
async def _init_pg_pool():
    await get_pg_pool()

apply_middleware(app, enable_auth=True)

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
