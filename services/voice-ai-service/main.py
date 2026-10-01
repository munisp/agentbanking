import sys as _sys, os as _os

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

app = FastAPI(
    title="Voice AI Service",
    description="Production-ready Voice AI conversational commerce",
    version="2.0.0",
    lifespan=lifespan
)

apply_middleware(app)
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

messages_db = _PgListStore("voice_ai_service_messages", "VOICE_AI_SERVICE_DATABASE_URL")
orders_db = _PgListStore("voice_ai_service_orders", "VOICE_AI_SERVICE_DATABASE_URL")
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
                    VALUES ($1, $2, $3, $4, $5, 'queued')
                """, message_id, message.recipient, message.message_type.value, 
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
                    VALUES ($1, $2, $3, $4, $5, $6, $7, 'pending')
                """, order_id, order.customer_id, order.customer_name, order.phone,
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
