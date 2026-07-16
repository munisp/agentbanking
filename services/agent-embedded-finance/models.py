"""
Agent Embedded Finance — SQLAlchemy ORM Models and Pydantic Schemas
Covers: Micro-Credit (float advance, working capital, micro-loan) and BNPL
"""
import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator
from sqlalchemy import (
    Boolean, Column, Date, DateTime, Enum as SAEnum,
    ForeignKey, Integer, Numeric, String, Text, func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


# ─── Enums ────────────────────────────────────────────────────────────────────

class LoanType(str, enum.Enum):
    FLOAT_ADVANCE = "float_advance"
    MICRO_LOAN = "micro_loan"
    WORKING_CAPITAL = "working_capital"
    DEVICE_FINANCING = "device_financing"


class LoanStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    DISBURSED = "disbursed"
    ACTIVE = "active"
    OVERDUE = "overdue"
    SETTLED = "settled"
    WRITTEN_OFF = "written_off"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class RepaymentMethod(str, enum.Enum):
    COMMISSION_DEDUCTION = "commission_deduction"
    WALLET_DEBIT = "wallet_debit"
    BANK_TRANSFER = "bank_transfer"
    MANUAL = "manual"


class BNPLStatus(str, enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    PARTIALLY_PAID = "partially_paid"
    FULLY_PAID = "fully_paid"
    OVERDUE = "overdue"
    DEFAULTED = "defaulted"
    CANCELLED = "cancelled"


class InstallmentStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    DUE = "due"
    PAID = "paid"
    OVERDUE = "overdue"
    WAIVED = "waived"


class CreditDecision(str, enum.Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    REFERRED = "referred"
    COUNTER_OFFER = "counter_offer"


# ─── ORM Models ───────────────────────────────────────────────────────────────

class AgentCreditProfile(Base):
    __tablename__ = "agent_credit_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), nullable=False, unique=True, index=True)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    approved_credit_limit = Column(Numeric(18, 2), nullable=False, default=0)
    available_credit = Column(Numeric(18, 2), nullable=False, default=0)
    utilized_credit = Column(Numeric(18, 2), nullable=False, default=0)

    credit_score = Column(Integer, nullable=True)
    credit_score_date = Column(Date, nullable=True)
    risk_level = Column(String(20), nullable=True)

    is_eligible = Column(Boolean, nullable=False, default=False)
    eligibility_reason = Column(Text, nullable=True)
    min_tenure_months = Column(Integer, nullable=False, default=3)
    min_txn_count = Column(Integer, nullable=False, default=100)

    total_loans_taken = Column(Integer, nullable=False, default=0)
    total_loans_settled = Column(Integer, nullable=False, default=0)
    total_loans_overdue = Column(Integer, nullable=False, default=0)
    total_amount_borrowed = Column(Numeric(18, 2), nullable=False, default=0)
    total_amount_repaid = Column(Numeric(18, 2), nullable=False, default=0)
    on_time_payment_rate = Column(Numeric(5, 2), nullable=False, default=100)

    last_evaluated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class AgentLoanApplication(Base):
    __tablename__ = "agent_loan_applications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_ref = Column(String(30), unique=True, nullable=False)
    agent_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)
    loan_type = Column(SAEnum(LoanType), nullable=False)

    requested_amount = Column(Numeric(18, 2), nullable=False)
    requested_tenure_days = Column(Integer, nullable=False)
    purpose = Column(Text, nullable=False)

    decision = Column(SAEnum(CreditDecision), nullable=True)
    approved_amount = Column(Numeric(18, 2), nullable=True)
    approved_tenure_days = Column(Integer, nullable=True)
    interest_rate_annual = Column(Numeric(6, 4), nullable=True)
    processing_fee = Column(Numeric(18, 2), nullable=False, default=0)
    total_repayable = Column(Numeric(18, 2), nullable=True)
    decision_reason = Column(Text, nullable=True)
    decision_at = Column(DateTime, nullable=True)
    decided_by = Column(String(100), nullable=True)

    credit_score_snapshot = Column(Integer, nullable=True)
    scorecard_snapshot = Column(JSONB, nullable=True)

    status = Column(SAEnum(LoanStatus), nullable=False, default=LoanStatus.DRAFT)
    submitted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    loan = relationship("AgentLoan", back_populates="application", uselist=False)


class AgentLoan(Base):
    __tablename__ = "agent_loans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    loan_ref = Column(String(30), unique=True, nullable=False)
    application_id = Column(UUID(as_uuid=True), ForeignKey("agent_loan_applications.id"), nullable=False)
    agent_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)
    loan_type = Column(SAEnum(LoanType), nullable=False)

    principal_amount = Column(Numeric(18, 2), nullable=False)
    interest_rate_annual = Column(Numeric(6, 4), nullable=False)
    processing_fee = Column(Numeric(18, 2), nullable=False, default=0)
    total_repayable = Column(Numeric(18, 2), nullable=False)
    total_repaid = Column(Numeric(18, 2), nullable=False, default=0)
    outstanding_balance = Column(Numeric(18, 2), nullable=False)
    accrued_interest = Column(Numeric(18, 2), nullable=False, default=0)
    penalty_amount = Column(Numeric(18, 2), nullable=False, default=0)

    disbursed_at = Column(DateTime, nullable=True)
    tenure_days = Column(Integer, nullable=False)
    due_date = Column(Date, nullable=False)
    repayment_method = Column(SAEnum(RepaymentMethod), nullable=False, default=RepaymentMethod.COMMISSION_DEDUCTION)

    status = Column(SAEnum(LoanStatus), nullable=False, default=LoanStatus.DISBURSED)
    days_overdue = Column(Integer, nullable=False, default=0)
    last_repayment_at = Column(DateTime, nullable=True)
    settled_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    application = relationship("AgentLoanApplication", back_populates="loan")
    repayments = relationship("AgentLoanRepayment", back_populates="loan", cascade="all, delete-orphan")


class AgentLoanRepayment(Base):
    __tablename__ = "agent_loan_repayments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    loan_id = Column(UUID(as_uuid=True), ForeignKey("agent_loans.id"), nullable=False, index=True)
    agent_id = Column(UUID(as_uuid=True), nullable=False)
    amount = Column(Numeric(18, 2), nullable=False)
    principal_portion = Column(Numeric(18, 2), nullable=False)
    interest_portion = Column(Numeric(18, 2), nullable=False, default=0)
    penalty_portion = Column(Numeric(18, 2), nullable=False, default=0)
    payment_method = Column(SAEnum(RepaymentMethod), nullable=False)
    transaction_ref = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    repaid_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    loan = relationship("AgentLoan", back_populates="repayments")


class AgentBNPLOrder(Base):
    __tablename__ = "agent_bnpl_orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bnpl_ref = Column(String(30), unique=True, nullable=False)
    agent_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)

    vendor_name = Column(String(200), nullable=False)
    vendor_id = Column(UUID(as_uuid=True), nullable=True)
    item_description = Column(Text, nullable=False)
    item_category = Column(String(100), nullable=False)
    order_amount = Column(Numeric(18, 2), nullable=False)

    down_payment = Column(Numeric(18, 2), nullable=False, default=0)
    financed_amount = Column(Numeric(18, 2), nullable=False)
    num_installments = Column(Integer, nullable=False)
    installment_amount = Column(Numeric(18, 2), nullable=False)
    interest_rate_annual = Column(Numeric(6, 4), nullable=False, default=0)
    total_repayable = Column(Numeric(18, 2), nullable=False)
    total_repaid = Column(Numeric(18, 2), nullable=False, default=0)
    outstanding_balance = Column(Numeric(18, 2), nullable=False)

    order_date = Column(Date, nullable=False, default=date.today)
    first_installment_date = Column(Date, nullable=False)
    last_installment_date = Column(Date, nullable=False)

    status = Column(SAEnum(BNPLStatus), nullable=False, default=BNPLStatus.PENDING)
    approved_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    fully_paid_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    installments = relationship("AgentBNPLInstallment", back_populates="order", cascade="all, delete-orphan")


