"""
Omnichannel Middleware Router
Routes messages across WhatsApp, Telegram, USSD, SMS with unified conversation context
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
import httpx
import os
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/omnichannel-middleware", tags=["omnichannel-middleware"])

WHATSAPP_SERVICE_URL = os.getenv("WHATSAPP_SERVICE_URL", "http://localhost:8140")
TELEGRAM_SERVICE_URL = os.getenv("TELEGRAM_SERVICE_URL", "http://localhost:8159")
USSD_SERVICE_URL = os.getenv("USSD_SERVICE_URL", "http://localhost:8141")
SMS_GATEWAY_URL = os.getenv("SMS_GATEWAY_URL", "http://localhost:8142")
REDIS_URL = os.getenv("REDIS_URL", "")

_redis = None

def _get_redis():
    global _redis
    if _redis is None and REDIS_URL:
        try:
            import redis as _redis_mod
            _redis = _redis_mod.from_url(REDIS_URL, decode_responses=True)
        except Exception:
            pass
    return _redis


class OmniMessage(BaseModel):
    channel: str
    recipient: str
    content: str
    user_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ConversationQuery(BaseModel):
    user_id: str
    limit: int = 50


@router.post("/send")
async def send_message(message: OmniMessage):
    channel = message.channel.lower()
    user_id = message.user_id or message.recipient
    r = _get_redis()

    if channel == "whatsapp":
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(f"{WHATSAPP_SERVICE_URL}/send", json={
                "recipient": message.recipient, "content": message.content, "message_type": "text"
            })
            result = resp.json()
    elif channel == "telegram":
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(f"{TELEGRAM_SERVICE_URL}/send", json={
                "chat_id": int(message.recipient), "text": message.content
            })
            result = resp.json()
    elif channel == "sms":
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(f"{SMS_GATEWAY_URL}/api/v1/sms-gateway/send", json={
                "recipient": message.recipient, "message": message.content
            })
            result = resp.json()
    elif channel == "ussd":
        raise HTTPException(status_code=400, detail="USSD is pull-based; cannot push messages")
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported channel: {channel}")

    if r:
        r.incr(f"omni:sent:{channel}")
        entry = json.dumps({
            "channel": channel, "direction": "outbound", "content": message.content,
            "recipient": message.recipient, "timestamp": datetime.utcnow().isoformat(),
        }, default=str)
        r.lpush(f"omni:context:{user_id}", entry)
        r.ltrim(f"omni:context:{user_id}", 0, 99)
        r.hset(f"omni:user:{user_id}", mapping={
            "last_channel": channel,
            "last_activity": datetime.utcnow().isoformat(),
        })

    return {"status": "sent", "channel": channel, "result": result}


@router.get("/health")
async def health_check():
    r = _get_redis()
    return {
        "status": "healthy",
        "service": "omnichannel-middleware",
        "redis": "connected" if r else "not_configured",
        "channels": ["whatsapp", "telegram", "ussd", "sms"],
    }


@router.get("/context/{user_id}")
async def get_conversation_context(user_id: str, limit: int = 20):
    r = _get_redis()
    if not r:
        return {"user_id": user_id, "messages": [], "note": "Redis not configured"}
    raw = r.lrange(f"omni:context:{user_id}", 0, limit - 1)
    messages = [json.loads(m) for m in raw]
    user_info = r.hgetall(f"omni:user:{user_id}") or {}
    return {
        "user_id": user_id,
        "last_channel": user_info.get("last_channel", "unknown"),
        "last_activity": user_info.get("last_activity", ""),
        "messages": messages,
        "total": len(messages),
    }


@router.get("/channels")
async def list_channels():
    return {"channels": [
        {"name": "whatsapp", "type": "push", "protocol": "Meta Cloud API"},
        {"name": "telegram", "type": "push", "protocol": "Telegram Bot API"},
        {"name": "ussd", "type": "pull", "protocol": "USSD Gateway"},
        {"name": "sms", "type": "push", "protocol": "Africa's Talking / Twilio"},
    ]}


@router.get("/metrics")
async def get_metrics():
    r = _get_redis()
    if not r:
        return {"channels": {}}
    return {
        "whatsapp_sent": int(r.get("omni:sent:whatsapp") or 0),
        "telegram_sent": int(r.get("omni:sent:telegram") or 0),
        "sms_sent": int(r.get("omni:sent:sms") or 0),
        "ussd_sessions": int(r.get("omni:sent:ussd") or 0),
    }

