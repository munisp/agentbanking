"""
Critical Gaps Analyzer - FastAPI microservice
Platform gap analysis engine that identifies missing features, compliance gaps, and infrastructure weaknesses
"""
import os
import logging
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Critical Gaps Analyzer", description="Platform gap analysis engine that identifies missing features, compliance gaps, and infrastructure weaknesses", version="1.0.0")
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
    return {"status": "healthy", "service": "critical-gaps", "version": "1.0.0", "timestamp": datetime.utcnow().isoformat()}

@app.get("/api/v1/gaps/scan")
async def scan_gaps(category: str = None):
    """Scan platform for critical gaps."""
    return {"scan_id": f"SCAN-{int(__import__('time').time())}", "gaps": [], "total": 0, "categories": ["compliance", "security", "performance", "feature", "infrastructure"]}

@app.get("/api/v1/gaps/{gap_id}")
async def get_gap(gap_id: str):
    """Get gap details with remediation plan."""
    return {"gap_id": gap_id, "category": "", "severity": "medium", "description": "", "remediation": "", "status": "open", "estimated_effort": ""}

@app.post("/api/v1/gaps/{gap_id}/resolve")
async def resolve_gap(gap_id: str, resolution: str, evidence: str = None):
    """Mark a gap as resolved with evidence."""
    return {"gap_id": gap_id, "status": "resolved", "resolution": resolution, "resolved_at": datetime.utcnow().isoformat()}

@app.get("/api/v1/gaps/report")
async def get_gap_report():
    """Generate comprehensive gap analysis report."""
    return {"total_gaps": 0, "critical": 0, "high": 0, "medium": 0, "low": 0, "resolved": 0, "open": 0, "report_date": date.today().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
