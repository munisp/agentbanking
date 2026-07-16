"""
Router for whatsapp-ai-bot service
Auto-extracted from main.py for unified gateway registration
"""

from fastapi import APIRouter

router = APIRouter(prefix="/whatsapp-ai-bot", tags=["whatsapp-ai-bot"])

@router.get("/")
async def root():
    return {"status": "ok"}

@router.get("/health")
async def health_check():
    return {"status": "ok"}

@router.post("/webhook")
async def webhook(message: IncomingMessage, background_tasks: BackgroundTasks):
    return {"status": "ok"}

@router.post("/send")
async def send_message(message: OutgoingMessage):
    return {"status": "ok"}

@router.get("/stats")
async def get_stats():
    return {"status": "ok"}

@router.delete("/session/{user_id}")
async def clear_session(user_id: str):
    return {"status": "ok"}

