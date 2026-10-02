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
Amazon-eBay Integration Service
Integrates Remittance Platform with Amazon and eBay marketplaces
"""
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware


from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
import os
from enum import Enum

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Amazon-eBay Integration Service",
    description="Integration service for Amazon and eBay marketplaces",
    version="1.0.0"
)

apply_middleware(app)
setup_logging("amazon-ebay-integration-service")
app.include_router(metrics_router)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
class Config:
    AMAZON_API_KEY = os.getenv("AMAZON_API_KEY", "")
    AMAZON_SECRET_KEY = os.getenv("AMAZON_SECRET_KEY", "")
    EBAY_API_KEY = os.getenv("EBAY_API_KEY", "")
    EBAY_SECRET_KEY = os.getenv("EBAY_SECRET_KEY", "")
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./amazon_ebay.db")

config = Config()

# Enums
class MarketplaceType(str, Enum):
    AMAZON = "amazon"
    EBAY = "ebay"

class ListingStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    SOLD = "sold"

# Models
class Product(BaseModel):
    id: Optional[str] = None
    agent_id: str
    title: str
    description: str
    price: float
    quantity: int
    category: str
    images: List[str] = []
    marketplace: MarketplaceType
    status: ListingStatus = ListingStatus.PENDING
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class ProductListing(BaseModel):
    product_id: str
    marketplace: MarketplaceType
    listing_id: str
    status: ListingStatus
    views: int = 0
    favorites: int = 0
    sales: int = 0

class Order(BaseModel):
    id: Optional[str] = None
    product_id: str
    marketplace: MarketplaceType
    buyer_id: str
    quantity: int
    total_amount: float
    status: str
    order_date: datetime
    shipping_address: Dict[str, Any]

class SyncRequest(BaseModel):
    agent_id: str
    marketplace: MarketplaceType
    product_ids: Optional[List[str]] = None

class AnalyticsResponse(BaseModel):
    total_listings: int
    active_listings: int
    total_sales: int
    total_revenue: float
    amazon_stats: Dict[str, Any]
    ebay_stats: Dict[str, Any]

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
products_db = _PgDictStore("amazon_ebay_products", "AMAZON_EBAY_DATABASE_URL", model_name="Product")
listings_db = _PgDictStore("amazon_ebay_listings", "AMAZON_EBAY_DATABASE_URL", model_name="ProductListing")
orders_db = _PgDictStore("amazon_ebay_orders", "AMAZON_EBAY_DATABASE_URL", model_name="Order")

# API Endpoints

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "amazon-ebay-integration",
        "timestamp": datetime.utcnow().isoformat(),
        "amazon_connected": bool(config.AMAZON_API_KEY),
        "ebay_connected": bool(config.EBAY_API_KEY)
    }

@app.post("/products", response_model=Product)
async def create_product(product: Product):
    """Create a new product for marketplace listing"""
    try:
        product.id = f"prod_{len(products_db) + 1}"
        product.created_at = datetime.utcnow()
        product.updated_at = datetime.utcnow()
        
        products_db[product.id] = product
        
        logger.info(f"Created product {product.id} for agent {product.agent_id}")
        return product
    except Exception as e:
        logger.error(f"Error creating product: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/products", response_model=List[Product])
async def list_products(
    agent_id: Optional[str] = None,
    marketplace: Optional[MarketplaceType] = None,
    status: Optional[ListingStatus] = None
):
    """List products with optional filters"""
    try:
        products = list(products_db.values())
        
        if agent_id:
            products = [p for p in products if p.agent_id == agent_id]
        if marketplace:
            products = [p for p in products if p.marketplace == marketplace]
        if status:
            products = [p for p in products if p.status == status]
        
        return products
    except Exception as e:
        logger.error(f"Error listing products: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/products/{product_id}", response_model=Product)
async def get_product(product_id: str):
    """Get a specific product"""
    if product_id not in products_db:
        raise HTTPException(status_code=404, detail="Product not found")
    return products_db[product_id]

@app.put("/products/{product_id}", response_model=Product)
async def update_product(product_id: str, product: Product):
    """Update a product"""
    if product_id not in products_db:
        raise HTTPException(status_code=404, detail="Product not found")
    
    product.id = product_id
    product.updated_at = datetime.utcnow()
    products_db[product_id] = product
    
    logger.info(f"Updated product {product_id}")
    return product

@app.delete("/products/{product_id}")
async def delete_product(product_id: str):
    """Delete a product"""
    if product_id not in products_db:
        raise HTTPException(status_code=404, detail="Product not found")
    
    del products_db[product_id]
    logger.info(f"Deleted product {product_id}")
    return {"message": "Product deleted successfully"}

@app.post("/listings/publish")
async def publish_listing(product_id: str, marketplace: MarketplaceType):
    """Publish a product to a marketplace"""
    try:
        if product_id not in products_db:
            raise HTTPException(status_code=404, detail="Product not found")
        
        product = products_db[product_id]
        
        # Simulate marketplace API call
        listing_id = f"{marketplace.value}_{product_id}_{len(listings_db) + 1}"
        
        listing = ProductListing(
            product_id=product_id,
            marketplace=marketplace,
            listing_id=listing_id,
            status=ListingStatus.ACTIVE
        )
        
        listings_db[listing_id] = listing
        product.status = ListingStatus.ACTIVE
        
        logger.info(f"Published product {product_id} to {marketplace.value}")
        
        return {
            "message": "Product published successfully",
            "listing_id": listing_id,
            "marketplace": marketplace.value
        }
    except Exception as e:
        logger.error(f"Error publishing listing: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/sync")
async def sync_marketplace(sync_request: SyncRequest):
    """Sync products with marketplace"""
    try:
        synced_products = []
        
        if sync_request.product_ids:
            products = [products_db.get(pid) for pid in sync_request.product_ids if pid in products_db]
        else:
            products = [p for p in products_db.values() if p.agent_id == sync_request.agent_id]
        
        for product in products:
            if product and product.marketplace == sync_request.marketplace:
                # Simulate sync operation
                product.updated_at = datetime.utcnow()
                synced_products.append(product.id)
        
        logger.info(f"Synced {len(synced_products)} products for agent {sync_request.agent_id}")
        
        return {
            "message": "Sync completed",
            "synced_count": len(synced_products),
            "synced_products": synced_products
        }
    except Exception as e:
        logger.error(f"Error syncing marketplace: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/orders", response_model=List[Order])
async def list_orders(
    agent_id: Optional[str] = None,
    marketplace: Optional[MarketplaceType] = None
):
    """List orders from marketplaces"""
    try:
        orders = list(orders_db.values())
        
        if marketplace:
            orders = [o for o in orders if o.marketplace == marketplace]
        
        # Filter by agent_id through products
        if agent_id:
            agent_product_ids = [p.id for p in products_db.values() if p.agent_id == agent_id]
            orders = [o for o in orders if o.product_id in agent_product_ids]
        
        return orders
    except Exception as e:
        logger.error(f"Error listing orders: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/analytics/{agent_id}", response_model=AnalyticsResponse)
async def get_analytics(agent_id: str):
    """Get marketplace analytics for an agent"""
    try:
        agent_products = [p for p in products_db.values() if p.agent_id == agent_id]
        agent_product_ids = [p.id for p in agent_products]
        agent_orders = [o for o in orders_db.values() if o.product_id in agent_product_ids]
        
        amazon_products = [p for p in agent_products if p.marketplace == MarketplaceType.AMAZON]
        ebay_products = [p for p in agent_products if p.marketplace == MarketplaceType.EBAY]
        
        amazon_orders = [o for o in agent_orders if o.marketplace == MarketplaceType.AMAZON]
        ebay_orders = [o for o in agent_orders if o.marketplace == MarketplaceType.EBAY]
        
        return AnalyticsResponse(
            total_listings=len(agent_products),
            active_listings=len([p for p in agent_products if p.status == ListingStatus.ACTIVE]),
            total_sales=len(agent_orders),
            total_revenue=sum(o.total_amount for o in agent_orders),
            amazon_stats={
                "listings": len(amazon_products),
                "sales": len(amazon_orders),
                "revenue": sum(o.total_amount for o in amazon_orders)
            },
            ebay_stats={
                "listings": len(ebay_products),
                "sales": len(ebay_orders),
                "revenue": sum(o.total_amount for o in ebay_orders)
            }
        )
    except Exception as e:
        logger.error(f"Error getting analytics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/webhooks/amazon")
async def amazon_webhook(data: Dict[str, Any]):
    """Handle Amazon marketplace webhooks"""
    try:
        logger.info(f"Received Amazon webhook: {data.get('event_type')}")
        
        # Process webhook based on event type
        event_type = data.get("event_type")
        
        if event_type == "order_created":
            # Create order in system
            pass
        elif event_type == "inventory_update":
            # Update inventory
            pass
        
        return {"message": "Webhook processed successfully"}
    except Exception as e:
        logger.error(f"Error processing Amazon webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/webhooks/ebay")
async def ebay_webhook(data: Dict[str, Any]):
    """Handle eBay marketplace webhooks"""
    try:
        logger.info(f"Received eBay webhook: {data.get('event_type')}")
        
        # Process webhook based on event type
        event_type = data.get("event_type")
        
        if event_type == "order_created":
            # Create order in system
            pass
        elif event_type == "inventory_update":
            # Update inventory
            pass
        
        return {"message": "Webhook processed successfully"}
    except Exception as e:
        logger.error(f"Error processing eBay webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)

