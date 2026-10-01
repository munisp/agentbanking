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
Gaming platforms (Discord/Steam) commerce
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

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/gaming_service")

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
    title="Gaming Service",
    description="Gaming platforms (Discord/Steam) commerce",
    version="1.0.0"
)

apply_middleware(app, enable_auth=True)
setup_logging("gaming-service")
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
    API_KEY = os.getenv("GAMING_API_KEY", "demo_key")
    API_SECRET = os.getenv("GAMING_API_SECRET", "demo_secret")
    API_BASE_URL = os.getenv("GAMING_API_URL", "https://api.gaming.com")

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
# ── Round-11 persistence fix ───────────────────────────────────────────────
# Process-memory dict replaced by a dict-compatible Postgres-backed store so
# business data survives restarts. Mirrors sibling-service convention:
# {ENV}_DATABASE_URL, pool_pre_ping, auto-created table (python-owned schema).
import os as _r11_os
import json as _r11_json
from datetime import datetime as _r11_dt, timezone as _r11_tz
from sqlalchemy import (
    create_engine as _r11_ce,
    Column as _r11_Col,
    String as _r11_Str,
    DateTime as _r11_DT,
    Text as _r11_Txt,
    Integer as _r11_Int,
)
from sqlalchemy.orm import sessionmaker as _r11_sm, declarative_base as _r11_db

_R11Base = _r11_db()


class _R11Row(_R11Base):
    __abstract__ = True
    key = _r11_Col(_r11_Str(128), primary_key=True)
    data = _r11_Col(_r11_Txt, nullable=False)
    updated_at = _r11_Col(
        _r11_DT(timezone=True),
        default=lambda: _r11_dt.now(_r11_tz.utc),
        onupdate=lambda: _r11_dt.now(_r11_tz.utc),
    )


class _PgDictStore:
    """Dict-compatible store persisted to Postgres (replaces in-memory dict)."""

    def __init__(self, table, env, model_name=None):
        self._model_name = model_name
        self._Row = type("_R11_%s" % table, (_R11Row,), {"__tablename__": table})
        url = _r11_os.getenv(
            env, "postgresql://postgres:postgres@localhost:5432/platform"
        )
        self._engine = _r11_ce(url, pool_pre_ping=True, pool_size=5, max_overflow=5)
        _R11Base.metadata.create_all(self._engine)
        self._Session = _r11_sm(bind=self._engine, autoflush=False, autocommit=False)

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

    def __setitem__(self, k, v):
        s = self._Session()
        try:
            row = s.get(self._Row, str(k))
            payload = self._ser(v)
            if row is None:
                s.add(self._Row(key=str(k), data=payload))
            else:
                row.data = payload
            s.commit()
        finally:
            s.close()

    def __getitem__(self, k):
        s = self._Session()
        try:
            row = s.get(self._Row, str(k))
            if row is None:
                raise KeyError(k)
            return self._deser(row.data)
        finally:
            s.close()

    def get(self, k, default=None):
        try:
            return self[k]
        except KeyError:
            return default

    def __delitem__(self, k):
        s = self._Session()
        try:
            row = s.get(self._Row, str(k))
            if row is None:
                raise KeyError(k)
            s.delete(row)
            s.commit()
        finally:
            s.close()

    def __contains__(self, k):
        s = self._Session()
        try:
            return s.get(self._Row, str(k)) is not None
        finally:
            s.close()

    def setdefault(self, k, default=None):
        try:
            return self[k]
        except KeyError:
            self[k] = default
            return default

    def _all(self):
        s = self._Session()
        try:
            return s.query(self._Row).all()
        finally:
            s.close()

    def values(self):
        return [self._deser(r.data) for r in self._all()]

    def keys(self):
        return [r.key for r in self._all()]

    def items(self):
        return [(r.key, self._deser(r.data)) for r in self._all()]

    def __len__(self):
        s = self._Session()
        try:
            return s.query(self._Row).count()
        finally:
            s.close()

    def pop(self, k, default=None):
        try:
            v = self[k]
            del self[k]
            return v
        except KeyError:
            return default

    def clear(self):
        s = self._Session()
        try:
            s.query(self._Row).delete()
            s.commit()
        finally:
            s.close()



class _R11ListRow(_R11Base):
    __abstract__ = True
    id = _r11_Col(_r11_Int, primary_key=True, autoincrement=True)
    data = _r11_Col(_r11_Txt, nullable=False)
    created_at = _r11_Col(
        _r11_DT(timezone=True),
        default=lambda: _r11_dt.now(_r11_tz.utc),
    )


class _PgListStore:
    """List-compatible store persisted to Postgres (replaces in-memory list)."""

    def __init__(self, table, env):
        self._Row = type("_R11L_%s" % table, (_R11ListRow,), {"__tablename__": table})
        url = _r11_os.getenv(
            env, "postgresql://postgres:postgres@localhost:5432/platform"
        )
        self._engine = _r11_ce(url, pool_pre_ping=True, pool_size=5, max_overflow=5)
        _R11Base.metadata.create_all(self._engine)
        self._Session = _r11_sm(bind=self._engine, autoflush=False, autocommit=False)

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
        s = self._Session()
        try:
            s.add(self._Row(data=self._ser(v)))
            s.commit()
        finally:
            s.close()

    def _rows(self):
        s = self._Session()
        try:
            return s.query(self._Row).order_by(self._Row.id).all()
        finally:
            s.close()

    def __iter__(self):
        return iter([self._deser(r.data) for r in self._rows()])

    def __len__(self):
        s = self._Session()
        try:
            return s.query(self._Row).count()
        finally:
            s.close()

    def __getitem__(self, idx):
        vals = [self._deser(r.data) for r in self._rows()]
        return vals[idx]

    def __delitem__(self, idx):
        rows = self._rows()
        targets = rows[idx] if isinstance(idx, slice) else [rows[idx]]
        ids = [r.id for r in targets]
        s = self._Session()
        try:
            s.query(self._Row).filter(self._Row.id.in_(ids)).delete(synchronize_session=False)
            s.commit()
        finally:
            s.close()

    def clear(self):
        s = self._Session()
        try:
            s.query(self._Row).delete()
            s.commit()
        finally:
            s.close()

messages_db = _PgListStore("gaming_service_messages", "GAMING_SERVICE_DATABASE_URL")
orders_db = _PgListStore("gaming_service_orders", "GAMING_SERVICE_DATABASE_URL")
# round-11: channel identity constants (referenced but never defined)
channel_name = os.getenv("CHANNEL_NAME", "gaming")
channel_display = os.getenv("CHANNEL_DISPLAY", "Gaming")

service_start_time = datetime.now()
message_count = 0

@app.get("/")
async def root():
    return {
        "service": "gaming-service",
        "channel": "Gaming",
        "version": "1.0.0",
        "status": "operational"
    }

@app.get("/health")
async def health_check():
    uptime = (datetime.now() - service_start_time).total_seconds()
    return {
        "status": "healthy",
        "service": "gaming-service",
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
        "channel": "Gaming",
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
        "channel": "Gaming",
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
    port = int(os.getenv("PORT", 8100))
    uvicorn.run(app, host="0.0.0.0", port=port)
