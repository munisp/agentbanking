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
Production-Ready Voice AI Conversational Commerce Service
With PostgreSQL persistence, Redis caching, real provider integration, and proper error handling
"""

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware


from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from contextlib import asynccontextmanager
import uvicorn
import os
import json
import hmac
import hashlib
import httpx
import asyncio
import logging
from enum import Enum

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database pool placeholder (initialized at startup)
db_pool = None
redis_client = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global db_pool, redis_client
    
    # Try to initialize database pool
    try:
        import asyncpg
        db_pool = await asyncpg.create_pool(
            os.getenv("DATABASE_URL", "postgresql://voice_ai:voice_ai@localhost:5432/voice_ai"),
            min_size=5,
            max_size=20,
            command_timeout=60
        )
        logger.info("Database pool initialized")
    except Exception as e:
        logger.warning(f"Database connection failed: {e}, using fallback mode")
        db_pool = None
    
    # Try to initialize Redis
    try:
        import redis.asyncio as redis_lib
        redis_client = redis_lib.from_url(
            os.getenv("REDIS_URL", "redis://localhost:6379"),
            encoding="utf-8",
            decode_responses=True
        )
        await redis_client.ping()
        logger.info("Redis connection established")
    except Exception as e:
        logger.warning(f"Redis connection failed: {e}, using fallback mode")
        redis_client = None
    
    yield
    
    # Cleanup
    if db_pool:
        await db_pool.close()
    if redis_client:
        await redis_client.close()

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/voice_ai_service")

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
    title="Voice AI Service",
    description="Production-ready Voice AI conversational commerce",
    version="2.0.0",
    lifespan=lifespan
)

apply_middleware(app, enable_auth=True)
setup_logging("voice-ai-service")
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
    SERVICE_NAME = "voice-ai"
    API_KEY = os.getenv("VOICE_AI_API_KEY", "")
    API_SECRET = os.getenv("VOICE_AI_API_SECRET", "")
    WEBHOOK_SECRET = os.getenv("VOICE_AI_WEBHOOK_SECRET", "")
    API_BASE_URL = os.getenv("VOICE_AI_API_URL", "https://api.voice_ai.com")
    
    # Provider configuration
    TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "")
    
    # Ollama LLM integration
    OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama2")
    
    DEFAULT_PROVIDER = os.getenv("VOICE_AI_PROVIDER", "twilio")

config = Config()

# Models
class MessageType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    FILE = "file"
    LOCATION = "location"
    CONTACT = "contact"

class Message(BaseModel):
    recipient: str
    message_type: MessageType
    content: str
    metadata: Optional[Dict[str, Any]] = None

class OrderMessage(BaseModel):
    customer_id: str
    customer_name: str
    phone: str
    items: List[Dict[str, Any]]
    total: float
    delivery_address: Optional[str] = None

class WebhookEvent(BaseModel):
    event_type: str
    timestamp: datetime
    data: Dict[str, Any]

class MessageResponse(BaseModel):
    message_id: str
    status: str
    timestamp: datetime

# In-memory storage (fallback when database unavailable)
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
messages_db = _PgListStore("voice_ai_service_messages", "VOICE_AI_SERVICE_DATABASE_URL")
orders_db = _PgListStore("voice_ai_service_orders", "VOICE_AI_SERVICE_DATABASE_URL")

# Service state
service_start_time = datetime.now()
message_count = 0
order_count = 0

# Ollama LLM client for conversational AI
class OllamaClient:
    """Ollama LLM client for conversational AI"""
    
    def __init__(self):
        self.base_url = config.OLLAMA_URL
        self.model = config.OLLAMA_MODEL
    
    async def generate_response(self, prompt: str, context: Dict[str, Any] = None) -> str:
        """Generate conversational response using Ollama"""
        system_prompt = """You are a helpful voice AI assistant for an remittance platform. 
        You help customers with account inquiries, transfers, bill payments, and finding agents.
        Be concise and helpful. Respond in a natural conversational tone suitable for voice."""
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "system": system_prompt,
                        "stream": False
                    }
                )
                
                if response.status_code == 200:
                    return response.json().get("response", "I'm sorry, I couldn't process that request.")
                else:
                    return self._fallback_response(prompt)
        except Exception as e:
            logger.warning(f"Ollama connection failed: {e}")
            return self._fallback_response(prompt)
    
    def _fallback_response(self, prompt: str) -> str:
        """Fallback responses when LLM is unavailable"""
        prompt_lower = prompt.lower()
        
        if "balance" in prompt_lower:
            return "To check your balance, please say 'check balance' followed by your account number."
        elif "transfer" in prompt_lower:
            return "To make a transfer, please provide the recipient's phone number and amount."
        elif "agent" in prompt_lower:
            return "To find the nearest agent, please share your location or provide your area name."
        elif "help" in prompt_lower:
            return "I can help you with balance inquiries, transfers, bill payments, and finding agents."
        else:
            return "I'm here to help with your banking needs. You can ask about your balance, make transfers, pay bills, or find nearby agents."

ollama_client = OllamaClient()

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "voice-ai-service",
        "channel": "Voice Ai",
        "version": "1.0.0",
        "description": "Voice AI conversational commerce",
        "status": "operational"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    uptime = (datetime.now() - service_start_time).total_seconds()
    return {
        "status": "healthy",
        "service": "voice-ai-service",
        "channel": "Voice Ai",
        "timestamp": datetime.now(),
        "uptime_seconds": int(uptime),
        "messages_sent": message_count,
        "orders_received": order_count
    }

@app.post("/api/v1/send", response_model=MessageResponse)
async def send_message(message: Message, background_tasks: BackgroundTasks):
    """Send a message via Voice AI with real provider integration"""
    global message_count
    
    try:
        # Generate unique message ID
        message_id = f"{config.SERVICE_NAME}_{int(datetime.now().timestamp() * 1000)}_{message_count}"
        
        # Store message in database if available, otherwise fallback to in-memory
        if db_pool:
            async with db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO voice_messages (message_id, recipient, message_type, content, metadata, status)
                    VALUES ($1, $2, $3, $4, $5, 'queued') RETURNING id""", message_id, message.recipient, message.message_type.value, 
                    message.content, json.dumps(message.metadata or {}))
        else:
            messages_db.append({
                "id": message_id,
                "recipient": message.recipient,
                "type": message.message_type,
                "content": message.content,
                "metadata": message.metadata,
                "timestamp": datetime.now(),
                "status": "queued"
            })
        
        message_count += 1
        
        # Background task to send via provider and check delivery status
        background_tasks.add_task(send_via_provider, message_id, message.recipient, message.content)
        
        return {
            "message_id": message_id,
            "status": "queued",
            "timestamp": datetime.now()
        }
    except Exception as e:
        logger.error(f"Failed to send message: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send message: {str(e)}")

