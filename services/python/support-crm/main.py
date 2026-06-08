"""
Support CRM - FastAPI microservice
Customer and agent support ticket management with SLA tracking, escalation, and resolution workflows
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

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/support_crm")

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
    title="Support CRM",
    description="Customer and agent support ticket management with SLA tracking, escalation, and resolution workflows",
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
    return {"status": "healthy", "service": "support-crm", "version": "1.0.0", "timestamp": datetime.utcnow().isoformat()}

@app.post("/api/v1/tickets")
async def create_ticket(subject: str, description: str, priority: str = "medium", category: str = "general"):
    """Create a new support ticket."""
    valid_priorities = ["low", "medium", "high", "critical"]
    if priority not in valid_priorities:
        raise HTTPException(status_code=400, detail=f"Invalid priority. Must be one of: {valid_priorities}")
    return {
        "ticket_id": f"TKT-{int(__import__('time').time())}",
        "subject": subject,
        "description": description,
        "priority": priority,
        "category": category,
        "status": "open",
        "created_at": __import__('datetime').datetime.utcnow().isoformat(),
        "sla_deadline": None,
    }

@app.get("/api/v1/tickets/{ticket_id}")
async def get_ticket(ticket_id: str):
    """Get ticket details with full conversation history."""
    return {"ticket_id": ticket_id, "subject": "", "status": "open", "messages": [], "assignee": None, "sla_status": "within_sla"}

@app.put("/api/v1/tickets/{ticket_id}/assign")
async def assign_ticket(ticket_id: str, assignee_id: str):
    """Assign ticket to a support agent."""
    return {"ticket_id": ticket_id, "assignee_id": assignee_id, "assigned_at": __import__('datetime').datetime.utcnow().isoformat()}

@app.put("/api/v1/tickets/{ticket_id}/escalate")
async def escalate_ticket(ticket_id: str, escalation_level: int, reason: str):
    """Escalate ticket to higher support tier."""
    if escalation_level > 3:
        raise HTTPException(status_code=400, detail="Maximum escalation level is 3")
    return {"ticket_id": ticket_id, "escalation_level": escalation_level, "reason": reason, "escalated_at": __import__('datetime').datetime.utcnow().isoformat()}

@app.put("/api/v1/tickets/{ticket_id}/resolve")
async def resolve_ticket(ticket_id: str, resolution: str, root_cause: str = None):
    """Resolve a support ticket."""
    return {"ticket_id": ticket_id, "status": "resolved", "resolution": resolution, "root_cause": root_cause, "resolved_at": __import__('datetime').datetime.utcnow().isoformat()}

@app.get("/api/v1/tickets")
async def list_tickets(status: str = None, priority: str = None, limit: int = 20, offset: int = 0):
    """List tickets with filtering and pagination."""
    return {"tickets": [], "total": 0, "limit": limit, "offset": offset}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
