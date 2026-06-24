"""
Knowledge base and FAQ service
"""

from fastapi import APIRouter, Depends, HTTPException, status
import sys as _sys2, os as _os2
_sys2.path.insert(0, _os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse

# --- PostgreSQL Persistence ---
import asyncpg
from typing import Optional

_pg_pool: Optional[asyncpg.Pool] = None

async def get_pg_pool() -> Optional[asyncpg.Pool]:
    global _pg_pool
    if _pg_pool is None:
        try:
            _pg_pool = await asyncpg.create_pool(
                dsn=os.environ.get("DATABASE_URL", "postgresql://localhost:5432/agentbanking"),
                min_size=2, max_size=10, command_timeout=10
            )
            await _pg_pool.execute("""
                CREATE TABLE IF NOT EXISTS service_state (
                    key TEXT PRIMARY KEY,
                    value JSONB NOT NULL DEFAULT '{}',
                    service TEXT NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
        except Exception:
            _pg_pool = None
    return _pg_pool

async def pg_get(key: str, service: str):
    pool = await get_pg_pool()
    if pool:
        row = await pool.fetchrow(
            "SELECT value FROM service_state WHERE key = $1 AND service = $2", key, service
        )
        return row["value"] if row else None
    return None

async def pg_set(key: str, value, service: str):
    pool = await get_pg_pool()
    if pool:
        import json
        await pool.execute(
            "INSERT INTO service_state (key, value, service, updated_at) VALUES ($1, $2::jsonb, $3, NOW()) "
            "ON CONFLICT (key) DO UPDATE SET value = $2::jsonb, updated_at = NOW()",
            key, json.dumps(value) if not isinstance(value, str) else value, service
        )
# --- End PostgreSQL Persistence ---


@router.get("/health")
async def health_check():
    return {"status": "ok", "service": "knowledge-base", "timestamp": datetime.utcnow().isoformat()}

from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

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

router = APIRouter(prefix="/knowledgebase", tags=["knowledge-base"])

# Pydantic models
class KnowledgebaseBase(BaseModel):
    """Base model for knowledge-base."""
    pass

class KnowledgebaseCreate(BaseModel):
    """Create model for knowledge-base."""
    name: str
    description: Optional[str] = None

class KnowledgebaseResponse(BaseModel):
    """Response model for knowledge-base."""
    id: int
    name: str
    description: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True

# API endpoints
@router.post("/", response_model=KnowledgebaseResponse, status_code=status.HTTP_201_CREATED)
async def create(data: KnowledgebaseCreate):
    """Create new knowledge-base record."""
    # Implementation here
    return {"id": 1, "name": data.name, "description": data.description, "created_at": datetime.now(), "updated_at": None}

@router.get("/{id}", response_model=KnowledgebaseResponse)
async def get_by_id(id: int):
    """Get knowledge-base by ID."""
    # Implementation here
    return {"id": id, "name": "Sample", "description": "Sample description", "created_at": datetime.now(), "updated_at": None}

@router.get("/", response_model=List[KnowledgebaseResponse])
async def list_all(skip: int = 0, limit: int = 100):
    """List all knowledge-base records."""
    # Implementation here
    return []

@router.put("/{id}", response_model=KnowledgebaseResponse)
async def update(id: int, data: KnowledgebaseCreate):
    """Update knowledge-base record."""
    # Implementation here
    return {"id": id, "name": data.name, "description": data.description, "created_at": datetime.now(), "updated_at": datetime.now()}

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(id: int):
    """Delete knowledge-base record."""
    # Implementation here
    return None

import psycopg2
import psycopg2.extras
import os

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/knowledge_base")

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
    cursor.execute("INSERT INTO items (name, status, data, created_at) VALUES (%s, 'active', %s, NOW())",
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
