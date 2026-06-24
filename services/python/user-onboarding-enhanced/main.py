from typing import Any, Dict, List, Optional, Union, Tuple

import logging
from fastapi import FastAPI, Request, status
import sys as _sys2, os as _os2
_sys2.path.insert(0, _os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from config import settings
from database import init_db
from router import router as onboarding_router # Assuming router.py will define a router named 'router'

# --- Production: Graceful Shutdown ---
import signal
import sys
import atexit
import logging

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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize database tables
init_db()

app = FastAPI(

import psycopg2
import psycopg2.extras
import os

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/user_onboarding_enhanced")
apply_middleware(app, enable_auth=True)

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
    # Load persisted state from PostgreSQL
    _pg_cached = await pg_get("list_items", "user-onboarding-enhanced")
    if _pg_cached is not None:
        import json as _json
        try:
            return _json.loads(_pg_cached) if isinstance(_pg_cached, str) else _pg_cached
        except Exception:
            pass

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, status, data, created_at FROM items ORDER BY created_at DESC LIMIT 100")
    rows = cursor.fetchall()
    conn.close()
    return {"items": [{"id": r[0], "name": r[1], "status": r[2], "data": r[3], "created_at": r[4]} for r in rows]}

@app.post("/api/v1/items")
async def create_item(request: Request):
    # Persist operation result to PostgreSQL
    import json as _json, time as _time
    await pg_set("create_item_" + str(int(_time.time() * 1000)), _json.dumps({"action": "create_item", "timestamp": _time.time()}), "user-onboarding-enhanced")

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
    # Load persisted state from PostgreSQL
    _pg_cached = await pg_get("get_item", "user-onboarding-enhanced")
    if _pg_cached is not None:
        import json as _json
        try:
            return _json.loads(_pg_cached) if isinstance(_pg_cached, str) else _pg_cached
        except Exception:
            pass

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
    # Persist operation result to PostgreSQL
    import json as _json, time as _time
    await pg_set("update_item_" + str(int(_time.time() * 1000)), _json.dumps({"action": "update_item", "timestamp": _time.time()}), "user-onboarding-enhanced")

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
    # Persist operation result to PostgreSQL
    import json as _json, time as _time
    await pg_set("delete_item_" + str(int(_time.time() * 1000)), _json.dumps({"action": "delete_item", "timestamp": _time.time()}), "user-onboarding-enhanced")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM items WHERE id = %s", (item_id,))
    conn.commit()
    conn.close()
    return {"id": item_id, "status": "deleted"}

@app.get("/health")
async def health():
    return {"status": "ok", "service": "user-onboarding-enhanced"}

    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="FastAPI service for Enhanced User Onboarding with KYC and Document Verification.",
)

# --- CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Custom Exception Handler (Example) ---
class UserOnboardingException(Exception):
    def __init__(self, name: str, status_code: int, detail: str) -> None:
        self.name = name
        self.status_code = status_code
        self.detail = detail

@app.exception_handler(UserOnboardingException)
async def custom_exception_handler(request: Request, exc: UserOnboardingException) -> None:
    logger.error(f"Custom Exception: {exc.name} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"message": exc.detail, "name": exc.name},
    )

# --- Root Endpoint ---
@app.get("/", tags=["Health Check"])
def read_root() -> Dict[str, Any]:
    # Load persisted state from PostgreSQL
    _pg_cached = await pg_get("read_root", "user-onboarding-enhanced")
    if _pg_cached is not None:
        import json as _json
        try:
            return _json.loads(_pg_cached) if isinstance(_pg_cached, str) else _pg_cached
        except Exception:
            pass

    return {"message": "User Onboarding Enhanced Service is running."}

# --- Include Routers ---
app.include_router(onboarding_router, prefix="/api/v1/onboarding", tags=["Onboarding"])

# --- Startup/Shutdown Events ---
@app.on_event("startup")
async def _init_pg_pool():
    await get_pg_pool()

@app.on_event("startup")
async def startup_event() -> None:
    logger.info(f"{settings.PROJECT_NAME} starting up...")

@app.on_event("shutdown")
async def shutdown_event() -> None:
    logger.info(f"{settings.PROJECT_NAME} shutting down...")

# Note: In a real application, we would also add authentication middleware here.
# For this task, we will handle authentication logic within the service/router layer.