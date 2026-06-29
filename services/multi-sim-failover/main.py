"""
Multi-SIM Failover - FastAPI microservice
Automatic SIM card failover for POS terminals with signal monitoring and carrier switching
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

app = FastAPI(title="Multi-SIM Failover", description="Automatic SIM card failover for POS terminals with signal monitoring and carrier switching", version="1.0.0")
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
    return {"status": "healthy", "service": "multi-sim-failover", "version": "1.0.0", "timestamp": datetime.utcnow().isoformat()}

@app.get("/api/v1/sim/{terminal_id}/status")
async def get_sim_status(terminal_id: str):
    """Get SIM status for all slots in a terminal."""
    return {"terminal_id": terminal_id, "active_sim": 1, "sims": [], "failover_enabled": True}

@app.post("/api/v1/sim/{terminal_id}/switch")
async def switch_sim(terminal_id: str, target_slot: int, reason: str = "manual"):
    """Switch active SIM to specified slot."""
    if target_slot not in [1, 2, 3]: raise HTTPException(400, "Slot must be 1, 2, or 3")
    return {"terminal_id": terminal_id, "previous_slot": 1, "new_slot": target_slot, "reason": reason, "switched_at": datetime.utcnow().isoformat()}

@app.get("/api/v1/sim/{terminal_id}/signal-history")
async def get_signal_history(terminal_id: str, hours: int = 24):
    """Get signal strength history for failover analysis."""
    return {"terminal_id": terminal_id, "hours": hours, "data_points": [], "avg_signal": 0}

@app.post("/api/v1/sim/failover-policy")
async def set_failover_policy(terminal_id: str, min_signal: int = -90, max_retries: int = 3):
    """Configure failover policy for a terminal."""
    return {"terminal_id": terminal_id, "min_signal_dbm": min_signal, "max_retries": max_retries, "policy_updated": True}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
