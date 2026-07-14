"""
Router for zapier-service service
Auto-extracted from main.py for unified gateway registration
"""

from fastapi import APIRouter

router = APIRouter(prefix="/zapier-service", tags=["zapier-service"])

@router.get("/")
async def root():
    return {"status": "ok"}

@router.get("/health")
async def health_check():
    return {"status": "ok"}

@router.post("/api/v1/send")
async def send_message(message: Message):
    return {"status": "ok"}

@router.post("/api/v1/order")
async def create_order(order: OrderMessage):
    return {"status": "ok"}

@router.get("/api/v1/messages")
async def get_messages(limit: int = 50):
    return {"status": "ok"}

@router.get("/api/v1/orders")
async def get_orders(limit: int = 50):
    return {"status": "ok"}

@router.get("/api/v1/metrics")
async def get_metrics():
    return {"status": "ok"}

@router.post("/webhook")
async def webhook_handler(request: Request):
    return {"status": "ok"}

