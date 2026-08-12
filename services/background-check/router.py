"""
Router for background-check service
Auto-extracted from main.py for unified gateway registration

NOTE: These stub handlers previously returned {"status": "ok"} for every
endpoint, fabricating successful background-check operations. They now fail
closed with HTTP 501 until real handlers are wired. The authoritative
implementations live in this service's main.py.
"""

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/background-check", tags=["background-check"])

_NOT_IMPLEMENTED_DETAIL = (
    "Not implemented in gateway router; use the background-check "
    "service endpoints directly"
)

@router.get("/health")
async def health_check():
    return {"status": "ok"}

@router.post("/api/v1/background-check/initiate")
async def initiate_background_check():
    raise HTTPException(status_code=501, detail=_NOT_IMPLEMENTED_DETAIL)

@router.get("/api/v1/background-check/{check_id}/status")
async def get_check_status(check_id: str):
    raise HTTPException(status_code=501, detail=_NOT_IMPLEMENTED_DETAIL)

@router.get("/api/v1/background-check/{check_id}/results")
async def get_check_results(check_id: str):
    raise HTTPException(status_code=501, detail=_NOT_IMPLEMENTED_DETAIL)

@router.post("/api/v1/background-check/{check_id}/retry")
async def retry_background_check(check_id: str):
    raise HTTPException(status_code=501, detail=_NOT_IMPLEMENTED_DETAIL)

@router.delete("/api/v1/background-check/{check_id}")
async def delete_background_check(check_id: str):
    raise HTTPException(status_code=501, detail=_NOT_IMPLEMENTED_DETAIL)

@router.get("/api/v1/background-check/agent/{agent_id}")
async def get_agent_background_checks(agent_id: str):
    raise HTTPException(status_code=501, detail=_NOT_IMPLEMENTED_DETAIL)
