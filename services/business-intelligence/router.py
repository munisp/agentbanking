"""
Router for business-intelligence service
Auto-extracted from main.py for unified gateway registration

WARNING (mockware remediation): these endpoints were auto-generated stubs that
returned fabricated {"status": "ok"} responses for status/metrics endpoints.
Until this stub is removed from every registration site, endpoints fail
loudly with 501 Not Implemented instead of fabricating data.
"""

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/business-intelligence", tags=["business-intelligence"])

_STUB_DETAIL = "business-intelligence stub endpoint disabled: no real handler is implemented in this auto-generated router"


def _not_implemented():
    raise HTTPException(status_code=501, detail=_STUB_DETAIL)


@router.get("/")
async def root():
    _not_implemented()


@router.get("/health")
async def health_check():
    return {"status": "ok", "note": "stub router only; no real handlers"}


@router.get("/api/v1/status")
async def get_status():
    _not_implemented()


@router.get("/api/v1/metrics")
async def get_metrics():
    _not_implemented()
