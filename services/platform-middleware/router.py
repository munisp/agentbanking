"""
Router for platform-middleware service
Auto-extracted from main.py for unified gateway registration
"""

from fastapi import APIRouter

router = APIRouter(prefix="/platform-middleware", tags=["platform-middleware"])

@router.get("/health")
async def health_check():
    return {"status": "ok"}

