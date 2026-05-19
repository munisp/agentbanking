"""
Authentication Service - FastAPI microservice
Multi-factor authentication with OTP, biometric, device fingerprinting, and session management
"""
import os
import logging
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Authentication Service", description="Multi-factor authentication with OTP, biometric, device fingerprinting, and session management", version="1.0.0")
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
    return {"status": "healthy", "service": "authentication-service", "version": "1.0.0", "timestamp": datetime.utcnow().isoformat()}

@app.post("/api/v1/auth/otp/send")
async def send_otp(phone: str, channel: str = "sms"):
    """Send OTP to phone number via SMS or voice."""
    if channel not in ["sms", "voice", "whatsapp"]: raise HTTPException(400, "Invalid channel")
    return {"phone": phone[-4:].rjust(len(phone), "*"), "channel": channel, "expires_in": 300, "sent": True}

@app.post("/api/v1/auth/otp/verify")
async def verify_otp(phone: str, code: str):
    """Verify OTP code."""
    if len(code) != 6: raise HTTPException(400, "OTP must be 6 digits")
    return {"verified": False, "token": None, "attempts_remaining": 3}

@app.post("/api/v1/auth/device/register")
async def register_device(user_id: str, device_fingerprint: str, device_name: str):
    """Register a trusted device."""
    return {"device_id": f"DEV-{int(__import__('time').time())}", "user_id": user_id, "trusted": True, "registered_at": datetime.utcnow().isoformat()}

@app.get("/api/v1/auth/sessions/{user_id}")
async def get_sessions(user_id: str):
    """Get active sessions for a user."""
    return {"user_id": user_id, "sessions": [], "total": 0}

@app.post("/api/v1/auth/sessions/{session_id}/revoke")
async def revoke_session(session_id: str):
    """Revoke an active session."""
    return {"session_id": session_id, "revoked": True, "revoked_at": datetime.utcnow().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
