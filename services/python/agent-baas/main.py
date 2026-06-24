"""
Agent Banking-as-a-Service - FastAPI microservice
Agent BaaS platform for managing agent banking operations, float management, and commission disbursement
"""
import os
import sys
import logging
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query, Path
import sys as _sys2, os as _os2
_sys2.path.insert(0, _os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/agent_baas")

@app.on_event("startup")
async def _init_pg_pool():
    await get_pg_pool()

apply_middleware(app, enable_auth=True)

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
    title="Agent Banking-as-a-Service",
    description="Agent BaaS platform for managing agent banking operations, float management, and commission disbursement",
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
    return {"status": "healthy", "service": "agent-baas", "version": "1.0.0", "timestamp": datetime.utcnow().isoformat()}

@app.get("/api/v1/agents/{agent_id}/float")
async def get_agent_float(agent_id: str):
    """Get agent float balance and allocation details."""
    # Load persisted state from PostgreSQL
    _pg_cached = await pg_get("get_agent_float", "agent-baas")
    if _pg_cached is not None:
        import json as _json
        try:
            return _json.loads(_pg_cached) if isinstance(_pg_cached, str) else _pg_cached
        except Exception:
            pass

    return {
        "agent_id": agent_id,
        "float_balance": 0.0,
        "allocated": 0.0,
        "available": 0.0,
        "currency": "NGN",
        "last_topup": None,
        "daily_limit": 500000.0,
        "daily_used": 0.0,
    }

@app.post("/api/v1/agents/{agent_id}/float/topup")
async def topup_float(agent_id: str, amount: float, source: str = "bank_transfer"):
    """Process float top-up for an agent."""
    # Persist operation result to PostgreSQL
    import json as _json, time as _time
    await pg_set("topup_float_" + str(int(_time.time() * 1000)), _json.dumps({"action": "topup_float", "timestamp": _time.time()}), "agent-baas")

    if amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")
    if amount > 1000000:
        raise HTTPException(status_code=400, detail="Amount exceeds single topup limit of 1,000,000")
    return {
        "agent_id": agent_id,
        "amount": amount,
        "source": source,
        "status": "pending",
        "reference": f"FT-{agent_id}-{int(__import__('time').time())}",
        "estimated_completion": "2-5 minutes",
    }

@app.get("/api/v1/agents/{agent_id}/commissions")
async def get_commissions(agent_id: str, period: str = "current_month"):
    """Get agent commission summary for a period."""
    # Load persisted state from PostgreSQL
    _pg_cached = await pg_get("get_commissions", "agent-baas")
    if _pg_cached is not None:
        import json as _json
        try:
            return _json.loads(_pg_cached) if isinstance(_pg_cached, str) else _pg_cached
        except Exception:
            pass

    return {
        "agent_id": agent_id,
        "period": period,
        "total_earned": 0.0,
        "total_paid": 0.0,
        "pending": 0.0,
        "breakdown": {
            "cash_in": 0.0,
            "cash_out": 0.0,
            "bill_payment": 0.0,
            "transfer": 0.0,
        },
    }

@app.post("/api/v1/agents/{agent_id}/kyc/verify")
async def verify_agent_kyc(agent_id: str, document_type: str, document_number: str):
    """Submit agent KYC verification request."""
    # Persist operation result to PostgreSQL
    import json as _json, time as _time
    await pg_set("verify_agent_kyc_" + str(int(_time.time() * 1000)), _json.dumps({"action": "verify_agent_kyc", "timestamp": _time.time()}), "agent-baas")

    valid_types = ["bvn", "nin", "passport", "drivers_license", "voters_card"]
    if document_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Invalid document type. Must be one of: {valid_types}")
    return {
        "agent_id": agent_id,
        "document_type": document_type,
        "verification_id": f"KYC-{agent_id}-{int(__import__('time').time())}",
        "status": "submitted",
        "estimated_completion": "24-48 hours",
    }

@app.get("/api/v1/agents/{agent_id}/transactions")
async def get_agent_transactions(agent_id: str, limit: int = 20, offset: int = 0):
    """Get agent transaction history with pagination."""
    # Load persisted state from PostgreSQL
    _pg_cached = await pg_get("get_agent_transactions", "agent-baas")
    if _pg_cached is not None:
        import json as _json
        try:
            return _json.loads(_pg_cached) if isinstance(_pg_cached, str) else _pg_cached
        except Exception:
            pass

    return {
        "agent_id": agent_id,
        "transactions": [],
        "total": 0,
        "limit": limit,
        "offset": offset,
        "has_more": False,
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
