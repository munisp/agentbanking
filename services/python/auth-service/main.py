"""
Authentication and authorization service
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

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


router = APIRouter(prefix="/authservice", tags=["auth-service"])

# Pydantic models
class AuthserviceBase(BaseModel):
    """Base model for auth-service."""
    pass

class AuthserviceCreate(BaseModel):
    """Create model for auth-service."""
    name: str
    description: Optional[str] = None

class AuthserviceResponse(BaseModel):
    """Response model for auth-service."""
    id: int
    name: str
    description: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True

# API endpoints
@router.post("/", response_model=AuthserviceResponse, status_code=status.HTTP_201_CREATED)
async def create(data: AuthserviceCreate):
    """Create new auth-service record."""
    # Implementation here
    return {"id": 1, "name": data.name, "description": data.description, "created_at": datetime.now(), "updated_at": None}

@router.get("/{id}", response_model=AuthserviceResponse)
async def get_by_id(id: int):
    """Get auth-service by ID."""
    # Implementation here
    return {"id": id, "name": "Sample", "description": "Sample description", "created_at": datetime.now(), "updated_at": None}

@router.get("/", response_model=List[AuthserviceResponse])
async def list_all(skip: int = 0, limit: int = 100):
    """List all auth-service records."""
    # Implementation here
    return []

@router.put("/{id}", response_model=AuthserviceResponse)
async def update(id: int, data: AuthserviceCreate):
    """Update auth-service record."""
    # Implementation here
    return {"id": id, "name": data.name, "description": data.description, "created_at": datetime.now(), "updated_at": datetime.now()}

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(id: int):
    """Delete auth-service record."""
    # Implementation here
    return None
