"""API Router for Instant Reversal Engine."""
from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from models import InitiateReversalRequest, ReversalResponse, AuditLogResponse
from service import InstantReversalEngine
from config import get_db

router = APIRouter(prefix="/api/v1/reversals", tags=["Instant Reversal Engine"])


def get_svc(db: Session = Depends(get_db)) -> InstantReversalEngine:
    return InstantReversalEngine(db)


@router.post("/", response_model=ReversalResponse, summary="Initiate instant reversal")
def initiate_reversal(payload: InitiateReversalRequest, svc: InstantReversalEngine = Depends(get_svc)):
    try:
        return svc.initiate_reversal(
            original_transaction_id=payload.original_transaction_id,
            agent_id=payload.agent_id,
            amount=payload.amount,
            reason=payload.reason,
            customer_phone=payload.customer_phone,
            auto_triggered=payload.auto_triggered,
            detection_source=payload.detection_source,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/{reversal_id}", response_model=ReversalResponse)
def get_reversal(reversal_id: UUID, svc: InstantReversalEngine = Depends(get_svc)):
    r = svc.get_reversal(reversal_id)
    if not r:
        raise HTTPException(status_code=404, detail="Reversal not found")
    return r


@router.get("/{reversal_id}/audit", response_model=List[AuditLogResponse])
def get_audit(reversal_id: UUID, svc: InstantReversalEngine = Depends(get_svc)):
    return svc.get_audit_trail(reversal_id)


@router.get("/agent/{agent_id}", response_model=List[ReversalResponse])
def get_agent_reversals(agent_id: UUID, limit: int = 50, svc: InstantReversalEngine = Depends(get_svc)):
    return svc.get_agent_reversals(agent_id, limit=limit)


@router.get("/admin/pending", response_model=List[ReversalResponse])
def get_pending(svc: InstantReversalEngine = Depends(get_svc)):
    return svc.get_pending_reversals()


@router.get("/admin/sla-breached", response_model=List[ReversalResponse])
def get_sla_breached(svc: InstantReversalEngine = Depends(get_svc)):
    return svc.get_sla_breached_reversals()


@router.get("/admin/metrics", summary="Reversal performance metrics")
def get_metrics(svc: InstantReversalEngine = Depends(get_svc)):
    return svc.get_reversal_metrics()


@router.get("/health")
def health():
    return {"status": "healthy", "service": "instant-reversal-engine", "sla_seconds": 60}
