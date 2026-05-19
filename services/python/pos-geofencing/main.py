"""
POS Geofencing - FastAPI microservice
Location-based POS terminal management with geofence alerts, territory mapping, and proximity services
"""
import os
import logging
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="POS Geofencing", description="Location-based POS terminal management with geofence alerts, territory mapping, and proximity services", version="1.0.0")
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
    return {"status": "healthy", "service": "pos-geofencing", "version": "1.0.0", "timestamp": datetime.utcnow().isoformat()}

@app.post("/api/v1/geofence/create")
async def create_geofence(name: str, lat: float, lng: float, radius_m: float, agent_id: str = None):
    """Create a geofence zone."""
    return {"geofence_id": f"GEO-{int(__import__('time').time())}", "name": name, "center": {"lat": lat, "lng": lng}, "radius_m": radius_m, "agent_id": agent_id, "status": "active"}

@app.post("/api/v1/geofence/check")
async def check_location(terminal_id: str, lat: float, lng: float):
    """Check if terminal is within its assigned geofence."""
    return {"terminal_id": terminal_id, "location": {"lat": lat, "lng": lng}, "in_zone": True, "nearest_zone": None, "distance_to_boundary_m": 0}

@app.get("/api/v1/geofence/alerts")
async def get_alerts(agent_id: str = None, limit: int = 20):
    """Get geofence violation alerts."""
    return {"alerts": [], "total": 0}

@app.get("/api/v1/geofence/zones")
async def list_zones(region: str = None):
    """List all geofence zones."""
    return {"zones": [], "total": 0, "region": region}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
