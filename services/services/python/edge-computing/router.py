"""
Router for edge-computing service
Auto-extracted from main.py for unified gateway registration
"""

from fastapi import APIRouter

router = APIRouter(prefix="/edge-computing", tags=["edge-computing"])

@router.get("/health")
async def health_check():
    return {"status": "ok"}

