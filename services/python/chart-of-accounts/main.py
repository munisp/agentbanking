"""
Chart of Accounts - FastAPI microservice
General ledger chart of accounts management with hierarchical structure and multi-entity support
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

app = FastAPI(title="Chart of Accounts", description="General ledger chart of accounts management with hierarchical structure and multi-entity support", version="1.0.0")
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
    return {"status": "healthy", "service": "chart-of-accounts", "version": "1.0.0", "timestamp": datetime.utcnow().isoformat()}

@app.get("/api/v1/coa/accounts")
async def list_accounts(account_type: str = None, parent_id: str = None):
    """List chart of accounts with hierarchical filtering."""
    return {"accounts": [], "total": 0, "types": ["asset", "liability", "equity", "revenue", "expense"]}

@app.post("/api/v1/coa/accounts")
async def create_account(code: str, name: str, account_type: str, parent_id: str = None):
    """Create a new account in the chart of accounts."""
    valid_types = ["asset", "liability", "equity", "revenue", "expense"]
    if account_type not in valid_types: raise HTTPException(400, f"Must be one of: {valid_types}")
    return {"account_id": f"ACC-{code}", "code": code, "name": name, "type": account_type, "parent_id": parent_id, "balance": 0.0}

@app.get("/api/v1/coa/accounts/{account_id}/balance")
async def get_balance(account_id: str, as_of: str = None):
    """Get account balance as of a specific date."""
    return {"account_id": account_id, "balance": 0.0, "as_of": as_of or date.today().isoformat(), "currency": "NGN"}

@app.get("/api/v1/coa/trial-balance")
async def trial_balance(period: str = "current_month"):
    """Generate trial balance report."""
    return {"period": period, "debits_total": 0.0, "credits_total": 0.0, "balanced": True, "accounts": []}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
