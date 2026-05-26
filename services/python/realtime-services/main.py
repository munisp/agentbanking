"""
Real-time Event Services - FastAPI microservice
WebSocket-based real-time event broadcasting for transaction updates, alerts, and dashboard feeds
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
    title="Real-time Event Services",
    description="WebSocket-based real-time event broadcasting for transaction updates, alerts, and dashboard feeds",
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
    return {"status": "healthy", "service": "realtime-services", "version": "1.0.0", "timestamp": datetime.utcnow().isoformat()}

@app.get("/api/v1/events/subscribe")
async def get_subscription_info():
    """Get WebSocket subscription endpoint and available channels."""
    return {
        "websocket_url": "/ws/events",
        "channels": [
            {"name": "transactions", "description": "Real-time transaction updates"},
            {"name": "alerts", "description": "System and fraud alerts"},
            {"name": "settlements", "description": "Settlement status updates"},
            {"name": "agent_status", "description": "Agent online/offline status"},
        ],
        "auth_required": True,
    }

@app.post("/api/v1/events/publish")
async def publish_event(channel: str, event_type: str, payload: dict):
    """Publish an event to a channel (internal use)."""
    valid_channels = ["transactions", "alerts", "settlements", "agent_status"]
    if channel not in valid_channels:
        raise HTTPException(status_code=400, detail=f"Invalid channel. Must be one of: {valid_channels}")
    return {
        "event_id": f"EVT-{int(__import__('time').time())}",
        "channel": channel,
        "event_type": event_type,
        "published_at": __import__('datetime').datetime.utcnow().isoformat(),
        "subscribers_notified": 0,
    }

@app.get("/api/v1/events/history")
async def get_event_history(channel: str = None, limit: int = 50):
    """Get recent event history for replay."""
    return {"events": [], "total": 0, "channel": channel, "limit": limit}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
