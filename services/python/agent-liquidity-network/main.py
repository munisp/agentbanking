"""
Agent Liquidity Network - FastAPI microservice
Peer-to-peer liquidity sharing between agents for float optimization and emergency fund access
"""
import os
import logging
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Agent Liquidity Network", description="Peer-to-peer liquidity sharing between agents for float optimization and emergency fund access", version="1.0.0")
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
    return {"status": "healthy", "service": "agent-liquidity-network", "version": "1.0.0", "timestamp": datetime.utcnow().isoformat()}

@app.get("/api/v1/liquidity/pools")
async def list_pools(region: str = None):
    """List active liquidity pools by region."""
    return {"pools": [], "total": 0, "region": region}

@app.post("/api/v1/liquidity/request")
async def request_liquidity(agent_id: str, amount: float, urgency: str = "normal"):
    """Request emergency float from liquidity network."""
    if amount <= 0: raise HTTPException(400, "Amount must be positive")
    if amount > 500000: raise HTTPException(400, "Max single request is 500,000")
    return {"request_id": f"LIQ-{agent_id}-{int(__import__('time').time())}", "agent_id": agent_id, "amount": amount, "urgency": urgency, "status": "matching", "estimated_fill_time": "2-5 minutes"}

@app.post("/api/v1/liquidity/offer")
async def offer_liquidity(agent_id: str, amount: float, interest_rate: float = 0.5):
    """Offer excess float to the liquidity network."""
    return {"offer_id": f"OFF-{agent_id}-{int(__import__('time').time())}", "agent_id": agent_id, "amount": amount, "interest_rate": interest_rate, "status": "active"}

@app.get("/api/v1/liquidity/{agent_id}/history")
async def get_history(agent_id: str, limit: int = 20):
    """Get agent's liquidity transaction history."""
    return {"agent_id": agent_id, "transactions": [], "total_borrowed": 0.0, "total_lent": 0.0, "net_interest": 0.0}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
