"""Aggregated router for Enterprise Services"""
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/enterprise", tags=["enterprise-services"])

try:
    from .bulk_payments.router import router as bp_router
    router.include_router(bp_router)
except Exception:
    pass
try:
    from .business_api.router import router as ba_router
    router.include_router(ba_router)
except Exception:
    pass
try:
    from .multi_tenant.router import router as mt_router
    router.include_router(mt_router)
except Exception:
    pass
try:
    from .payroll.router import router as pr_router
    router.include_router(pr_router)
except Exception:
    pass
try:
    from .white_label_api.router import router as wla_router
    router.include_router(wla_router)
except Exception:
    pass
try:
    from .white_label_config.router import router as wlc_router
    router.include_router(wlc_router)
except Exception:
    pass

@router.get("/health")
async def enterprise_health():
    return {"status": "healthy", "service": "enterprise-services"}
