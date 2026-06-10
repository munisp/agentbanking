"""Aggregated router for Payment Gateway Service"""
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/payment-gateway-svc", tags=["payment-gateway-service"])

try:
    from .services.router import router as pg_router
    router.include_router(pg_router)
except Exception:
    pass

@router.get("/health")
async def payment_gateway_svc_health():
    return {"status": "healthy", "service": "payment-gateway-service"}
