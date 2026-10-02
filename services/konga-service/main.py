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
Konga Nigeria marketplace integration
Full marketplace integration with order sync and inventory management
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware


from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
import uvicorn
import os
import httpx

app = FastAPI(
    title="Konga Marketplace Service",
    description="Konga Nigeria marketplace integration",
    version="1.0.0"
)

apply_middleware(app)
setup_logging("konga-marketplace-service")
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
    SELLER_ID = os.getenv("KONGA_SELLER_ID", "demo_seller")
    API_KEY = os.getenv("KONGA_API_KEY", "demo_key")
    API_SECRET = os.getenv("KONGA_API_SECRET", "demo_secret")
    API_BASE_URL = os.getenv("KONGA_API_URL", "https://api.konga.com")

config = Config()

# Models
class Product(BaseModel):
    sku: str
    name: str
    price: float
    quantity: int
    description: Optional[str] = None
    category: Optional[str] = None

class MarketplaceOrder(BaseModel):
    marketplace_order_id: str
    customer_name: str
    customer_email: str
    items: List[Dict[str, Any]]
    total: float
    shipping_address: Dict[str, str]

class InventoryUpdate(BaseModel):
    sku: str
    quantity: int
    operation: str = "set"  # set, add, subtract

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


class _PgListStore:
    """List-compatible store persisted to Postgres (replaces in-memory list)."""

    def __init__(self, table, env):
        if not table.replace("_", "").isalnum():
            raise ValueError("unsafe table name: %r" % table)
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
                "id SERIAL PRIMARY KEY, "
                "data TEXT NOT NULL, "
                "created_at TIMESTAMPTZ NOT NULL DEFAULT now()"
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
        return _r11_json.dumps(_cv(v), default=str)

    @staticmethod
    def _deser(raw):
        return _r11_json.loads(raw)

    def append(self, v):
        async def _a():
            async with self._pool.acquire() as c:
                await c.execute(
                    'INSERT INTO "%s" (data) VALUES ($1)' % self._table,
                    self._ser(v),
                )
        _r11_sync(_a())

    async def _arows(self):
        async with self._pool.acquire() as c:
            return await c.fetch(
                'SELECT id, data FROM "%s" ORDER BY id' % self._table
            )

    def _rows(self):
        return _r11_sync(self._arows())

    def __iter__(self):
        return iter([self._deser(r["data"]) for r in self._rows()])

    def __len__(self):
        async def _n():
            async with self._pool.acquire() as c:
                return await c.fetchval('SELECT COUNT(*) FROM "%s"' % self._table)
        return _r11_sync(_n())

    def __getitem__(self, idx):
        vals = [self._deser(r["data"]) for r in self._rows()]
        return vals[idx]

    def __delitem__(self, idx):
        rows = self._rows()
        targets = rows[idx] if isinstance(idx, slice) else [rows[idx]]
        ids = [r["id"] for r in targets]
        if not ids:
            return
        async def _d():
            async with self._pool.acquire() as c:
                await c.execute(
                    'DELETE FROM "%s" WHERE id = ANY($1::int[])' % self._table, ids
                )
        _r11_sync(_d())

    def clear(self):
        async def _c():
            async with self._pool.acquire() as c:
                await c.execute('DELETE FROM "%s"' % self._table)
        _r11_sync(_c())
products_db = _PgListStore("konga_service_products", "KONGA_SERVICE_DATABASE_URL")
orders_db = _PgListStore("konga_service_orders", "KONGA_SERVICE_DATABASE_URL")
# round-11: channel identity constants (referenced but never defined)
channel_name = os.getenv("CHANNEL_NAME", "konga")
channel_display = os.getenv("CHANNEL_DISPLAY", "Konga")

service_start_time = datetime.now()

@app.get("/")
async def root():
    return {
        "service": "konga-service",
        "marketplace": "Konga",
        "version": "1.0.0",
        "status": "operational",
        "seller_id": config.SELLER_ID
    }

@app.get("/health")
async def health_check():
    uptime = (datetime.now() - service_start_time).total_seconds()
    return {
        "status": "healthy",
        "service": "konga-service",
        "marketplace": "Konga",
        "uptime_seconds": int(uptime),
        "products_listed": len(products_db),
        "orders_processed": len(orders_db)
    }

