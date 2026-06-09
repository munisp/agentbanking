"""Aggregated router for Admin Services"""
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/admin", tags=["admin-services"])

try:
    from .bi_dashboard.router import router as bi_router
    router.include_router(bi_router)
except Exception:
    pass
try:
    from .customer_analytics.router import router as ca_router
    router.include_router(ca_router)
except Exception:
    pass
try:
    from .fraud_dashboard.router import router as fd_router
    router.include_router(fd_router)
except Exception:
    pass
try:
    from .real_time_monitor.router import router as rtm_router
    router.include_router(rtm_router)
except Exception:
    pass
try:
    from .revenue_analytics.router import router as ra_router
    router.include_router(ra_router)
except Exception:
    pass

@router.get("/health")
async def admin_health():
    return {"status": "healthy", "service": "admin-services"}
