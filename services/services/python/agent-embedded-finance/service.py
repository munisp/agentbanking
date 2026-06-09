"""
Agent Embedded Finance Service
Full credit underwriting engine, loan lifecycle management, and BNPL processing.
"""
import random
import string
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from .models import (
    AgentBNPLInstallment, AgentBNPLOrder, AgentCreditProfile,
    AgentLoan, AgentLoanApplication, AgentLoanRepayment,
    BNPLOrderRequest, BNPLStatus, CreditDecision, InstallmentStatus,
    LoanApplicationRequest, LoanStatus, LoanType, RepaymentMethod,
    RepaymentRequest,
)


# ─── Interest Rate Table (annual) ─────────────────────────────────────────────
# Rates vary by loan type and credit risk level
INTEREST_RATES = {
    LoanType.FLOAT_ADVANCE: {"Low": 0.18, "Medium": 0.24, "High": 0.36},
    LoanType.MICRO_LOAN: {"Low": 0.24, "Medium": 0.30, "High": 0.42},
    LoanType.WORKING_CAPITAL: {"Low": 0.20, "Medium": 0.28, "High": 0.40},
    LoanType.DEVICE_FINANCING: {"Low": 0.15, "Medium": 0.20, "High": 0.30},
}

# Processing fee as % of loan amount
PROCESSING_FEE_RATE = 0.01  # 1%

# Max loan amounts by type (NGN)
MAX_LOAN_AMOUNTS = {
    LoanType.FLOAT_ADVANCE: 500_000,
    LoanType.MICRO_LOAN: 1_000_000,
    LoanType.WORKING_CAPITAL: 5_000_000,
    LoanType.DEVICE_FINANCING: 2_000_000,
}

# Penalty rate per day overdue (annual 36% / 365)
DAILY_PENALTY_RATE = 0.36 / 365

# BNPL interest rate (annual)
BNPL_INTEREST_RATE = 0.0  # 0% for first 3 months, then 18%
BNPL_DEFERRED_RATE = 0.18


def _generate_ref(prefix: str, length: int = 12) -> str:
    chars = string.ascii_uppercase + string.digits
    suffix = "".join(random.choices(chars, k=length))
    return f"{prefix}-{suffix}"


# ─── Credit Profile Management ────────────────────────────────────────────────