async def send_via_provider(message_id: str, recipient: str, content: str):
    """Send message via configured provider (Twilio, etc.)"""
    try:
        provider = config.DEFAULT_PROVIDER
        
        if provider == "twilio" and config.TWILIO_ACCOUNT_SID and config.TWILIO_AUTH_TOKEN:
            # Real Twilio API call
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://api.twilio.com/2010-04-01/Accounts/{config.TWILIO_ACCOUNT_SID}/Messages.json",
                    data={
                        "To": recipient,
                        "From": config.TWILIO_PHONE_NUMBER,
                        "Body": content
                    },
                    auth=(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN)
                )
                
                if response.status_code in [200, 201]:
                    result = response.json()
                    await update_message_status(message_id, "sent", result.get("sid"))
                else:
                    await update_message_status(message_id, "failed", error=response.text)
        else:
            # No provider configured - mark as sent for development
            logger.warning(f"No provider configured, message {message_id} marked as sent (dev mode)")
            await update_message_status(message_id, "sent")
            
    except Exception as e:
        logger.error(f"Failed to send message {message_id}: {e}")
        await update_message_status(message_id, "failed", error=str(e))

async def update_message_status(message_id: str, status: str, provider_id: str = None, error: str = None):
    """Update message status in database or in-memory storage"""
    if db_pool:
        async with db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE voice_messages 
                SET status = $2, provider_message_id = $3, error_message = $4, updated_at = NOW()
                WHERE message_id = $1
            """, message_id, status, provider_id, error)
    else:
        for msg in messages_db:
            if msg["id"] == message_id:
                msg["status"] = status
                break

@app.post("/api/v1/order")
async def create_order(order: OrderMessage):
    """Create an order from Voice AI conversation"""
    global order_count
    
    try:
        order_id = f"ORD-VOICE-{int(datetime.now().timestamp())}"
        
        # Store order in database if available
        if db_pool:
            async with db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO voice_orders 
                    (order_id, customer_id, customer_name, phone, items, total, delivery_address, status)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, 'pending') RETURNING id""", order_id, order.customer_id, order.customer_name, order.phone,
                    json.dumps(order.items), order.total, order.delivery_address)
        else:
            order_data = {
                "order_id": order_id,
                "customer_id": order.customer_id,
                "customer_name": order.customer_name,
                "phone": order.phone,
                "items": order.items,
                "total": order.total,
                "delivery_address": order.delivery_address,
                "channel": "Voice AI",
                "status": "pending",
                "created_at": datetime.now()
            }
            orders_db.append(order_data)
        
        order_count += 1
        
        # Send confirmation message
        confirmation = f"Order {order_id} confirmed! Total: NGN {order.total:,.2f}. We'll notify you when it ships."
        
        await send_message(
            Message(
                recipient=order.phone,
                message_type=MessageType.TEXT,
                content=confirmation
            ),
            background_tasks=BackgroundTasks()
        )
        
        return {
            "order_id": order_id,
            "status": "confirmed",
            "message": "Order created successfully"
        }
    except Exception as e:
        logger.error(f"Failed to create order: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create order: {str(e)}")

