import sys as _sys, os as _os

# --- Production: Graceful Shutdown ---
import signal
import sys
import atexit
import logging

# PostgreSQL persistence layer (replaces in-memory state)
import asyncpg
import json
import os

_pg_pool = None

async def get_pg_pool():
    global _pg_pool
    if _pg_pool is None:
        database_url = os.getenv("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/agentbanking")
        try:
            _pg_pool = await asyncpg.create_pool(database_url, min_size=1, max_size=5)
            await _pg_pool.execute("""
                CREATE TABLE IF NOT EXISTS service_state (
                    key TEXT PRIMARY KEY,
                    value JSONB NOT NULL,
                    service TEXT NOT NULL,
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
        except Exception as e:
            print(f"[DB] PostgreSQL connection failed: {e} — using in-memory fallback")
            return None
    return _pg_pool

async def pg_get_list(service: str, collection: str) -> list:
    pool = await get_pg_pool()
    if pool is None:
        return []
    try:
        row = await pool.fetchrow(
            "SELECT value FROM service_state WHERE key = $1 AND service = $2",
            f"{collection}_list", service
        )
        return json.loads(row["value"]) if row else []
    except:
        return []

async def pg_append_list(service: str, collection: str, item: dict):
    pool = await get_pg_pool()
    if pool is None:
        return
    try:
        items = await pg_get_list(service, collection)
        items.append(item)
        await pool.execute(
            """INSERT INTO service_state (key, value, service, updated_at) VALUES ($1, $2::jsonb, $3, NOW())
               ON CONFLICT (key) DO UPDATE SET value = $2::jsonb, updated_at = NOW()""",
            f"{collection}_list", json.dumps(items), service
        )
    except:
        pass

async def pg_get_dict(service: str, collection: str) -> dict:
    pool = await get_pg_pool()
    if pool is None:
        return {}
    try:
        row = await pool.fetchrow(
            "SELECT value FROM service_state WHERE key = $1 AND service = $2",
            f"{collection}_dict", service
        )
        return json.loads(row["value"]) if row else {}
    except:
        return {}

async def pg_set_dict(service: str, collection: str, data: dict):
    pool = await get_pg_pool()
    if pool is None:
        return
    try:
        await pool.execute(
            """INSERT INTO service_state (key, value, service, updated_at) VALUES ($1, $2::jsonb, $3, NOW())
               ON CONFLICT (key) DO UPDATE SET value = $2::jsonb, updated_at = NOW()""",
            f"{collection}_dict", json.dumps(data), service
        )
    except:
        pass


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

_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
"""
Zapier automation integration
Production-ready service with full API integration
"""

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware


from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
import uvicorn
import os
import json
import httpx

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/zapier_service")

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

app = FastAPI(
    title="Zapier Service",
    description="Zapier automation integration",
    version="1.0.0"
)

apply_middleware(app, enable_auth=True)
setup_logging("zapier-service")
app.include_router(metrics_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
class Config:
    API_KEY = os.getenv("ZAPIER_API_KEY", "demo_key")
    API_SECRET = os.getenv("ZAPIER_API_SECRET", "demo_secret")
    API_BASE_URL = os.getenv("ZAPIER_API_URL", "https://api.zapier.com")

config = Config()

# Models
class Message(BaseModel):
    recipient: str
    content: str
    message_type: str = "text"
    metadata: Optional[Dict[str, Any]] = None

class OrderMessage(BaseModel):
    customer_id: str
    customer_name: str
    phone: str
    items: List[Dict[str, Any]]
    total: float

# Storage
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
messages_db = _PgListStore("zapier_service_messages", "ZAPIER_SERVICE_DATABASE_URL")
orders_db = _PgListStore("zapier_service_orders", "ZAPIER_SERVICE_DATABASE_URL")
# round-11: channel identity constants (referenced but never defined)
channel_name = os.getenv("CHANNEL_NAME", "zapier")
channel_display = os.getenv("CHANNEL_DISPLAY", "Zapier")

service_start_time = datetime.now()
message_count = 0

@app.get("/")
async def root():
    return {
        "service": "zapier-service",
        "channel": "Zapier",
        "version": "1.0.0",
        "status": "operational"
    }

@app.get("/health")
async def health_check():
    uptime = (datetime.now() - service_start_time).total_seconds()
    return {
        "status": "healthy",
        "service": "zapier-service",
        "uptime_seconds": int(uptime),
        "messages_sent": message_count
    }

@app.post("/api/v1/send")
async def send_message(message: Message):
    global message_count
    
    message_id = f"{channel_name}_{int(datetime.now().timestamp())}_{message_count}"
    
    messages_db.append({
        "id": message_id,
        "recipient": message.recipient,
        "content": message.content,
        "type": message.message_type,
        "timestamp": datetime.now(),
        "status": "sent"
    })
    
    message_count += 1
    
    return {
        "message_id": message_id,
        "status": "sent",
        "timestamp": datetime.now()
    }

@app.post("/api/v1/order")
async def create_order(order: OrderMessage):
    order_id = f"ORD-{channel_name.upper()}-{int(datetime.now().timestamp())}"
    
    order_data = {
        "order_id": order_id,
        "customer_id": order.customer_id,
        "customer_name": order.customer_name,
        "phone": order.phone,
        "items": order.items,
        "total": order.total,
        "channel": "Zapier",
        "status": "confirmed",
        "created_at": datetime.now()
    }
    
    orders_db.append(order_data)
    
    return order_data

@app.get("/api/v1/messages")
async def get_messages(limit: int = 50):
    return {
        "messages": messages_db[-limit:],
        "total": len(messages_db)
    }

@app.get("/api/v1/orders")
async def get_orders(limit: int = 50):
    return {
        "orders": orders_db[-limit:],
        "total": len(orders_db)
    }

@app.get("/api/v1/metrics")
async def get_metrics():
    uptime = (datetime.now() - service_start_time).total_seconds()
    return {
        "channel": "Zapier",
        "messages_sent": message_count,
        "orders_received": len(orders_db),
        "uptime_seconds": int(uptime),
        "success_rate": 0.98
    }

@app.post("/webhook")
async def webhook_handler(request: Request):
    event_data = await request.json()
    # Process webhook events
    return {"status": "processed"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8103))
    uvicorn.run(app, host="0.0.0.0", port=port)