def get_or_create_credit_profile(
    db: Session,
    agent_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> AgentCreditProfile:
    profile = db.query(AgentCreditProfile).filter(
        AgentCreditProfile.agent_id == agent_id
    ).first()
    if not profile:
        profile = AgentCreditProfile(
            agent_id=agent_id,
            tenant_id=tenant_id,
            approved_credit_limit=0,
            available_credit=0,
            utilized_credit=0,
            is_eligible=False,
            eligibility_reason="Profile not yet evaluated.",
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


def evaluate_credit_eligibility(
    db: Session,
    agent_id: uuid.UUID,
    tenant_id: uuid.UUID,
    agent_tenure_months: int,
    txn_count_last_90_days: int,
    credit_score: Optional[int] = None,
    scorecard_composite: Optional[float] = None,
) -> AgentCreditProfile:
    """
    Full credit underwriting eligibility assessment.
    Sets credit limit based on scorecard tier, tenure, and transaction history.
    """
    profile = get_or_create_credit_profile(db, agent_id, tenant_id)

    # ── Eligibility Gates ──────────────────────────────────────────────────────
    if agent_tenure_months < 3:
        profile.is_eligible = False
        profile.eligibility_reason = (
            f"Minimum 3 months active agent tenure required. "
            f"Current tenure: {agent_tenure_months} months."
        )
        profile.last_evaluated_at = datetime.utcnow()
        db.commit()
        return profile

    if txn_count_last_90_days < 100:
        profile.is_eligible = False
        profile.eligibility_reason = (
            f"Minimum 100 transactions in last 90 days required. "
            f"Current count: {txn_count_last_90_days}."
        )
        profile.last_evaluated_at = datetime.utcnow()
        db.commit()
        return profile

    # ── Determine Risk Level ───────────────────────────────────────────────────
    if credit_score and credit_score >= 700:
        risk_level = "Low"
    elif credit_score and credit_score >= 550:
        risk_level = "Medium"
    elif credit_score:
        risk_level = "High"
    elif scorecard_composite and scorecard_composite >= 700:
        risk_level = "Low"
    elif scorecard_composite and scorecard_composite >= 500:
        risk_level = "Medium"
    else:
        risk_level = "High"

    # ── Compute Credit Limit ───────────────────────────────────────────────────
    # Base limit: 2x average monthly transaction value (estimated from count)
    # Scaled by risk level and tenure
    base_multiplier = {
        "Low": 2.0,
        "Medium": 1.5,
        "High": 1.0,
    }[risk_level]

    tenure_bonus = min(1.5, 1.0 + (agent_tenure_months - 3) * 0.05)
    txn_bonus = min(2.0, 1.0 + (txn_count_last_90_days / 1000))

    # Estimated average transaction value: NGN 5,000
    estimated_monthly_value = (txn_count_last_90_days / 3) * 5_000
    credit_limit = estimated_monthly_value * base_multiplier * tenure_bonus * txn_bonus

    # Cap at NGN 5,000,000
    credit_limit = min(credit_limit, 5_000_000)
    credit_limit = round(credit_limit / 1000) * 1000  # round to nearest 1000

    # ── Update Profile ─────────────────────────────────────────────────────────
    profile.is_eligible = True
    profile.eligibility_reason = "Eligible based on tenure, transaction history, and credit assessment."
    profile.credit_score = credit_score
    profile.credit_score_date = date.today()
    profile.risk_level = risk_level
    profile.approved_credit_limit = credit_limit
    profile.available_credit = max(0, credit_limit - float(profile.utilized_credit))
    profile.last_evaluated_at = datetime.utcnow()

    db.commit()
    db.refresh(profile)
    return profile


# ─── Loan Application & Underwriting ─────────────────────────────────────────

def _compute_total_repayable(
    principal: float,
    annual_rate: float,
    tenure_days: int,
    processing_fee: float,
) -> float:
    """Simple interest calculation: I = P * r * t"""
    interest = principal * annual_rate * (tenure_days / 365)
    return round(principal + interest + processing_fee, 2)


def submit_loan_application(
    db: Session,
    req: LoanApplicationRequest,
) -> AgentLoanApplication:
    """Submit a new loan application and run auto-underwriting."""
    profile = get_or_create_credit_profile(db, req.agent_id, req.tenant_id)

    app = AgentLoanApplication(
        application_ref=_generate_ref("LA"),
        agent_id=req.agent_id,
        tenant_id=req.tenant_id,
        loan_type=req.loan_type,
        requested_amount=req.requested_amount,
        requested_tenure_days=req.requested_tenure_days,
        purpose=req.purpose,
        status=LoanStatus.PENDING_REVIEW,
        submitted_at=datetime.utcnow(),
        credit_score_snapshot=profile.credit_score,
    )

    # ── Auto-Underwriting ──────────────────────────────────────────────────────
    decision, reason, approved_amount, approved_tenure, rate, fee, total = _underwrite(
        profile=profile,
        loan_type=req.loan_type,
        requested_amount=req.requested_amount,
        requested_tenure_days=req.requested_tenure_days,
    )

    app.decision = decision
    app.decision_reason = reason
    app.decision_at = datetime.utcnow()
    app.decided_by = "auto-engine"

    if decision in (CreditDecision.APPROVED, CreditDecision.COUNTER_OFFER):
        app.approved_amount = approved_amount
        app.approved_tenure_days = approved_tenure
        app.interest_rate_annual = rate
        app.processing_fee = fee
        app.total_repayable = total
        app.status = LoanStatus.APPROVED

    elif decision == CreditDecision.REJECTED:
        app.status = LoanStatus.REJECTED

    else:  # REFERRED
        app.status = LoanStatus.PENDING_REVIEW

    db.add(app)
    db.commit()
    db.refresh(app)
    return app


def _underwrite(
    profile: AgentCreditProfile,
    loan_type: LoanType,
    requested_amount: float,
    requested_tenure_days: int,
) -> Tuple[CreditDecision, str, Optional[float], Optional[int], Optional[float], Optional[float], Optional[float]]:
    """
    Returns: (decision, reason, approved_amount, approved_tenure, rate, fee, total)
    """
    # Gate 1: Eligibility
    if not profile.is_eligible:
        return (
            CreditDecision.REJECTED,
            profile.eligibility_reason or "Agent is not eligible for credit.",
            None, None, None, None, None,
        )

    # Gate 2: No active overdue loans
    if profile.total_loans_overdue > 0:
        return (
            CreditDecision.REJECTED,
            "You have overdue loan(s). Please settle all outstanding obligations before applying.",
            None, None, None, None, None,
        )

    # Gate 3: On-time payment rate
    if float(profile.on_time_payment_rate) < 70 and profile.total_loans_taken > 2:
        return (
            CreditDecision.REJECTED,
            f"On-time payment rate of {profile.on_time_payment_rate}% is below the minimum threshold of 70%.",
            None, None, None, None, None,
        )

    # Gate 4: Max loan amount for type
    max_for_type = MAX_LOAN_AMOUNTS.get(loan_type, 500_000)
    available = float(profile.available_credit)

    if available <= 0:
        return (
            CreditDecision.REJECTED,
            "No available credit limit. Please wait for your current loans to be settled.",
            None, None, None, None, None,
        )

    # Determine approved amount
    approved_amount = min(requested_amount, available, max_for_type)
    counter_offer = approved_amount < requested_amount

    risk_level = profile.risk_level or "Medium"
    rate = INTEREST_RATES.get(loan_type, {}).get(risk_level, 0.30)
    fee = round(approved_amount * PROCESSING_FEE_RATE, 2)
    total = _compute_total_repayable(approved_amount, rate, requested_tenure_days, fee)

    if counter_offer:
        return (
            CreditDecision.COUNTER_OFFER,
            f"Approved for NGN {approved_amount:,.2f} (requested NGN {requested_amount:,.2f}) "
            f"based on available credit limit.",
            approved_amount, requested_tenure_days, rate, fee, total,
        )

    return (
        CreditDecision.APPROVED,
        "Application approved based on credit assessment.",
        approved_amount, requested_tenure_days, rate, fee, total,
    )


def disburse_loan(
    db: Session,
    application_id: uuid.UUID,
    repayment_method: RepaymentMethod = RepaymentMethod.COMMISSION_DEDUCTION,
) -> AgentLoan:
    """Disburse an approved loan and update the credit profile."""
    app = db.query(AgentLoanApplication).filter(
        AgentLoanApplication.id == application_id,
        AgentLoanApplication.status == LoanStatus.APPROVED,
    ).first()
    if not app:
        raise ValueError("Application not found or not in approved status.")

    profile = db.query(AgentCreditProfile).filter(
        AgentCreditProfile.agent_id == app.agent_id
    ).first()
    if not profile:
        raise ValueError("Credit profile not found.")

    principal = float(app.approved_amount)
    due_date = date.today() + timedelta(days=app.approved_tenure_days)

    loan = AgentLoan(
        loan_ref=_generate_ref("LN"),
        application_id=app.id,
        agent_id=app.agent_id,
        tenant_id=app.tenant_id,
        loan_type=app.loan_type,
        principal_amount=principal,
        interest_rate_annual=float(app.interest_rate_annual),
        processing_fee=float(app.processing_fee),
        total_repayable=float(app.total_repayable),
        outstanding_balance=float(app.total_repayable),
        tenure_days=app.approved_tenure_days,
        due_date=due_date,
        repayment_method=repayment_method,
        status=LoanStatus.ACTIVE,
        disbursed_at=datetime.utcnow(),
    )
    db.add(loan)

    # Update application status
    app.status = LoanStatus.DISBURSED

    # Update credit profile
    profile.utilized_credit = float(profile.utilized_credit) + principal
    profile.available_credit = max(0, float(profile.approved_credit_limit) - float(profile.utilized_credit))
    profile.total_loans_taken = profile.total_loans_taken + 1
    profile.total_amount_borrowed = float(profile.total_amount_borrowed) + principal

    db.commit()
    db.refresh(loan)
    return loan


def process_repayment(db: Session, req: RepaymentRequest) -> AgentLoan:
    """
    Process a loan repayment. Allocates payment to: penalty → interest → principal.
    Settles the loan if fully paid.
    """
    loan = db.query(AgentLoan).filter(
        AgentLoan.id == req.loan_id,
        AgentLoan.status.in_([LoanStatus.ACTIVE, LoanStatus.OVERDUE]),
    ).first()
    if not loan:
        raise ValueError("Loan not found or not in repayable status.")

    amount = req.amount
    penalty_paid = 0.0
    interest_paid = 0.0
    principal_paid = 0.0

    # Allocate: penalty first, then interest, then principal
    if float(loan.penalty_amount) > 0:
        penalty_paid = min(amount, float(loan.penalty_amount))
        amount -= penalty_paid
        loan.penalty_amount = float(loan.penalty_amount) - penalty_paid

    if amount > 0 and float(loan.accrued_interest) > 0:
        interest_paid = min(amount, float(loan.accrued_interest))
        amount -= interest_paid
        loan.accrued_interest = float(loan.accrued_interest) - interest_paid

    if amount > 0:
        principal_paid = min(amount, float(loan.outstanding_balance) - float(loan.accrued_interest) - float(loan.penalty_amount))
        principal_paid = max(0, principal_paid)

    total_paid = penalty_paid + interest_paid + principal_paid
    loan.total_repaid = float(loan.total_repaid) + total_paid
    loan.outstanding_balance = max(0, float(loan.outstanding_balance) - total_paid)
    loan.last_repayment_at = datetime.utcnow()

    # Check if fully settled
    if float(loan.outstanding_balance) <= 0.01:
        loan.status = LoanStatus.SETTLED
        loan.settled_at = datetime.utcnow()
        loan.outstanding_balance = 0

        # Update credit profile
        profile = db.query(AgentCreditProfile).filter(
            AgentCreditProfile.agent_id == loan.agent_id
        ).first()
        if profile:
            profile.utilized_credit = max(0, float(profile.utilized_credit) - float(loan.principal_amount))
            profile.available_credit = max(0, float(profile.approved_credit_limit) - float(profile.utilized_credit))
            profile.total_loans_settled = profile.total_loans_settled + 1
            profile.total_amount_repaid = float(profile.total_amount_repaid) + total_paid
            # Update on-time payment rate
            if loan.days_overdue == 0:
                settled_on_time = profile.total_loans_settled
                total_settled = profile.total_loans_settled
                profile.on_time_payment_rate = min(100, round((settled_on_time / max(total_settled, 1)) * 100, 2))

    # Record repayment
    repayment = AgentLoanRepayment(
        loan_id=loan.id,
        agent_id=loan.agent_id,
        amount=total_paid,
        principal_portion=principal_paid,
        interest_portion=interest_paid,
        penalty_portion=penalty_paid,
        payment_method=req.payment_method,
        transaction_ref=req.transaction_ref,
        notes=req.notes,
    )
    db.add(repayment)
    db.commit()
    db.refresh(loan)
    return loan


def accrue_overdue_penalties(db: Session) -> int:
    """
    Scheduled job: accrue daily penalties on overdue loans.
    Returns count of loans updated.
    """
    today = date.today()
    overdue_loans = db.query(AgentLoan).filter(
        AgentLoan.due_date < today,
        AgentLoan.status.in_([LoanStatus.ACTIVE, LoanStatus.OVERDUE]),
        AgentLoan.outstanding_balance > 0,
    ).all()

    updated = 0
    for loan in overdue_loans:
        loan.status = LoanStatus.OVERDUE
        loan.days_overdue = (today - loan.due_date).days
        daily_penalty = float(loan.outstanding_balance) * DAILY_PENALTY_RATE
        loan.penalty_amount = float(loan.penalty_amount) + round(daily_penalty, 2)
        loan.outstanding_balance = float(loan.outstanding_balance) + round(daily_penalty, 2)
        updated += 1

    if updated:
        db.commit()
    return updated


# ─── BNPL ─────────────────────────────────────────────────────────────────────

def _compute_installment_amount(
    financed_amount: float,
    num_installments: int,
    annual_rate: float,
) -> Tuple[float, float]:
    """
    Compute equal installment amount using reducing balance method.
    Returns (installment_amount, total_repayable)
    """
    if annual_rate == 0:
        installment = round(financed_amount / num_installments, 2)
        return installment, round(installment * num_installments, 2)

    monthly_rate = annual_rate / 12
    # EMI formula: P * r * (1+r)^n / ((1+r)^n - 1)
    factor = (1 + monthly_rate) ** num_installments
    emi = financed_amount * monthly_rate * factor / (factor - 1)
    emi = round(emi, 2)
    total = round(emi * num_installments, 2)
    return emi, total


def create_bnpl_order(db: Session, req: BNPLOrderRequest) -> AgentBNPLOrder:
    """Create a BNPL order with auto-generated installment schedule."""
    profile = get_or_create_credit_profile(db, req.agent_id, req.tenant_id)

    if not profile.is_eligible:
        raise ValueError(f"Agent is not eligible for BNPL: {profile.eligibility_reason}")

    financed = req.order_amount - req.down_payment
    if financed <= 0:
        raise ValueError("Down payment cannot exceed or equal the order amount.")

    if financed > float(profile.available_credit):
        raise ValueError(
            f"Financed amount NGN {financed:,.2f} exceeds available credit "
            f"NGN {float(profile.available_credit):,.2f}."
        )

    # Determine rate: 0% for ≤3 installments, 18% for >3
    annual_rate = 0.0 if req.num_installments <= 3 else BNPL_DEFERRED_RATE
    installment_amount, total_repayable = _compute_installment_amount(
        financed, req.num_installments, annual_rate
    )

    last_installment_date = req.first_installment_date + timedelta(days=30 * (req.num_installments - 1))

    order = AgentBNPLOrder(
        bnpl_ref=_generate_ref("BNPL"),
        agent_id=req.agent_id,
        tenant_id=req.tenant_id,
        vendor_name=req.vendor_name,
        vendor_id=req.vendor_id,
        item_description=req.item_description,
        item_category=req.item_category,
        order_amount=req.order_amount,
        down_payment=req.down_payment,
        financed_amount=financed,
        num_installments=req.num_installments,
        installment_amount=installment_amount,
        interest_rate_annual=annual_rate,
        total_repayable=total_repayable,
        outstanding_balance=total_repayable,
        order_date=date.today(),
        first_installment_date=req.first_installment_date,
        last_installment_date=last_installment_date,
        status=BNPLStatus.ACTIVE,
        approved_at=datetime.utcnow(),
    )
    db.add(order)
    db.flush()

    # Generate installment schedule
    for i in range(1, req.num_installments + 1):
        due = req.first_installment_date + timedelta(days=30 * (i - 1))
        installment = AgentBNPLInstallment(
            bnpl_order_id=order.id,
            agent_id=req.agent_id,
            installment_number=i,
            due_date=due,
            amount_due=installment_amount,
            status=InstallmentStatus.SCHEDULED,
        )
        db.add(installment)

    # Update credit profile
    profile.utilized_credit = float(profile.utilized_credit) + financed
    profile.available_credit = max(0, float(profile.approved_credit_limit) - float(profile.utilized_credit))

    db.commit()
    db.refresh(order)
    return order


def pay_bnpl_installment(
    db: Session,
    installment_id: uuid.UUID,
    amount_paid: float,
    transaction_ref: Optional[str] = None,
) -> AgentBNPLInstallment:
    """Record payment for a BNPL installment."""
    installment = db.query(AgentBNPLInstallment).filter(
        AgentBNPLInstallment.id == installment_id,
        AgentBNPLInstallment.status.in_([
            InstallmentStatus.SCHEDULED,
            InstallmentStatus.DUE,
            InstallmentStatus.OVERDUE,
        ]),
    ).first()
    if not installment:
        raise ValueError("Installment not found or already paid.")

    installment.amount_paid = float(installment.amount_paid) + amount_paid
    installment.transaction_ref = transaction_ref
    installment.paid_at = datetime.utcnow()

    if float(installment.amount_paid) >= float(installment.amount_due):
        installment.status = InstallmentStatus.PAID
    else:
        installment.status = InstallmentStatus.DUE  # partial payment

    # Update BNPL order totals
    order = installment.order
    order.total_repaid = float(order.total_repaid) + amount_paid
    order.outstanding_balance = max(0, float(order.outstanding_balance) - amount_paid)

    if float(order.outstanding_balance) <= 0.01:
        order.status = BNPLStatus.FULLY_PAID
        order.fully_paid_at = datetime.utcnow()
        order.outstanding_balance = 0
        # Release credit
        profile = db.query(AgentCreditProfile).filter(
            AgentCreditProfile.agent_id == order.agent_id
        ).first()
        if profile:
            profile.utilized_credit = max(0, float(profile.utilized_credit) - float(order.financed_amount))
            profile.available_credit = max(0, float(profile.approved_credit_limit) - float(profile.utilized_credit))
    elif float(order.total_repaid) > 0:
        order.status = BNPLStatus.PARTIALLY_PAID

    db.commit()
    db.refresh(installment)
    return installment


# ─── Portfolio Summary ────────────────────────────────────────────────────────

def get_agent_portfolio(db: Session, agent_id: uuid.UUID, tenant_id: uuid.UUID) -> dict:
    """Return full embedded finance portfolio for an agent."""
    profile = get_or_create_credit_profile(db, agent_id, tenant_id)

    active_loans = db.query(AgentLoan).filter(
        AgentLoan.agent_id == agent_id,
        AgentLoan.status.in_([LoanStatus.ACTIVE, LoanStatus.OVERDUE]),
    ).all()

    active_bnpl = db.query(AgentBNPLOrder).filter(
        AgentBNPLOrder.agent_id == agent_id,
        AgentBNPLOrder.status.in_([BNPLStatus.ACTIVE, BNPLStatus.PARTIALLY_PAID, BNPLStatus.OVERDUE]),
    ).all()

    # Upcoming payments (next 30 days)
    today = date.today()
    upcoming_cutoff = today + timedelta(days=30)
    upcoming = []

    for loan in active_loans:
        if loan.due_date <= upcoming_cutoff:
            upcoming.append({
                "type": "loan",
                "ref": loan.loan_ref,
                "due_date": loan.due_date.isoformat(),
                "amount": float(loan.outstanding_balance),
                "status": loan.status.value,
            })

    upcoming_installments = db.query(AgentBNPLInstallment).filter(
        AgentBNPLInstallment.agent_id == agent_id,
        AgentBNPLInstallment.due_date <= upcoming_cutoff,
        AgentBNPLInstallment.due_date >= today,
        AgentBNPLInstallment.status.in_([InstallmentStatus.SCHEDULED, InstallmentStatus.DUE]),
    ).all()

    for inst in upcoming_installments:
        upcoming.append({
            "type": "bnpl_installment",
            "ref": f"INST-{inst.installment_number}",
            "bnpl_order_id": str(inst.bnpl_order_id),
            "due_date": inst.due_date.isoformat(),
            "amount": float(inst.amount_due),
            "status": inst.status.value,
        })

    upcoming.sort(key=lambda x: x["due_date"])

    total_outstanding = sum(float(l.outstanding_balance) for l in active_loans) + \
                        sum(float(b.outstanding_balance) for b in active_bnpl)
    total_overdue = sum(float(l.outstanding_balance) for l in active_loans if l.status == LoanStatus.OVERDUE) + \
                    sum(float(b.outstanding_balance) for b in active_bnpl if b.status == BNPLStatus.OVERDUE)

    return {
        "credit_profile": profile,
        "active_loans": active_loans,
        "active_bnpl_orders": active_bnpl,
        "upcoming_payments": upcoming,
        "total_outstanding": round(total_outstanding, 2),
        "total_overdue": round(total_overdue, 2),
    }


def get_loan_history(db: Session, agent_id: uuid.UUID, limit: int = 20) -> List[AgentLoan]:
    return (
        db.query(AgentLoan)
        .filter(AgentLoan.agent_id == agent_id)
        .order_by(AgentLoan.created_at.desc())
        .limit(limit)
        .all()
    )


def get_bnpl_history(db: Session, agent_id: uuid.UUID, limit: int = 20) -> List[AgentBNPLOrder]:
    return (
        db.query(AgentBNPLOrder)
        .filter(AgentBNPLOrder.agent_id == agent_id)
        .order_by(AgentBNPLOrder.created_at.desc())
        .limit(limit)
        .all()
    )