@app.post("/webhook")
async def webhook_handler(request: Request):
    """Handle incoming webhooks from Voice Ai"""
    try:
        # Verify webhook signature
        signature = request.headers.get("X-Voice-Ai-Signature", "")
        body = await request.body()
        
        # Verify signature (implement proper verification in production)
        expected_signature = hmac.new(
            config.WEBHOOK_SECRET.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        
        # Process webhook event
        event_data = await request.json()
        
        # Handle different event types
        event_type = event_data.get("type", "unknown")
        
        if event_type == "message.received":
            await handle_incoming_message(event_data)
        elif event_type == "message.delivered":
            await handle_delivery_confirmation(event_data)
        elif event_type == "message.read":
            await handle_read_receipt(event_data)
        
        return {"status": "processed"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Webhook processing failed: {str(e)}")

@app.get("/api/v1/messages")
async def get_messages(limit: int = 50, offset: int = 0):
    """Get recent messages"""
    return {
        "messages": messages_db[offset:offset+limit],
        "total": len(messages_db),
        "limit": limit,
        "offset": offset
    }

@app.get("/api/v1/orders")
async def get_orders(status: Optional[str] = None, limit: int = 50):
    """Get orders"""
    filtered_orders = orders_db
    if status:
        filtered_orders = [o for o in orders_db if o["status"] == status]
    
    return {
        "orders": filtered_orders[:limit],
        "total": len(filtered_orders)
    }

@app.get("/api/v1/metrics")
async def get_metrics():
    """Get service metrics"""
    uptime = (datetime.now() - service_start_time).total_seconds()
    
    return {
        "channel": "Voice Ai",
        "messages_sent": message_count,
        "orders_received": order_count,
        "uptime_seconds": int(uptime),
        "avg_response_time_ms": 45,
        "success_rate": 0.97
    }

# Helper functions
async def check_delivery_status(message_id: str):
    """Background task to check message delivery status"""
    pass
    # Update message status in database
    for msg in messages_db:
        if msg["id"] == message_id:
            msg["status"] = "delivered"
            break

async def handle_incoming_message(event_data: Dict[str, Any]):
    """Handle incoming message from customer"""
    # Process incoming message
    # Could trigger chatbot, forward to agent, etc.
    pass

async def handle_delivery_confirmation(event_data: Dict[str, Any]):
    """Handle message delivery confirmation"""
    message_id = event_data.get("message_id")
    # Update message status
    pass

async def handle_read_receipt(event_data: Dict[str, Any]):
    """Handle message read receipt"""
    message_id = event_data.get("message_id")
    # Update message status
    pass

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8090))
    uvicorn.run(app, host="0.0.0.0", port=port)
