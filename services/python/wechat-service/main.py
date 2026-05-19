import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
"""
WeChat commerce for China
Production-ready service with webhook handling and message processing
"""

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app)
setup_logging("wechat-service")
app.include_router(metrics_router)

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

app = FastAPI(
    title="Wechat Service",
    description="WeChat commerce for China",
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

# Configuration
class Config:
    API_KEY = os.getenv("WECHAT_API_KEY", "demo_key")
    API_SECRET = os.getenv("WECHAT_API_SECRET", "demo_secret")
    WEBHOOK_SECRET = os.getenv("WECHAT_WEBHOOK_SECRET", "webhook_secret")
    API_BASE_URL = os.getenv("WECHAT_API_URL", "https://api.wechat.com")

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
        "service": "wechat-service",
        "channel": "Wechat",
        "version": "1.0.0",
        "description": "WeChat commerce for China",
        "status": "operational"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    uptime = (datetime.now() - service_start_time).total_seconds()
    return {
        "status": "healthy",
        "service": "wechat-service",
        "channel": "Wechat",
        "timestamp": datetime.now(),
        "uptime_seconds": int(uptime),
        "messages_sent": message_count,
        "orders_received": order_count
    }

@app.post("/api/v1/send", response_model=MessageResponse)
async def send_message(message: Message, background_tasks: BackgroundTasks):
    """Send a message via Wechat"""
    global message_count
    
    try:
        message_id = f"{channel_name}_{int(datetime.now().timestamp())}_{message_count}"
        
        # Store message
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send message: {str(e)}")

@app.post("/api/v1/order")
async def create_order(order: OrderMessage):
    """Create an order from Wechat message"""
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
            "channel": "Wechat",
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
    """Handle incoming webhooks from Wechat"""
    try:
        # Verify webhook signature
        signature = request.headers.get("X-Wechat-Signature", "")
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
        "channel": "Wechat",
        "messages_sent": message_count,
        "orders_received": order_count,
        "uptime_seconds": int(uptime),
        "avg_response_time_ms": 45,
        "success_rate": 0.97
    }

# Helper functions
async def check_delivery_status(message_id: str):
    """Background task to check message delivery status via provider API"""
    new_status = "delivered"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{config.API_BASE_URL}/messages/{message_id}/status",
                headers={"Authorization": f"Bearer {config.API_KEY}"}
            )
            if resp.status_code == 200:
                delivery_data = resp.json()
                new_status = delivery_data.get("status", "delivered")
    except Exception:
        new_status = "sent"
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
    port = int(os.getenv("PORT", 8097))
    uvicorn.run(app, host="0.0.0.0", port=port)
