"""
Communication Gateway Router - Unified omni-channel message routing
Delegates to WhatsApp, Telegram, USSD, SMS channel services
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
import httpx
import os
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/communication-gateway", tags=["communication-gateway"])

WHATSAPP_SERVICE_URL = os.getenv("WHATSAPP_SERVICE_URL", "http://localhost:8140")
TELEGRAM_SERVICE_URL = os.getenv("TELEGRAM_SERVICE_URL", "http://localhost:8159")
USSD_SERVICE_URL = os.getenv("USSD_SERVICE_URL", "http://localhost:8141")
SMS_GATEWAY_URL = os.getenv("SMS_GATEWAY_URL", "http://localhost:8142")
REDIS_URL = os.getenv("REDIS_URL", "")

CHANNEL_URLS = {
    "whatsapp": WHATSAPP_SERVICE_URL,
    "telegram": TELEGRAM_SERVICE_URL,
    "ussd": USSD_SERVICE_URL,
    "sms": SMS_GATEWAY_URL,
}

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


class SendRequest(BaseModel):
    channel: str
    recipient: str
    content: str
    metadata: Optional[Dict[str, Any]] = None


@router.get("/")
async def root():
    return {
        "service": "communication-gateway",
        "version": "2.0.0",
        "channels": list(CHANNEL_URLS.keys()),
        "status": "operational",
    }


@router.get("/health")
async def health_check():
    channel_health = {}
    for ch, url in CHANNEL_URLS.items():
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{url}/health")
                channel_health[ch] = "healthy" if resp.status_code == 200 else "degraded"
        except Exception:
            channel_health[ch] = "unreachable"
    return {"status": "healthy", "channels": channel_health}


async def _dispatch(channel: str, url: str, payload: dict) -> dict:
    """POST to a channel service and FAIL LOUDLY on any failure.

    The previous implementation returned {"status": "sent"} regardless of the
    downstream response code, confirming delivery that never happened.
    """
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload)
    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Channel service '{channel}' unreachable: {e}",
        )
    if resp.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail=f"Channel service '{channel}' rejected the message: HTTP {resp.status_code}: {resp.text[:300]}",
        )
    try:
        return resp.json()
    except ValueError:
        return {"raw": resp.text[:500]}


@router.post("/send")
async def send_message(req: SendRequest):
    channel = req.channel.lower()
    r = _get_redis()

    if channel == "whatsapp":
        result = await _dispatch(channel, f"{WHATSAPP_SERVICE_URL}/send", {
            "recipient": req.recipient, "content": req.content, "message_type": "text"
        })
    elif channel == "telegram":
        try:
            chat_id = int(req.recipient)
        except ValueError:
            raise HTTPException(status_code=400, detail="Telegram recipient must be a numeric chat_id")
        result = await _dispatch(channel, f"{TELEGRAM_SERVICE_URL}/send", {
            "chat_id": chat_id, "text": req.content
        })
    elif channel == "sms":
        result = await _dispatch(channel, f"{SMS_GATEWAY_URL}/api/v1/sms-gateway/send", {
            "recipient": req.recipient, "message": req.content
        })
    elif channel == "ussd":
        raise HTTPException(status_code=400, detail="USSD is pull-based; use /ussd/callback instead")
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported channel: {channel}")

    # Redis bookkeeping happens only after the channel service accepted the
    # message (any failure above raises before this point).
    if r:
        r.incr(f"gateway:sent:{channel}")
        r.lpush(f"gateway:conversation:{req.recipient}", json.dumps({
            "channel": channel, "direction": "outbound", "content": req.content,
            "timestamp": datetime.utcnow().isoformat()
        }, default=str))
        r.ltrim(f"gateway:conversation:{req.recipient}", 0, 99)

    return {"status": "sent", "channel": channel, "result": result}


@router.get("/conversation/{user_id}")
async def get_conversation(user_id: str, limit: int = 20):
    r = _get_redis()
    if not r:
        return {"messages": [], "note": "Redis not configured"}
    raw = r.lrange(f"gateway:conversation:{user_id}", 0, limit - 1)
    messages = [json.loads(m) for m in raw]
    return {"user_id": user_id, "messages": messages, "total": len(messages)}


@router.get("/channels")
async def list_channels():
    return {"channels": [
        {"name": "whatsapp", "protocol": "Meta Cloud API"},
        {"name": "telegram", "protocol": "Telegram Bot API"},
        {"name": "ussd", "protocol": "USSD Gateway (pull)"},
        {"name": "sms", "protocol": "Africa's Talking / Twilio"},
    ]}


@router.get("/metrics")
async def get_metrics():
    r = _get_redis()
    if not r:
        return {"channels": {}}
    metrics = {}
    for ch in CHANNEL_URLS:
        metrics[ch] = int(r.get(f"gateway:sent:{ch}") or 0)
    return {"messages_sent": metrics}


@router.get("/stats")
async def get_statistics():
    return await get_metrics()
