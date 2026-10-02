import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
"""
WhatsApp Order Management Service
Handles WhatsApp-based order processing, messaging, and automation
"""

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware


from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import json
import httpx
import os

app = FastAPI(title="WhatsApp Order Service", version="1.0.0")

# Shared middleware/observability wiring (must run after `app` exists; the
# previous ordering raised NameError at import time).
apply_middleware(app)
setup_logging("whatsapp-order-service")
app.include_router(metrics_router)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class OrderStatus(str, Enum):
    NEW = "new"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"

class MessageSender(str, Enum):
    CUSTOMER = "customer"
    STORE = "store"
    SYSTEM = "system"

class OrderItem(BaseModel):
    name: str
    quantity: int
    price: float
    sku: Optional[str] = None

class Customer(BaseModel):
    name: str
    phone: str
    avatar: str
    email: Optional[str] = None

class Message(BaseModel):
    sender: MessageSender
    text: str
    time: str
    timestamp: datetime = datetime.now()

class WhatsAppOrder(BaseModel):
    id: str
    customer: Customer
    items: List[OrderItem]
    total: float
    status: OrderStatus
    time: str
    messages: List[Message] = []
    created_at: datetime = datetime.now()
    updated_at: datetime = datetime.now()

class QuickActionRequest(BaseModel):
    order_id: str
    action: str
    custom_message: Optional[str] = None

class SendMessageRequest(BaseModel):
    order_id: str
    message: str

# In-memory storage (replace with database in production)

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
orders_db = _PgDictStore("whatsapp_orders", "WHATSAPP_ORDER_DATABASE_URL", model_name="WhatsAppOrder")
stats_db = {
    "todayOrders": 0,
    "pendingResponses": 0,
    "conversionRate": 0.0,
    "revenue": 0.0,
    "avgResponseTime": 0.0
}

# WebSocket connections for real-time updates
active_connections: List[WebSocket] = []

# WhatsApp API configuration
WHATSAPP_API_URL = os.getenv("WHATSAPP_API_URL", "https://graph.facebook.com/v17.0")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID", "")

# Helper Functions
async def send_whatsapp_message(phone: str, message: str) -> bool:
    """Send WhatsApp message via Meta Business API"""
    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_ID:
        print("WHATSAPP_TOKEN/WHATSAPP_PHONE_ID not configured; cannot send WhatsApp message")
        return False
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{WHATSAPP_API_URL}/{WHATSAPP_PHONE_ID}/messages",
                headers={
                    "Authorization": f"Bearer {WHATSAPP_TOKEN}",
                    "Content-Type": "application/json"
                },
                json={
                    "messaging_product": "whatsapp",
                    "to": phone.replace("+", ""),
                    "type": "text",
                    "text": {"body": message}
                }
            )
            return response.status_code == 200
    except Exception as e:
        print(f"Error sending WhatsApp message: {e}")
        return False

async def broadcast_update(data: dict):
    """Broadcast updates to all connected WebSocket clients"""
    for connection in active_connections:
        try:
            await connection.send_json(data)
        except:
            active_connections.remove(connection)

def calculate_stats():
    """Calculate real-time statistics"""
    today = datetime.now().date()
    today_orders = [o for o in orders_db.values() if o.created_at.date() == today]
    
    stats_db["todayOrders"] = len(today_orders)
    stats_db["pendingResponses"] = len([o for o in orders_db.values() if o.status == OrderStatus.NEW])
    stats_db["revenue"] = sum(o.total for o in today_orders)
    
    # Calculate conversion rate (simplified)
    total_conversations = len(orders_db)
    completed_orders = len([o for o in orders_db.values() if o.status in [OrderStatus.DELIVERED, OrderStatus.SHIPPED]])
    stats_db["conversionRate"] = (completed_orders / total_conversations * 100) if total_conversations > 0 else 0
    
    # Calculate average response time (simplified)
    response_times = []
    for order in orders_db.values():
        if len(order.messages) >= 2:
            first_msg = order.messages[0]
            second_msg = order.messages[1]
            if first_msg.sender == MessageSender.CUSTOMER and second_msg.sender == MessageSender.STORE:
                time_diff = (second_msg.timestamp - first_msg.timestamp).total_seconds() / 60
                response_times.append(time_diff)
    
    stats_db["avgResponseTime"] = sum(response_times) / len(response_times) if response_times else 0

# API Endpoints

