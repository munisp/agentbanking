"""Aggregated router for Security Services"""
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/security-svc", tags=["security-services"])

try:
    from .compliance_kyc.router import router as ck_router
    router.include_router(ck_router)
except Exception:
    pass
try:
    from .quantum_crypto.router import router as qc_router
    router.include_router(qc_router)
except Exception:
    pass
try:
    from .security.router import router as sec_router
    router.include_router(sec_router)
except Exception:
    pass
try:
    from .security_enhancements.router import router as se_router
    router.include_router(se_router)
except Exception:
    pass

@router.get("/health")
async def security_svc_health():
    return {"status": "healthy", "service": "security-services"}
