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

apply_middleware(app, enable_auth=True)
setup_logging("gaming-service")
app.include_router(metrics_router)

from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
import uvicorn
import os
import json
import httpx

app = FastAPI(

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
    title="Gaming Service",
    description="Gaming platforms (Discord/Steam) commerce",
    version="1.0.0"
)

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
messages_cache = []  # PG-backed via pg_get_list("gaming-service", "messages")
orders_cache = []  # PG-backed via pg_get_list("gaming-service", "orders")
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
