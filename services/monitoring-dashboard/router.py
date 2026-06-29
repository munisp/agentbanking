"""
Router for monitoring-dashboard service
Auto-extracted from main.py for unified gateway registration
"""

from fastapi import APIRouter

router = APIRouter(prefix="/monitoring-dashboard", tags=["monitoring-dashboard"])

@router.get("/metrics/current")
async def get_current_metrics():
    return {"status": "ok"}

@router.get("/health")
async def health_check():
    return {"status": "ok"}

