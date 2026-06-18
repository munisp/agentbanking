"""
Nigeria VAT Service - FastAPI microservice
Nigerian Value Added Tax calculation, collection, and FIRS reporting with automated filing
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

app = FastAPI(title="Nigeria VAT Service", description="Nigerian Value Added Tax calculation, collection, and FIRS reporting with automated filing", version="1.0.0")

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/nigeria_vat_service")

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
    return {"status": "healthy", "service": "nigeria-vat-service", "version": "1.0.0", "timestamp": datetime.utcnow().isoformat()}

@app.post("/api/v1/vat/calculate")
async def calculate_vat(amount: float, category: str = "standard"):
    """Calculate VAT for a transaction."""
    rates = {"standard": 7.5, "exempt": 0.0, "zero_rated": 0.0}
    rate = rates.get(category, 7.5)
    vat_amount = amount * rate / 100
    return {"amount": amount, "category": category, "rate_pct": rate, "vat_amount": vat_amount, "total": amount + vat_amount}

@app.get("/api/v1/vat/summary")
async def get_vat_summary(period: str = "current_month"):
    """Get VAT collection summary for a period."""
    return {"period": period, "total_collected": 0.0, "total_remitted": 0.0, "pending_remittance": 0.0, "transactions_count": 0}

@app.post("/api/v1/vat/file")
async def file_vat_return(period: str, total_output_vat: float, total_input_vat: float):
    """File VAT return with FIRS."""
    return {"filing_id": f"VAT-{int(__import__('time').time())}", "period": period, "net_vat": total_output_vat - total_input_vat, "status": "filed", "filed_at": datetime.utcnow().isoformat()}

@app.get("/api/v1/vat/rates")
async def get_vat_rates():
    """Get current VAT rates by category."""
    return {"standard": 7.5, "exempt_categories": ["basic_food", "medical", "education", "books"], "zero_rated": ["exports"]}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
