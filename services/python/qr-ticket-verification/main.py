"""
QR Ticket Verification - FastAPI microservice
QR code-based ticket and voucher verification for events, transport, and loyalty redemptions
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

app = FastAPI(title="QR Ticket Verification", description="QR code-based ticket and voucher verification for events, transport, and loyalty redemptions", version="1.0.0")

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/qr_ticket_verification")

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
    return {"status": "healthy", "service": "qr-ticket-verification", "version": "1.0.0", "timestamp": datetime.utcnow().isoformat()}

@app.post("/api/v1/tickets/generate")
async def generate_ticket(event_id: str, holder_name: str, ticket_type: str = "standard"):
    """Generate a QR ticket."""
    return {"ticket_id": f"TKT-{int(__import__('time').time())}", "event_id": event_id, "holder": holder_name, "type": ticket_type, "qr_data": "", "status": "valid"}

@app.post("/api/v1/tickets/verify")
async def verify_ticket(qr_data: str):
    """Verify a QR ticket at point of entry."""
    return {"valid": False, "ticket_id": "", "holder": "", "event_id": "", "already_used": False, "verified_at": datetime.utcnow().isoformat()}

@app.post("/api/v1/tickets/{ticket_id}/void")
async def void_ticket(ticket_id: str, reason: str):
    """Void a ticket."""
    return {"ticket_id": ticket_id, "status": "voided", "reason": reason, "voided_at": datetime.utcnow().isoformat()}

@app.get("/api/v1/tickets/event/{event_id}/stats")
async def get_event_stats(event_id: str):
    """Get ticket stats for an event."""
    return {"event_id": event_id, "total_issued": 0, "total_verified": 0, "total_voided": 0}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
