"""
Router for websocket-service service
Auto-extracted from main.py for unified gateway registration

WARNING (mockware remediation): these endpoints were auto-generated stubs that
returned fabricated {"status": "ok"} responses and referenced an undefined
Message model, so they could not even be imported. The real websocket
connection/send logic lives in this service's main.py. Until this stub is
removed from every registration site, endpoints fail loudly with
501 Not Implemented instead of pretending messages were sent.
"""

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/websocket-service", tags=["websocket-service"])

_STUB_DETAIL = "websocket-service stub endpoint disabled: use the real implementation in this service's main.py"


def _not_implemented():
    raise HTTPException(status_code=501, detail=_STUB_DETAIL)


@router.get("/health")
async def health_check():
    return {"status": "ok", "note": "stub router only; real implementation is in main.py"}


@router.get("/connections")
async def list_connections():
    _not_implemented()


@router.get("/connections/{agent_id}")
async def get_agent_connections(agent_id: str):
    _not_implemented()


@router.post("/send/agent/{agent_id}")
async def send_to_agent(agent_id: str):
    _not_implemented()


@router.post("/send/broadcast")
async def broadcast_message():
    _not_implemented()


@router.post("/send/room/{room_id}")
async def send_to_room(room_id: str):
    _not_implemented()