@app.post("/api/v1/products")
async def list_product(product: Product):
    """List a product on Konga"""
    
    product_data = {
        **product.dict(),
        "marketplace_product_id": f"{channel_name.upper()}-{product.sku}",
        "listed_at": datetime.now(),
        "status": "active"
    }
    
    products_db.append(product_data)
    
    return {
        "marketplace_product_id": product_data["marketplace_product_id"],
        "status": "listed",
        "message": f"Product listed on {channel_display}"
    }

@app.get("/api/v1/products")
async def get_products(status: Optional[str] = None):
    """Get all listed products"""
    filtered = products_db
    if status:
        filtered = [p for p in products_db if p["status"] == status]
    
    return {
        "products": filtered,
        "total": len(filtered),
        "marketplace": "Konga"
    }

@app.put("/api/v1/products/{sku}/inventory")
async def update_inventory(sku: str, update: InventoryUpdate):
    """Update product inventory"""
    
    for product in products_db:
        if product["sku"] == sku:
            if update.operation == "set":
                product["quantity"] = update.quantity
            elif update.operation == "add":
                product["quantity"] += update.quantity
            elif update.operation == "subtract":
                product["quantity"] = max(0, product["quantity"] - update.quantity)
            
            product["last_updated"] = datetime.now()
            
            return {
                "sku": sku,
                "new_quantity": product["quantity"],
                "status": "updated"
            }
    
    raise HTTPException(status_code=404, detail="Product not found")

@app.post("/webhook/orders")
async def order_webhook(request: Request):
    """Receive new orders from Konga"""
    
    order_data = await request.json()
    
    # Process marketplace order
    internal_order_id = f"ORD-{channel_name.upper()}-{int(datetime.now().timestamp())}"
    
    order = {
        "internal_order_id": internal_order_id,
        "marketplace_order_id": order_data.get("order_id"),
        "marketplace": "Konga",
        "customer": order_data.get("customer", {}),
        "items": order_data.get("items", []),
        "total": order_data.get("total", 0),
        "status": "received",
        "received_at": datetime.now()
    }
    
    orders_db.append(order)
    
    # Update inventory
    for item in order["items"]:
        sku = item.get("sku")
        quantity = item.get("quantity", 1)
        
        for product in products_db:
            if product["sku"] == sku:
                product["quantity"] = max(0, product["quantity"] - quantity)
                break
    
    return {
        "internal_order_id": internal_order_id,
        "status": "processed"
    }

@app.get("/api/v1/orders")
async def get_orders(status: Optional[str] = None, limit: int = 50):
    """Get marketplace orders"""
    filtered = orders_db
    if status:
        filtered = [o for o in orders_db if o["status"] == status]
    
    return {
        "orders": filtered[-limit:],
        "total": len(filtered),
        "marketplace": "Konga"
    }

@app.put("/api/v1/orders/{order_id}/status")
async def update_order_status(order_id: str, status: str):
    """Update order status"""
    
    for order in orders_db:
        if order["internal_order_id"] == order_id or order["marketplace_order_id"] == order_id:
            order["status"] = status
            order["updated_at"] = datetime.now()
            
            return {
                "order_id": order_id,
                "new_status": status,
                "message": "Order status updated"
            }
    
    raise HTTPException(status_code=404, detail="Order not found")

@app.get("/api/v1/metrics")
async def get_metrics():
    """Get marketplace metrics"""
    uptime = (datetime.now() - service_start_time).total_seconds()
    
    total_revenue = sum(o["total"] for o in orders_db)
    
    return {
        "marketplace": "Konga",
        "products_listed": len(products_db),
        "active_products": len([p for p in products_db if p["status"] == "active"]),
        "orders_received": len(orders_db),
        "total_revenue": total_revenue,
        "uptime_seconds": int(uptime)
    }

@app.post("/api/v1/sync")
async def sync_with_marketplace():
    """Sync products and orders with Konga"""
    
    # Fetch latest data from Konga API
    return {
        "status": "synced",
        "products_synced": len(products_db),
        "orders_synced": len(orders_db),
        "timestamp": datetime.now()
    }

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8102))
    uvicorn.run(app, host="0.0.0.0", port=port)
