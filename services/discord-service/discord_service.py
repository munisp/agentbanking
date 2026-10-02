import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
"""
Discord Order Management Service
Community-based commerce via Discord
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware


from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime
import httpx
import os

app = FastAPI(title="Discord Order Service", version="1.0.0")

apply_middleware(app)
setup_logging("discord-order-service")
app.include_router(metrics_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Discord configuration
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
DISCORD_API_URL = "https://discord.com/api/v10"

# Models
class DiscordOrder(BaseModel):
    guild_id: str
    channel_id: str
    user_id: str
    username: str
    items: List[Dict]
    total: float
    status: str = "pending"

# Storage

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
orders_db = _PgDictStore("discord_orders", "DISCORD_SERVICE_DATABASE_URL", model_name="DiscordOrder")

async def send_discord_message(channel_id: str, content: str = None, embed: Dict = None):
    """Send message to Discord channel"""
    try:
        async with httpx.AsyncClient() as client:
            payload = {}
            if content:
                payload["content"] = content
            if embed:
                payload["embeds"] = [embed]
            
            response = await client.post(
                f"{DISCORD_API_URL}/channels/{channel_id}/messages",
                headers={"Authorization": f"Bot {DISCORD_BOT_TOKEN}"},
                json=payload
            )
            return response.json()
    except Exception as e:
        print(f"Error sending Discord message: {e}")
        return None

def create_product_embed(product: Dict):
    """Create Discord embed for product"""
    return {
        "title": product["name"],
        "description": product["description"],
        "color": 5814783,  # Purple
        "fields": [
            {"name": "Price", "value": f"₦{product['price']:,.0f}", "inline": True},
            {"name": "Stock", "value": str(product["stock"]), "inline": True}
        ],
        "footer": {"text": "Use /order <product_id> <quantity> to order"}
    }

def create_order_confirmation_embed(order_id: str, items: List[Dict], total: float):
    """Create Discord embed for order confirmation"""
    items_text = "\n".join([f"• {item['name']} x{item['quantity']} - ₦{item['price']:,.0f}" for item in items])
    
    return {
        "title": "🎉 Order Confirmed!",
        "description": f"Order ID: `{order_id}`",
        "color": 3066993,  # Green
        "fields": [
            {"name": "Items", "value": items_text},
            {"name": "Total", "value": f"₦{total:,.0f}", "inline": True},
            {"name": "Status", "value": "Processing", "inline": True}
        ],
        "footer": {"text": "Thank you for your order!"}
    }

@app.get("/")
async def root():
    return {"service": "Discord Order Service", "status": "running"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/interactions")
async def handle_interaction(request: Request):
    """Handle Discord interactions (slash commands, buttons)"""
    data = await request.json()
    
    # Handle slash commands
    if data.get("type") == 2:  # APPLICATION_COMMAND
        command_name = data["data"]["name"]
        
        if command_name == "products":
            # Show products
            products = [
                {"id": "1", "name": "Premium Rice (50kg)", "price": 45000, "description": "High-quality rice", "stock": 50},
                {"id": "2", "name": "Cooking Oil (5L)", "price": 8500, "description": "Pure vegetable oil", "stock": 120}
            ]
            
            embeds = [create_product_embed(p) for p in products[:5]]
            
            return {
                "type": 4,  # CHANNEL_MESSAGE_WITH_SOURCE
                "data": {
                    "content": "🛍️ **Available Products**",
                    "embeds": embeds
                }
            }
        
        elif command_name == "order":
            # Create order
            options = {opt["name"]: opt["value"] for opt in data["data"].get("options", [])}
            product_id = options.get("product_id")
            quantity = options.get("quantity", 1)
            
            # Create order
            order_id = f"DC-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            order = DiscordOrder(
                guild_id=data["guild_id"],
                channel_id=data["channel_id"],
                user_id=data["member"]["user"]["id"],
                username=data["member"]["user"]["username"],
                items=[{"name": "Product", "quantity": quantity, "price": 10000}],
                total=10000 * quantity
            )
            orders_db[order_id] = order
            
            embed = create_order_confirmation_embed(order_id, order.items, order.total)
            
            return {
                "type": 4,
                "data": {
                    "embeds": [embed]
                }
            }
    
    return {"type": 1}  # PONG

@app.post("/send-notification/{channel_id}")
async def send_notification(channel_id: str, message: str):
    """Send notification to Discord channel"""
    result = await send_discord_message(channel_id, content=message)
    return {"status": "sent" if result else "failed"}

@app.get("/orders")
async def get_orders():
    """Get all Discord orders"""
    return {"orders": list(orders_db.values()), "count": len(orders_db)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8044)
