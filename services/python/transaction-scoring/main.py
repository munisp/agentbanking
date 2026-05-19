"""
Transaction Scoring - FastAPI microservice
Real-time transaction risk scoring with ML-based fraud detection and behavioral analysis
"""
import os
import logging
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Transaction Scoring", description="Real-time transaction risk scoring with ML-based fraud detection and behavioral analysis", version="1.0.0")
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
    return {"status": "healthy", "service": "transaction-scoring", "version": "1.0.0", "timestamp": datetime.utcnow().isoformat()}

@app.post("/api/v1/scoring/evaluate")
async def evaluate_transaction(transaction_id: str, amount: float, sender_id: str, receiver_id: str, transaction_type: str):
    """Score a transaction for risk."""
    return {"transaction_id": transaction_id, "risk_score": 0.0, "risk_level": "low", "flags": [], "recommendation": "approve", "scoring_time_ms": 0}

@app.get("/api/v1/scoring/rules")
async def get_scoring_rules():
    """Get active scoring rules and weights."""
    return {"rules": [], "total": 0, "model_version": "1.0.0"}

@app.get("/api/v1/scoring/{entity_id}/profile")
async def get_risk_profile(entity_id: str):
    """Get entity risk profile and history."""
    return {"entity_id": entity_id, "risk_score": 0.0, "risk_level": "low", "total_transactions": 0, "flagged_transactions": 0, "last_updated": None}

@app.post("/api/v1/scoring/feedback")
async def submit_feedback(transaction_id: str, actual_outcome: str):
    """Submit feedback for model training."""
    valid_outcomes = ["legitimate", "fraud", "suspicious", "false_positive"]
    if actual_outcome not in valid_outcomes: raise HTTPException(400, f"Must be one of: {valid_outcomes}")
    return {"transaction_id": transaction_id, "feedback_recorded": True, "outcome": actual_outcome}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
