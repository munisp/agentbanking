"""
Router for workflow-integration service
Replaces a generated stub that returned canned {"status": "ok"} payloads for
every endpoint (mockware) and referenced undefined symbols, so it could not be
imported by the unified gateway.

The real implementation lives in the standalone service (services/workflow-integration/).
This router now FAILS LOUDLY: /health reports 503 and every other route
returns 501 until the gateway wires real handlers. No responses are
fabricated here.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/workflow-integration", tags=["workflow-integration"])

_UNAVAILABLE = (
    "workflow-integration endpoints are not served by this gateway router. "
    "Use the standalone workflow-integration service."
)


@router.get("/health")
async def health_check():
    return JSONResponse(
        status_code=503,
        content={"status": "unavailable", "service": "workflow-integration", "detail": _UNAVAILABLE},
    )


@router.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def not_implemented(full_path: str):
    raise HTTPException(status_code=501, detail=_UNAVAILABLE)
