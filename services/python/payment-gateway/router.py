"""
Router for payment-gateway service
Auto-extracted from main.py for unified gateway registration
"""

from fastapi import APIRouter

router = APIRouter(prefix="/payment-gateway", tags=["payment-gateway"])

@router.post("/payments")
async def create_payment(request: PaymentRequest):
    return {"status": "ok"}

@router.get("/payments/{payment_id}")
async def get_payment(payment_id: str):
    return {"status": "ok"}

