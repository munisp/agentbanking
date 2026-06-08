"""
Agent Commerce Integration - FastAPI microservice
E-commerce integration for agent-assisted purchases, marketplace orders, and product catalog management
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

import psycopg2
import psycopg2.extras
import os

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/agent_commerce_integration")

def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return conn

def init_db():
    conn = get_db()
    for stmt in """CREATE TABLE IF NOT EXISTS items (
            id SERIAL PRIMARY KEY,
            name TEXT, status TEXT, data TEXT, created_at TEXT
        )""".split(";"):
        stmt = stmt.strip()
        if stmt:
            conn.execute(stmt)
    conn.commit()
    conn.close()

init_db()

@app.get("/api/v1/items")
async def list_items():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, status, data, created_at FROM items ORDER BY created_at DESC LIMIT 100")
    rows = cursor.fetchall()
    conn.close()
    return {"items": [{"id": r[0], "name": r[1], "status": r[2], "data": r[3], "created_at": r[4]} for r in rows]}

@app.post("/api/v1/items")
async def create_item(request: Request):
    body = await request.json()
    name = body.get("name", "")
    if not name:
        raise HTTPException(status_code=400, detail="Name required")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO items (name, status, data, created_at) VALUES (?, 'active', ?, NOW())",
                   (name, str(body)))
    conn.commit()
    item_id = cursor.fetchone()[0]
    conn.close()
    return {"id": item_id, "name": name, "status": "active"}

@app.get("/api/v1/items/{item_id}")
async def get_item(item_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM items WHERE id = %s", (item_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"id": row[0], "name": row[1], "status": row[2]}

@app.put("/api/v1/items/{item_id}")
async def update_item(item_id: int, request: Request):
    body = await request.json()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE items SET name = %s, status = %s, data = %s WHERE id = %s",
                   (body.get("name", ""), body.get("status", "active"), str(body), item_id))
    conn.commit()
    conn.close()
    return {"id": item_id, "status": "updated"}

@app.delete("/api/v1/items/{item_id}")
async def delete_item(item_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM items WHERE id = %s", (item_id,))
    conn.commit()
    conn.close()
    return {"id": item_id, "status": "deleted"}
    title="Agent Commerce Integration",
    description="E-commerce integration for agent-assisted purchases, marketplace orders, and product catalog management",
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
    return {"status": "healthy", "service": "agent-commerce-integration", "version": "1.0.0", "timestamp": datetime.utcnow().isoformat()}

@app.get("/api/v1/products")
async def list_products(category: str = None, limit: int = 20, offset: int = 0):
    """List available products in the agent marketplace."""
    return {"products": [], "total": 0, "limit": limit, "offset": offset, "category": category}

@app.post("/api/v1/orders")
async def create_order(agent_id: str, customer_phone: str, items: list):
    """Create a new order on behalf of a customer."""
    if not items:
        raise HTTPException(status_code=400, detail="Order must contain at least one item")
    return {
        "order_id": f"ORD-{int(__import__('time').time())}",
        "agent_id": agent_id,
        "customer_phone": customer_phone,
        "items": items,
        "total": 0.0,
        "status": "pending_payment",
        "created_at": __import__('datetime').datetime.utcnow().isoformat(),
    }

@app.get("/api/v1/orders/{order_id}")
async def get_order(order_id: str):
    """Get order details and status."""
    return {"order_id": order_id, "status": "pending", "items": [], "total": 0.0, "tracking": None}

@app.put("/api/v1/orders/{order_id}/fulfill")
async def fulfill_order(order_id: str, tracking_number: str = None):
    """Mark order as fulfilled/shipped."""
    return {"order_id": order_id, "status": "fulfilled", "tracking_number": tracking_number, "fulfilled_at": __import__('datetime').datetime.utcnow().isoformat()}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
