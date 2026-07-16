"""Aggregated router for CDP Service"""
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/cdp", tags=["cdp-service"])

try:
    from .app.services.router import router as cdp_router
    router.include_router(cdp_router)
except Exception:
    pass

@router.get("/health")
async def cdp_health():
    return {"status": "healthy", "service": "cdp-service"}
