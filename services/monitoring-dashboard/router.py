"""
Router for monitoring-dashboard service
Auto-extracted from main.py for unified gateway registration

WARNING (mockware remediation): these endpoints were auto-generated stubs that
returned fabricated {"status": "ok"} responses (including a fake "current
metrics" payload). Metrics must come from the real monitoring pipeline; until
this stub is removed from every registration site, endpoints fail loudly with
501 Not Implemented instead of fabricating data.
"""

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/monitoring-dashboard", tags=["monitoring-dashboard"])

_STUB_DETAIL = "monitoring-dashboard stub endpoint disabled: no real handler is implemented in this auto-generated router"


def _not_implemented():
    raise HTTPException(status_code=501, detail=_STUB_DETAIL)


@router.get("/metrics/current")
async def get_current_metrics():
    _not_implemented()


@router.get("/health")
async def health_check():
    return {"status": "ok", "note": "stub router only; no real handlers"}
