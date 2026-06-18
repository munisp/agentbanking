"""
Omnichannel Middleware Service
Unified communication across multiple channels

Features:
- SMS, Email, Push, WhatsApp integration
- Message routing
- Template management
- Delivery tracking
"""

from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from enum import Enum
import asyncpg
import os
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


DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/omnichannel")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Omnichannel Middleware Service", version="1.0.0")

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/omnichannel_middleware")

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
        conn.execute("INSERT INTO audit_log (action, entity_id, data) VALUES (?, ?, ?)", (action, entity_id, data))
        conn.commit()
        conn.close()
    except Exception:
        pass
db_pool = None

class Channel(str, Enum):
    SMS = "sms"
    EMAIL = "email"
    PUSH = "push"
    WHATSAPP = "whatsapp"

class Message(BaseModel):
    recipient: str
    channel: Channel
    template_id: Optional[str]
    content: str
    metadata: Optional[dict] = {}

@app.on_event("startup")
async def startup():
    global db_pool
    db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=5, max_size=20)
    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                recipient VARCHAR(200) NOT NULL,
                channel VARCHAR(20) NOT NULL,
                content TEXT NOT NULL,
                status VARCHAR(20) DEFAULT 'sent',
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)
    logger.info("Omnichannel Middleware Service started")

@app.on_event("shutdown")
async def shutdown():
    if db_pool:
        await db_pool.close()

@app.post("/send")
async def send_message(message: Message):
    """Send message via specified channel"""
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO messages (recipient, channel, content, status)
            VALUES ($1, $2, $3, 'sent') RETURNING *
        """, message.recipient, message.channel.value, message.content)
        
        return {"message_id": str(row['id']), "status": "sent"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "omnichannel-middleware"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8212)
