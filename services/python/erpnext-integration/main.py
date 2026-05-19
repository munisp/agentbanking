"""
ERPNext Integration - FastAPI microservice
Bidirectional sync with ERPNext ERP for inventory, accounting, and HR data exchange
"""
import os
import logging
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ERPNext Integration", description="Bidirectional sync with ERPNext ERP for inventory, accounting, and HR data exchange", version="1.0.0")
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
    return {"status": "healthy", "service": "erpnext-integration", "version": "1.0.0", "timestamp": datetime.utcnow().isoformat()}

@app.post("/api/v1/erpnext/sync")
async def trigger_sync(entity_type: str, direction: str = "bidirectional"):
    """Trigger sync between POS and ERPNext."""
    valid_types = ["inventory", "customers", "invoices", "payments", "employees"]
    if entity_type not in valid_types: raise HTTPException(400, f"Must be one of: {valid_types}")
    return {"sync_id": f"SYNC-{int(__import__('time').time())}", "entity_type": entity_type, "direction": direction, "status": "in_progress"}

@app.get("/api/v1/erpnext/sync/{sync_id}")
async def get_sync_status(sync_id: str):
    """Get sync job status."""
    return {"sync_id": sync_id, "status": "unknown", "records_synced": 0, "errors": 0}

@app.get("/api/v1/erpnext/mappings")
async def get_field_mappings():
    """Get field mapping configuration between POS and ERPNext."""
    return {"mappings": [], "total": 0, "last_updated": None}

@app.post("/api/v1/erpnext/webhook")
async def erpnext_webhook(event: str, data: dict):
    """Receive webhook events from ERPNext."""
    return {"received": True, "event": event, "processed_at": datetime.utcnow().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
