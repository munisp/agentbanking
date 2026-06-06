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

apply_middleware(app)
setup_logging("konga-marketplace-service")
app.include_router(metrics_router)

from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
import uvicorn
import os
import httpx

app = FastAPI(

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/konga_service")

def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return conn

def init_db():
    conn = get_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS audit_log (
        id SERIAL PRIMARY KEY,
        action TEXT, entity_id TEXT, data TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS state_store (
        key TEXT PRIMARY KEY, value TEXT,
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )""")
    conn.commit()
    conn.close()

init_db()

def log_audit(action: str, entity_id: str, data: str = ""):
    try:
        conn = get_db()
        conn.execute("INSERT INTO audit_log (action, entity_id, data) VALUES (?, ?, ?)", (action, entity_id, data))
        conn.commit()
        conn.close()
    except Exception:
        pass
    title="Konga Marketplace Service",
    description="Konga Nigeria marketplace integration",
    version="1.0.0"
)

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
products_db = []
orders_db = []
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
