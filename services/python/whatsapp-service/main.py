import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
import uvicorn
import os
import json
import httpx
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CHANNEL_NAME = "whatsapp"
WHATSAPP_API_URL = os.getenv("WHATSAPP_API_URL", "https://graph.facebook.com/v18.0")
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID", "")
WHATSAPP_WEBHOOK_VERIFY_TOKEN = os.getenv("WHATSAPP_WEBHOOK_VERIFY_TOKEN", "agent_banking_verify")
REDIS_URL = os.getenv("REDIS_URL", "")

app = FastAPI(
    title="WhatsApp Service",
    description="WhatsApp Business API integration with Meta Cloud API",
    version="2.0.0"
)

from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
apply_middleware(app)
setup_logging("whatsapp-service")
app.include_router(metrics_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

def _store_message(msg_data: dict):
    r = _get_redis()
    if r:
        key = f"wa:msg:{msg_data['id']}"
        r.setex(key, 86400, json.dumps(msg_data, default=str))
        r.lpush("wa:messages", msg_data["id"])
        r.ltrim("wa:messages", 0, 9999)

def _get_messages(limit: int = 50) -> list:
    r = _get_redis()
    if r:
        ids = r.lrange("wa:messages", 0, limit - 1)
        msgs = []
        for mid in ids:
            data = r.get(f"wa:msg:{mid}")
            if data:
                msgs.append(json.loads(data))
        return msgs
    return []

def _store_order(order_data: dict):
    r = _get_redis()
    if r:
        key = f"wa:order:{order_data['order_id']}"
        r.setex(key, 604800, json.dumps(order_data, default=str))
        r.lpush("wa:orders", order_data["order_id"])
        r.ltrim("wa:orders", 0, 9999)

def _get_orders(limit: int = 50) -> list:
    r = _get_redis()
    if r:
        ids = r.lrange("wa:orders", 0, limit - 1)
        orders = []
        for oid in ids:
            data = r.get(f"wa:order:{oid}")
            if data:
                orders.append(json.loads(data))
        return orders
    return []

def _incr_counter(name: str) -> int:
    r = _get_redis()
    if r:
        return r.incr(f"wa:counter:{name}")
    return 0


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


async def _send_via_meta_api(recipient: str, content: str, msg_type: str = "text") -> dict:
    if not WHATSAPP_ACCESS_TOKEN or not WHATSAPP_PHONE_ID:
        logger.warning("WhatsApp API credentials not configured, message queued locally")
        return {"status": "queued_locally", "whatsapp_id": None}

    url = f"{WHATSAPP_API_URL}/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    if msg_type == "template":
        payload = {
            "messaging_product": "whatsapp",
            "to": recipient,
            "type": "template",
            "template": {"name": content, "language": {"code": "en"}},
        }
    else:
        payload = {
            "messaging_product": "whatsapp",
            "to": recipient,
            "type": "text",
            "text": {"body": content},
        }

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code in (200, 201):
            data = resp.json()
            wa_id = data.get("messages", [{}])[0].get("id", "")
            return {"status": "sent", "whatsapp_id": wa_id}
        else:
            logger.error(f"Meta API error {resp.status_code}: {resp.text}")
            raise HTTPException(status_code=502, detail=f"WhatsApp API error: {resp.status_code}")


@app.get("/")
async def root():
    return {
        "service": "whatsapp-service",
        "channel": CHANNEL_NAME,
        "version": "2.0.0",
        "status": "operational",
        "provider": "Meta Cloud API",
    }

@app.get("/health")
async def health_check():
    r = _get_redis()
    return {
        "status": "healthy",
        "service": "whatsapp-service",
        "redis": "connected" if r else "not_configured",
        "meta_api": "configured" if WHATSAPP_ACCESS_TOKEN else "not_configured",
    }

@app.post("/api/v1/send")
async def send_message(message: Message):
    count = _incr_counter("messages_sent")
    message_id = f"{CHANNEL_NAME}_{int(datetime.now().timestamp())}_{count}"

    api_result = await _send_via_meta_api(message.recipient, message.content, message.message_type)

    msg_data = {
        "id": message_id,
        "recipient": message.recipient,
        "content": message.content,
        "type": message.message_type,
        "timestamp": datetime.now().isoformat(),
        "status": api_result["status"],
        "whatsapp_id": api_result.get("whatsapp_id"),
    }
    _store_message(msg_data)

    return {
        "message_id": message_id,
        "status": api_result["status"],
        "whatsapp_id": api_result.get("whatsapp_id"),
        "timestamp": datetime.now().isoformat(),
    }

@app.post("/send")
async def send_message_simple(message: Message):
    return await send_message(message)

@app.post("/api/v1/order")
async def create_order(order: OrderMessage):
    count = _incr_counter("orders")
    order_id = f"ORD-{CHANNEL_NAME.upper()}-{int(datetime.now().timestamp())}-{count}"

    confirmation_text = (
        f"Order {order_id} confirmed!\n"
        f"Customer: {order.customer_name}\n"
        f"Items: {len(order.items)}\n"
        f"Total: NGN {order.total:,.2f}\n"
        f"Thank you for your order."
    )
    try:
        await _send_via_meta_api(order.phone, confirmation_text)
    except Exception as e:
        logger.warning(f"Could not send order confirmation via WhatsApp: {e}")

    order_data = {
        "order_id": order_id,
        "customer_id": order.customer_id,
        "customer_name": order.customer_name,
        "phone": order.phone,
        "items": order.items,
        "total": order.total,
        "channel": CHANNEL_NAME,
        "status": "confirmed",
        "created_at": datetime.now().isoformat(),
    }
    _store_order(order_data)
    return order_data

@app.get("/api/v1/messages")
async def get_messages(limit: int = 50):
    msgs = _get_messages(limit)
    return {"messages": msgs, "total": len(msgs)}

@app.get("/api/v1/orders")
async def get_orders(limit: int = 50):
    orders = _get_orders(limit)
    return {"orders": orders, "total": len(orders)}

@app.get("/api/v1/metrics")
async def get_metrics():
    r = _get_redis()
    sent = int(r.get("wa:counter:messages_sent") or 0) if r else 0
    orders_count = int(r.get("wa:counter:orders") or 0) if r else 0
    return {
        "channel": CHANNEL_NAME,
        "messages_sent": sent,
        "orders_received": orders_count,
        "provider": "meta_cloud_api",
        "api_configured": bool(WHATSAPP_ACCESS_TOKEN),
    }

@app.post("/webhook")
async def webhook_handler(request: Request):
    params = request.query_params
    if params.get("hub.mode") == "subscribe":
        if params.get("hub.verify_token") == WHATSAPP_WEBHOOK_VERIFY_TOKEN:
            return int(params.get("hub.challenge", "0"))
        raise HTTPException(status_code=403, detail="Invalid verify token")

    body = await request.json()
    logger.info("WhatsApp webhook event received")

    entries = body.get("entry", [])
    for entry in entries:
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for msg in value.get("messages", []):
                sender = msg.get("from", "")
                text = msg.get("text", {}).get("body", "")
                logger.info(f"Incoming message from {sender}: {text[:50]}")
                _store_message({
                    "id": f"in_{msg.get('id', '')}",
                    "recipient": "self",
                    "content": text,
                    "type": "incoming",
                    "timestamp": datetime.now().isoformat(),
                    "status": "received",
                    "sender": sender,
                })
            for st in value.get("statuses", []):
                logger.info(f"Status update: {st.get('id')} -> {st.get('status')}")

    return {"status": "processed"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
