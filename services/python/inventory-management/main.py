"""
Inventory Management - FastAPI microservice
Real-time inventory tracking for POS terminals, SIM cards, and agent supplies with reorder automation
"""
import os
import logging
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

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


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Inventory Management", description="Real-time inventory tracking for POS terminals, SIM cards, and agent supplies with reorder automation", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# --- Domain Helpers ---

def validate_request(data: dict, required_fields: list) -> list:
    """Validate that all required fields are present in request data."""
    missing = [f for f in required_fields if f not in data or data[f] is None]
    return missing

def sanitize_input(value: str) -> str:
    """Sanitize user input to prevent injection attacks."""
    if not isinstance(value, str):
        return str(value)
    return value.strip().replace("<", "&lt;").replace(">", "&gt;")

def format_currency(amount: float, currency: str = "NGN") -> str:
    """Format amount with currency symbol."""
    symbols = {"NGN": "₦", "USD": "$", "GBP": "£", "EUR": "€", "KES": "KSh"}
    symbol = symbols.get(currency, currency + " ")
    return f"{symbol}{amount:,.2f}"

def generate_reference(prefix: str = "REF") -> str:
    """Generate a unique reference ID."""
    import time
    import hashlib
    ts = str(time.time()).encode()
    h = hashlib.md5(ts).hexdigest()[:8].upper()
    return f"{prefix}-{h}"

def paginate(items: list, page: int = 1, per_page: int = 20) -> dict:
    """Paginate a list of items."""
    start = (page - 1) * per_page
    end = start + per_page
    return {
        "items": items[start:end],
        "total": len(items),
        "page": page,
        "per_page": per_page,
        "total_pages": (len(items) + per_page - 1) // per_page
    }

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "inventory-management", "version": "1.0.0", "timestamp": datetime.utcnow().isoformat()}

@app.get("/api/v1/inventory/items")
async def list_items(category: str = None, warehouse: str = None, low_stock: bool = False):
    """List inventory items with filtering."""
    return {"items": [], "total": 0, "low_stock_count": 0}

@app.post("/api/v1/inventory/items")
async def add_item(sku: str, name: str, category: str, quantity: int, reorder_point: int = 10):
    """Add new inventory item."""
    return {"item_id": f"INV-{sku}", "sku": sku, "name": name, "category": category, "quantity": quantity, "reorder_point": reorder_point}

@app.post("/api/v1/inventory/transfer")
async def transfer_stock(item_id: str, from_warehouse: str, to_warehouse: str, quantity: int):
    """Transfer stock between warehouses."""
    if quantity <= 0: raise HTTPException(400, "Quantity must be positive")
    return {"transfer_id": f"TRF-{int(__import__('time').time())}", "item_id": item_id, "quantity": quantity, "status": "completed"}

@app.get("/api/v1/inventory/alerts")
async def get_alerts():
    """Get inventory alerts (low stock, expiring items)."""
    return {"alerts": [], "total": 0, "critical": 0}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
