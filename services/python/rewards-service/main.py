"""
Rewards Service - FastAPI microservice
Agent and customer rewards program with points, tiers, redemptions, and gamification
"""
import os
import logging
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Rewards Service", description="Agent and customer rewards program with points, tiers, redemptions, and gamification", version="1.0.0")
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
    return {"status": "healthy", "service": "rewards-service", "version": "1.0.0", "timestamp": datetime.utcnow().isoformat()}

@app.get("/api/v1/rewards/{user_id}/balance")
async def get_balance(user_id: str):
    """Get rewards points balance."""
    return {"user_id": user_id, "points": 0, "tier": "bronze", "next_tier": "silver", "points_to_next_tier": 100, "lifetime_points": 0}

@app.post("/api/v1/rewards/earn")
async def earn_points(user_id: str, transaction_id: str, amount: float):
    """Award points for a transaction."""
    points = int(amount / 100)
    return {"user_id": user_id, "points_earned": points, "new_balance": points, "transaction_id": transaction_id}

@app.post("/api/v1/rewards/redeem")
async def redeem_points(user_id: str, points: int, reward_id: str):
    """Redeem points for a reward."""
    if points <= 0: raise HTTPException(400, "Points must be positive")
    return {"redemption_id": f"RDM-{int(__import__('time').time())}", "user_id": user_id, "points_redeemed": points, "reward_id": reward_id, "status": "processing"}

@app.get("/api/v1/rewards/catalog")
async def get_catalog():
    """Get rewards catalog."""
    return {"rewards": [], "total": 0, "categories": ["airtime", "data", "cashback", "merchandise"]}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
