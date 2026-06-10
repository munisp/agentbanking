"""API Router for Real-Time Receipt Engine."""
from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from models import GenerateReceiptRequest, ResendRequest, ReceiptResponse
from service import RealtimeReceiptEngine
from config import get_db

router = APIRouter(prefix="/api/v1/receipts", tags=["Real-Time Receipt Engine"])


def get_svc(db: Session = Depends(get_db)) -> RealtimeReceiptEngine:
    return RealtimeReceiptEngine(db)


@router.post("/generate", response_model=ReceiptResponse, summary="Generate and deliver a transaction receipt")
async def generate_receipt(payload: GenerateReceiptRequest, svc: RealtimeReceiptEngine = Depends(get_svc)):
    receipt = svc.generate_receipt(
        transaction_id=payload.transaction_id, agent_id=payload.agent_id,
        agent_name=payload.agent_name, agent_code=payload.agent_code,
        customer_phone=payload.customer_phone, customer_name=payload.customer_name,
        transaction_type=payload.transaction_type, amount=payload.amount,
        fee=payload.fee, new_balance=payload.new_balance, reference=payload.reference,
        status=payload.status, currency=payload.currency, language=payload.language,
        extra_data=payload.extra_data,
    )
    if payload.channels:
        await svc.deliver_receipt(receipt, channels=payload.channels)
    return receipt


@router.post("/resend", summary="Resend a receipt via a specific channel")
async def resend_receipt(payload: ResendRequest, svc: RealtimeReceiptEngine = Depends(get_svc)):
    try:
        return await svc.resend_receipt(payload.reference, payload.channel)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{reference}", response_model=ReceiptResponse)
def get_receipt(reference: str, svc: RealtimeReceiptEngine = Depends(get_svc)):
    receipt = svc.get_receipt_by_reference(reference)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return receipt


@router.get("/{reference}/text", response_class=PlainTextResponse)
def get_receipt_text(reference: str, svc: RealtimeReceiptEngine = Depends(get_svc)):
    receipt = svc.get_receipt_by_reference(reference)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return receipt.receipt_text


@router.get("/agents/{agent_id}/receipts", response_model=List[ReceiptResponse])
def get_agent_receipts(agent_id: UUID, limit: int = 50, svc: RealtimeReceiptEngine = Depends(get_svc)):
    return svc.get_agent_receipts(agent_id, limit=limit)


@router.get("/health")
def health():
    return {"status": "healthy", "service": "realtime-receipt-engine"}
