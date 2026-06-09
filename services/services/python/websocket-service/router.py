"""
Router for websocket-service service
Auto-extracted from main.py for unified gateway registration
"""

from fastapi import APIRouter

router = APIRouter(prefix="/websocket-service", tags=["websocket-service"])

@router.get("/health")
async def health_check():
    return {"status": "ok"}

@router.get("/connections")
async def list_connections():
    return {"status": "ok"}

@router.get("/connections/{agent_id}")
async def get_agent_connections(agent_id: str):
    return {"status": "ok"}

@router.post("/send/agent/{agent_id}")
async def send_to_agent(agent_id: str, message: Message):
    return {"status": "ok"}

@router.post("/send/broadcast")
async def broadcast_message(message: Message):
    return {"status": "ok"}

@router.post("/send/room/{room_id}")
async def send_to_room(room_id: str, message: Message):
    return {"status": "ok"}

