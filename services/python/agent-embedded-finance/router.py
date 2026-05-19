"""
Agent Embedded Finance API Router
Micro-Credit and BNPL endpoints for the agent network.
"""
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from .config import get_db
from .models import (
    BNPLInstallmentPayRequest, BNPLOrderOut, BNPLOrderRequest,
    CreditProfileOut, LoanApplicationOut, LoanApplicationRequest,
    LoanOut, PortfolioSummary, RepaymentOut, RepaymentRequest,
)
from . import service

router = APIRouter(
    prefix="/embedded-finance",
    tags=["Agent Embedded Finance"],
    responses={404: {"description": "Not found"}},
)


# ─── Credit Profile ───────────────────────────────────────────────────────────

@router.get(
    "/credit-profile/{agent_id}",
    response_model=CreditProfileOut,
    summary="Get agent credit profile",
)
def get_credit_profile(
    agent_id: uuid.UUID,
    tenant_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
):
    profile = service.get_or_create_credit_profile(db, agent_id, tenant_id)
    return profile


@router.post(
    "/credit-profile/evaluate",
    response_model=CreditProfileOut,
    summary="Evaluate and update agent credit eligibility",
    description=(
        "Runs the full credit underwriting assessment for an agent. "
        "Sets credit limit based on tenure, transaction history, and credit score."
    ),
)
def evaluate_credit(
    agent_id: uuid.UUID = Query(...),
    tenant_id: uuid.UUID = Query(...),
    agent_tenure_months: int = Query(..., ge=0),
    txn_count_last_90_days: int = Query(..., ge=0),
    credit_score: Optional[int] = Query(default=None, ge=300, le=850),
    scorecard_composite: Optional[float] = Query(default=None, ge=0, le=1000),
    db: Session = Depends(get_db),
):
    profile = service.evaluate_credit_eligibility(
        db=db,
        agent_id=agent_id,
        tenant_id=tenant_id,
        agent_tenure_months=agent_tenure_months,
        txn_count_last_90_days=txn_count_last_90_days,
        credit_score=credit_score,
        scorecard_composite=scorecard_composite,
    )
    return profile


# ─── Loan Applications ────────────────────────────────────────────────────────

@router.post(
    "/loans/apply",
    response_model=LoanApplicationOut,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a loan application",
    description=(
        "Submits a new loan application and runs auto-underwriting. "
        "Returns the application with the credit decision (approved, counter_offer, rejected, or referred)."
    ),
)
def apply_for_loan(
    req: LoanApplicationRequest,
    db: Session = Depends(get_db),
):
    try:
        app = service.submit_loan_application(db, req)
        return app
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.post(
    "/loans/{application_id}/disburse",
    response_model=LoanOut,
    summary="Disburse an approved loan",
    description="Disburses an approved loan to the agent's float/wallet and activates it.",
)
def disburse_loan(
    application_id: uuid.UUID,
    repayment_method: str = Query(default="commission_deduction"),
    db: Session = Depends(get_db),
):
    try:
        from .models import RepaymentMethod
        method = RepaymentMethod(repayment_method)
        loan = service.disburse_loan(db, application_id, method)
        return loan
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get(
    "/loans/{agent_id}/active",
    response_model=List[LoanOut],
    summary="Get all active loans for an agent",
)
def get_active_loans(
    agent_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    from .models import LoanStatus
    from sqlalchemy import and_
    loans = db.query(service.AgentLoan).filter(
        service.AgentLoan.agent_id == agent_id,
        service.AgentLoan.status.in_([LoanStatus.ACTIVE, LoanStatus.OVERDUE]),
    ).all()
    return loans


@router.get(
    "/loans/{agent_id}/history",
    response_model=List[LoanOut],
    summary="Get loan history for an agent",
)
def get_loan_history(
    agent_id: uuid.UUID,
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return service.get_loan_history(db, agent_id, limit)


@router.post(
    "/loans/repay",
    response_model=LoanOut,
    summary="Process a loan repayment",
    description="Processes a repayment. Allocates payment to penalty → interest → principal.",
)
def repay_loan(
    req: RepaymentRequest,
    db: Session = Depends(get_db),
):
    try:
        loan = service.process_repayment(db, req)
        return loan
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ─── BNPL ─────────────────────────────────────────────────────────────────────

@router.post(
    "/bnpl/orders",
    response_model=BNPLOrderOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a BNPL order",
    description=(
        "Creates a Buy Now Pay Later order for inventory, devices, or supplies. "
        "Generates a full installment schedule automatically. "
        "0% interest for ≤3 installments, 18% p.a. for >3 installments."
    ),
)
def create_bnpl_order(
    req: BNPLOrderRequest,
    db: Session = Depends(get_db),
):
    try:
        order = service.create_bnpl_order(db, req)
        return order
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get(
    "/bnpl/{agent_id}/orders",
    response_model=List[BNPLOrderOut],
    summary="Get BNPL order history for an agent",
)
def get_bnpl_orders(
    agent_id: uuid.UUID,
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return service.get_bnpl_history(db, agent_id, limit)


@router.post(
    "/bnpl/installments/pay",
    summary="Pay a BNPL installment",
    description="Records payment for a specific BNPL installment.",
)
def pay_installment(
    req: BNPLInstallmentPayRequest,
    db: Session = Depends(get_db),
):
    try:
        installment = service.pay_bnpl_installment(
            db, req.installment_id, req.amount_paid, req.transaction_ref
        )
        return {"message": "Payment recorded successfully.", "installment_id": str(installment.id), "status": installment.status.value}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ─── Portfolio ────────────────────────────────────────────────────────────────

@router.get(
    "/portfolio/{agent_id}",
    summary="Get agent's full embedded finance portfolio",
    description=(
        "Returns the agent's complete embedded finance view: credit profile, "
        "active loans, active BNPL orders, upcoming payments, and totals."
    ),
)
def get_portfolio(
    agent_id: uuid.UUID,
    tenant_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
):
    return service.get_agent_portfolio(db, agent_id, tenant_id)


# ─── Admin / Scheduled Jobs ───────────────────────────────────────────────────

@router.post(
    "/admin/accrue-penalties",
    summary="[Admin] Accrue daily penalties on overdue loans",
    description="Scheduled job endpoint. Accrues daily penalty on all overdue loans.",
    include_in_schema=False,
)
def accrue_penalties(db: Session = Depends(get_db)):
    count = service.accrue_overdue_penalties(db)
    return {"message": f"Penalties accrued on {count} overdue loan(s)."}


@router.get("/health", include_in_schema=False)
def health():
    return {"status": "healthy", "service": "agent-embedded-finance"}
