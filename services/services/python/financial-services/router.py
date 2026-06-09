"""Aggregated router for Financial Services"""
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/financial", tags=["financial-services"])

try:
    from .bill_payments.router import router as bp_router
    router.include_router(bp_router)
except Exception:
    pass
try:
    from .crypto_trading.router import router as ct_router
    router.include_router(ct_router)
except Exception:
    pass
try:
    from .insurance.router import router as ins_router
    router.include_router(ins_router)
except Exception:
    pass
try:
    from .investment_portfolio.router import router as ip_router
    router.include_router(ip_router)
except Exception:
    pass
try:
    from .lending.router import router as lend_router
    router.include_router(lend_router)
except Exception:
    pass

@router.get("/health")
async def financial_health():
    return {"status": "healthy", "service": "financial-services"}
