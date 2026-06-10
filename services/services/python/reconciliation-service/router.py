"""
Router for reconciliation-service service
Auto-extracted from main.py for unified gateway registration
"""

from fastapi import APIRouter

router = APIRouter(prefix="/reconciliation-service", tags=["reconciliation-service"])

@router.get("/")
async def root():
    return {"status": "ok"}

@router.get("/health")
async def health_check():
    return {"status": "ok"}

@router.get("/api/v1/status")
async def get_status():
    return {"status": "ok"}

@router.get("/api/v1/metrics")
async def get_metrics():
    return {"status": "ok"}

