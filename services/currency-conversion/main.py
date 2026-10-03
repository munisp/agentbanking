"""
Currency Conversion Service - Production Implementation
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Optional
import os
import json
import asyncpg
from datetime import datetime
from decimal import Decimal
import uvicorn
import logging

# --- Production: Graceful Shutdown ---
import signal
import sys
import atexit
import logging

# ── Round-11 persistence fix (wave-6: asyncpg) ────────────────────────────
# Process-memory containers replaced by Postgres-backed stores so business
# data survives restarts. Wave-6 upgrade: all DB I/O now runs on asyncpg via
# a dedicated background event loop, so async FastAPI handlers no longer
# block the main loop on sync SQLAlchemy calls. Same dict/list-compatible
# public API; {ENV}_DATABASE_URL convention unchanged.
import os as _r11_os
import json as _r11_json
import asyncio as _r11_asyncio
import threading as _r11_threading
import asyncpg as _r11_apg

_r11_loop = _r11_asyncio.new_event_loop()


def _r11_loop_main(loop):
    _r11_asyncio.set_event_loop(loop)
    loop.run_forever()


_r11_threading.Thread(
    target=_r11_loop_main, args=(_r11_loop,), daemon=True, name="r11-pg-io"
).start()


def _r11_sync(coro):
    """Run an asyncpg coroutine on the dedicated loop and wait for it."""
    return _r11_asyncio.run_coroutine_threadsafe(coro, _r11_loop).result()


class _PgDictStore:
    """Dict-compatible store persisted to Postgres (replaces in-memory dict)."""

    def __init__(self, table, env, model_name=None):
        if not table.replace("_", "").isalnum():
            raise ValueError("unsafe table name: %r" % table)
        self._model_name = model_name
        self._table = table
        url = _r11_os.getenv(
            env, "postgresql://postgres:postgres@localhost:5432/platform"
        )
        self._pool = _r11_sync(_r11_apg.create_pool(url, min_size=1, max_size=10))
        _r11_sync(self._ensure())

    async def _ensure(self):
        async with self._pool.acquire() as c:
            await c.execute(
                'CREATE TABLE IF NOT EXISTS "%s" ('
                "key VARCHAR(128) PRIMARY KEY, "
                "data TEXT NOT NULL, "
                "updated_at TIMESTAMPTZ NOT NULL DEFAULT now()"
                ")" % self._table
            )

    @staticmethod
    def _ser(v):
        def _cv(x):
            if hasattr(x, "model_dump"):
                return x.model_dump()
            if hasattr(x, "dict") and callable(x.dict):
                return x.dict()
            return x
        if isinstance(v, list):
            v = [_cv(x) for x in v]
        else:
            v = _cv(v)
        return _r11_json.dumps(v, default=str)

    def _deser(self, raw):
        d = _r11_json.loads(raw)
        if self._model_name:
            cls = globals().get(self._model_name)
            if cls is not None:
                if isinstance(d, list):
                    return [cls(**x) if isinstance(x, dict) else x for x in d]
                return cls(**d)
        return d

    async def _aset(self, k, payload):
        async with self._pool.acquire() as c:
            await c.execute(
                'INSERT INTO "%s" (key, data) VALUES ($1, $2) '
                "ON CONFLICT (key) DO UPDATE SET data = EXCLUDED.data, "
                "updated_at = now()" % self._table,
                str(k), payload,
            )

    def __setitem__(self, k, v):
        _r11_sync(self._aset(k, self._ser(v)))

    async def _aget(self, k):
        async with self._pool.acquire() as c:
            return await c.fetchval(
                'SELECT data FROM "%s" WHERE key = $1' % self._table, str(k)
            )

    def __getitem__(self, k):
        raw = _r11_sync(self._aget(k))
        if raw is None:
            raise KeyError(k)
        return self._deser(raw)

    def get(self, k, default=None):
        try:
            return self[k]
        except KeyError:
            return default

    async def _adel(self, k):
        async with self._pool.acquire() as c:
            return await c.execute(
                'DELETE FROM "%s" WHERE key = $1' % self._table, str(k)
            )

    def __delitem__(self, k):
        res = _r11_sync(self._adel(k))
        if res == "DELETE 0":
            raise KeyError(k)

    def __contains__(self, k):
        return _r11_sync(self._aget(k)) is not None

    def setdefault(self, k, default=None):
        try:
            return self[k]
        except KeyError:
            self[k] = default
            return default

    async def _aall(self):
        async with self._pool.acquire() as c:
            return await c.fetch('SELECT key, data FROM "%s"' % self._table)

    def _all(self):
        return _r11_sync(self._aall())

    def values(self):
        return [self._deser(r["data"]) for r in self._all()]

    def keys(self):
        return [r["key"] for r in self._all()]

    def items(self):
        return [(r["key"], self._deser(r["data"])) for r in self._all()]

    def __len__(self):
        async def _n():
            async with self._pool.acquire() as c:
                return await c.fetchval('SELECT COUNT(*) FROM "%s"' % self._table)
        return _r11_sync(_n())

    def pop(self, k, default=None):
        try:
            v = self[k]
            del self[k]
            return v
        except KeyError:
            return default

    def clear(self):
        async def _c():
            async with self._pool.acquire() as c:
                await c.execute('DELETE FROM "%s"' % self._table)
        _r11_sync(_c())


class _PgListStore:
    """List-compatible store persisted to Postgres (replaces in-memory list)."""

    def __init__(self, table, env):
        if not table.replace("_", "").isalnum():
            raise ValueError("unsafe table name: %r" % table)
        self._table = table
        url = _r11_os.getenv(
            env, "postgresql://postgres:postgres@localhost:5432/platform"
        )
        self._pool = _r11_sync(_r11_apg.create_pool(url, min_size=1, max_size=10))
        _r11_sync(self._ensure())

    async def _ensure(self):
        async with self._pool.acquire() as c:
            await c.execute(
                'CREATE TABLE IF NOT EXISTS "%s" ('
                "id SERIAL PRIMARY KEY, "
                "data TEXT NOT NULL, "
                "created_at TIMESTAMPTZ NOT NULL DEFAULT now()"
                ")" % self._table
            )

    @staticmethod
    def _ser(v):
        def _cv(x):
            if hasattr(x, "model_dump"):
                return x.model_dump()
            if hasattr(x, "dict") and callable(x.dict):
                return x.dict()
            return x
        return _r11_json.dumps(_cv(v), default=str)

    @staticmethod
    def _deser(raw):
        return _r11_json.loads(raw)

    def append(self, v):
        async def _a():
            async with self._pool.acquire() as c:
                await c.execute(
                    'INSERT INTO "%s" (data) VALUES ($1)' % self._table,
                    self._ser(v),
                )
        _r11_sync(_a())

    async def _arows(self):
        async with self._pool.acquire() as c:
            return await c.fetch(
                'SELECT id, data FROM "%s" ORDER BY id' % self._table
            )

    def _rows(self):
        return _r11_sync(self._arows())

    def __iter__(self):
        return iter([self._deser(r["data"]) for r in self._rows()])

    def __len__(self):
        async def _n():
            async with self._pool.acquire() as c:
                return await c.fetchval('SELECT COUNT(*) FROM "%s"' % self._table)
        return _r11_sync(_n())

    def __getitem__(self, idx):
        vals = [self._deser(r["data"]) for r in self._rows()]
        return vals[idx]

    def __delitem__(self, idx):
        rows = self._rows()
        targets = rows[idx] if isinstance(idx, slice) else [rows[idx]]
        ids = [r["id"] for r in targets]
        if not ids:
            return
        async def _d():
            async with self._pool.acquire() as c:
                await c.execute(
                    'DELETE FROM "%s" WHERE id = ANY($1::int[])' % self._table, ids
                )
        _r11_sync(_d())

    def clear(self):
        async def _c():
            async with self._pool.acquire() as c:
                await c.execute('DELETE FROM "%s"' % self._table)
        _r11_sync(_c())


_shutdown_handlers = []  # function registry — must stay in-process (wave-8 revert of wave-7 overreach)  # round-11 wave-7 persistence

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

# ── Round-11 wave-8: no hardcoded FX rates ──────────────────────────────────
# Hardcoded in-repo exchange rates are fabricated market data. Rates now come
# from (1) the currency_conversion_rates Postgres table, or (2) the RATES_JSON
# env var (operator-provided feed snapshot). When neither is configured the
# service fails closed with 503 instead of quoting invented rates.

_fx_pool = None

async def get_db_pool():
    global _fx_pool
    if _fx_pool is None:
        url = os.getenv("CURRENCY_CONVERSION_DATABASE_URL",
                        os.getenv("DATABASE_URL",
                                  "postgresql://postgres:postgres@localhost:5432/platform"))
        _fx_pool = await asyncpg.create_pool(url, min_size=1, max_size=5)
        async with _fx_pool.acquire() as c:
            await c.execute("""
                CREATE TABLE IF NOT EXISTS currency_conversion_rates (
                    id BIGSERIAL PRIMARY KEY,
                    from_currency VARCHAR(8) NOT NULL,
                    to_currency VARCHAR(8) NOT NULL,
                    rate NUMERIC(24, 10) NOT NULL,
                    source VARCHAR(64),
                    effective_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )""")
    return _fx_pool


def _load_env_rates():
    raw = os.getenv("RATES_JSON", "")
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return {(k.split("-")[0].upper(), k.split("-")[1].upper()): Decimal(str(v))
                for k, v in data.items()}
    except Exception as e:
        logging.warning("RATES_JSON unparsable: %s", e)
        return {}

_env_rates = _load_env_rates()


async def get_rates():
    try:
        pool = await get_db_pool()
        async with pool.acquire() as c:
            rows = await c.fetch("""
                SELECT DISTINCT ON (from_currency, to_currency)
                       from_currency, to_currency, rate
                FROM currency_conversion_rates
                ORDER BY from_currency, to_currency, effective_at DESC""")
        rates = {(r["from_currency"], r["to_currency"]): Decimal(str(r["rate"])) for r in rows}
    except Exception as e:
        logging.warning("rates table unavailable: %s", e)
        rates = {}
    if rates:
        return rates
    return dict(_env_rates)


class CurrencyService:
    @staticmethod
    async def convert(request: ConversionRequest) -> ConversionResult:
        rates = await get_rates()
        if not rates:
            raise HTTPException(status_code=503,
                detail="No FX rate source configured (currency_conversion_rates table or RATES_JSON)")
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

@app.get("/api/v1/rates")
async def list_rates(base: Optional[str] = None):
    """Current rates, optionally filtered to a base currency. Backs the mobile
    /rates and /exchange-rates frontend calls (via APISIX alias)."""
    rates = await get_rates()
    if not rates:
        raise HTTPException(status_code=503,
            detail="No FX rate source configured (currency_conversion_rates table or RATES_JSON)")
    items = [{"from": f, "to": t_, "rate": str(r)} for (f, t_), r in sorted(rates.items())]
    if base:
        items = [i for i in items if i["from"] == base.upper()]
    return {"base": base.upper() if base else None, "rates": items, "count": len(items)}


@app.get("/api/v1/rates/{pair}")
async def get_pair_rate(pair: str):
    """Single-pair rate for the mobile RateLock screen, e.g. /api/v1/rates/USD-NGN.
    Fails closed when no rate source is configured (wave-8)."""
    parts = pair.upper().split("-")
    if len(parts) != 2 or not all(len(p) == 3 and p.isalpha() for p in parts):
        raise HTTPException(status_code=400, detail="pair must be CCC-CCC, e.g. USD-NGN")
    rates = await get_rates()
    if not rates:
        raise HTTPException(status_code=503,
            detail="No FX rate source configured (currency_conversion_rates table or RATES_JSON)")
    key = (parts[0], parts[1])
    if key not in rates:
        raise HTTPException(status_code=404, detail="Currency pair not supported")
    rate = rates[key]
    return {
        "pair": f"{parts[0]}-{parts[1]}",
        "rate": float(rate),
        "inverseRate": float(1 / rate),
        "timestamp": datetime.utcnow().isoformat(),
    }


class RateLockRequest(BaseModel):
    pair: str          # e.g. "USD-NGN"
    duration: int      # minutes


@app.post("/api/v1/rates/lock", status_code=201)
async def lock_rate(request: RateLockRequest):
    """Persist a rate lock so the quote is honored for the requested window.
    Backs the mobile POST /rates/lock call (via APISIX alias). Fails closed
    when the DB or rate source is unavailable — no simulated locks (wave-8)."""
    parts = request.pair.upper().split("-")
    if len(parts) != 2 or not all(len(p) == 3 and p.isalpha() for p in parts):
        raise HTTPException(status_code=400, detail="pair must be CCC-CCC, e.g. USD-NGN")
    if not (1 <= request.duration <= 24 * 60):
        raise HTTPException(status_code=400, detail="duration must be 1..1440 minutes")
    rates = await get_rates()
    if not rates:
        raise HTTPException(status_code=503,
            detail="No FX rate source configured (currency_conversion_rates table or RATES_JSON)")
    key = (parts[0], parts[1])
    if key not in rates:
        raise HTTPException(status_code=404, detail="Currency pair not supported")
    rate = rates[key]
    try:
        pool = await get_db_pool()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Rate lock store unavailable: {e}")
    async with pool.acquire() as c:
        await c.execute("""
            CREATE TABLE IF NOT EXISTS currency_rate_locks (
                id BIGSERIAL PRIMARY KEY,
                pair VARCHAR(8) NOT NULL,
                rate NUMERIC(24, 10) NOT NULL,
                duration_minutes INTEGER NOT NULL,
                expires_at TIMESTAMPTZ NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )""")
        row = await c.fetchrow("""
            INSERT INTO currency_rate_locks (pair, rate, duration_minutes, expires_at)
            VALUES ($1, $2, $3, now() + make_interval(mins => $3))
            RETURNING id, pair, rate, duration_minutes, expires_at
        """, f"{parts[0]}-{parts[1]}", str(rate), request.duration)
    return {
        "lock_id": row["id"],
        "pair": row["pair"],
        "rate": float(row["rate"]),
        "duration_minutes": row["duration_minutes"],
        "expires_at": row["expires_at"].isoformat(),
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "currency-conversion", "version": "2.0.0"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8079)
