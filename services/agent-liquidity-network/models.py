"""Models for Agent-to-Agent Liquidity Network."""
from datetime import datetime, timezone
from typing import Optional, Dict
from uuid import UUID, uuid4
from decimal import Decimal
from pydantic import BaseModel
from sqlalchemy import Column, String, Boolean, DateTime, Numeric, Text, Integer
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class AgentLiquidityProfile(Base):
    __tablename__ = "liquidity_agent_profiles"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    agent_id = Column(PGUUID(as_uuid=True), unique=True, nullable=False, index=True)
    agent_name = Column(String(200))
    agent_code = Column(String(50))
    reputation_score = Column(Numeric(8, 2), default=100)
    total_lent = Column(Numeric(18, 2), default=0)
    total_borrowed = Column(Numeric(18, 2), default=0)
    successful_repayments = Column(Integer, default=0)
    late_repayments = Column(Integer, default=0)
    defaults = Column(Integer, default=0)
    is_lender_eligible = Column(Boolean, default=True)
    is_borrower_eligible = Column(Boolean, default=True)
    max_lend_amount = Column(Numeric(18, 2), default=100000)
    max_borrow_amount = Column(Numeric(18, 2), default=50000)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class LiquidityRequest(Base):
    __tablename__ = "liquidity_requests"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    borrower_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    amount = Column(Numeric(18, 2), nullable=False)
    duration_hours = Column(Integer, nullable=False)
    max_interest_rate = Column(Numeric(8, 6))
    purpose = Column(String(200))
    status = Column(String(30), default="pending", index=True)
    matched_offer_id = Column(PGUUID(as_uuid=True))
    expires_at = Column(DateTime(timezone=True))
    repayment_due_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class LiquidityOffer(Base):
    __tablename__ = "liquidity_offers"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    lender_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    amount = Column(Numeric(18, 2), nullable=False)
    available_amount = Column(Numeric(18, 2), nullable=False)
    interest_rate = Column(Numeric(8, 6), nullable=False)
    min_duration_hours = Column(Integer, default=1)
    max_duration_hours = Column(Integer, default=168)
    status = Column(String(20), default="active", index=True)
    expires_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class LiquidityMatch(Base):
    __tablename__ = "liquidity_matches"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    request_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    offer_id = Column(PGUUID(as_uuid=True), nullable=False)
    borrower_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    lender_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    matched_amount = Column(Numeric(18, 2), nullable=False)
    interest_rate = Column(Numeric(8, 6))
    interest_amount = Column(Numeric(18, 2))
    platform_fee = Column(Numeric(18, 2))
    total_repayable = Column(Numeric(18, 2))
    status = Column(String(30), default="pending_disbursement", index=True)
    tigerbeetle_transfer_id = Column(String(100))
    matched_at = Column(DateTime(timezone=True))
    disbursed_at = Column(DateTime(timezone=True))
    repayment_due_at = Column(DateTime(timezone=True))
    repaid_at = Column(DateTime(timezone=True))


class LiquidityRepayment(Base):
    __tablename__ = "liquidity_repayments"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    match_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    borrower_id = Column(PGUUID(as_uuid=True), nullable=False)
    lender_id = Column(PGUUID(as_uuid=True), nullable=False)
    amount_paid = Column(Numeric(18, 2), nullable=False)
    payment_reference = Column(String(100))
    is_late = Column(Boolean, default=False)
    paid_at = Column(DateTime(timezone=True))


class NetworkTransaction(Base):
    __tablename__ = "liquidity_network_transactions"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    match_id = Column(PGUUID(as_uuid=True))
    transaction_type = Column(String(30))
    from_agent_id = Column(PGUUID(as_uuid=True))
    to_agent_id = Column(PGUUID(as_uuid=True))
    amount = Column(Numeric(18, 2))
    reference = Column(String(100))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# Pydantic schemas
class RegisterProfileRequest(BaseModel):
    agent_id: UUID
    agent_name: str
    agent_code: str


class CreateRequestRequest(BaseModel):
    borrower_id: UUID
    amount: Decimal
    duration_hours: int
    max_interest_rate: Optional[Decimal] = None
    purpose: Optional[str] = None


class CreateOfferRequest(BaseModel):
    lender_id: UUID
    amount: Decimal
    interest_rate: Decimal
    min_duration_hours: int = 1
    max_duration_hours: int = 168


class ConfirmDisbursementRequest(BaseModel):
    tigerbeetle_transfer_id: str


class ProcessRepaymentRequest(BaseModel):
    amount_paid: Decimal
    payment_reference: str


class RequestStatus:
    PENDING = "pending"
    MATCHED = "matched"
    ACTIVE = "active"
    REPAID = "repaid"
    EXPIRED = "expired"
    DEFAULTED = "defaulted"


class MatchStatus:
    PENDING_DISBURSEMENT = "pending_disbursement"
    ACTIVE = "active"
    OVERDUE = "overdue"
    REPAID = "repaid"
    DEFAULTED = "defaulted"
