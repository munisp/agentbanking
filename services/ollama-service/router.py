"""
Router for ollama-service service
Replaces a generated stub that returned canned {"status": "ok"} payloads for
every endpoint (mockware) and referenced undefined symbols, so it could not be
imported by the unified gateway.

The real implementation lives in the standalone service (services/ollama-service/).
This router now FAILS LOUDLY: /health reports 503 and every other route
returns 501 until the gateway wires real handlers. No responses are
fabricated here.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/ollama-service", tags=["ollama-service"])

_UNAVAILABLE = (
    "ollama-service endpoints are not served by this gateway router. "
    "Use the standalone ollama-service service."
)


@router.get("/health")
async def health_check():
    return JSONResponse(
        status_code=503,
        content={"status": "unavailable", "service": "ollama-service", "detail": _UNAVAILABLE},
    )


@router.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def not_implemented(full_path: str):
    raise HTTPException(status_code=501, detail=_UNAVAILABLE)