@app.get("/")
async def root():
    return {"service": "WhatsApp Order Service", "status": "running", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/orders")
async def get_orders(status: Optional[str] = None):
    """Get all orders, optionally filtered by status"""
    filtered_orders = list(orders_db.values())
    
    if status and status != "all":
        filtered_orders = [o for o in filtered_orders if o.status == status]
    
    # Sort by created_at descending
    filtered_orders.sort(key=lambda x: x.created_at, reverse=True)
    
    return {
        "orders": [order.dict() for order in filtered_orders],
        "count": len(filtered_orders)
    }

@app.get("/orders/{order_id}")
async def get_order(order_id: str):
    """Get specific order by ID"""
    if order_id not in orders_db:
        raise HTTPException(status_code=404, detail="Order not found")
    
    return orders_db[order_id].dict()

@app.post("/orders")
async def create_order(order: WhatsAppOrder):
    """Create a new order"""
    if order.id in orders_db:
        raise HTTPException(status_code=400, detail="Order ID already exists")
    
    orders_db[order.id] = order
    calculate_stats()
    
    # Broadcast new order to connected clients
    await broadcast_update({
        "type": "new_order",
        "order": order.dict()
    })
    
    return {"message": "Order created successfully", "order_id": order.id}

@app.put("/orders/{order_id}/status")
async def update_order_status(order_id: str, status: OrderStatus):
    """Update order status"""
    if order_id not in orders_db:
        raise HTTPException(status_code=404, detail="Order not found")
    
    order = orders_db[order_id]
    old_status = order.status
    order.status = status
    order.updated_at = datetime.now()
    orders_db[order_id] = order  # round-11: write back mutation
    
    calculate_stats()
    
    # Broadcast status update
    await broadcast_update({
        "type": "status_update",
        "order_id": order_id,
        "old_status": old_status,
        "new_status": status
    })
    
    return {"message": "Status updated successfully", "order_id": order_id, "status": status}

@app.post("/orders/{order_id}/messages")
async def add_message(order_id: str, message_req: SendMessageRequest):
    """Add a message to an order"""
    if order_id not in orders_db:
        raise HTTPException(status_code=404, detail="Order not found")
    
    order = orders_db[order_id]
    
    message = Message(
        sender=MessageSender.STORE,
        text=message_req.message,
        time=datetime.now().strftime("%H:%M"),
        timestamp=datetime.now()
    )
    
    # Send via WhatsApp FIRST and fail loudly if the provider rejects it;
    # previously the API reported "Message sent successfully" even when the
    # WhatsApp send failed or WHATSAPP_TOKEN was not configured.
    sent = await send_whatsapp_message(order.customer.phone, message_req.message)
    if not sent:
        raise HTTPException(
            status_code=503,
            detail="WhatsApp message could not be delivered (provider unreachable or not configured)",
        )

    order.messages.append(message)
    order.updated_at = datetime.now()
    orders_db[order_id] = order  # round-11: write back mutation

    # Broadcast message
    await broadcast_update({
        "type": "new_message",
        "order_id": order_id,
        "message": message.dict()
    })
    
    return {"message": "Message sent successfully"}

@app.post("/orders/{order_id}/quick-action")
async def execute_quick_action(order_id: str, action_req: QuickActionRequest):
    """Execute a quick action on an order"""
    if order_id not in orders_db:
        raise HTTPException(status_code=404, detail="Order not found")
    
    order = orders_db[order_id]
    
    # round-11 wave-3: no fabricated rider/contact/bank details — everything
    # customer-facing comes from env-configured merchant settlement/contact
    # settings; unset values omit the section instead of sending fake data.
    store_contact = os.getenv("STORE_SUPPORT_CONTACT", "").strip()
    tracking_base = os.getenv("ORDER_TRACKING_BASE_URL", "").rstrip("/")
    pay_bank = os.getenv("MERCHANT_BANK_NAME", "").strip()
    pay_acct = os.getenv("MERCHANT_ACCOUNT_NUMBER", "").strip()
    pay_name = os.getenv("MERCHANT_ACCOUNT_NAME", "").strip()

    ship_lines = [f"📦 Your order is on the way!\n\nOrder #{order_id}"]
    if store_contact:
        ship_lines.append(f"Store contact: {store_contact}")
    if tracking_base:
        ship_lines.append(f"Track your order: {tracking_base}/{order_id}")
    tracking_lines = ["🚚 Track your order:"]
    if tracking_base:
        tracking_lines.append(f"{tracking_base}/{order_id}")
    else:
        tracking_lines.append("Your tracking link will be shared once dispatch is confirmed.")
    payment_lines = [f"💳 Payment Request\n\nOrder #{order_id}\nAmount: ₦{order.total:,.0f}"]
    if pay_bank and pay_acct and pay_name:
        payment_lines.append(f"Transfer to:\nBank: {pay_bank}\nAccount: {pay_acct}\nName: {pay_name}")
    else:
        payment_lines.append("Please request the store's current payment details before transferring.")

    # Define quick action messages
    action_messages = {
        "confirm": f"✅ Order confirmed! We're preparing your items.\n\nOrder #{order_id}\nTotal: ₦{order.total:,.0f}\n\nEstimated ready time: 20 minutes.",
        "ship": "\n".join(ship_lines),
        "tracking": "\n".join(tracking_lines),
        "payment": "\n".join(payment_lines),
        "info": "📋 Please provide the following information:\n• Full delivery address\n• Preferred delivery time\n• Any special instructions",
        "cancel": f"❌ Order Cancelled\n\nOrder #{order_id} has been cancelled.\n\nReason: {action_req.custom_message or 'Customer request'}\n\nRefund will be processed within 24 hours if payment was made."
    }
    
    # Get message for action
    message_text = action_messages.get(action_req.action, action_req.custom_message or "Action completed")
    
    # Update order status based on action
    status_updates = {
        "confirm": OrderStatus.PROCESSING,
        "ship": OrderStatus.SHIPPED,
        "cancel": OrderStatus.CANCELLED
    }
    
    if action_req.action in status_updates:
        order.status = status_updates[action_req.action]
    
    # Add message
    message = Message(
        sender=MessageSender.STORE,
        text=message_text,
        time=datetime.now().strftime("%H:%M"),
        timestamp=datetime.now()
    )
    
    # Send via WhatsApp FIRST and fail loudly on provider failure; previously
    # success was reported even when the send failed.
    sent = await send_whatsapp_message(order.customer.phone, message_text)
    if not sent:
        raise HTTPException(
            status_code=503,
            detail="WhatsApp message could not be delivered (provider unreachable or not configured)",
        )

    order.messages.append(message)
    order.updated_at = datetime.now()
    orders_db[order_id] = order  # round-11: write back mutation

    calculate_stats()
    
    # Broadcast update
    await broadcast_update({
        "type": "quick_action",
        "order_id": order_id,
        "action": action_req.action,
        "status": order.status
    })
    
    return {"message": f"Quick action '{action_req.action}' executed successfully"}

@app.get("/stats")
async def get_stats():
    """Get real-time statistics"""
    calculate_stats()
    return stats_db

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await websocket.accept()
    active_connections.append(websocket)
    
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        active_connections.remove(websocket)

# Webhook endpoint for receiving WhatsApp messages
@app.post("/webhook/whatsapp")
async def whatsapp_webhook(data: dict):
    """Handle incoming WhatsApp messages"""
    try:
        # Parse WhatsApp webhook data
        entry = data.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])
        
        for msg in messages:
            phone = msg.get("from")
            text = msg.get("text", {}).get("body", "")
            
            # Find or create order for this customer
            customer_orders = [o for o in orders_db.values() if o.customer.phone == f"+{phone}"]
            
            if customer_orders:
                # Add message to most recent order
                order = customer_orders[0]
                message = Message(
                    sender=MessageSender.CUSTOMER,
                    text=text,
                    time=datetime.now().strftime("%H:%M"),
                    timestamp=datetime.now()
                )
                order.messages.append(message)
                order.updated_at = datetime.now()
                orders_db[order.id] = order  # round-11: write back mutation
                
                # Broadcast new message
                await broadcast_update({
                    "type": "customer_message",
                    "order_id": order.id,
                    "message": message.dict()
                })
        
        return {"status": "success"}
    except Exception as e:
        print(f"Webhook error: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/webhook/whatsapp")
async def verify_webhook(hub_mode: str, hub_verify_token: str, hub_challenge: str):
    """Verify WhatsApp webhook"""
    verify_token = os.getenv("WHATSAPP_VERIFY_TOKEN", "your_verify_token")
    
    if hub_mode == "subscribe" and hub_verify_token == verify_token:
        return int(hub_challenge)
    
    raise HTTPException(status_code=403, detail="Verification failed")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8040)
