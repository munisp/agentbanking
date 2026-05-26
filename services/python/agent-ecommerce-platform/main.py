"""
Agent E-Commerce Platform API - FastAPI microservice
Full e-commerce platform for agents to sell products and services to customers
"""
import os
import sys
import logging
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query, Path
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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

app = FastAPI(
    title="Agent E-Commerce Platform API",
    description="Full e-commerce platform for agents to sell products and services to customers",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    """Service health check endpoint."""
    return {"status": "healthy", "service": "agent-ecommerce-platform", "version": "1.0.0", "timestamp": datetime.utcnow().isoformat()}

@app.get("/api/v1/store/{agent_id}/catalog")
async def get_store_catalog(agent_id: str, category: str = None):
    """Get agent's store product catalog."""
    return {"agent_id": agent_id, "products": [], "categories": [], "total": 0}

@app.post("/api/v1/store/{agent_id}/products")
async def add_product(agent_id: str, name: str, price: float, category: str, stock: int = 0):
    """Add a product to agent's store."""
    if price < 0:
        raise HTTPException(status_code=400, detail="Price must be non-negative")
    return {
        "product_id": f"PRD-{int(__import__('time').time())}",
        "agent_id": agent_id,
        "name": name,
        "price": price,
        "category": category,
        "stock": stock,
        "status": "active",
    }

@app.post("/api/v1/store/checkout")
async def checkout(agent_id: str, customer_phone: str, cart_items: list, payment_method: str = "cash"):
    """Process checkout for a customer purchase."""
    return {
        "order_id": f"ORD-{int(__import__('time').time())}",
        "agent_id": agent_id,
        "customer_phone": customer_phone,
        "items_count": len(cart_items),
        "total": 0.0,
        "payment_method": payment_method,
        "status": "completed",
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
