"""
Agent Art & Branding Service - FastAPI microservice
Agent branding asset management: storefront customization, marketing materials, and digital signage
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
    title="Agent Art & Branding Service",
    description="Agent branding asset management: storefront customization, marketing materials, and digital signage",
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
    return {"status": "healthy", "service": "art-agent-service", "version": "1.0.0", "timestamp": datetime.utcnow().isoformat()}

@app.get("/api/v1/branding/{agent_id}")
async def get_agent_branding(agent_id: str):
    """Get agent's branding configuration."""
    return {
        "agent_id": agent_id,
        "business_name": "",
        "logo_url": None,
        "color_scheme": {"primary": "#1a73e8", "secondary": "#34a853"},
        "storefront_banner": None,
        "qr_code_url": None,
    }

@app.put("/api/v1/branding/{agent_id}")
async def update_branding(agent_id: str, business_name: str = None, primary_color: str = None):
    """Update agent branding configuration."""
    return {"agent_id": agent_id, "updated_fields": [], "updated_at": __import__('datetime').datetime.utcnow().isoformat()}

@app.post("/api/v1/branding/{agent_id}/materials")
async def generate_materials(agent_id: str, material_type: str):
    """Generate marketing materials for an agent."""
    valid_types = ["business_card", "flyer", "banner", "receipt_header", "qr_poster"]
    if material_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Invalid type. Must be one of: {valid_types}")
    return {"agent_id": agent_id, "material_type": material_type, "status": "generating", "download_url": None}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
