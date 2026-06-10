"""API Router for Agent Wallet Transparency Service."""
from datetime import datetime
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from models import BalanceResponse, LedgerEntryResponse, StatementResponse, RecordEntryRequest, StatementRequest
from service import AgentWalletTransparencyService
from config import get_db

router = APIRouter(prefix="/api/v1/wallet", tags=["Agent Wallet Transparency"])


def get_svc(db: Session = Depends(get_db)) -> AgentWalletTransparencyService:
    return AgentWalletTransparencyService(db)


@router.get("/agents/{agent_id}/balance", response_model=BalanceResponse)
def get_balance(agent_id: UUID, svc: AgentWalletTransparencyService = Depends(get_svc)):
    return svc.get_balance(agent_id)


@router.get("/agents/{agent_id}/ledger")
def get_ledger(
    agent_id: UUID,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    entry_type: Optional[str] = None,
    direction: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    svc: AgentWalletTransparencyService = Depends(get_svc),
):
    result = svc.get_ledger_entries(
        agent_id=agent_id,
        start_date=start_date,
        end_date=end_date,
        entry_type=entry_type,
        direction=direction,
        limit=limit,
        offset=offset,
    )
    result["entries"] = [LedgerEntryResponse.model_validate(e) for e in result["entries"]]
    return result


@router.post("/agents/{agent_id}/statement", response_model=StatementResponse)
def generate_statement(
    agent_id: UUID,
    payload: StatementRequest,
    svc: AgentWalletTransparencyService = Depends(get_svc),
):
    try:
        return svc.generate_statement(
            agent_id=agent_id,
            start_date=payload.start_date,
            end_date=payload.end_date,
            format=payload.format,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/entries", summary="Record a wallet ledger entry (internal)")
def record_entry(payload: RecordEntryRequest, svc: AgentWalletTransparencyService = Depends(get_svc)):
    from decimal import Decimal
    fee = svc.calculate_fee(payload.entry_type, payload.amount)
    return svc.record_entry(
        agent_id=payload.agent_id,
        entry_type=payload.entry_type,
        amount=payload.amount,
        direction=payload.direction,
        description=payload.description,
        transaction_id=payload.transaction_id,
        reference=payload.reference,
        fee_amount=fee if payload.direction == "debit" else Decimal("0"),
        customer_phone=payload.customer_phone,
    )


@router.get("/agents/{agent_id}/analytics")
def get_analytics(
    agent_id: UUID,
    days: int = Query(default=30, le=365),
    svc: AgentWalletTransparencyService = Depends(get_svc),
):
    return svc.get_wallet_analytics(agent_id, days=days)


@router.get("/fee-schedule", summary="Published fee schedule for agent transparency")
def get_fee_schedule(svc: AgentWalletTransparencyService = Depends(get_svc)):
    return svc.get_fee_schedule()


@router.get("/health")
def health():
    return {"status": "healthy", "service": "agent-wallet-transparency"}
