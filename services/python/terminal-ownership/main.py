"""
Terminal Ownership Registry - FastAPI microservice
POS terminal lifecycle management: provisioning, assignment, transfer, and decommissioning
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

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/terminal_ownership")

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
    title="Terminal Ownership Registry",
    description="POS terminal lifecycle management: provisioning, assignment, transfer, and decommissioning",
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
    return {"status": "healthy", "service": "terminal-ownership", "version": "1.0.0", "timestamp": datetime.utcnow().isoformat()}

@app.post("/api/v1/terminals/provision")
async def provision_terminal(serial_number: str, model: str, agent_id: str = None):
    """Provision a new POS terminal."""
    return {
        "terminal_id": f"TRM-{serial_number[-6:]}",
        "serial_number": serial_number,
        "model": model,
        "status": "provisioned",
        "assigned_to": agent_id,
        "provisioned_at": __import__('datetime').datetime.utcnow().isoformat(),
    }

@app.get("/api/v1/terminals/{terminal_id}")
async def get_terminal(terminal_id: str):
    """Get terminal details and current assignment."""
    return {
        "terminal_id": terminal_id,
        "serial_number": "",
        "model": "",
        "status": "active",
        "assigned_to": None,
        "firmware_version": "",
        "last_transaction": None,
        "battery_level": None,
        "location": None,
    }

@app.post("/api/v1/terminals/{terminal_id}/transfer")
async def transfer_terminal(terminal_id: str, from_agent: str, to_agent: str, reason: str = ""):
    """Transfer terminal ownership between agents."""
    return {
        "transfer_id": f"TXF-{terminal_id}-{int(__import__('time').time())}",
        "terminal_id": terminal_id,
        "from_agent": from_agent,
        "to_agent": to_agent,
        "reason": reason,
        "status": "completed",
        "transferred_at": __import__('datetime').datetime.utcnow().isoformat(),
    }

@app.post("/api/v1/terminals/{terminal_id}/decommission")
async def decommission_terminal(terminal_id: str, reason: str):
    """Decommission a terminal (end of life, damaged, lost)."""
    valid_reasons = ["end_of_life", "damaged", "lost", "stolen", "recalled"]
    if reason not in valid_reasons:
        raise HTTPException(status_code=400, detail=f"Invalid reason. Must be one of: {valid_reasons}")
    return {
        "terminal_id": terminal_id,
        "status": "decommissioned",
        "reason": reason,
        "decommissioned_at": __import__('datetime').datetime.utcnow().isoformat(),
    }

@app.get("/api/v1/terminals")
async def list_terminals(status: str = None, agent_id: str = None, limit: int = 20, offset: int = 0):
    """List terminals with filtering."""
    return {"terminals": [], "total": 0, "limit": limit, "offset": offset}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
