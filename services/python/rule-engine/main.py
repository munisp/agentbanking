"""
Business Rule Engine - FastAPI microservice
Configurable business rule engine for transaction routing, fee calculation, and compliance checks
"""
import os
import logging
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Business Rule Engine", description="Configurable business rule engine for transaction routing, fee calculation, and compliance checks", version="1.0.0")
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
    return {"status": "healthy", "service": "rule-engine", "version": "1.0.0", "timestamp": datetime.utcnow().isoformat()}

@app.get("/api/v1/rules")
async def list_rules(category: str = None, active: bool = True):
    """List business rules."""
    return {"rules": [], "total": 0, "categories": ["routing", "fee", "compliance", "limit", "fraud"]}

@app.post("/api/v1/rules")
async def create_rule(name: str, category: str, conditions: dict, actions: dict, priority: int = 50):
    """Create a new business rule."""
    return {"rule_id": f"RULE-{int(__import__('time').time())}", "name": name, "category": category, "priority": priority, "status": "active", "created_at": datetime.utcnow().isoformat()}

@app.post("/api/v1/rules/evaluate")
async def evaluate_rules(context: dict, category: str = None):
    """Evaluate rules against a transaction context."""
    return {"matched_rules": [], "actions": [], "evaluation_time_ms": 0}

@app.put("/api/v1/rules/{rule_id}/toggle")
async def toggle_rule(rule_id: str, active: bool):
    """Enable or disable a rule."""
    return {"rule_id": rule_id, "active": active, "updated_at": datetime.utcnow().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
