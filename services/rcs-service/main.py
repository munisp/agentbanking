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
Rich Communication Services
Production-ready service with webhook handling and message processing
"""

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware


from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
import uvicorn
import os
import json
import hmac
import hashlib
import httpx
import asyncio
from enum import Enum

# Shared middleware/observability wiring happens after `app` is created
# further below (the previous ordering raised NameError at import time).
app = FastAPI(
    title="Rcs Service",
    description="Rich Communication Services",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

apply_middleware(app)
setup_logging("rcs-service")
app.include_router(metrics_router)

# Configuration
class Config:
    # No demo defaults: demo credentials previously allowed the service to
    # "send" messages against a fictional provider configuration.
    API_KEY = os.getenv("RCS_API_KEY", "")
    API_SECRET = os.getenv("RCS_API_SECRET", "")
    WEBHOOK_SECRET = os.getenv("RCS_WEBHOOK_SECRET", "")
    API_BASE_URL = os.getenv("RCS_API_URL", "https://api.rcs.com")
    SIMULATION_MODE = os.getenv("RCS_SIMULATION_MODE", "").lower() == "true"
    ENVIRONMENT = os.getenv("ENVIRONMENT", os.getenv("APP_ENV", "development")).lower()

config = Config()

channel_name = "rcs"

if config.SIMULATION_MODE and config.ENVIRONMENT == "production":
    raise RuntimeError(
        "RCS_SIMULATION_MODE=true is forbidden in production. "
        "Configure real RCS provider credentials instead."
    )

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

# In-memory storage (replace with database in production)
messages_db = []
orders_db = []

# Service state
service_start_time = datetime.now()
message_count = 0
order_count = 0

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "rcs-service",
        "channel": "Rcs",
        "version": "1.0.0",
        "description": "Rich Communication Services",
        "status": "operational"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    uptime = (datetime.now() - service_start_time).total_seconds()
    return {
        "status": "healthy",
        "service": "rcs-service",
        "channel": "Rcs",
        "timestamp": datetime.now(),
        "uptime_seconds": int(uptime),
        "messages_sent": message_count,
        "orders_received": order_count
    }

@app.post("/api/v1/send", response_model=MessageResponse)
async def send_message(message: Message, background_tasks: BackgroundTasks):
    """Send a message via the RCS provider API.

    FAIL LOUD: previously every message was stored with status 'sent' without
    contacting any provider. The message is now only accepted after the
    provider confirms acceptance; otherwise a 503/502 is raised.
    """
    global message_count

    if not config.API_KEY:
        if config.SIMULATION_MODE and config.ENVIRONMENT != "production":
            raise HTTPException(
                status_code=503,
                detail="RCS provider is not configured (RCS_API_KEY unset). Simulation mode does not fabricate sends.",
            )
        raise HTTPException(status_code=503, detail="RCS provider is not configured (RCS_API_KEY unset)")

    message_id = f"{channel_name}_{int(datetime.now().timestamp())}_{message_count}"

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{config.API_BASE_URL}/messages",
                headers={"Authorization": f"Bearer {config.API_KEY}"},
                json={
                    "recipient": message.recipient,
                    "type": message.message_type.value,
                    "content": message.content,
                    "metadata": message.metadata or {},
                    "client_message_id": message_id,
                },
            )
    except httpx.HTTPError as e:
        raise HTTPException(status_code=503, detail=f"RCS provider unreachable: {e}")

    if resp.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail=f"RCS provider rejected the message: HTTP {resp.status_code}: {resp.text[:300]}",
        )

    # Store message only after provider acceptance
    messages_db.append({
        "id": message_id,
        "recipient": message.recipient,
        "type": message.message_type,
        "content": message.content,
        "metadata": message.metadata,
        "timestamp": datetime.now(),
        "status": "sent"
    })

    message_count += 1

    # Background task to check delivery status
    background_tasks.add_task(check_delivery_status, message_id)

    return {
        "message_id": message_id,
        "status": "sent",
        "timestamp": datetime.now()
    }

@app.post("/api/v1/order")
async def create_order(order: OrderMessage):
    """Create an order from Rcs message"""
    global order_count
    
    try:
        order_id = f"ORD-{channel_name.upper()}-{int(datetime.now().timestamp())}"
        
        order_data = {
            "order_id": order_id,
            "customer_id": order.customer_id,
            "customer_name": order.customer_name,
            "phone": order.phone,
            "items": order.items,
            "total": order.total,
            "delivery_address": order.delivery_address,
            "channel": "Rcs",
            "status": "pending",
            "created_at": datetime.now()
        }
        
        orders_db.append(order_data)
        order_count += 1
        
        # Send confirmation message
        confirmation = f"✅ Order {order_id} confirmed!\n\nTotal: ${order.total:.2f}\n\nWe'll notify you when it ships."
        
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
        raise HTTPException(status_code=500, detail=f"Failed to create order: {str(e)}")

@app.post("/webhook")
async def webhook_handler(request: Request):
    """Handle incoming webhooks from Rcs"""
    try:
        # Verify webhook signature
        signature = request.headers.get("X-Rcs-Signature", "")
        body = await request.body()
        
        # Verify webhook signature. Previously the expected signature was
        # computed but never compared, so any forged webhook was accepted.
        if not config.WEBHOOK_SECRET:
            raise HTTPException(status_code=503, detail="Webhook secret is not configured")
        expected_signature = hmac.new(
            config.WEBHOOK_SECRET.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        if not signature or not hmac.compare_digest(signature, expected_signature):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

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
    
    total_tracked = len(messages_db)
    delivered = sum(1 for m in messages_db if m["status"] == "delivered")
    failed = sum(1 for m in messages_db if m["status"] == "failed")
    return {
        "channel": "Rcs",
        "messages_sent": message_count,
        "orders_received": order_count,
        "uptime_seconds": int(uptime),
        "messages_tracked": total_tracked,
        "messages_delivered": delivered,
        "messages_failed": failed,
        "delivery_rate": (delivered / total_tracked) if total_tracked > 0 else None,
    }

# Helper functions
async def check_delivery_status(message_id: str):
    """Background task to check message delivery status via provider API"""
    new_status = "sent"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{config.API_BASE_URL}/messages/{message_id}/status",
                headers={"Authorization": f"Bearer {config.API_KEY}"}
            )
            if resp.status_code == 200:
                delivery_data = resp.json()
                new_status = delivery_data.get("status", "sent")
    except Exception:
        new_status = "unknown"
    for msg in messages_db:
        if msg["id"] == message_id:
            msg["status"] = new_status
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
    port = int(os.getenv("PORT", 8093))
    uvicorn.run(app, host="0.0.0.0", port=port)
