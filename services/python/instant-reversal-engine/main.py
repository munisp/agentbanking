"""
Instant Reversal Engine - FastAPI microservice
Real-time transaction reversal with automated validation, approval workflows, and settlement adjustment
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

app = FastAPI(title="Instant Reversal Engine", description="Real-time transaction reversal with automated validation, approval workflows, and settlement adjustment", version="1.0.0")
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
    return {"status": "healthy", "service": "instant-reversal-engine", "version": "1.0.0", "timestamp": datetime.utcnow().isoformat()}

@app.post("/api/v1/reversals/initiate")
async def initiate_reversal(transaction_id: str, reason: str, amount: float = None):
    """Initiate a transaction reversal."""
    valid_reasons = ["customer_request", "duplicate", "fraud", "error", "timeout", "failed_delivery"]
    if reason not in valid_reasons: raise HTTPException(400, f"Must be one of: {valid_reasons}")
    return {"reversal_id": f"REV-{transaction_id}", "transaction_id": transaction_id, "reason": reason, "amount": amount, "status": "pending_validation", "created_at": datetime.utcnow().isoformat()}

@app.get("/api/v1/reversals/{reversal_id}")
async def get_reversal(reversal_id: str):
    """Get reversal status and details."""
    return {"reversal_id": reversal_id, "status": "unknown", "original_amount": 0.0, "reversal_amount": 0.0, "approval_status": None}

@app.post("/api/v1/reversals/{reversal_id}/approve")
async def approve_reversal(reversal_id: str, approver_id: str):
    """Approve a pending reversal."""
    return {"reversal_id": reversal_id, "approved_by": approver_id, "status": "approved", "approved_at": datetime.utcnow().isoformat()}

@app.get("/api/v1/reversals")
async def list_reversals(status: str = None, limit: int = 20):
    """List reversals with filtering."""
    return {"reversals": [], "total": 0, "status": status}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
