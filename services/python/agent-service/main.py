"""
Core Agent Service - FastAPI microservice
Core agent lifecycle management: registration, activation, suspension, and profile management
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
    title="Core Agent Service",
    description="Core agent lifecycle management: registration, activation, suspension, and profile management",
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
    return {"status": "healthy", "service": "agent-service", "version": "1.0.0", "timestamp": datetime.utcnow().isoformat()}

@app.post("/api/v1/agents/register")
async def register_agent(name: str, phone: str, email: str = None, territory_id: str = None):
    """Register a new agent in the system."""
    if not phone or len(phone) < 10:
        raise HTTPException(status_code=400, detail="Valid phone number is required")
    return {
        "agent_id": f"AGT-{int(__import__('time').time())}",
        "name": name,
        "phone": phone,
        "email": email,
        "status": "pending_kyc",
        "territory_id": territory_id,
        "created_at": __import__('datetime').datetime.utcnow().isoformat(),
    }

@app.get("/api/v1/agents/{agent_id}")
async def get_agent(agent_id: str):
    """Get agent profile and status."""
    return {
        "agent_id": agent_id,
        "name": "",
        "phone": "",
        "email": None,
        "status": "active",
        "kyc_status": "verified",
        "tier": "standard",
        "territory_id": None,
        "created_at": None,
        "last_active": None,
    }

@app.put("/api/v1/agents/{agent_id}/status")
async def update_agent_status(agent_id: str, status: str, reason: str = ""):
    """Update agent status (activate, suspend, deactivate)."""
    valid_statuses = ["active", "suspended", "deactivated", "pending_review"]
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
    return {
        "agent_id": agent_id,
        "previous_status": "active",
        "new_status": status,
        "reason": reason,
        "updated_at": __import__('datetime').datetime.utcnow().isoformat(),
    }

@app.get("/api/v1/agents")
async def list_agents(status: str = None, territory: str = None, limit: int = 20, offset: int = 0):
    """List agents with filtering and pagination."""
    return {"agents": [], "total": 0, "limit": limit, "offset": offset, "filters": {"status": status, "territory": territory}}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
