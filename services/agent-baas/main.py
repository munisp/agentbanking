"""
Agent Banking-as-a-Service - FastAPI microservice
Agent BaaS platform for managing agent banking operations, float management, and commission disbursement
"""
import os
import sys
import logging
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query, Path
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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

app = FastAPI(
    title="Agent Banking-as-a-Service",
    description="Agent BaaS platform for managing agent banking operations, float management, and commission disbursement",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    """Service health check endpoint."""
    return {"status": "healthy", "service": "agent-baas", "version": "1.0.0", "timestamp": datetime.utcnow().isoformat()}

@app.get("/api/v1/agents/{agent_id}/float")
async def get_agent_float(agent_id: str):
    """Get agent float balance and allocation details."""
    return {
        "agent_id": agent_id,
        "float_balance": 0.0,
        "allocated": 0.0,
        "available": 0.0,
        "currency": "NGN",
        "last_topup": None,
        "daily_limit": 500000.0,
        "daily_used": 0.0,
    }

@app.post("/api/v1/agents/{agent_id}/float/topup")
async def topup_float(agent_id: str, amount: float, source: str = "bank_transfer"):
    """Process float top-up for an agent."""
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")
    if amount > 1000000:
        raise HTTPException(status_code=400, detail="Amount exceeds single topup limit of 1,000,000")
    return {
        "agent_id": agent_id,
        "amount": amount,
        "source": source,
        "status": "pending",
        "reference": f"FT-{agent_id}-{int(__import__('time').time())}",
        "estimated_completion": "2-5 minutes",
    }

@app.get("/api/v1/agents/{agent_id}/commissions")
async def get_commissions(agent_id: str, period: str = "current_month"):
    """Get agent commission summary for a period."""
    return {
        "agent_id": agent_id,
        "period": period,
        "total_earned": 0.0,
        "total_paid": 0.0,
        "pending": 0.0,
        "breakdown": {
            "cash_in": 0.0,
            "cash_out": 0.0,
            "bill_payment": 0.0,
            "transfer": 0.0,
        },
    }

@app.post("/api/v1/agents/{agent_id}/kyc/verify")
async def verify_agent_kyc(agent_id: str, document_type: str, document_number: str):
    """Submit agent KYC verification request."""
    valid_types = ["bvn", "nin", "passport", "drivers_license", "voters_card"]
    if document_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Invalid document type. Must be one of: {valid_types}")
    return {
        "agent_id": agent_id,
        "document_type": document_type,
        "verification_id": f"KYC-{agent_id}-{int(__import__('time').time())}",
        "status": "submitted",
        "estimated_completion": "24-48 hours",
    }

@app.get("/api/v1/agents/{agent_id}/transactions")
async def get_agent_transactions(agent_id: str, limit: int = 20, offset: int = 0):
    """Get agent transaction history with pagination."""
    return {
        "agent_id": agent_id,
        "transactions": [],
        "total": 0,
        "limit": limit,
        "offset": offset,
        "has_more": False,
    }

# In-memory device store (no DB dependency)
_device_store: Dict[str, List[Dict[str, Any]]] = {}

class DeviceRegistration(BaseModel):
    fingerprint: str
    user_agent: Optional[str] = None
    screen_resolution: Optional[str] = None
    timezone: Optional[str] = None
    language: Optional[str] = None
    platform: Optional[str] = None
    label: Optional[str] = None

@app.get("/api/v1/devices/{agent_id}")
async def get_agent_devices(agent_id: str):
    """List registered trusted devices for an agent."""
    devices = _device_store.get(agent_id, [])
    return {"agent_id": agent_id, "devices": devices, "total": len(devices)}

@app.post("/api/v1/devices/{agent_id}", status_code=201)
async def register_device(agent_id: str, payload: DeviceRegistration):
    """Register a new trusted device for an agent."""
    import uuid
    devices = _device_store.setdefault(agent_id, [])
    if any(d["fingerprint"] == payload.fingerprint for d in devices):
        raise HTTPException(status_code=409, detail="Device already registered")
    device = {
        "id": str(uuid.uuid4()),
        "agent_id": agent_id,
        "fingerprint": payload.fingerprint,
        "user_agent": payload.user_agent,
        "screen_resolution": payload.screen_resolution,
        "timezone": payload.timezone,
        "language": payload.language,
        "platform": payload.platform,
        "label": payload.label or payload.platform,
        "created_at": datetime.utcnow().isoformat(),
    }
    devices.append(device)
    return device

@app.delete("/api/v1/devices/{agent_id}/{device_id}", status_code=204)
async def remove_device(agent_id: str, device_id: str):
    """Remove a trusted device for an agent."""
    devices = _device_store.get(agent_id, [])
    updated = [d for d in devices if d["id"] != device_id]
    if len(updated) == len(devices):
        raise HTTPException(status_code=404, detail="Device not found")
    _device_store[agent_id] = updated

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
