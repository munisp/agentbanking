"""API Router for Agent-to-Agent Liquidity Network."""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from models import (RegisterProfileRequest, CreateRequestRequest,
                     CreateOfferRequest, ConfirmDisbursementRequest, ProcessRepaymentRequest)
from service import AgentLiquidityNetworkService
from config import get_db

router = APIRouter(prefix="/api/v1/liquidity-network", tags=["Agent Liquidity Network"])


def get_svc(db: Session = Depends(get_db)) -> AgentLiquidityNetworkService:
    return AgentLiquidityNetworkService(db)


@router.post("/profiles/register")
def register_profile(payload: RegisterProfileRequest, svc: AgentLiquidityNetworkService = Depends(get_svc)):
    return svc.get_or_create_profile(payload.agent_id, payload.agent_name, payload.agent_code)


@router.get("/profiles/{agent_id}/summary")
def get_summary(agent_id: UUID, svc: AgentLiquidityNetworkService = Depends(get_svc)):
    try:
        return svc.get_agent_network_summary(agent_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/requests")
async def create_request(payload: CreateRequestRequest, svc: AgentLiquidityNetworkService = Depends(get_svc)):
    try:
        return svc.create_float_request(
            borrower_id=payload.borrower_id, amount=payload.amount,
            duration_hours=payload.duration_hours, max_interest_rate=payload.max_interest_rate,
            purpose=payload.purpose,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/requests/active")
def get_active_requests(limit: int = 50, svc: AgentLiquidityNetworkService = Depends(get_svc)):
    return svc.get_active_requests(limit=limit)


@router.post("/offers")
async def create_offer(payload: CreateOfferRequest, svc: AgentLiquidityNetworkService = Depends(get_svc)):
    try:
        return svc.create_float_offer(
            lender_id=payload.lender_id, amount=payload.amount,
            interest_rate=payload.interest_rate, min_duration_hours=payload.min_duration_hours,
            max_duration_hours=payload.max_duration_hours,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/matches/{match_id}/confirm-disbursement")
def confirm_disbursement(match_id: UUID, payload: ConfirmDisbursementRequest, svc: AgentLiquidityNetworkService = Depends(get_svc)):
    try:
        return svc.confirm_disbursement(match_id, payload.tigerbeetle_transfer_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/matches/{match_id}/repay")
def process_repayment(match_id: UUID, payload: ProcessRepaymentRequest, svc: AgentLiquidityNetworkService = Depends(get_svc)):
    try:
        repayment, match = svc.process_repayment(match_id, payload.amount_paid, payload.payment_reference)
        return {"repayment": repayment, "match": match}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/health")
def health():
    return {"status": "healthy", "service": "agent-liquidity-network"}
