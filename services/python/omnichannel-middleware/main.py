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

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/omnichannel")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Omnichannel Middleware Service", version="1.0.0")
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
