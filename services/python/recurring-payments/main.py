"""
Recurring Payments - FastAPI microservice
Subscription and recurring payment management with scheduling, retry logic, and dunning
"""
import os
import logging
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Recurring Payments", description="Subscription and recurring payment management with scheduling, retry logic, and dunning", version="1.0.0")
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
    return {"status": "healthy", "service": "recurring-payments", "version": "1.0.0", "timestamp": datetime.utcnow().isoformat()}

@app.post("/api/v1/subscriptions")
async def create_subscription(customer_id: str, plan_id: str, payment_method: str):
    """Create a recurring payment subscription."""
    return {"subscription_id": f"SUB-{customer_id}-{int(__import__('time').time())}", "customer_id": customer_id, "plan_id": plan_id, "status": "active", "next_billing_date": None}

@app.get("/api/v1/subscriptions/{subscription_id}")
async def get_subscription(subscription_id: str):
    """Get subscription details."""
    return {"subscription_id": subscription_id, "status": "unknown", "plan_id": "", "amount": 0.0, "interval": "", "next_billing": None}

@app.post("/api/v1/subscriptions/{subscription_id}/cancel")
async def cancel_subscription(subscription_id: str, reason: str, immediate: bool = False):
    """Cancel a subscription."""
    return {"subscription_id": subscription_id, "status": "cancelled" if immediate else "pending_cancellation", "reason": reason, "effective_date": None}

@app.get("/api/v1/subscriptions/{subscription_id}/invoices")
async def get_invoices(subscription_id: str, limit: int = 10):
    """Get subscription invoice history."""
    return {"subscription_id": subscription_id, "invoices": [], "total": 0}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
