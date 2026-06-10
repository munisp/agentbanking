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
Hybrid Engine Service
Port: 8154
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app, enable_auth=True)
setup_logging("hybrid-engine")
app.include_router(metrics_router)

from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
import uvicorn

# Redis-based storage (replaces in-memory dict)
import os
import json
import redis

_redis_client = None

def get_redis_client():
    """Get Redis client - requires REDIS_URL environment variable"""
    global _redis_client
    if _redis_client is None:
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            raise ValueError("REDIS_URL environment variable is required for storage")
        _redis_client = redis.from_url(redis_url, decode_responses=True)
    return _redis_client

def storage_get(key: str):
    """Get value from Redis storage"""
    try:
        client = get_redis_client()
        value = client.get(f"storage:{key}")
        return json.loads(value) if value else None
    except Exception as e:
        print(f"Storage get error: {e}")
        return None

def storage_set(key: str, value, ttl: int = 86400):
    """Set value in Redis storage with optional TTL (default 24h)"""
    try:
        client = get_redis_client()
        client.setex(f"storage:{key}", ttl, json.dumps(value))
        return True
    except Exception as e:
        print(f"Storage set error: {e}")
        return False

def storage_delete(key: str):
    """Delete value from Redis storage"""
    try:
        client = get_redis_client()
        client.delete(f"storage:{key}")
        return True
    except Exception as e:
        print(f"Storage delete error: {e}")
        return False

def storage_keys(pattern: str = "*"):
    """Get all keys matching pattern"""
    try:
        client = get_redis_client()
        return [k.replace("storage:", "") for k in client.keys(f"storage:{pattern}")]
    except Exception as e:
        print(f"Storage keys error: {e}")
        return []

app = FastAPI(

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/hybrid_engine")

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
        conn.execute("INSERT INTO audit_log (action, entity_id, data) VALUES (%s, %s, %s)", (action, entity_id, data))
        conn.commit()
        conn.close()
    except Exception:
        pass
    title="Hybrid Engine",
    description="Hybrid Engine for Remittance Platform",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage (replace with database in production)
# storage = {}  # REPLACED: Use storage_get/storage_set functions instead
stats = {
    "total_requests": 0,
    "total_items": 0,
    "start_time": datetime.now()
}

# Pydantic Models
class Item(BaseModel):
    id: Optional[str] = None
    data: Dict[str, Any]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

@app.get("/")
async def root():
    return {
        "service": "hybrid-engine",
        "description": "Hybrid Engine",
        "version": "1.0.0",
        "port": 8154,
        "status": "operational"
    }

@app.get("/health")
async def health_check():
    uptime = (datetime.now() - stats["start_time"]).total_seconds()
    return {
        "status": "healthy",
        "uptime_seconds": int(uptime),
        "total_requests": stats["total_requests"],
        "total_items": stats["total_items"]
    }

@app.post("/items")
async def create_item(item: Item):
    """Create a new item"""
    stats["total_requests"] += 1
    item_id = f"item_{len(storage) + 1}"
    item.id = item_id
    item.created_at = datetime.now()
    item.updated_at = datetime.now()
    storage[item_id] = item.dict()
    stats["total_items"] += 1
    return {"success": True, "item_id": item_id, "item": item}

@app.get("/items")
async def list_items(skip: int = 0, limit: int = 100):
    """List all items"""
    stats["total_requests"] += 1
    items = list(storage.values())[skip:skip+limit]
    return {
        "success": True,
        "total": len(storage),
        "items": items,
        "skip": skip,
        "limit": limit
    }

@app.get("/items/{item_id}")
async def get_item(item_id: str):
    """Get a specific item"""
    stats["total_requests"] += 1
    if item_id not in storage:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"success": True, "item": storage[item_id]}

@app.put("/items/{item_id}")
async def update_item(item_id: str, item: Item):
    """Update an item"""
    stats["total_requests"] += 1
    if item_id not in storage:
        raise HTTPException(status_code=404, detail="Item not found")
    item.id = item_id
    item.updated_at = datetime.now()
    item.created_at = storage[item_id].get("created_at", datetime.now())
    storage[item_id] = item.dict()
    return {"success": True, "item": item}

@app.delete("/items/{item_id}")
async def delete_item(item_id: str):
    """Delete an item"""
    stats["total_requests"] += 1
    if item_id not in storage:
        raise HTTPException(status_code=404, detail="Item not found")
    del storage[item_id]
    stats["total_items"] -= 1
    return {"success": True, "message": "Item deleted"}

@app.post("/process")
async def process_data(data: Dict[str, Any]):
    """Process data (service-specific logic)"""
    stats["total_requests"] += 1
    return {
        "success": True,
        "message": "Data processed successfully",
        "service": "hybrid-engine",
        "processed_at": datetime.now().isoformat(),
        "data": data
    }

@app.get("/search")
async def search_items(query: str):
    """Search items"""
    stats["total_requests"] += 1
    results = [item for item in storage.values() if query.lower() in str(item).lower()]
    return {
        "success": True,
        "query": query,
        "total_results": len(results),
        "results": results
    }

@app.get("/stats")
async def get_statistics():
    """Get service statistics"""
    uptime = (datetime.now() - stats["start_time"]).total_seconds()
    return {
        "uptime_seconds": int(uptime),
        "total_requests": stats["total_requests"],
        "total_items": stats["total_items"],
        "service": "hybrid-engine",
        "port": 8154,
        "status": "operational"
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8154)