class AgentBNPLInstallment(Base):
    __tablename__ = "agent_bnpl_installments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bnpl_order_id = Column(UUID(as_uuid=True), ForeignKey("agent_bnpl_orders.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id = Column(UUID(as_uuid=True), nullable=False)
    installment_number = Column(Integer, nullable=False)
    due_date = Column(Date, nullable=False, index=True)
    amount_due = Column(Numeric(18, 2), nullable=False)
    amount_paid = Column(Numeric(18, 2), nullable=False, default=0)
    penalty_amount = Column(Numeric(18, 2), nullable=False, default=0)
    status = Column(SAEnum(InstallmentStatus), nullable=False, default=InstallmentStatus.SCHEDULED)
    paid_at = Column(DateTime, nullable=True)
    transaction_ref = Column(String(100), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    order = relationship("AgentBNPLOrder", back_populates="installments")


# ─── Pydantic Request/Response Schemas ───────────────────────────────────────

class LoanApplicationRequest(BaseModel):
    agent_id: uuid.UUID
    tenant_id: uuid.UUID
    loan_type: LoanType
    requested_amount: float = Field(..., gt=0)
    requested_tenure_days: int = Field(..., ge=1, le=365)
    purpose: str = Field(..., min_length=10, max_length=500)
    repayment_method: RepaymentMethod = RepaymentMethod.COMMISSION_DEDUCTION


class RepaymentRequest(BaseModel):
    loan_id: uuid.UUID
    amount: float = Field(..., gt=0)
    payment_method: RepaymentMethod
    transaction_ref: Optional[str] = None
    notes: Optional[str] = None


class BNPLOrderRequest(BaseModel):
    agent_id: uuid.UUID
    tenant_id: uuid.UUID
    vendor_name: str = Field(..., min_length=2, max_length=200)
    vendor_id: Optional[uuid.UUID] = None
    item_description: str = Field(..., min_length=5, max_length=500)
    item_category: str = Field(..., min_length=2, max_length=100)
    order_amount: float = Field(..., gt=0)
    down_payment: float = Field(default=0, ge=0)
    num_installments: int = Field(..., ge=1, le=24)
    first_installment_date: date


class BNPLInstallmentPayRequest(BaseModel):
    installment_id: uuid.UUID
    amount_paid: float = Field(..., gt=0)
    transaction_ref: Optional[str] = None


class CreditProfileOut(BaseModel):
    id: uuid.UUID
    agent_id: uuid.UUID
    approved_credit_limit: float
    available_credit: float
    utilized_credit: float
    credit_score: Optional[int]
    risk_level: Optional[str]
    is_eligible: bool
    eligibility_reason: Optional[str]
    total_loans_taken: int
    total_loans_settled: int
    on_time_payment_rate: float
    last_evaluated_at: Optional[datetime]

    class Config:
        from_attributes = True


class LoanApplicationOut(BaseModel):
    id: uuid.UUID
    application_ref: str
    agent_id: uuid.UUID
    loan_type: LoanType
    requested_amount: float
    requested_tenure_days: int
    purpose: str
    decision: Optional[CreditDecision]
    approved_amount: Optional[float]
    approved_tenure_days: Optional[int]
    interest_rate_annual: Optional[float]
    processing_fee: float
    total_repayable: Optional[float]
    decision_reason: Optional[str]
    decision_at: Optional[datetime]
    status: LoanStatus
    submitted_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class RepaymentOut(BaseModel):
    id: uuid.UUID
    loan_id: uuid.UUID
    amount: float
    principal_portion: float
    interest_portion: float
    penalty_portion: float
    payment_method: RepaymentMethod
    transaction_ref: Optional[str]
    repaid_at: datetime

    class Config:
        from_attributes = True


class LoanOut(BaseModel):
    id: uuid.UUID
    loan_ref: str
    application_id: uuid.UUID
    agent_id: uuid.UUID
    loan_type: LoanType
    principal_amount: float
    interest_rate_annual: float
    processing_fee: float
    total_repayable: float
    total_repaid: float
    outstanding_balance: float
    accrued_interest: float
    penalty_amount: float
    disbursed_at: Optional[datetime]
    tenure_days: int
    due_date: date
    repayment_method: RepaymentMethod
    status: LoanStatus
    days_overdue: int
    last_repayment_at: Optional[datetime]
    settled_at: Optional[datetime]
    repayments: List[RepaymentOut] = []
    created_at: datetime

    class Config:
        from_attributes = True


class InstallmentOut(BaseModel):
    id: uuid.UUID
    installment_number: int
    due_date: date
    amount_due: float
    amount_paid: float
    penalty_amount: float
    status: InstallmentStatus
    paid_at: Optional[datetime]
    transaction_ref: Optional[str]

    class Config:
        from_attributes = True


class BNPLOrderOut(BaseModel):
    id: uuid.UUID
    bnpl_ref: str
    agent_id: uuid.UUID
    vendor_name: str
    item_description: str
    item_category: str
    order_amount: float
    down_payment: float
    financed_amount: float
    num_installments: int
    installment_amount: float
    interest_rate_annual: float
    total_repayable: float
    total_repaid: float
    outstanding_balance: float
    order_date: date
    first_installment_date: date
    last_installment_date: date
    status: BNPLStatus
    approved_at: Optional[datetime]
    fully_paid_at: Optional[datetime]
    installments: List[InstallmentOut] = []
    created_at: datetime

    class Config:
        from_attributes = True


class PortfolioSummary(BaseModel):
    """Agent's full embedded finance portfolio summary."""
    credit_profile: CreditProfileOut
    active_loans: List[LoanOut]
    active_bnpl_orders: List[BNPLOrderOut]
    upcoming_payments: List[Dict[str, Any]]
    total_outstanding: float
    total_overdue: float
